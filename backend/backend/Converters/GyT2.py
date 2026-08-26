import pdfplumber
import pandas as pd
import re
import os

MESES = {
    "ENERO": "01", "FEBRERO": "02", "MARZO": "03", "ABRIL": "04",
    "MAYO": "05", "JUNIO": "06", "JULIO": "07", "AGOSTO": "08",
    "SEPTIEMBRE": "09", "OCTUBRE": "10", "NOVIEMBRE": "11", "DICIEMBRE": "12"
}


def detectar_mes_y_anio(texto):
    match = re.search(r"-([A-ZÑ]+)\s+(\d{4})-", texto)
    if match:
        mes_nombre = match.group(1).strip().upper()
        anio = match.group(2)
        mes = MESES.get(mes_nombre)
        if mes:
            return mes, anio
    return "01", "2025"


def convert_gyt_to_excel(pdf_path, excel_path):
    """Formato G&T con día suelto y periodo en encabezado."""
    try:
        data = {
            "DIA": [],
            "REFERENCIA": [],
            "DESCRIPCION": [],
            "DEBITO": [],
            "CREDITO": []
        }

        with pdfplumber.open(pdf_path) as pdf:
            texto_completo = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
            mes, anio = detectar_mes_y_anio(texto_completo)

            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                for line in text.split('\n'):
                    if "Saldo inicial" in line or "Saldo final" in line or "promedio" in line.lower():
                        continue

                    matches = list(re.finditer(r'(\d{1,3}(?:,\d{3})*\.\d{2})', line))
                    if len(matches) < 1:
                        continue

                    monto_match = matches[-2] if len(matches) >= 2 else matches[-1]
                    monto = float(monto_match.group(1).replace(",", ""))

                    pre_monto_text = line[:monto_match.start()].strip()
                    tokens = pre_monto_text.split()

                    if len(tokens) < 3:
                        continue

                    dia = tokens[0].zfill(2)
                    ref_tokens = [t for t in tokens if t.isdigit() and len(t) >= 5]
                    referencia = ref_tokens[-1] if ref_tokens else "N/A"
                    descripcion = " ".join(tokens[1:]).replace(referencia, "").strip()

                    if "DEBITO" in descripcion.upper() or "ISR" in descripcion.upper():
                        debito = monto
                        credito = 0.0
                    else:
                        debito = 0.0
                        credito = monto

                    fecha_formateada = f"{dia}/{mes}/{anio}"
                    data["DIA"].append(fecha_formateada)
                    data["REFERENCIA"].append(referencia)
                    data["DESCRIPCION"].append(descripcion.title())
                    data["DEBITO"].append(debito)
                    data["CREDITO"].append(credito)

        if not any(data.values()):
            raise ValueError("No se encontraron movimientos válidos en el PDF.")

        df = pd.DataFrame(data)
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)
        df.to_excel(excel_path, index=False)

        return excel_path

    except Exception as e:
        print(f"Error durante la conversión: {e}")
        raise
