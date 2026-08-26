import pdfplumber
import pandas as pd
import re
import os

from Converters.GyT2 import convert_gyt_to_excel as _convert_gyt2

GYT1_LINE_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+?)\s+(-?\d{1,3}(?:,\d{3})*\.\d{2}|-?)\s+"
    r"(\d{1,3}(?:,\d{3})*\.\d{2})\s+(.+)"
)


def detect_gyt_format(pdf_path):
    """
    Detecta el formato del estado de cuenta G&T.

    - gyt1: fechas completas DD/MM/AAAA en cada movimiento
    - gyt2: periodo en encabezado (-MES AAAA-) y día suelto al inicio de fila
    """
    gyt1_hits = 0
    gyt2_hits = 0

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages[:4])

        if re.search(r"-[A-ZÑ]+\s+\d{4}-", text):
            gyt2_hits += 3

        if "Saldo inicial" in text or "Saldo final" in text:
            gyt2_hits += 2

        if "G&T" in text.upper() or "G Y T" in text.upper():
            gyt2_hits += 1

        for line in text.split("\n"):
            if GYT1_LINE_RE.match(line.strip()):
                gyt1_hits += 3
            elif re.match(r"\d{2}/\d{2}/\d{4}\s+\d+\s+", line.strip()):
                gyt1_hits += 1
            elif re.match(r"^\d{1,2}\s+\d{5,}", line.strip()):
                gyt2_hits += 1

    if gyt2_hits > gyt1_hits:
        return "gyt2"
    if gyt1_hits > 0:
        return "gyt1"
    return "gyt2"


def _convert_gyt1(pdf_path, excel_path):
    output_dir = os.path.dirname(excel_path)
    base_name = os.path.basename(excel_path)
    safe_name = "".join(c for c in base_name if c.isalnum() or c in ("-", "_", "."))
    safe_excel_path = os.path.join(output_dir, safe_name)

    data = {
        "Fecha": [],
        "Docto": [],
        "Descripcion": [],
        "Debito": [],
        "Credito": [],
    }

    print(f"Procesando PDF G&T (formato clásico): {pdf_path}")

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                match = GYT1_LINE_RE.match(line)
                if not match:
                    continue

                fecha, docto, descripcion, monto, saldo, agencia = match.groups()
                try:
                    if "-" in monto:
                        data["Debito"].append(abs(float(monto.replace(",", ""))))
                        data["Credito"].append(0.0)
                    else:
                        data["Debito"].append(0.0)
                        data["Credito"].append(abs(float(monto.replace(",", ""))))
                    data["Fecha"].append(fecha)
                    data["Docto"].append(docto)
                    data["Descripcion"].append(descripcion.strip())
                except ValueError as e:
                    print(f"Error al procesar valores numéricos: {e}")
                    continue

    if not any(data.values()):
        raise ValueError("No se encontraron datos válidos en el PDF")

    df = pd.DataFrame(data)
    os.makedirs(os.path.dirname(safe_excel_path), exist_ok=True)
    df.to_excel(safe_excel_path, index=False)

    if not os.path.exists(safe_excel_path):
        raise FileNotFoundError(f"El archivo Excel no se creó en {safe_excel_path}")

    return safe_excel_path


def _try_converters(pdf_path, excel_path, order):
    last_error = None
    for fmt in order:
        try:
            print(f"Intentando conversión G&T formato: {fmt}")
            if fmt == "gyt1":
                return _convert_gyt1(pdf_path, excel_path)
            return _convert_gyt2(pdf_path, excel_path)
        except Exception as exc:
            print(f"Formato {fmt} falló: {exc}")
            last_error = exc
    raise last_error or ValueError("No se pudo convertir el PDF G&T")


def convert_gyt(pdf_path, excel_path):
    formato = detect_gyt_format(pdf_path)
    print(f"Formato G&T detectado: {formato}")
    alternativo = "gyt1" if formato == "gyt2" else "gyt2"
    return _try_converters(pdf_path, excel_path, [formato, alternativo])
