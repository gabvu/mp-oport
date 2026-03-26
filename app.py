import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import concurrent.futures

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
        r = requests.get(url, timeout=5)
        data = r.json()
        if data['Cantidad'] > 0:
            lic = data['Listado'][0]
            # Filtramos solo las que están desiertas o similares
            if lic['Estado'] in ['Desierta', 'Revocada', 'Adjudicación Sin Ofertas']:
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
        
        # 1. Obtener lista de IDs por cada día
        ids_a_consultar = []
        for f in fechas:
            url_lista = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?fecha={f}&ticket={api_key}"
            res = requests.get(url_lista).json()
            if 'Listado' in res:
                for l in res['Listado']:
                    # Filtro rápido por palabra clave antes de ir al detalle (ahorra tiempo)
                    if any(kw in l['Nombre'].lower() for kw in ['consultoria', 'asesoria', 'estudio']):
                        ids_a_consultar.append(l['CodigoExterno'])

        # 2. Consultar detalles en paralelo para cumplir con los 60s
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_id = {executor.submit(fetch_detalle, id_lic, api_key): id_lic for id_lic in ids_a_consultar}
            for future in concurrent.futures.as_completed(future_to_id):
                res = future.result()
                if res:
                    all_results.append(res)

        if all_results:
            df = pd.DataFrame(all_results)
            st.success(f"Se encontraron {len(df)} oportunidades potenciales.")
            st.dataframe(df)
            
            # Descargas
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Descargar Excel (CSV)", csv, "oceanos_azules.csv", "text/csv")
        else:
            st.warning("No se encontraron procesos desiertos en este rubro para el periodo seleccionado.")
