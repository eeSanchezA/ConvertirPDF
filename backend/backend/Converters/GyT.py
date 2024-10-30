import pdfplumber
import pandas as pd
import re

def convert_gyt(pdf_path, excel_path):
    # Estructura de conversión del PDF a Excel
    data = {
        "Fecha": [], "Docto": [], "Descripcion": [],
        "Debito": [], "Credito": []
    }

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            lines = text.split('\n')

            for line in lines:
                match = re.match(
                    r"(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+?)\s+(-?\d{1,3}(?:,\d{3})*\.\d{2}|-?)\s+"
                    r"(\d{1,3}(?:,\d{3})*\.\d{2})\s+(.+)", line
                )
                if match:
                    fecha, docto, descripcion, monto, saldo, agencia = match.groups()
                    if '-' in monto:
                        data["Debito"].append(abs(float(monto.replace(',', ''))))  # Positivo
                        data["Credito"].append(0.0)
                    else:
                        data["Debito"].append(0.0)
                        data["Credito"].append(abs(float(monto.replace(',', ''))))  # Positivo
                    data["Fecha"].append(fecha)
                    data["Docto"].append(docto)
                    data["Descripcion"].append(descripcion.strip())

    # Crear DataFrame y exportar a Excel
    df = pd.DataFrame(data)
    df.to_excel(excel_path, index=False)
