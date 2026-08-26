import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime


def convert_bam_pdf_to_excel(pdf_path, excel_path):
    try:
        if not pdf_path or not excel_path:
            raise ValueError("Las rutas de archivo no pueden ser None")
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"El archivo PDF no existe en la ruta: {pdf_path}")
        os.makedirs(os.path.dirname(os.path.abspath(excel_path)), exist_ok=True)

        data = {
            "Fecha": [],
            "Referencia": [],
            "Descripción": [],
            "Débito": [],
            "Crédito": [],
        }

        print(f"Procesando PDF: {pdf_path}")
        mes_año = None

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):

                # -----------------------------------------------------------------
                # Se usa extract_words() con coordenadas X en lugar de
                # extract_text() + regex. El PDF BAM fusiona el número de DOC
                # con la descripción en texto plano, por ej.:
                #   "1774234254Deposito Efectivo 15640234"
                # Con coordenadas cada columna se separa correctamente.
                #
                # Los límites de columna se detectan dinámicamente desde la fila
                # de encabezados (DÍA, DOC., DESCRIPCIÓN, DÉBITOS, CRÉDITOS,
                # SALDO, y opcionalmente NÚM.) usando el punto medio entre
                # encabezados consecutivos. Esto soporta PDFs con o sin las
                # columnas extra NÚM. y VALOR.
                #
                # El rango vertical de transacciones se detecta dinámicamente:
                # desde la fila de encabezados hasta la línea "ULTIMA LINEA",
                # lo que permite procesar cualquier cantidad de transacciones
                # sin importar cuántas filas ocupe la página.
                # -----------------------------------------------------------------

                words = page.extract_words(
                    keep_blank_chars=False,
                    x_tolerance=2,
                    y_tolerance=3
                )
                if not words:
                    print(f"No se encontró texto en la página {page_num}")
                    continue

                # Detectar mes y año
                if mes_año is None:
                    text = page.extract_text() or ""
                    mes_match = re.search(r'([A-ZÁÉÍÓÚ]+)-(\d{4})', text)
                    if mes_match:
                        meses = {
                            'ENERO': '01', 'FEBRERO': '02', 'MARZO': '03', 'ABRIL': '04',
                            'MAYO': '05', 'JUNIO': '06', 'JULIO': '07', 'AGOSTO': '08',
                            'SEPTIEMBRE': '09', 'OCTUBRE': '10', 'NOVIEMBRE': '11', 'DICIEMBRE': '12'
                        }
                        mes_año = (meses.get(mes_match.group(1), '01'), mes_match.group(2))
                        print(f"Mes y año detectados: {mes_match.group(1)} {mes_match.group(2)}")
                if mes_año is None:
                    mes_año = ('01', '2026')
                    print("Usando mes/año por defecto: Enero 2026")

                # Detectar límites de columna dinámicamente
                col_limits = _detect_column_limits(words)
                if col_limits is None:
                    print(f"No se encontró fila de encabezados en página {page_num}, omitiendo.")
                    continue

                dia_max, doc_max, desc_max, deb_max, cred_max, saldo_max, header_top = col_limits

                # -----------------------------------------------------------------
                # CAMBIO: detectar TX_TOP_MAX dinámicamente buscando "ULTIMA LINEA"
                # (marcada con ******************) en lugar de usar header_top + 70.
                # Esto permite procesar páginas con cualquier cantidad de filas.
                # -----------------------------------------------------------------
                ultima_linea_top = _find_ultima_linea(words, header_top)
                TX_TOP_MIN = header_top + 5
                TX_TOP_MAX = ultima_linea_top - 2 if ultima_linea_top else header_top + 500

                print(f"Página {page_num} | columnas: DÍA<{dia_max:.0f} DOC<{doc_max:.0f} "
                      f"DESC<{desc_max:.0f} DEB<{deb_max:.0f} CRED<{cred_max:.0f} SALDO<{saldo_max:.0f} "
                      f"| filas: {TX_TOP_MIN:.0f} → {TX_TOP_MAX:.0f}")

                # Agrupar palabras por fila (top ± 3px)
                row_groups = {}
                for w in words:
                    top = w['top']
                    if not (TX_TOP_MIN <= top <= TX_TOP_MAX):
                        continue
                    matched = next((k for k in row_groups if abs(k - top) <= 3), None)
                    key = matched if matched is not None else top
                    row_groups.setdefault(key, []).append(w)

                for top_y, row_words in sorted(row_groups.items()):
                    try:
                        combined = ' '.join(w['text'] for w in row_words)
                        if '***' in combined or 'ANTERIOR' in combined:
                            continue

                        dia_p, doc_p, desc_p, deb_p, cred_p = [], [], [], [], []

                        for w in sorted(row_words, key=lambda x: x['x0']):
                            x, t = w['x0'], w['text']
                            if   x < dia_max:   dia_p.append(t)
                            elif x < doc_max:   doc_p.append(t)
                            elif x < desc_max:  desc_p.append(t)
                            elif x < deb_max:   deb_p.append(t)
                            elif x < cred_max:  cred_p.append(t)
                            # SALDO y columnas NÚM./VALOR se ignoran (no solicitadas)

                        dia         = ' '.join(dia_p).strip()
                        doc_numero  = ' '.join(doc_p).strip()
                        descripcion = ' '.join(desc_p).strip()
                        debito_str  = ' '.join(deb_p).strip()
                        credito_str = ' '.join(cred_p).strip()

                        # Validar fila real de transacción
                        if not re.match(r'^\d{1,2}$', dia):
                            continue

                        fecha_completa = f"{dia.zfill(2)}/{mes_año[0]}/{mes_año[1]}"
                        try:
                            fecha_formato = datetime.strptime(fecha_completa, '%d/%m/%Y').strftime('%d/%m/%Y')
                        except ValueError:
                            print(f"Error en formato de fecha: {fecha_completa}")
                            continue

                        def parse_num(s):
                            try:
                                return float(s.replace(',', '')) if s else 0.0
                            except ValueError:
                                return 0.0

                        data["Fecha"].append(fecha_formato)
                        data["Referencia"].append(doc_numero)
                        data["Descripción"].append(descripcion)
                        data["Débito"].append(parse_num(debito_str))
                        data["Crédito"].append(parse_num(credito_str))

                        print(f"  {fecha_formato} | {doc_numero} | {descripcion[:30]:30} | "
                              f"DEB={debito_str or '—':>10} CRED={credito_str or '—':>10}")

                    except Exception as e:
                        print(f"Error procesando fila (top={top_y:.1f}): {str(e)}")
                        continue

        if not any(data.values()):
            raise ValueError("No se encontraron transacciones válidas en el PDF")

        print(f"\nTotal de transacciones encontradas: {len(data['Fecha'])}")

        df = pd.DataFrame(data)
        df_fmt = df.copy()
        df_fmt["Débito"] = df_fmt["Débito"].map(lambda x: '{:,.2f}'.format(x) if x != 0 else '')
        df_fmt["Crédito"] = df_fmt["Crédito"].map(lambda x: '{:,.2f}'.format(x) if x != 0 else '')

        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df_fmt.to_excel(writer, index=False, sheet_name='Estado de Cuenta BAM')
            ws = writer.sheets['Estado de Cuenta BAM']
            for col, width in {'A': 12, 'B': 15, 'C': 40, 'D': 14, 'E': 14}.items():
                ws.column_dimensions[col].width = width

        print(f"Archivo Excel creado exitosamente en: {excel_path}")
        return excel_path

    except Exception as e:
        print(f"Error en la conversión: {str(e)}")
        print(f"PDF path: {pdf_path}")
        print(f"Excel path: {excel_path}")
        raise


def _detect_column_limits(words):
    """
    Busca la fila de encabezados (contiene 'DÉBITOS') y calcula los límites X
    de cada columna usando el punto medio entre encabezados consecutivos.

    Columnas reconocidas: DÍA, DOC., DESCRIPCIÓN, DÉBITOS, CRÉDITOS, SALDO
    Columnas opcionales:  NÚM. (presente en cuentas con cheques)

    El límite de SALDO usa el punto medio hasta NÚM. si existe, o un margen
    fijo, para evitar que datos de NÚM./VALOR contaminen la columna SALDO.

    Retorna: (dia_max, doc_max, desc_max, deb_max, cred_max, saldo_max, header_top)
    """
    HEADER_KEYWORDS = {
        'DÍA': 'dia', 'DOC.': 'doc', 'DESCRIPCIÓN': 'desc',
        'DÉBITOS': 'deb', 'CRÉDITOS': 'cred', 'SALDO': 'saldo',
        'NÚM.': 'num',
    }

    header_top = next((w['top'] for w in words if w['text'] == 'DÉBITOS'), None)
    if header_top is None:
        return None

    header_words = [w for w in words if abs(w['top'] - header_top) <= 3]
    col_x = {HEADER_KEYWORDS[w['text']]: w['x0'] for w in header_words if w['text'] in HEADER_KEYWORDS}

    required = ['dia', 'doc', 'desc', 'deb', 'cred', 'saldo']
    if not all(k in col_x for k in required):
        print(f"Advertencia: columnas no encontradas: {[k for k in required if k not in col_x]}")
        return None

    mid = lambda a, b: (col_x[a] + col_x[b]) / 2

    # Punto medio entre SALDO y NÚM. si existe, sino margen fijo
    saldo_max = mid('saldo', 'num') if 'num' in col_x else col_x['saldo'] + 60

    return (
        mid('dia',  'doc'),
        mid('doc',  'desc'),
        mid('desc', 'deb'),
        mid('deb',  'cred'),
        mid('cred', 'saldo'),
        saldo_max,
        header_top,
    )


def _find_ultima_linea(words, header_top):
    """
    Busca la fila con '******************' que marca el fin de transacciones.
    Solo considera filas debajo del encabezado de columnas.
    Retorna el top de esa fila, o None si no se encuentra.
    """
    for w in words:
        if w['top'] > header_top and w['text'].startswith('****'):
            return w['top']
    return None