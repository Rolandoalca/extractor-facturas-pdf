import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Extractor de Facturas PDF", page_icon="📄", layout="wide")
st.title("📄 Extractor de Datos de Facturas PDF")
st.markdown("---")

# Función para extraer texto
def extract_text_from_pdf(pdf_file):
    try:
        with pdfplumber.open(pdf_file) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        st.error(f"Error al leer PDF: {str(e)}")
        return ""

# Función para extraer número de factura
def extract_invoice_number(text):
    patterns = [
        r'(?:factura|invoice|bill)\s*(?:no|number|#)?\s*[:\-]?\s*([A-Z0-9\-]{3,20})',
        r'(?:no\.?\s*factura|invoice\s*no\.?)\s*[:\-]?\s*([A-Z0-9\-]{3,20})',
        r'factura\s*([A-Z0-9\-]{3,20})',
        r'invoice\s*([A-Z0-9\-]{3,20})',
        r'(?:^|\n)#\s*([A-Z0-9\-]{3,20})',
        r'(?:^|\n)(\d{4,20})(?=\s|$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            number = match.group(1).strip()
            if len(number) <= 20:
                return number
    return "No encontrado"

# Función para extraer monto total
def extract_total_amount(text):
    patterns = [
        r'(?:t\s*o\s*t\s*a\s*l|total|total\s*general|grand\s*total|importe\s*total|monto\s*total|amount\s*due)\s*[:\-]?\s*(?:\$|¢|€|USD|CRC)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
        r'(?:^|\n|\s)total\s*(?:\$|¢|€)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
    ]
    amounts = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            try:
                # Normalizar el número
                normalized = match.replace('.', '').replace(',', '.')
                if ',' in match and match.count(',') == 1 and match.rfind(',') > match.rfind('.') - 3:
                    normalized = match.replace('.', '').replace(',', '.')
                else:
                    normalized = match.replace(',', '')
                amount = float(normalized)
                if 0 < amount < 100000000:
                    amounts.append(amount)
            except:
                continue
    return max(amounts) if amounts else 0.0

# Función para extraer impuestos
def extract_tax_amount(text):
    patterns = [
        r'(?:i\s*v\s*a|iva|impuesto|tax|vat)\s*[:\-]?\s*(?:\$|¢|€|USD|CRC)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
        r'(?:sales\s*tax|tax\s*amount|total\s*tax|impuestos?)\s*[:\-]?\s*(?:\$|¢|€|USD|CRC)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
        r'iva\s*\([\d.]+%\)\s*[:\-]?\s*(?:\$|¢|€)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
        r'(?:^|\n|\s)(?:i\s*v\s*a|iva|impuesto|tax)\s*(?:\$|¢|€)?\s*([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})',
    ]
    taxes = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            try:
                normalized = match.replace('.', '').replace(',', '.')
                if ',' in match and match.count(',') == 1 and match.rfind(',') > match.rfind('.') - 3:
                    normalized = match.replace('.', '').replace(',', '.')
                else:
                    normalized = match.replace(',', '')
                tax = float(normalized)
                if 0 < tax < 100000:
                    taxes.append(tax)
            except:
                continue
    return sum(taxes) if taxes else 0.0

# Procesar PDF
def process_pdf(pdf_file, filename):
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
        'Texto Extraído': text[:500] + "..." if len(text) > 500 else text
    }

# Sidebar
with st.sidebar:
    st.header("ℹ️ Información")
    st.markdown("""
    **¿Cómo usar esta app?**
    1. Sube tus archivos PDF
    2. Procesa y revisa la tabla
    3. Descarga en Excel si lo deseas
    """)

# Cargar archivos
uploaded_files = st.file_uploader("📁 Selecciona archivos PDF de facturas", type=['pdf'], accept_multiple_files=True)

if uploaded_files:
    st.success(f"✅ {len(uploaded_files)} archivo(s) cargado(s)")
    if st.button("🔄 Procesar Facturas", type="primary"):
        with st.spinner("Procesando..."):
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Procesando: {uploaded_file.name}")
                result = process_pdf(uploaded_file, uploaded_file.name)
                results.append(result)
                progress_bar.progress((i + 1) / len(uploaded_files))
            status_text.text("¡Completado!")
            df = pd.DataFrame(results)
            st.session_state['results_df'] = df
            st.success("✅ Procesamiento finalizado")

# Mostrar resultados
if 'results_df' in st.session_state:
    df = st.session_state['results_df']
    st.markdown("### 📊 Resultados Extraídos")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 Procesadas", len(df))
    col2.metric("💰 Total General", f"${df['Monto Total'].sum():,.2f}")
    col3.metric("🏛️ Impuestos", f"${df['Impuestos'].sum():,.2f}")
    col4.metric("✅ Éxitos", f"{len(df[df['Estado']=='Procesado'])}/{len(df)}")
    
    df_display = df.copy()
    df_display['Monto Total'] = df_display['Monto Total'].apply(lambda x: f"${x:,.2f}")
    df_display['Impuestos'] = df_display['Impuestos'].apply(lambda x: f"${x:,.2f}")
    df_table = df_display.drop('Texto Extraído', axis=1, errors='ignore')
    
    st.dataframe(df_table, use_container_width=True, hide_index=True)
    
    if st.checkbox("🔍 Mostrar texto extraído (debug)"):
        for _, row in df.iterrows():
            with st.expander(f"📄 {row['Archivo']}"):
                st.text_area("Texto extraído:", row.get('Texto Extraído', 'No disponible'), height=200)
    
    def convert_df_to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Facturas')
        return output.getvalue()
    
    excel_data = convert_df_to_excel(df)
    st.download_button(
        "📥 Descargar Excel",
        data=excel_data,
        file_name=f"facturas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    if st.button("🗑️ Limpiar Resultados"):
        del st.session_state['results_df']
        st.rerun()

# Footer
st.markdown("---")
st.markdown("<div style='text-align: center; color: #666;'>🔧 Desarrollado con Streamlit | Extractor de Facturas PDF</div>", unsafe_allow_html=True)
