import streamlit as st
import pandas as pd
import requests
import concurrent.futures
import time

st.set_page_config(page_title="Océanos Azules - Modo Puente", layout="wide")
st.title("🌊 Buscador de Océanos Azules: Modo Puente CSV")
st.markdown("Sube el archivo descargado desde Mercado Público. El sistema extraerá los motivos de desierto y datos ocultos a máxima velocidad.")

with st.sidebar:
    st.header("1. Credenciales")
    api_key = st.text_input("Ingresa tu API Ticket", type="password")
    
    st.markdown("---")
    st.header("2. Sube tu Búsqueda")
    st.info("Ve a mercadopublico.cl, busca tus licitaciones, haz clic en 'Descargar resultados' y sube ese archivo aquí.")
    archivo_subido = st.file_uploader("Sube el archivo CSV o Excel", type=["csv", "xlsx", "xls"])

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

def fetch_detalle_rapido(id_licitacion, ticket):
    """Consulta directa por ID (Este endpoint de la API NO se cae)"""
    url = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?codigo={id_licitacion}&ticket={ticket}"
    
    for intento in range(2):
        try:
            r = requests.get(url, headers=HEADERS, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get('Cantidad', 0) > 0:
                    lic = data['Listado'][0]
                    rubro_real = "No especificado"
                    try:
                        rubro_real = lic['Items']['Listado'][0]['Categoria']
                    except: pass

                    return {
                        "ID Licitación": lic['CodigoExterno'],
                        "Nombre": lic['Nombre'],
                        "Rubro Específico": rubro_real,
                        "Institución": lic['Entidad']['Nombre'],
                        "Estado Final": lic['Estado'],
                        "Motivo (Por qué quedó desierta)": lic.get('JustificacionPublicacion', 'No detallado en API (Ver bases)'),
                        "Monto Estimado": lic.get('MontoEstimado', 'No público')
                    }
            time.sleep(1)
        except: time.sleep(1)
    return None

if archivo_subido and api_key:
    if st.button("Analizar Oportunidades y Extraer Motivos", type="primary"):
        with st.spinner("Leyendo archivo..."):
            try:
                # Leer el archivo dependiendo de su formato
                if archivo_subido.name.endswith('.csv'):
                    df_base = pd.read_csv(archivo_subido, sep=None, engine='python') # sep=None detecta automáticamente comas o punto y coma
                else:
                    df_base = pd.read_excel(archivo_subido)
                
                # Buscar la columna que contiene los IDs (Mercado Público a veces cambia los nombres)
                col_id = None
                for col in df_base.columns:
                    if "codigo" in col.lower() or "id" in col.lower() or "licitación" in col.lower():
                        col_id = col
                        break
                
                if not col_id:
                    st.error("No se pudo encontrar la columna con los Códigos de Licitación en el archivo. Verifica el formato.")
                else:
                    ids_a_consultar = df_base[col_id].dropna().astype(str).unique().tolist()
                    st.success(f"Se encontraron {len(ids_a_consultar)} licitaciones en el documento. Conectando a la API...")
                    
                    # Extraer detalles en paralelo
                    bar = st.progress(0)
                    resultados_enriquecidos = []
                    
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        # Lanzamos las consultas
                        futures = {executor.submit(fetch_detalle_rapido, lic_id, api_key): lic_id for lic_id in ids_a_consultar}
                        
                        completados = 0
                        for future in concurrent.futures.as_completed(futures):
                            res = future.result()
                            if res:
                                # Filtramos para quedarnos solo con las que realmente son "Océanos Azules"
                                if res['Estado Final'] in ['Desierta', 'Revocada', 'Adjudicación Sin Ofertas']:
                                    resultados_enriquecidos.append(res)
                            
                            completados += 1
                            bar.progress(completados / len(ids_a_consultar))
                    
                    if resultados_enriquecidos:
                        df_final = pd.DataFrame(resultados_enriquecidos)
                        st.balloons()
                        st.write("### 🏆 Océanos Azules Encontrados")
                        st.dataframe(df_final, use_container_width=True)
                        
                        csv_final = df_final.to_csv(index=False).encode('utf-8-sig') # utf-8-sig arregla los tildes en Excel
                        st.download_button("📥 Descargar Reporte Final de Océanos Azules (CSV)", csv_final, "oceanos_azules_analizados.csv", "text/csv")
                    else:
                        st.warning("Se analizaron las licitaciones, pero ninguna de ellas está marcada como 'Desierta' o 'Sin Ofertas' en la API final.")

            except Exception as e:
                st.error(f"Error al leer el archivo: {str(e)}")
