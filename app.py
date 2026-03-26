import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import concurrent.futures
import time  # <--- NUEVO: Necesario para los reintentos

# Configuración de página
st.set_page_config(page_title="Analizador Océanos Azules MP", layout="wide")
st.title("🔍 Buscador de Océanos Azules: Consultorías Desiertas")
st.markdown("Identifica licitaciones donde no hubo competencia para capturar nuevas oportunidades.")

# Sidebar
with st.sidebar:
    api_key = st.text_input("Ingresa tu API Ticket de Mercado Público", type="password")
    dias = st.selectbox("Periodo de búsqueda", [7, 14, 30])
    st.info("Este proceso filtra específicamente procesos de Consultoría que terminaron sin adjudicación.")

def fetch_detalle(id_licitacion, ticket):
    """Obtiene el detalle de una licitación específica para ver el motivo de desierto."""
    url = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?codigo={id_licitacion}&ticket={ticket}"
    try:
        r = requests.get(url, timeout=20) # Aumentamos un poco el timeout aquí también
        data = r.json()
        if data['Cantidad'] > 0:
            lic = data['Listado'][0]
            # Filtramos solo las que están desiertas o similares
            if lic['Estado'] in ['Desierta', 'Revocada', 'Adjudicación Sin Ofertas', 'Desierto']:
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

if st.button("Iniciar Extracción de Datos") and api_key:
    with st.spinner(f"Analizando últimos {dias} días..."):
        all_results = []
        fechas = [(datetime.now() - timedelta(days=x)).strftime("%d%m%Y") for x in range(dias)]
        
        # --- SECCIÓN CORREGIDA CON REINTENTOS Y TIMEOUT ---
        ids_a_consultar = []
        for f in fechas:
            url_lista = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?fecha={f}&ticket={api_key}"
            
            exito_fecha = False
            reintentos = 2 # Si falla, lo intenta 2 veces más
            
            while reintentos >= 0 and not exito_fecha:
                try:
                    # Esperamos hasta 30 segundos por respuesta
                    response = requests.get(url_lista, timeout=30)
                    
                    if response.status_code == 200:
                        res = response.json()
                        if 'Listado' in res and res['Listado'] is not None:
                            for l in res['Listado']:
                                # Filtro por rubro Consultoría
                                if any(kw in l['Nombre'].lower() for kw in ['consultoria', 'asesoria', 'estudio']):
                                    ids_a_consultar.append(l['CodigoExterno'])
                        exito_fecha = True 
                    elif response.status_code == 504:
                        st.warning(f"Servidor saturado el día {f}. Reintentando en 3 segundos...")
                        time.sleep(3)
                        reintentos -= 1
                    else:
                        st.error(f"Error {response.status_code} en fecha {f}")
                        break
                except (requests.exceptions.Timeout, requests.exceptions.RequestException):
                    st.warning(f"Tiempo de espera agotado en {f}. Reintentando...")
                    reintentos -= 1
                    time.sleep(2)
        # --- FIN DE SECCIÓN CORREGIDA ---

        # 2. Consultar detalles en paralelo
        if ids_a_consultar:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_id = {executor.submit(fetch_detalle, id_lic, api_key): id_lic for id_lic in ids_a_consultar}
                for future in concurrent.futures.as_completed(future_to_id):
                    res = future.result()
                    if res:
                        all_results.append(res)

        if all_results:
            df = pd.DataFrame(all_results)
            st.success(f"Se encontraron {len(df)} oportunidades potenciales.")
            st.dataframe(df)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Descargar Excel (CSV)", csv, "oceanos_azules.csv", "text/csv")
        else:
            st.warning("No se encontraron procesos desiertos en este rubro. Intenta con un rango mayor de días o revisa tu conexión.")
            else:
                st.warning(f"No se pudo obtener datos para la fecha {f} (Código {response.status_code})")
