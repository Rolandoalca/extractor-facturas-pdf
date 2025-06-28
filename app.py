import streamlit as st
import pandas as pd
import PyPDF2
import pdfplumber
import re
from io import BytesIO
import numpy as np
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Extractor de Facturas PDF",
    page_icon="📄",
    layout="wide"
)

# Título principal
st.title("📄 Extractor de Datos de Facturas PDF")
st.markdown("---")

# Funciones auxiliares
def extract_text_from_pdf(pdf_file):
    """Extrae texto de un archivo PDF usando pdfplumber"""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        st.error(f"Error al leer PDF: {str(e)}")
        return ""

def extract_invoice_number(text):
    """Extrae el número de factura del texto"""
    patterns = [
        # Patrones más específicos para números de factura
        r'(?:factura|invoice|bill)\s*(?:no|number|#)?\s*[:\-]?\s*([A-Z0-9\-]{3,15})',
        r'(?:no\.?\s*factura|invoice\s*no\.?)\s*[:\-]?\s*([A-Z0-9\-]{3,15})',
        r'factura\s*([A-Z0-9\-]{3,15})',
        r'invoice\s*([A-Z0-9\-]{3,15})',
        r'(?:^|\n)#\s*([A-Z0-9\-]{3,15})',
        r'(?:^|\n)(\d{4,10})(?=\s|$)',  # Números de 4-10 dígitos al inicio de línea
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            number = match.group(1)
            # Filtrar números que son demasiado largos (probablemente códigos de barras)
            if len(number) <= 15:
                return number
    
    return "No encontrado"

def extract_total_amount(text):
    """Extrae el monto total de la factura"""
    patterns = [
        # Patrones más específicos para totales
        r'(?:total|amount|sum|suma)\s*[:\-]?\s*(?:\$|€|USD|EUR)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
        r'total\s*general\s*[:\-]?\s*(?:\$|€)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
        r'grand\s*total\s*[:\-]?\s*(?:\$|€)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
        r'amount\s*due\s*[:\-]?\s*(?:\$|€)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
        r'(?:^|\n|\s)total\s*(?:\$|€)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
    ]
    
    amounts = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            try:
                # Manejar formato europeo vs americano
                if ',' in match and match.count(',') == 1 and match.rfind(',') > match.rfind('.') - 3:
                    # Formato europeo: 1.025,20
                    clean_amount = match.replace('.', '').replace(',', '.')
                else:
                    # Formato americano: 1,025.20
                    clean_amount = match.replace(',', '')
                
                amount = float(clean_amount)
                # Filtrar montos razonables (no códigos largos)
                if 0 < amount < 1000000:  # Montos razonables
                    amounts.append(amount)
            except ValueError:
                continue
    
    # Retornar el mayor monto encontrado
    return max(amounts) if amounts else 0.0

def extract_tax_amount(text):
    """Extrae el monto de impuestos"""
    patterns = [
        # Patrones más específicos para impuestos
        r'(?:impuesto|iva|tax|vat)\s*[:\-]?\s*(?:\$|€|USD|EUR)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
        r'(?:sales\s*tax|tax\s*amount|total\s*tax)\s*[:\-]?\s*(?:\$|€)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
        r'iva\s*\([\d.]+%\)\s*[:\-]?\s*(?:\$|€)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
        r'impuestos?\s*[:\-]?\s*(?:\$|€)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
        r'(?:^|\n|\s)(?:impuesto|iva|tax)\s*(?:\$|€)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
    ]
    
    taxes = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            try:
                # Normalizar formato (convertir comas europeas a puntos)
                clean_tax = match.replace('.', '').replace(',', '.')
                # Si tenía formato europeo, intercambiar
                if ',' in match and match.count(',') == 1 and match.rfind(',') > match.rfind('.') - 3:
                    clean_tax = match.replace('.', '').replace(',', '.')
                else:
                    clean_tax = match.replace(',', '')
                
                tax = float(clean_tax)
                # Filtrar valores que son demasiado grandes (probablemente códigos)
                if 0 < tax < 100000:  # Impuestos razonables
                    taxes.append(tax)
            except ValueError:
                continue
    
    return sum(taxes) if taxes else 0.0

def process_pdf(pdf_file, filename):
    """Procesa un archivo PDF y extrae la información de la factura"""
    text = extract_text_from_pdf(pdf_file)
    
    if not text:
        return {
            'Archivo': filename,
            'Número de Factura': 'Error al leer PDF',
            'Monto Total': 0.0,
            'Impuestos': 0.0,
            'Estado': 'Error',
            'Texto Extraído': 'Error al leer'
        }
    
    invoice_number = extract_invoice_number(text)
    total_amount = extract_total_amount(text)
    tax_amount = extract_tax_amount(text)
    
    return {
        'Archivo': filename,
        'Número de Factura': invoice_number,
        'Monto Total': total_amount,
        'Impuestos': tax_amount,
        'Estado': 'Procesado',
        'Texto Extraído': text[:500] + "..." if len(text) > 500 else text  # Primeros 500 caracteres para debug
    }

# Sidebar con información
with st.sidebar:
    st.header("ℹ️ Información")
    st.markdown("""
    **¿Cómo usar esta aplicación?**
    
    1. Sube uno o varios archivos PDF de facturas
    2. La aplicación extraerá automáticamente:
       - Número de factura
       - Monto total
       - Monto de impuestos
    3. Revisa los resultados en la tabla
    4. Descarga los datos en formato Excel
    
    **Formatos soportados:**
    - PDF con texto seleccionable
    - Facturas en español e inglés
    """)

# Interfaz principal
uploaded_files = st.file_uploader(
    "📁 Selecciona archivos PDF de facturas",
    type=['pdf'],
    accept_multiple_files=True,
    help="Puedes seleccionar múltiples archivos PDF"
)

if uploaded_files:
    st.success(f"✅ {len(uploaded_files)} archivo(s) cargado(s)")
    
    # Botón para procesar
    if st.button("🔄 Procesar Facturas", type="primary"):
        with st.spinner("Procesando facturas..."):
            results = []
            
            # Crear barra de progreso
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Procesando: {uploaded_file.name}")
                
                # Procesar archivo
                result = process_pdf(uploaded_file, uploaded_file.name)
                results.append(result)
                
                # Actualizar progreso
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("¡Procesamiento completado!")
            
            # Crear DataFrame
            df = pd.DataFrame(results)
            
            # Guardar en session_state
            st.session_state['results_df'] = df
            
            st.success("✅ Procesamiento completado!")

# Mostrar resultados si existen
if 'results_df' in st.session_state:
    df = st.session_state['results_df']
    
    st.markdown("### 📊 Resultados Extraídos")
    
    # Métricas resumen
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📄 Facturas Procesadas", len(df))
    
    with col2:
        total_sum = df['Monto Total'].sum()
        st.metric("💰 Total General", f"${total_sum:,.2f}")
    
    with col3:
        tax_sum = df['Impuestos'].sum()
        st.metric("🏛️ Total Impuestos", f"${tax_sum:,.2f}")
    
    with col4:
        successful = len(df[df['Estado'] == 'Procesado'])
        st.metric("✅ Exitosos", f"{successful}/{len(df)}")
    
    # Tabla de resultados
    st.markdown("#### 📋 Detalle de Facturas")
    
    # Formatear montos en la tabla
    df_display = df.copy()
    df_display['Monto Total'] = df_display['Monto Total'].apply(lambda x: f"${x:,.2f}")
    df_display['Impuestos'] = df_display['Impuestos'].apply(lambda x: f"${x:,.2f}")
    
    # Crear tabla sin la columna de texto extraído
    df_table = df_display.drop('Texto Extraído', axis=1, errors='ignore')
    
    st.dataframe(
        df_table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Archivo": st.column_config.TextColumn("Archivo", width="medium"),
            "Número de Factura": st.column_config.TextColumn("Número de Factura", width="medium"),
            "Monto Total": st.column_config.TextColumn("Monto Total", width="small"),
            "Impuestos": st.column_config.TextColumn("Impuestos", width="small"),
            "Estado": st.column_config.TextColumn("Estado", width="small")
        }
    )
    
    # Opción para ver texto extraído (para debug)
    if st.checkbox("🔍 Mostrar texto extraído (para depuración)"):
        for i, row in df.iterrows():
            with st.expander(f"📄 {row['Archivo']}"):
                st.text_area("Texto extraído:", row.get('Texto Extraído', 'No disponible'), height=200)
    
    # Botón de descarga
    def convert_df_to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Facturas', index=False)
        return output.getvalue()
    
    excel_data = convert_df_to_excel(df)
    
    st.download_button(
        label="📥 Descargar resultados en Excel",
        data=excel_data,
        file_name=f"facturas_extraidas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )
    
    # Opción para limpiar resultados
    if st.button("🗑️ Limpiar Resultados"):
        del st.session_state['results_df']
        st.rerun()

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        🔧 Desarrollado con Streamlit | 📄 Extractor de Facturas PDF
    </div>
    """,
    unsafe_allow_html=True
)
