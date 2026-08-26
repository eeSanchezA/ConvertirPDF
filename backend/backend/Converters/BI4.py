import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

MESES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
    "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12
}

MONEY = r'\d{1,3}(?:,\d{3})*\.\d{2}'


def convert_bi_integrado(pdf_path, excel_path):
    """Formato BI 'Estado de Cuenta Integrado' con débito/crédito explícitos."""
    try:
        if not pdf_path or not excel_path:
            raise ValueError("Las rutas de archivo no pueden ser None")

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"El archivo PDF no existe en la ruta: {pdf_path}")

        os.makedirs(os.path.dirname(os.path.abspath(excel_path)), exist_ok=True)

        data = {
            "Fecha": [],
            "Documento": [],
            "Descripción": [],
            "Débito(GTQ.)": [],
            "Crédito(GTQ.)": [],
            "Saldo": []
        }

        logger.info(f"Procesando PDF: {pdf_path}")

        all_text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    logger.warning(f"No se encontró texto en la página {page_num}")
                    continue
                all_text += text + "\n"

        lines = [l.strip() for l in all_text.split('\n') if l.strip()]

        mes_num, anio = None, None
        for line in lines:
            m = re.search(r'DEL MES DE\s+([A-ZÁÉÍÓÚÑ]+)\s*-\s*(\d{4})', line, re.IGNORECASE)
            if m:
                mes_nombre = m.group(1).upper()
                anio = int(m.group(2))
                mes_num = MESES.get(mes_nombre)
                break

        if not mes_num or not anio:
            raise ValueError("No se pudo detectar el mes/año del estado de cuenta (encabezado 'DEL MES DE ...').")

        table_started = False

        for line in lines:
            if not table_started:
                if re.search(r'D[ií]a\s+Documento\s+Descripci', line, re.IGNORECASE):
                    table_started = True
                continue

            if "ULTIMA LINEA" in line.upper() or line.upper().startswith("TOTALES"):
                break

            if "SALDO ANTERIOR" in line.upper():
                continue

            row_match = re.match(
                r'^(\d{1,2})\s+(\S+)\s+(.*?)\s+(' + MONEY + r')\s+(' + MONEY + r')\s+(' + MONEY + r')$',
                line
            )
            if not row_match:
                continue

            dia, documento, descripcion, debito_str, credito_str, saldo_str = row_match.groups()

            try:
                fecha_obj = datetime(anio, mes_num, int(dia))
                fecha_formato = fecha_obj.strftime('%d/%m/%Y')
            except ValueError:
                continue

            debito_valor = float(debito_str.replace(',', ''))
            credito_valor = float(credito_str.replace(',', ''))
            saldo_valor = float(saldo_str.replace(',', ''))

            data["Fecha"].append(fecha_formato)
            data["Documento"].append(documento)
            data["Descripción"].append(descripcion.strip())
            data["Débito(GTQ.)"].append(debito_valor)
            data["Crédito(GTQ.)"].append(credito_valor)
            data["Saldo"].append(saldo_valor)

        if len(data["Fecha"]) == 0:
            raise ValueError("No se encontraron transacciones válidas en el PDF")

        df = pd.DataFrame(data)
        df["Débito(GTQ.)"] = df["Débito(GTQ.)"].map('{:,.2f}'.format)
        df["Crédito(GTQ.)"] = df["Crédito(GTQ.)"].map('{:,.2f}'.format)
        df["Saldo"] = df["Saldo"].map('{:,.2f}'.format)

        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Estado de Cuenta')
            worksheet = writer.sheets['Estado de Cuenta']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(col)
                ) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = max_length

        logger.info(f"Archivo Excel creado exitosamente en: {excel_path}")
        return excel_path

    except Exception as e:
        logger.error(f"Error en la conversión: {str(e)}")
        raise
