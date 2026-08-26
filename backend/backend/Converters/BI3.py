import pdfplumber
import pandas as pd
import re
import os


def convert_bi_statement_v2(pdf_path, excel_path):
    """Formato BI con tablas o movimientos ND/DE/NC/CQ."""
    try:
        data = {
            "Fecha": [],
            "Descripción": [],
            "No. Doc.": [],
            "Debe (Débito)": [],
            "Haber (Crédito)": []
        }

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()

                if tables:
                    for table in tables:
                        for row in table[1:]:
                            if len(row) >= 5 and row[0]:
                                fecha = row[0] if row[0] else ""
                                tipo_desc = row[2] if len(row) > 2 and row[2] else ""
                                no_doc = row[3] if len(row) > 3 and row[3] else ""
                                debe = row[4] if len(row) > 4 and row[4] else "0"
                                haber = row[5] if len(row) > 5 and row[5] else "0"

                                try:
                                    debe_val = float(debe.replace(',', '')) if debe and debe != '0' else 0.0
                                    haber_val = float(haber.replace(',', '')) if haber and haber != '0' else 0.0
                                except Exception:
                                    debe_val = 0.0
                                    haber_val = 0.0

                                if fecha and re.match(r'\d{2}-\d{2}-\d{4}', fecha):
                                    data["Fecha"].append(fecha)
                                    data["Descripción"].append(tipo_desc)
                                    data["No. Doc."].append(no_doc)
                                    data["Debe (Débito)"].append(debe_val)
                                    data["Haber (Crédito)"].append(haber_val)
                else:
                    text = page.extract_text()
                    if not text:
                        continue

                    for line in text.split('\n'):
                        pattern = (
                            r'(\d{2}-\d{2}-\d{4})\s+(ND|DE|NC|CQ)\s+(.+?)(\d+)\s+'
                            r'(\d{1,3}(?:,\d{3})*\.\d{2})\s+(\d{1,3}(?:,\d{3})*\.\d{2})\s+'
                            r'(\d{1,3}(?:,\d{3})*\.\d{2})'
                        )
                        match = re.search(pattern, line)
                        if not match:
                            continue

                        fecha = match.group(1)
                        tipo = match.group(2)
                        descripcion = match.group(3).strip()
                        no_doc = match.group(4)
                        montos = [match.group(5), match.group(6)]

                        if tipo in ['ND', 'CQ']:
                            debe_val = float(montos[0].replace(',', ''))
                            haber_val = 0.0
                        else:
                            debe_val = 0.0
                            haber_val = float(montos[0].replace(',', ''))

                        data["Fecha"].append(fecha)
                        data["Descripción"].append(f"{tipo} {descripcion}")
                        data["No. Doc."].append(no_doc)
                        data["Debe (Débito)"].append(debe_val)
                        data["Haber (Crédito)"].append(haber_val)

        if not data["Fecha"]:
            raise ValueError("No se encontraron transacciones válidas en el PDF.")

        df = pd.DataFrame(data)
        os.makedirs(os.path.dirname(excel_path) if os.path.dirname(excel_path) else '.', exist_ok=True)
        df.to_excel(excel_path, index=False)

        print(f"Archivo Excel creado exitosamente: {excel_path}")
        print(f"Se procesaron {len(df)} transacciones.")

        return excel_path

    except Exception as e:
        print(f"Error al procesar el archivo: {e}")
        raise
