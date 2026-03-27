import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import concurrent.futures
import time

st.set_page_config(page_title="Analizador Océanos Azules MP", layout="wide")
st.title("🔍 Buscador de Océanos Azules: Consultorías Desiertas")

with st.sidebar:
    api_key = st.text_input("Ingresa tu API Ticket de Mercado Público", type="password")
    dias = st.selectbox("Periodo de búsqueda", [7, 14, 30])

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

if st.button("Iniciar Extracción de Datos"):
    if not api_key:
        st.error("Por favor, ingresa tu API Ticket.")
    else:
        estado_texto = st.empty() 
        with st.spinner(f"Analizando últimos {dias} días..."):
            all_results = []
            fechas = [(datetime.now() - timedelta(days=x)).strftime("%d%m%Y") for x in range(dias)]
            ids_a_consultar = []
            total_licitaciones_revisadas = 0
            keywords = ['consultoria', 'consultoría', 'asesoria', 'asesoría', 'estudio', 'analisis', 'análisis', 'auditoria', 'auditoría']
            
            for f in fechas:
                estado_texto.info(f"⏳ Descargando día {f[:2]}/{f[2:4]}/{f[4:]}...")
                url_lista = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?fecha={f}&ticket={api_key}"
                intentos = 0
                while intentos < 2:
                    try:
                        response = requests.get(url_lista, timeout=30)
                        if response.status_code == 200:
                            res = response.json()
                            
                            # --- 🚨 MODO DIAGNÓSTICO ACTIVO 🚨 ---
                            # Imprimimos la respuesta cruda solo para el primer día evaluado
                            if f == fechas[0]:
                                st.warning("🛠️ DIAGNÓSTICO: Esto es lo que responde la API de Mercado Público:")
                                st.json(res)
                            # ------------------------------------

                            if 'Listado' in res and res['Listado']:
                                total_licitaciones_revisadas += len(res['Listado'])
                                for l in res['Listado']:
                                    nombre = l['Nombre'].lower()
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

            if ids_a_consultar:
                estado_texto.warning(f"🔍 Verificando {len(ids_a_consultar)} posibles licitaciones...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(fetch_detalle, id_lic, api_key) for id_lic in ids_a_consultar]
                    for future in concurrent.futures.as_completed(futures):
                        res = future.result()
                        if res:
                            all_results.append(res)

            estado_texto.empty() 
            
            if all_results:
                df = pd.DataFrame(all_results)
                st.success(f"¡Bingo! Encontramos {len(df)} Océanos Azules.")
                st.dataframe(df)
            else:
                st.error(f"Revisamos {total_licitaciones_revisadas} licitaciones en total. Encontramos {len(ids_a_consultar)} de tu rubro, pero ninguna desierta.")
