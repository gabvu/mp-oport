import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, date
import concurrent.futures

st.set_page_config(page_title="Océanos Azules PRO", layout="wide")
st.title("🌊 Buscador de Océanos Azules: Consultorías")
st.markdown("Filtra licitaciones desiertas por rango de fechas de publicación y extrae el rubro real.")

with st.sidebar:
    st.header("Configuración de Búsqueda")
    api_key = st.text_input("Ingresa tu API Ticket", type="password")
    st.markdown("---")
    
    st.subheader("Rango de Publicación")
    col1, col2 = st.columns(2)
    with col1:
        fecha_desde = st.date_input("Desde", date.today() - timedelta(days=30))
    with col2:
        fecha_hasta = st.date_input("Hasta", date.today())
        
    st.markdown("---")
    st.subheader("Filtros Avanzados")
    keywords = st.text_input("Palabras clave en el título (separadas por coma)", "consultoria, asesoria, estudio, diseño, actualizacion, servicio")
    st.caption("Filtra para acelerar la búsqueda. Si buscas un rubro muy específico, ponlo aquí.")

def fetch_lista_diaria(fecha_str, ticket):
    url = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?fecha={fecha_str}&ticket={ticket}"
    try:
        res = requests.get(url, timeout=5).json()
        return res.get('Listado', [])
    except: return []

def fetch_detalle(id_licitacion, ticket):
    url = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?codigo={id_licitacion}&ticket={ticket}"
    try:
        r = requests.get(url, timeout=5).json()
        if r['Cantidad'] > 0:
            lic = r['Listado'][0]
            rubro_real = "No especificado"
            try:
                rubro_real = lic['Items']['Listado'][0]['Categoria']
            except: pass

            return {
                "ID": lic['CodigoExterno'],
                "Nombre": lic['Nombre'],
                "Rubro / Categoría": rubro_real,
                "Institución": lic['Entidad']['Nombre'],
                "Estado": lic['Estado'],
                "Motivo Desierta": lic.get('JustificacionPublicacion', 'No especificado'),
                "Monto Estimado": lic.get('MontoEstimado', 'No público')
            }
    except: return None

if st.button("Buscar Oportunidades (Océanos Azules)", type="primary"):
    if not api_key:
        st.error("Por favor ingresa tu API Ticket en la barra lateral.")
    elif fecha_desde > fecha_hasta:
        st.error("Error: La fecha 'Desde' no puede ser posterior a la fecha 'Hasta'.")
    else:
        dias_diferencia = (fecha_hasta - fecha_desde).days + 1
        
        if dias_diferencia > 90:
            st.warning("⚠️ Estás buscando un rango mayor a 90 días. Esto podría superar los 60 segundos de procesamiento o el límite de tu API.")
            
        with st.spinner(f"Escaneando {dias_diferencia} días en los servidores de Mercado Público..."):
            fechas_a_consultar = [(fecha_desde + timedelta(days=i)).strftime("%d%m%Y") for i in range(dias_diferencia)]
            kws = [k.strip().lower() for k in keywords.split(",")] if keywords else []
            
            ids_desiertas = []
            
            # Escaneo de listas diarias en paralelo
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                listados = list(executor.map(lambda f: fetch_lista_diaria(f, api_key), fechas_a_consultar))
            
            # Filtrar desiertas y por palabra clave
            for listado in listados:
                for lic in listado:
                    if str(lic.get('CodigoEstado')) in ['8', '18'] or lic.get('Estado') in ['Desierta', 'Revocada', 'Adjudicación Sin Ofertas']:
                        nombre_min = lic.get('Nombre', '').lower()
                        if not kws or any(kw in nombre_min for kw in kws):
                            ids_desiertas.append(lic['CodigoExterno'])
            
            ids_desiertas = list(set(ids_desiertas))
            
            if not ids_desiertas:
                st.info("No se encontraron licitaciones desiertas con estos parámetros en este rango de fechas.")
            else:
                st.success(f"Se pre-seleccionaron {len(ids_desiertas)} procesos desiertos. Descargando detalles y rubros...")
                
                # Descargar detalles de cada licitación encontrada
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    resultados = list(executor.map(lambda x: fetch_detalle(x, api_key), ids_desiertas))
                
                resultados = [r for r in resultados if r]
                
                if resultados:
                    df = pd.DataFrame(resultados)
                    st.balloons()
                    st.dataframe(df, use_container_width=True)
                    
                    # Generar CSV para descarga
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar Reporte en Excel (CSV)",
                        data=csv,
                        file_name=f"oceanos_azules_{fecha_desde.strftime('%Y%m%d')}_al_{fecha_hasta.strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
