import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, date
import concurrent.futures
import time

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
    keywords = st.text_input("Palabras clave en el título", "consultoria, asesoria, estudio, diseñ, actualizacion, servicio")

# SISTEMA ANTI-BLOQUEO
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Connection": "keep-alive"
}

def fetch_lista_diaria(fecha_str, ticket):
    """Descarga la lista con disfraz de navegador y sistema de reintentos"""
    url = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?fecha={fecha_str}&ticket={ticket}"
    
    # Intentar hasta 3 veces si Mercado Público falla
    for intento in range(3):
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            
            if res.status_code == 200:
                data = res.json()
                if 'Mensaje' in data and data.get('Cantidad', 0) == 0:
                     return {"error": data['Mensaje'], "data": []}
                return {"error": None, "data": data.get('Listado', [])}
            elif res.status_code == 401 or res.status_code == 403:
                return {"error": "API Ticket rechazado o inválido.", "data": []}
            else:
                # Si es 500, esperamos 2 segundos y reintentamos
                time.sleep(2) 
                
        except requests.exceptions.Timeout:
            time.sleep(2) # Esperar antes de reintentar
        except Exception as e:
            time.sleep(2)
            
    # Si falló las 3 veces, reportamos el error
    return {"error": f"Fallo tras 3 intentos en fecha {fecha_str} (Revisa estado de la API)", "data": []}

def fetch_detalle(id_licitacion, ticket):
    url = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?codigo={id_licitacion}&ticket={ticket}"
    for intento in range(2): # 2 intentos para el detalle
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data['Cantidad'] > 0:
                    lic = data['Listado'][0]
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
            time.sleep(1)
        except: time.sleep(1)
    return None

if st.button("Buscar Oportunidades (Océanos Azules)", type="primary"):
    if not api_key:
        st.error("Por favor ingresa tu API Ticket en la barra lateral.")
    elif fecha_desde > fecha_hasta:
        st.error("Error: La fecha 'Desde' no puede ser posterior a la fecha 'Hasta'.")
    else:
        dias_diferencia = (fecha_hasta - fecha_desde).days + 1
            
        with st.spinner(f"Modo Sigilo Activo: Escaneando {dias_diferencia} días en Mercado Público..."):
            fechas_a_consultar = [(fecha_desde + timedelta(days=i)).strftime("%d%m%Y") for i in range(dias_diferencia)]
            kws = [k.strip().lower() for k in keywords.split(",")] if keywords else []
            
            ids_desiertas = []
            total_licitaciones_revisadas = 0
            errores_detectados = []
            
            # Bajamos a 3 "trabajadores" simultáneos para no saturar su servidor y evitar el Error 500
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                resultados_diarios = list(executor.map(lambda f: fetch_lista_diaria(f, api_key), fechas_a_consultar))
            
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
            
            st.write(f"📊 **Métricas de la búsqueda:** Revisamos {total_licitaciones_revisadas} licitaciones en total en la API.")
            
            if errores_detectados:
                st.error("⚠️ Persisten problemas de conexión con Mercado Público (puede que sus servidores estén caídos hoy o tu Ticket esté caducado):")
                for e in set(errores_detectados): 
                    st.caption(f"- {e}")
            
            if total_licitaciones_revisadas == 0 and not errores_detectados:
                 st.warning("Mercado Público respondió, pero indica 0 licitaciones publicadas. Intenta ampliar el rango de fechas.")

            elif total_licitaciones_revisadas > 0 and not ids_desiertas:
                st.info("¡Conexión Exitosa! Revisamos los datos, pero no se encontraron licitaciones DESIERTAS con tus palabras clave en este periodo.")
            elif ids_desiertas:
                st.success(f"¡Éxito! Se pre-seleccionaron {len(ids_desiertas)} procesos desiertos. Descargando detalles y rubros...")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
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
