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
        fecha_desde = st.date_input("Desde", date.today() - timedelta(days=7))
    with col2:
        fecha_hasta = st.date_input("Hasta", date.today())
        
    st.markdown("---")
    st.subheader("Filtros Avanzados")
    keywords = st.text_input("Palabras clave en el título", "consultoria, asesoria, estudio, diseño, actualizacion, servicio")

def fetch_lista_diaria(fecha_str, ticket):
    """Descarga la lista con un timeout mayor y captura errores de la API"""
    url = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?fecha={fecha_str}&ticket={ticket}"
    try:
        # Aumentamos a 15 segundos porque la API del Estado suele ser lenta
        res = requests.get(url, timeout=15)
        
        # Si la API rechaza el ticket (Ej: Error 401 o 500)
        if res.status_code != 200:
            return {"error": f"Error API HTTP {res.status_code} en fecha {fecha_str}", "data": []}
            
        data = res.json()
        
        # Si Mercado Público envía un mensaje de error dentro del JSON
        if 'Mensaje' in data and data.get('Cantidad', 0) == 0:
             return {"error": data['Mensaje'], "data": []}
             
        return {"error": None, "data": data.get('Listado', [])}
        
    except requests.exceptions.Timeout:
        return {"error": f"Timeout (API muy lenta) en fecha {fecha_str}", "data": []}
    except Exception as e:
        return {"error": f"Error de conexión en fecha {fecha_str}", "data": []}

def fetch_detalle(id_licitacion, ticket):
    url = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?codigo={id_licitacion}&ticket={ticket}"
    try:
        r = requests.get(url, timeout=10).json()
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
            
        with st.spinner(f"Escaneando {dias_diferencia} días en los servidores de Mercado Público..."):
            fechas_a_consultar = [(fecha_desde + timedelta(days=i)).strftime("%d%m%Y") for i in range(dias_diferencia)]
            kws = [k.strip().lower() for k in keywords.split(",")] if keywords else []
            
            ids_desiertas = []
            total_licitaciones_revisadas = 0
            errores_detectados = []
            
            # Escaneo de listas diarias en paralelo
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                resultados_diarios = list(executor.map(lambda f: fetch_lista_diaria(f, api_key), fechas_a_consultar))
            
            # Procesar resultados y capturar errores
            for resultado in resultados_diarios:
                if resultado["error"]:
                    errores_detectados.append(resultado["error"])
                
                listado = resultado["data"]
                total_licitaciones_revisadas += len(listado)
                
                for lic in listado:
                    if str(lic.get('CodigoEstado')) in ['8', '18'] or lic.get('Estado') in ['Desierta', 'Revocada', 'Adjudicación Sin Ofertas']:
                        nombre_min = lic.get('Nombre', '').lower()
                        if not kws or any(kw in nombre_min for kw in kws):
                            ids_desiertas.append(lic['CodigoExterno'])
            
            ids_desiertas = list(set(ids_desiertas))
            
            # Mostrar métricas y posibles errores
            st.write(f"📊 **Métricas de la búsqueda:** Revisamos {total_licitaciones_revisadas} licitaciones en total en la API.")
            
            if errores_detectados:
                st.error("⚠️ Tuvimos problemas para conectarnos con Mercado Público en algunas fechas:")
                for e in set(errores_detectados): # Mostrar errores únicos
                    st.caption(f"- {e}")
            
            if total_licitaciones_revisadas == 0 and not errores_detectados:
                 st.warning("Mercado Público respondió correctamente, pero dice que hay 0 licitaciones publicadas en esas fechas. Verifica el rango.")

            elif not ids_desiertas:
                st.info("No se encontraron licitaciones desiertas con tus palabras clave en las licitaciones revisadas.")
            else:
                st.success(f"Se pre-seleccionaron {len(ids_desiertas)} procesos desiertos. Descargando detalles y rubros...")
                
                # Descargar detalles
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    detalles = list(executor.map(lambda x: fetch_detalle(x, api_key), ids_desiertas))
                
                detalles = [r for r in detalles if r]
                
                if detalles:
                    df = pd.DataFrame(detalles)
                    st.balloons()
                    st.dataframe(df, use_container_width=True)
                    
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar Reporte en Excel (CSV)",
                        data=csv,
                        file_name=f"oceanos_azules_{fecha_desde.strftime('%Y%m%d')}_al_{fecha_hasta.strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
