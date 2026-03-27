import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import concurrent.futures
import time

# 1. Configuración de la interfaz
st.set_page_config(page_title="Analizador Océanos Azules MP", layout="wide")
st.title("🔍 Buscador de Océanos Azules: Consultorías Desiertas")
st.markdown("Identifica licitaciones donde no hubo competencia para capturar nuevas oportunidades.")

# 2. Panel Lateral
with st.sidebar:
    api_key = st.text_input("Ingresa tu API Ticket de Mercado Público", type="password")
    dias = st.selectbox("Periodo de búsqueda", [7, 14, 30])
    st.info("Buscando procesos de Consultoría que terminaron sin adjudicación.")

# 3. Función para obtener detalles de una licitación
def fetch_detalle(id_licitacion, ticket):
    url = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?codigo={id_licitacion}&ticket={ticket}"
    try:
        r = requests.get(url, timeout=25)
        if r.status_code == 200:
            data = r.json()
            if data['Cantidad'] > 0:
                lic = data['Listado'][0]
                estados_objetivo = ['Desierta', 'Revocada', 'Adjudicación Sin Ofertas', 'Desierto']
                if lic['Estado'] in estados_objetivo:
                    return {
                        "ID": lic['CodigoExterno'],
                        "Nombre": lic['Nombre'],
                        "Institucion": lic['Entidad']['Nombre'],
                        "Estado": lic['Estado'],
                        "Motivo": lic.get('JustificacionPublicacion', 'No especificado'),
                        "Monto": lic.get('MontoEstimado', 'No disponible')
                    }
    except:
        return None
    return None

# 4. Lógica Principal
if st.button("Iniciar Extracción de Datos"):
    if not api_key:
        st.error("Por favor, ingresa tu API Ticket en la barra lateral.")
    else:
        # Contenedor para mostrar el progreso en vivo
        estado_texto = st.empty() 
        
        with st.spinner(f"Analizando últimos {dias} días..."):
            all_results = []
            fechas = [(datetime.now() - timedelta(days=x)).strftime("%d%m%Y") for x in range(dias)]
            ids_a_consultar = []
            total_licitaciones_revisadas = 0

            # Fase 1: Recolectar IDs (Ahora con tildes y más palabras clave)
            keywords = ['consultoria', 'consultoría', 'asesoria', 'asesoría', 'estudio', 'analisis', 'análisis', 'auditoria', 'auditoría']
            
            for f in fechas:
                estado_texto.info(f"⏳ Descargando licitaciones del día {f[:2]}/{f[2:4]}/{f[4:]}...")
                url_lista = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?fecha={f}&ticket={api_key}"
                intentos = 0
                while intentos < 2:
                    try:
                        response = requests.get(url_lista, timeout=30)
                        if response.status_code == 200:
                            res = response.json()
                            if 'Listado' in res and res['Listado']:
                                total_licitaciones_revisadas += len(res['Listado'])
                                for l in res['Listado']:
                                    nombre = l['Nombre'].lower()
                                    # Verificamos si alguna palabra clave está en el nombre
                                    if any(kw in nombre for kw in keywords):
                                        ids_a_consultar.append(l['CodigoExterno'])
                            break 
                        elif response.status_code == 504:
                            time.sleep(2)
                            intentos += 1
                        else:
                            break
                    except:
                        intentos += 1

            # Fase 2: Consultar detalles de los "candidatos" a Océano Azul
            if ids_a_consultar:
                estado_texto.warning(f"🔍 Se encontraron {len(ids_a_consultar)} licitaciones de consultoría entre {total_licitaciones_revisadas} publicadas. Verificando cuáles quedaron desiertas...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(fetch_detalle, id_lic, api_key) for id_lic in ids_a_consultar]
                    for future in concurrent.futures.as_completed(futures):
                        res = future.result()
                        if res:
                            all_results.append(res)

            # Fase 3: Mostrar resultados
            estado_texto.empty() # Limpiamos el texto de progreso
            
            if all_results:
                df = pd.DataFrame(all_results)
                st.success(f"¡Bingo! De {total_licitaciones_revisadas} procesos totales, encontramos {len(df)} Océanos Azules.")
                st.dataframe(df)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Océanos Azules (CSV)",
                    data=csv,
                    file_name=f"oportunidades_mp_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning(f"Revisamos {total_licitaciones_revisadas} licitaciones en total. Encontramos {len(ids_a_consultar)} de tu rubro, pero ninguna quedó desierta en este periodo.")
