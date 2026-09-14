import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$")
DOC_RE = re.compile(r"^\d+$")
MONEY_RE = re.compile(r"^-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?$")
ACCOUNT_RE = re.compile(r"Cuenta:\s*(\S+)", re.IGNORECASE)

CREDIT_TYPE_RE = re.compile(
    r"^(PAGO|CREDITO|CRÉDITO|NC|ABONO|NOTA\s+DE\s+CREDITO|NOTA\s+DE\s+CRÉDITO)",
    re.IGNORECASE,
)

SKIP_PREFIXES = (
    "detalle de movimientos",
    "fecha tipo",
    "banco industrial",
    "saldo anterior",
    "saldo al final",
    "cuenta:",
)


def _parse_money(token):
    return float(token.replace(",", ""))


def _normalize_date(token):
    match = DATE_RE.match(token)
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    if year < 100:
        year += 2000
    try:
        return datetime(year, month, day).strftime("%d/%m/%Y")
    except ValueError:
        return None


def _is_skip_line(line):
    lowered = line.lower()
    return any(lowered.startswith(prefix) for prefix in SKIP_PREFIXES)


def _detect_currency(line):
    lowered = line.lower()
    if "valor" not in lowered or "saldo" not in lowered:
        return None
    if "(q" in lowered:
        return "GTQ"
    if "us" in lowered or "usd" in lowered or "($)" in lowered:
        return "USD"
    return None


def _parse_transaction_line(line):
    parts = line.split()
    if len(parts) < 5:
        return None

    fecha = _normalize_date(parts[0])
    if not fecha:
        return None

    index = 1
    tipo_parts = []
    while index < len(parts) and not DOC_RE.match(parts[index]) and not DATE_RE.match(parts[index]):
        token = parts[index]
        if not re.match(r"^[A-ZÁÉÍÓÚÑ./]+$", token, re.IGNORECASE):
            return None
        tipo_parts.append(token)
        index += 1

    if not tipo_parts or index >= len(parts) or not DOC_RE.match(parts[index]):
        return None

    tipo = " ".join(tipo_parts).upper()
    documento = parts[index]
    rest = parts[index + 1:]

    if len(rest) < 3:
        return None

    saldo_token = rest[-1]
    valor_token = rest[-2]
    if not MONEY_RE.match(saldo_token) or not MONEY_RE.match(valor_token):
        return None

    concepto = " ".join(rest[:-2]).strip()
    if not concepto:
        return None

    valor = _parse_money(valor_token)
    amount = abs(valor)

    if CREDIT_TYPE_RE.match(tipo):
        debito, credito = 0.0, amount
    else:
        debito, credito = amount, 0.0

    return {
        "Fecha": fecha,
        "Tipo": tipo,
        "Documento": documento,
        "Descripción": concepto,
        "Débito": debito,
        "Crédito": credito,
    }


def _format_sheet(df, currency):
    formatted = df.copy()
    prefix = "Q " if currency == "GTQ" else "$ "
    formatted["Débito"] = formatted["Débito"].apply(lambda x: f"{prefix}{x:,.2f}" if x else "")
    formatted["Crédito"] = formatted["Crédito"].apply(lambda x: f"{prefix}{x:,.2f}" if x else "")
    return formatted


def convert_bi_tarjeta(pdf_path, excel_path):
    """
    Convierte el detalle de movimientos de Tarjeta de crédito BI a Excel.
    Extrae Fecha, Tipo, Documento, Descripción, Débito y Crédito.
    Deduplica movimientos repetidos cuando el PDF incluye varios periodos.
    """
    pdf_path = str(pdf_path) if pdf_path is not None else None
    excel_path = str(excel_path) if excel_path is not None else None

    if not pdf_path or not excel_path:
        raise ValueError("Las rutas de archivo no pueden ser None")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"El archivo PDF no existe en la ruta: {pdf_path}")

    os.makedirs(os.path.dirname(os.path.abspath(excel_path)), exist_ok=True)

    transactions = {"GTQ": [], "USD": []}
    seen = {"GTQ": set(), "USD": set()}
    current_currency = "GTQ"
    current_account = ""

    logger.info(f"Procesando PDF de tarjeta BI: {pdf_path}")

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                logger.warning(f"No se encontró texto en la página {page_num}")
                continue

            for raw_line in text.split("\n"):
                line = " ".join(raw_line.split())
                if not line:
                    continue

                account_match = ACCOUNT_RE.search(line)
                if account_match:
                    current_account = account_match.group(1)
                    continue

                detected = _detect_currency(line)
                if detected:
                    current_currency = detected
                    continue

                if _is_skip_line(line):
                    continue

                parsed = _parse_transaction_line(line)
                if not parsed:
                    continue

                parsed["Cuenta"] = current_account
                key = (parsed["Fecha"], parsed["Documento"], round(parsed["Débito"] + parsed["Crédito"], 2))
                if key in seen[current_currency]:
                    continue
                seen[current_currency].add(key)
                transactions[current_currency].append(parsed)

    sheets = {}
    for currency, rows in transactions.items():
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df["Fecha_Sort"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y")
        df = df.sort_values(["Fecha_Sort", "Documento"], kind="mergesort").drop(columns=["Fecha_Sort"])
        columns = ["Fecha", "Tipo", "Documento", "Descripción", "Débito", "Crédito"]
        if df["Cuenta"].astype(str).str.strip().any():
            columns = ["Cuenta"] + columns
        sheets[currency] = _format_sheet(df[columns], currency)

    if not sheets:
        raise ValueError("No se encontraron movimientos de tarjeta de crédito BI en el PDF")

    sheet_names = {"GTQ": "Quetzales", "USD": "Dólares"}
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        for currency, df_sheet in sheets.items():
            name = sheet_names[currency]
            df_sheet.to_excel(writer, index=False, sheet_name=name)
            worksheet = writer.sheets[name]
            for idx, col in enumerate(df_sheet.columns):
                max_length = max(df_sheet[col].astype(str).apply(len).max(), len(col)) + 2
                if col == "Descripción":
                    max_length = min(max_length, 50)
                elif col in ("Débito", "Crédito"):
                    max_length = max(max_length, 16)
                worksheet.column_dimensions[chr(65 + idx)].width = max_length

    total = sum(len(rows) for rows in transactions.values())
    logger.info(f"Tarjeta BI: {total} movimientos únicos escritos en {excel_path}")
    return excel_path
