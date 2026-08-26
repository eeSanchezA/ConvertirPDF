import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime
import logging

from Converters.BI2 import convert_bi_statement as _convert_bi2
from Converters.BI3 import convert_bi_statement_v2 as _convert_bi3
from Converters.BI4 import convert_bi_integrado as _convert_bi4

# Configurar logging
logger = logging.getLogger(__name__)


def detect_bi_format(pdf_path):
    """
    Detecta el formato del estado de cuenta del Banco Industrial.

    - bi4: encabezado 'DEL MES DE ...' (cuenta integrada)
    - bi3: tablas con Debe/Haber o movimientos ND/DE/NC/CQ
    - bi2: columnas por coordenadas con día suelto y mes en encabezado
    - bi1: saldo anterior + fechas DD-MM-AAAA y lógica por saldo corrido
    """
    scores = {"bi1": 0, "bi2": 0, "bi3": 0, "bi4": 0}

    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        if re.search(r"DEL MES DE\s+[A-ZÁÉÍÓÚÑ]+\s*-\s*\d{4}", full_text, re.IGNORECASE):
            scores["bi4"] += 5
        if re.search(r"D[ií]a\s+Documento\s+Descripci", full_text, re.IGNORECASE):
            scores["bi4"] += 3
        if "Estado de Cuenta Integrado" in full_text:
            scores["bi4"] += 2

        for page in pdf.pages[:4]:
            for table in page.extract_tables() or []:
                if not table:
                    continue
                header = " ".join(str(cell or "") for cell in table[0])
                if "Debe" in header or "Haber" in header:
                    scores["bi3"] += 4

        if re.search(r"\d{2}-\d{2}-\d{4}\s+(ND|DE|NC|CQ)\s+", full_text):
            scores["bi3"] += 3

        for page in pdf.pages[:4]:
            word_texts = [w["text"] for w in (page.extract_words() or [])]
            if {"Débito", "Crédito", "Saldo"}.issubset(set(word_texts)):
                if "Doc." in word_texts or "Día" in word_texts:
                    scores["bi2"] += 3

        if re.search(
            r"\b(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)/\d{2,4}\b",
            full_text,
            re.IGNORECASE,
        ):
            scores["bi2"] += 2

        if re.search(r"SALDO\s*ANTERIOR", full_text, re.IGNORECASE):
            scores["bi1"] += 3
        if "Docto." in full_text and "Día" in full_text:
            scores["bi1"] += 2
        if re.search(r"^\d{2}-\d{2}-\d{4}", full_text, re.MULTILINE):
            scores["bi1"] += 1

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "bi1"
    return best


def _run_bi_converter(converter, pdf_path, excel_path):
    result = converter(pdf_path, excel_path)
    if isinstance(result, tuple):
        return result[0]
    return result


def _try_bi_converters(pdf_path, excel_path, order):
    converters = {
        "bi1": _convert_bi1,
        "bi2": _convert_bi2,
        "bi3": _convert_bi3,
        "bi4": _convert_bi4,
    }
    last_error = None
    for fmt in order:
        try:
            print(f"Intentando conversión BI formato: {fmt}")
            return _run_bi_converter(converters[fmt], pdf_path, excel_path)
        except Exception as exc:
            print(f"Formato {fmt} falló: {exc}")
            last_error = exc
    raise last_error or ValueError("No se pudo convertir el PDF del Banco Industrial")


def convert_bi(pdf_path, excel_path):
    formato = detect_bi_format(pdf_path)
    print(f"Formato BI detectado: {formato}")
    orden = [formato] + [fmt for fmt in ("bi4", "bi3", "bi2", "bi1") if fmt != formato]
    return _try_bi_converters(pdf_path, excel_path, orden)


def _convert_bi1(pdf_path, excel_path):
    """
    Convierte un estado de cuenta de Banco Industrial de PDF a Excel.
    Versión mejorada que usa el saldo para determinar débito/crédito y maneja saltos de línea.

    Args:
        pdf_path (str): Ruta al archivo PDF del estado de cuenta
        excel_path (str): Ruta donde se guardará el archivo Excel

    Returns:
        str: Ruta del archivo Excel generado
    """
    try:
        # Verificar que los paths no sean None y existan
        if not pdf_path or not excel_path:
            raise ValueError("Las rutas de archivo no pueden ser None")

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"El archivo PDF no existe en la ruta: {pdf_path}")

        # Asegurar que el directorio del excel existe
        os.makedirs(os.path.dirname(os.path.abspath(excel_path)), exist_ok=True)

        data = {
            "Fecha": [],
            "Docto.": [],
            "Descripción": [],
            "Débito(GTQ.)": [],
            "Crédito(GTQ.)": [],
            "Saldo": []
        }

        logger.info(f"Procesando PDF: {pdf_path}")

        # Extraer el texto completo del PDF
        all_text = ""

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    logger.warning(f"No se encontró texto en la página {page_num}")
                    continue

                logger.info(f"Extrayendo texto de la página {page_num}")
                all_text += text + "\n"

        # Dividir en líneas y procesar
        lines = all_text.split('\n')
        logger.info(f"Total de líneas extraídas: {len(lines)}")

        # Procesar línea por línea
        table_started = False
        saldo_anterior = None  # Ya no se usa un valor por defecto hardcodeado
        i = 0

        # Regex robusto: tolera que pdfplumber pegue las palabras sin espacios
        # (ej. "****SALDOANTERIOR****") o las separe normalmente.
        saldo_anterior_pattern = re.compile(r'SALDO\s*ANTERIOR', re.IGNORECASE)

        while i < len(lines):
            line = lines[i].strip()

            # Saltar líneas vacías
            if not line:
                i += 1
                continue

            # Detectar el saldo anterior (robusto a espacios pegados/asteriscos)
            if saldo_anterior_pattern.search(line):
                saldo_match = re.search(r'(\d{1,3}(?:,\d{3})*\.\d{2})', line)
                if saldo_match:
                    saldo_anterior = float(saldo_match.group(1).replace(',', ''))
                    logger.info(f"Saldo anterior detectado: {saldo_anterior}")
                else:
                    # El valor puede estar en la línea siguiente en algunos formatos
                    if i + 1 < len(lines):
                        next_match = re.search(r'(\d{1,3}(?:,\d{3})*\.\d{2})', lines[i + 1])
                        if next_match:
                            saldo_anterior = float(next_match.group(1).replace(',', ''))
                            logger.info(f"Saldo anterior detectado (línea siguiente): {saldo_anterior}")
                table_started = True
                i += 1
                continue

            # Detectar el encabezado de la tabla
            if ("Día" in line and "Docto." in line and "Descripción" in line):
                table_started = True
                i += 1
                continue

            # Ignorar líneas antes del inicio de la tabla
            if not table_started:
                i += 1
                continue

            # Ignorar líneas de pie de página
            if "FAVOR DE REVISAR" in line or "Totales:" in line:
                i += 1
                continue

            # Buscar líneas que inician con fecha (inicio de transacción)
            if re.match(r"^\d{2}-\d{2}-\d{4}", line):
                if saldo_anterior is None:
                    # No se pudo detectar el saldo anterior en el documento;
                    # no hay forma confiable de calcular débito/crédito.
                    raise ValueError(
                        "No se pudo detectar el 'SALDO ANTERIOR' en el PDF. "
                        "Revisa el formato del documento."
                    )

                # Procesar transacción
                transaction_result = process_transaction_with_balance_logic(lines, i, saldo_anterior)

                if transaction_result:
                    fecha, docto, descripcion, debito, credito, saldo, lines_consumed = transaction_result

                    # Actualizar saldo anterior para la siguiente transacción
                    try:
                        saldo_anterior = float(saldo.replace(',', ''))
                    except ValueError:
                        logger.error(f"Error al actualizar saldo anterior: {saldo}")

                    # Convertir fecha
                    try:
                        fecha_obj = datetime.strptime(fecha, '%d-%m-%Y')
                        fecha_formato = fecha_obj.strftime('%d/%m/%Y')
                    except ValueError:
                        logger.error(f"Error en formato de fecha: {fecha}")
                        i += lines_consumed
                        continue

                    # Convertir valores monetarios
                    try:
                        debito_valor = float(debito.replace(',', '')) if debito != "0.00" else 0.0
                        credito_valor = float(credito.replace(',', '')) if credito != "0.00" else 0.0
                        saldo_valor = float(saldo.replace(',', ''))
                    except ValueError:
                        logger.error(f"Error en valores monetarios: {debito}, {credito}, {saldo}")
                        i += lines_consumed
                        continue

                    # Agregar a los datos
                    data["Fecha"].append(fecha_formato)
                    data["Docto."].append(docto)
                    data["Descripción"].append(descripcion.strip())
                    data["Débito(GTQ.)"].append(debito_valor)
                    data["Crédito(GTQ.)"].append(credito_valor)
                    data["Saldo"].append(saldo_valor)

                    logger.debug(f"Transacción agregada: {fecha} {docto} '{descripcion}' D:{debito} C:{credito} S:{saldo}")

                    # Avanzar el índice según las líneas consumidas
                    i += lines_consumed
                else:
                    i += 1
            else:
                i += 1

        # Verificar si se encontraron datos
        if len(data["Fecha"]) == 0:
            logger.warning("No se encontraron transacciones en el PDF.")
            raise ValueError("No se encontraron transacciones válidas en el PDF")

        logger.info(f"Total de transacciones encontradas: {len(data['Fecha'])}")

        # Crear DataFrame
        df = pd.DataFrame(data)

        # Formatear columnas numéricas
        df["Débito(GTQ.)"] = df["Débito(GTQ.)"].map('{:,.2f}'.format)
        df["Crédito(GTQ.)"] = df["Crédito(GTQ.)"].map('{:,.2f}'.format)
        df["Saldo"] = df["Saldo"].map('{:,.2f}'.format)

        # Guardar a Excel con formato
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Estado de Cuenta')

            # Obtener el libro de trabajo y la hoja
            workbook = writer.book
            worksheet = writer.sheets['Estado de Cuenta']

            # Ajustar el ancho de las columnas
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


def process_transaction_with_balance_logic(lines, start_index, saldo_anterior):
    """
    Procesa una transacción usando la lógica del saldo para determinar débito/crédito.
    Solo toma la primera línea de descripción si hay salto de línea.

    Args:
        lines (list): Lista de todas las líneas del documento
        start_index (int): Índice de la línea que inicia con fecha
        saldo_anterior (float): Saldo de la transacción anterior

    Returns:
        tuple: (fecha, docto, descripcion, debito, credito, saldo, lines_consumed) o None si no es válida
    """
    if start_index >= len(lines):
        return None

    # Línea inicial (debe empezar con fecha)
    first_line = lines[start_index].strip()

    # Extraer fecha y documento de la primera línea
    parts = first_line.split()
    if len(parts) < 2:
        return None

    fecha = parts[0]
    docto = parts[1]

    # Verificar formato de fecha
    if not re.match(r"^\d{2}-\d{2}-\d{4}$", fecha):
        return None

    # Buscar valores monetarios en la línea actual
    monetary_values = re.findall(r'\d{1,3}(?:,\d{3})*\.\d{2}', first_line)

    if monetary_values:
        # La transacción está completa en una línea
        saldo_nuevo = monetary_values[-1]  # El último valor es el saldo

        # Extraer descripción (entre docto y primer valor monetario)
        first_monetary_value = monetary_values[0]
        docto_end = first_line.find(docto) + len(docto)
        valor_start = first_line.find(first_monetary_value)

        if docto_end < valor_start:
            descripcion = first_line[docto_end:valor_start].strip()
        else:
            # Método alternativo: tomar partes entre docto y valores
            desc_parts = parts[2:]
            desc_text = " ".join(desc_parts)
            for val in monetary_values:
                desc_text = desc_text.replace(val, "")
            descripcion = desc_text.strip()

        lines_consumed = 1
    else:
        # La transacción se extiende a múltiples líneas
        # Buscar en las siguientes líneas hasta encontrar valores monetarios
        current_index = start_index + 1
        descripcion_parts = []

        # Agregar descripción de la primera línea (después del docto)
        first_line_desc = " ".join(parts[2:]) if len(parts) > 2 else ""
        if first_line_desc:
            descripcion_parts.append(first_line_desc)

        saldo_nuevo = None
        found_values = False
        first_desc_line_added = False  # Flag para controlar que solo tomemos la primera línea de descripción

        while current_index < len(lines) and not found_values:
            current_line = lines[current_index].strip()

            # Línea vacía, continuar
            if not current_line:
                current_index += 1
                continue

            # Nueva transacción (empieza con fecha) - detener
            if re.match(r"^\d{2}-\d{2}-\d{4}", current_line):
                break

            # Línea de pie de página - detener
            if "FAVOR DE REVISAR" in current_line or "Totales:" in current_line:
                break

            # Buscar valores monetarios en esta línea
            line_monetary_values = re.findall(r'\d{1,3}(?:,\d{3})*\.\d{2}', current_line)

            if line_monetary_values:
                # Esta línea contiene los valores monetarios
                saldo_nuevo = line_monetary_values[-1]
                monetary_values = line_monetary_values
                found_values = True

                # Extraer cualquier texto adicional antes de los valores monetarios
                first_val = line_monetary_values[0]
                val_index = current_line.find(first_val)
                if val_index > 0:
                    additional_desc = current_line[:val_index].strip()
                    if additional_desc and not first_desc_line_added:
                        descripcion_parts.append(additional_desc)
            else:
                # Solo texto de descripción - tomar solo la primera línea después del salto
                if not first_desc_line_added:
                    # Si no tenemos descripción de la primera línea, esta es la primera descripción
                    if not descripcion_parts:
                        descripcion_parts.append(current_line)
                    else:
                        # Ya tenemos descripción de la primera línea, esta es la primera después del salto
                        descripcion_parts.append(current_line)
                    first_desc_line_added = True
                # Ignorar líneas adicionales (como "INSTA" en el ejemplo)

            current_index += 1

        if not found_values or not saldo_nuevo:
            logger.warning(f"No se encontraron valores monetarios para transacción en línea {start_index}")
            return None

        descripcion = " ".join(descripcion_parts)
        lines_consumed = current_index - start_index

    # Determinar débito/crédito usando la lógica del saldo
    try:
        saldo_nuevo_float = float(saldo_nuevo.replace(',', ''))
        diferencia = saldo_nuevo_float - saldo_anterior

        if diferencia > 0:
            # El saldo aumentó = es un crédito
            credito = f"{abs(diferencia):,.2f}"
            debito = "0.00"
        else:
            # El saldo disminuyó = es un débito
            debito = f"{abs(diferencia):,.2f}"
            credito = "0.00"

    except ValueError:
        logger.error(f"Error al calcular diferencia de saldo: {saldo_nuevo}")
        return None

    # Limpiar la descripción
    descripcion = re.sub(r'\s+', ' ', descripcion).strip()

    logger.debug(f"Saldo anterior: {saldo_anterior}, Saldo nuevo: {saldo_nuevo_float}, Diferencia: {diferencia}")

    return fecha, docto, descripcion, debito, credito, saldo_nuevo, lines_consumed