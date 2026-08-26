import pdfplumber
import pandas as pd
import re
import os
import sys
from datetime import datetime

MESES = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}

NUM_RE = re.compile(r"^-?\d{1,3}(?:,\d{3})*\.\d{2}$")
BAC1_LINE_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s+"
    r"(\d+)\s+"
    r"([A-Z0-9]+)\s+"
    r"(.+?)\s+"
    r"(-?\d{1,3}(?:,\d{3})*\.\d{2}|0\.00)\s*"
    r"(\d{1,3}(?:,\d{3})*\.\d{2}|0\.00)\s*"
    r"(-?\d{1,3}(?:,\d{3})*\.\d{2})"
)


def _to_float(s):
    return float(s.replace(",", ""))


def _group_words_into_rows(words, y_tol=3):
    rows = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        placed = False
        for row in rows:
            if abs(row[0]["top"] - w["top"]) <= y_tol:
                row.append(w)
                placed = True
                break
        if not placed:
            rows.append([w])
    for row in rows:
        row.sort(key=lambda w: w["x0"])
    rows.sort(key=lambda row: row[0]["top"])
    return rows


def detect_bac_format(pdf_path):
    """
    Detecta el formato del estado de cuenta BAC.

    - bac2: encabezado con Débitos/Créditos/Concepto y fechas MES/DD
    - bac1: líneas con fecha DD/MM/AAAA y débito + crédito en la misma fila
    """
    bac1_hits = 0
    bac2_hits = 0

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:4]:
            text = page.extract_text() or ""
            words = page.extract_words() or []
            word_texts = [w["text"] for w in words]

            if "Débitos" in word_texts and "Créditos" in word_texts and "Concepto" in word_texts:
                bac2_hits += 3

            if re.search(r"\b(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)/\d{2}\b", text):
                bac2_hits += 2

            if "Fecha de Corte:" in text and re.search(r"/[A-Z]{3}/", text):
                bac2_hits += 1

            for line in text.split("\n"):
                if BAC1_LINE_RE.match(line.strip()):
                    bac1_hits += 2
                elif re.match(r"\d{2}/\d{2}/\d{4}\s+\d+\s+[A-Z0-9]+\s+", line.strip()):
                    bac1_hits += 1

    if bac2_hits > bac1_hits:
        return "bac2"
    if bac1_hits > 0:
        return "bac1"
    return "bac2"


def _convert_bac1(pdf_path, excel_path):
    data = {
        "Fecha": [],
        "Referencia": [],
        "Descripción": [],
        "Débito": [],
        "Créditos": [],
        "Balance": [],
    }

    print(f"Procesando PDF BAC (formato clásico): {pdf_path}")

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                print(f"No se encontró texto en la página {page_num}")
                continue

            lines = text.split("\n")
            print(f"Procesando página {page_num} con {len(lines)} líneas")

            for line_num, line in enumerate(lines, 1):
                try:
                    match = BAC1_LINE_RE.match(line.strip())
                    if not match:
                        if re.search(r"\d{2}/\d{2}/\d{4}", line):
                            print(f"No coincide: {line}")
                        continue

                    fecha, referencia, codigo, descripcion, debito, credito, balance = match.groups()

                    try:
                        fecha_obj = datetime.strptime(fecha, "%d/%m/%Y")
                        fecha_formato = fecha_obj.strftime("%d/%m/%Y")
                    except ValueError:
                        print(f"Error en formato de fecha: {fecha}")
                        continue

                    try:
                        debito_valor = abs(float(debito.replace(",", "")))
                        credito_valor = abs(float(credito.replace(",", "")))
                        balance_valor = float(balance.replace(",", ""))
                    except ValueError:
                        print(f"Error en valores numéricos: Débito={debito}, Crédito={credito}, Balance={balance}")
                        continue

                    data["Fecha"].append(fecha_formato)
                    data["Referencia"].append(referencia)
                    data["Descripción"].append(f"{codigo} {descripcion.strip()}")
                    data["Débito"].append(debito_valor)
                    data["Créditos"].append(credito_valor)
                    data["Balance"].append(balance_valor)

                except Exception as e:
                    print(f"Error procesando línea {line_num}: {str(e)}")
                    print(f"Línea problemática: {line}")
                    continue

    if not any(data.values()):
        raise ValueError("No se encontraron transacciones válidas en el PDF")

    print(f"Total de transacciones encontradas: {len(data['Fecha'])}")

    df = pd.DataFrame(data)
    df["Débito"] = df["Débito"].map("{:,.2f}".format)
    df["Créditos"] = df["Créditos"].map("{:,.2f}".format)
    df["Balance"] = df["Balance"].map("{:,.2f}".format)

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Estado de Cuenta")
        worksheet = writer.sheets["Estado de Cuenta"]
        for idx, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = max_length

    print(f"Archivo Excel creado exitosamente en: {excel_path}")
    return excel_path


def _convert_bac2(pdf_path, excel_path, year=None):
    registros = []
    year_detectado = year

    print(f"Procesando PDF BAC (formato por columnas): {pdf_path}")

    with pdfplumber.open(pdf_path) as pdf:
        if year_detectado is None:
            texto_p1 = pdf.pages[0].extract_text() or ""
            m = re.search(r"Fecha de Corte:\s*(\d{2})/([A-Z]{3})/(\d{2,4})", texto_p1)
            if m:
                yy = m.group(3)
                year_detectado = int(yy) if len(yy) == 4 else 2000 + int(yy)
        if year_detectado is None:
            year_detectado = datetime.now().year
            print(f"Aviso: no se detectó el año en el PDF, usando {year_detectado}")

        for page_num, page in enumerate(pdf.pages, 1):
            words = page.extract_words()
            if not words:
                continue

            rows = _group_words_into_rows(words)

            header_row = None
            for row in rows:
                texts = [w["text"] for w in row]
                if "Débitos" in texts and "Créditos" in texts and "Concepto" in texts:
                    header_row = row
                    break
            if header_row is None:
                continue

            def x0_of(label):
                for w in header_row:
                    if w["text"].startswith(label):
                        return w["x0"]
                return None

            x_debito = x0_of("Débitos")
            x_credito = x0_of("Créditos")
            x_saldo = x0_of("Saldo")
            header_top = header_row[0]["top"]

            limite_deb_cred = (x_debito + x_credito) / 2
            limite_cred_saldo = (x_credito + x_saldo) / 2

            for row in rows:
                if row[0]["top"] <= header_top:
                    continue

                texts = [w["text"] for w in row]
                linea = " ".join(texts)

                if "ULTIMA LINEA" in linea or "Pagina" in linea or "Continuación" in linea:
                    continue

                if texts[:2] == ["Saldo", "Anterior"]:
                    continue

                if "Saldo al Corte" in linea or texts[:2] == ["Saldo", "al"]:
                    continue

                if not re.match(r"^\d+$", texts[0]):
                    continue
                if len(texts) < 5:
                    continue

                referencia = texts[0]
                fecha_txt = texts[2]
                m_fecha = re.match(r"^([A-Z]{3})/(\d{2})$", fecha_txt)
                if not m_fecha:
                    continue
                mes_abbr, dia = m_fecha.groups()
                mes_num = MESES.get(mes_abbr)
                if mes_num is None:
                    continue
                fecha_obj = datetime(year_detectado, mes_num, int(dia))

                monto_words = [w for w in row if NUM_RE.match(w["text"])]
                if not monto_words:
                    continue

                saldo_word = max(monto_words, key=lambda w: w["x0"])
                saldo_valor = _to_float(saldo_word["text"])

                debito_valor = 0.0
                credito_valor = 0.0
                for w in monto_words:
                    if w is saldo_word:
                        continue
                    if w["x0"] < limite_deb_cred:
                        debito_valor += _to_float(w["text"])
                    elif w["x0"] < limite_cred_saldo:
                        credito_valor += _to_float(w["text"])

                registros.append({
                    "Fecha": fecha_obj.strftime("%d/%m/%Y"),
                    "Referencia": referencia,
                    "Débito": debito_valor,
                    "Crédito": credito_valor,
                    "Saldo": saldo_valor,
                })

    if not registros:
        raise ValueError("No se encontraron movimientos válidos en el PDF")

    df = pd.DataFrame(registros)
    df["Referencia"] = df["Referencia"].astype(str)

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Estado de Cuenta")

        worksheet = writer.sheets["Estado de Cuenta"]
        from openpyxl.styles import Font

        for row_cells in worksheet.iter_rows():
            for cell in row_cells:
                cell.font = Font(name="Arial", size=10, bold=(cell.row == 1))

        for col_letter in ("C", "D", "E"):
            for cell in worksheet[col_letter][1:]:
                cell.number_format = "#,##0.00;(#,##0.00)"

        anchos = {"A": 12, "B": 14, "C": 14, "D": 14, "E": 14}
        for col, ancho in anchos.items():
            worksheet.column_dimensions[col].width = ancho

    print(f"Archivo Excel creado exitosamente en: {excel_path}")
    print(f"Total de movimientos: {len(df)}")
    return excel_path


def convert_pdf_to_excel(pdf_path, excel_path):
    if not pdf_path or not excel_path:
        raise ValueError("Las rutas de archivo no pueden ser None")

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"El archivo PDF no existe en la ruta: {pdf_path}")

    os.makedirs(os.path.dirname(os.path.abspath(excel_path)) or ".", exist_ok=True)

    formato = detect_bac_format(pdf_path)
    print(f"Formato BAC detectado: {formato}")

    try:
        if formato == "bac2":
            return _convert_bac2(pdf_path, excel_path)
        return _convert_bac1(pdf_path, excel_path)
    except ValueError:
        print(f"Conversión {formato} sin resultados, intentando formato alternativo…")
        alternativo = "bac1" if formato == "bac2" else "bac2"
        if alternativo == "bac2":
            return _convert_bac2(pdf_path, excel_path)
        return _convert_bac1(pdf_path, excel_path)


if __name__ == "__main__":
    pdf_in = sys.argv[1] if len(sys.argv) > 1 else "estado_de_cuenta.pdf"
    excel_out = sys.argv[2] if len(sys.argv) > 2 else "estado_de_cuenta.xlsx"
    convert_pdf_to_excel(pdf_in, excel_out)
