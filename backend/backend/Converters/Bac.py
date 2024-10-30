import pdfplumber
import pandas as pd
import re

def convert_pdf_to_excel(pdf_path, excel_path):
    data = {
        "Fecha": [], "Referencia": [],
        "Descripción": [], "Débito": [], "Créditos": []
    }

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue  # Skip if no text is found on the page
            lines = text.split('\n')

            # Extract relevant data using regex
            for line in lines:
                match = re.match(
                    r"(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+?)\s+(-?\d{1,3}(?:,\d{3})*\.\d{2}|0\.00)\s+"
                    r"(\d{1,3}(?:,\d{3})*\.\d{2}|0\.00)\s+(\d{1,3}(?:,\d{3})*\.\d{2})", line
                )
                if match:
                    fecha, referencia, codigo, debito, credito, balance = match.groups()
                    data["Fecha"].append(fecha)
                    data["Referencia"].append(referencia)
                    data["Descripción"].append(codigo.strip())
                    data["Débito"].append(abs(float(debito.replace(',', ''))))
                    data["Créditos"].append(abs(float(credito.replace(',', ''))))

    # Convert to DataFrame and save to Excel
    df = pd.DataFrame(data)
    df.to_excel(excel_path, index=False, engine='openpyxl')

