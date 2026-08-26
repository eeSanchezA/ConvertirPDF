"""
Convierte estados de cuenta del Banco Industrial (Bi) de PDF a Excel.
Formato con columnas por coordenadas (día suelto + mes en encabezado).
"""

import pdfplumber
import pandas as pd
import re
import os

MESES = {
    "ENERO": "01", "FEBRERO": "02", "MARZO": "03", "ABRIL": "04",
    "MAYO": "05", "JUNIO": "06", "JULIO": "07", "AGOSTO": "08",
    "SEPTIEMBRE": "09", "OCTUBRE": "10", "NOVIEMBRE": "11", "DICIEMBRE": "12"
}

AMOUNT_RE = re.compile(r'^-?[\d,]*\.\d{2}$')
DAY_RE = re.compile(r'^\d{1,2}$')


def detectar_mes_anio(texto):
    match = re.search(r'\b([A-ZÑ]+)/(\d{2,4})\b', texto)
    if match:
        mes_txt = match.group(1).strip().upper()
        anio_txt = match.group(2).strip()
        mes = MESES.get(mes_txt)
        anio = "20" + anio_txt if len(anio_txt) == 2 else anio_txt
        if mes and anio:
            return mes, anio
    return "01", "2025"


def obtener_columnas(words):
    header = {}
    for w in words:
        t = w['text'].strip()
        if t in ('Débito', 'Crédito', 'Saldo', 'Día', 'Doc.'):
            header[t] = w
    if 'Débito' not in header or 'Crédito' not in header or 'Saldo' not in header:
        return None

    debito_x1 = header['Débito']['x1']
    credito_x0 = header['Crédito']['x0']
    credito_x1 = header['Crédito']['x1']
    saldo_x0 = header['Saldo']['x0']
    header_top = header['Saldo']['top']

    return {
        'header_top': header_top,
        'boundary_debito_credito': (debito_x1 + credito_x0) / 2,
        'boundary_credito_saldo': (credito_x1 + saldo_x0) / 2,
    }


def clasificar_monto(x0, cols):
    if x0 < cols['boundary_debito_credito']:
        return 'DEBITO'
    elif x0 < cols['boundary_credito_saldo']:
        return 'CREDITO'
    else:
        return 'SALDO'


def agrupar_filas(words, y_tol=2.5):
    filas = []
    for w in sorted(words, key=lambda w: (w['top'], w['x0'])):
        colocado = False
        for fila in filas:
            if abs(fila[0]['top'] - w['top']) <= y_tol:
                fila.append(w)
                colocado = True
                break
        if not colocado:
            filas.append([w])
    return filas


def convert_bi_statement(pdf_path, excel_path):
    data = {
        "DIA": [],
        "REFERENCIA": [],
        "DESCRIPCION": [],
        "DEBITO": [],
        "CREDITO": [],
        "SALDO": [],
    }

    with pdfplumber.open(pdf_path) as pdf:
        texto_completo = "\n".join(
            page.extract_text() for page in pdf.pages if page.extract_text()
        )
        mes, anio = detectar_mes_anio(texto_completo)

        for page in pdf.pages:
            words = page.extract_words()
            if not words:
                continue

            cols = obtener_columnas(words)
            if cols is None:
                continue

            filas = agrupar_filas(words)

            for fila in filas:
                fila = sorted(fila, key=lambda w: w['x0'])

                if fila[0]['top'] <= cols['header_top']:
                    continue

                texto_fila = " ".join(w['text'] for w in fila)
                if ("SALDO ANTERIOR" in texto_fila
                        or "ULTIMA LINEA" in texto_fila
                        or "Totales" in texto_fila
                        or texto_fila.strip() == ""):
                    continue

                if not DAY_RE.match(fila[0]['text']):
                    continue

                dia = fila[0]['text'].zfill(2)

                if len(fila) < 2:
                    continue
                ref = fila[1]['text']

                montos = [w for w in fila if AMOUNT_RE.match(w['text'])]
                if not montos:
                    continue

                primer_monto_x0 = min(w['x0'] for w in montos)
                desc_tokens = [
                    w['text'] for w in fila[2:]
                    if w['x0'] < primer_monto_x0
                ]
                desc = " ".join(desc_tokens).strip().title()
                if not desc:
                    continue

                debito = credito = saldo = 0.0
                for w in montos:
                    valor = float(w['text'].replace(",", ""))
                    tipo = clasificar_monto(w['x0'], cols)
                    if tipo == 'DEBITO':
                        debito = valor
                    elif tipo == 'CREDITO':
                        credito = valor
                    else:
                        saldo = valor

                fecha = f"{dia}/{mes}/{anio}"
                data["DIA"].append(fecha)
                data["REFERENCIA"].append(ref)
                data["DESCRIPCION"].append(desc)
                data["DEBITO"].append(debito)
                data["CREDITO"].append(credito)
                data["SALDO"].append(saldo)

    if not any(data.values()):
        raise ValueError("No se encontraron movimientos válidos.")

    df = pd.DataFrame(data)

    saldo_prev = None
    inconsistencias = []
    for i, row in df.iterrows():
        if saldo_prev is None:
            saldo_prev = row['SALDO'] - row['CREDITO'] + row['DEBITO']
        esperado = round(saldo_prev + row['CREDITO'] - row['DEBITO'], 2)
        if abs(esperado - row['SALDO']) > 0.01:
            inconsistencias.append(i)
        saldo_prev = row['SALDO']

    if inconsistencias:
        print(f"Aviso: {len(inconsistencias)} fila(s) no cuadran con el saldo corrido.")

    os.makedirs(os.path.dirname(excel_path) or ".", exist_ok=True)
    df.to_excel(excel_path, index=False)

    return excel_path
