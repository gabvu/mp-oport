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
            response = requests.get(url_lista)
            
            # Verificamos si la respuesta es exitosa (Código 200)
            if response.status_code == 200:
                try:
                    res = response.json()
                    if 'Listado' in res and res['Listado'] is not None:
                        for l in res['Listado']:
                            if any(kw in l['Nombre'].lower() for kw in ['consultoria', 'asesoria', 'estudio']):
                                ids_a_consultar.append(l['CodigoExterno'])
                except ValueError:
                    st.error(f"Error: La API devolvió un formato extraño para la fecha {f}. Puede que el servicio esté inestable.")
            elif response.status_code == 401:
                st.error("⚠️ Error 401: Tu API Ticket es inválido o expiró. Por favor, revísalo.")
                st.stop() # Detiene la ejecución para no seguir fallando
            else:
                st.warning(f"No se pudo obtener datos para la fecha {f} (Código {response.status_code})")
