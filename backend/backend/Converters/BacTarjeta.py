import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime

def convert_bac_statement_to_excel(pdf_path, excel_path):
    """
    Convierte un estado de cuenta BAC Credomatic PDF a Excel
    Extrae las transacciones de las tablas 'Detalle de movimientos del mes'
    Separa transacciones en hojas de Quetzales y Dólares
    
    Args:
        pdf_path (str): Ruta al archivo PDF
        excel_path (str): Ruta donde guardar el archivo Excel
    
    Returns:
        str: Ruta del archivo Excel creado
    """
    try:
        # Convertir a string si es necesario y verificar que no sean None
        pdf_path = str(pdf_path) if pdf_path is not None else None
        excel_path = str(excel_path) if excel_path is not None else None
        
        if not pdf_path or not excel_path:
            raise ValueError("Las rutas de archivo no pueden ser None")
        
        # Verificar que el archivo PDF existe
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"El archivo PDF no existe en la ruta: {pdf_path}")

        # Asegurar que el directorio del excel existe
        excel_dir = os.path.dirname(os.path.abspath(excel_path))
        if excel_dir:  # Solo crear directorio si no está vacío
            os.makedirs(excel_dir, exist_ok=True)

        # Estructura de datos para las transacciones separadas por moneda
        transactions_quetzales = []
        transactions_dolares = []

        print(f"Procesando PDF: {pdf_path}")

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    print(f"No se encontró texto en la página {page_num}")
                    continue

                lines = text.split('\n')
                print(f"Procesando página {page_num} con {len(lines)} líneas")

                # Variables para rastrear si estamos en una sección de movimientos
                in_movement_section = False
                current_card = ""

                for line_num, line in enumerate(lines, 1):
                    try:
                        line = line.strip()
                        
                        # Detectar inicio de sección de movimientos
                        if "Detalle de movimientos del mes" in line:
                            in_movement_section = True
                            # Extraer número de tarjeta si está en la línea
                            card_match = re.search(r'\*{4}-\*{4}-\*{4}-(\d{4})', line)
                            if card_match:
                                current_card = card_match.group(1)
                            print(f"Iniciando sección de movimientos para tarjeta: {current_card}")
                            continue
                        
                        # Detectar las columnas de moneda
                        if in_movement_section and ("Quetzales" in line and "Dólares" in line):
                            print("Encontrado encabezado de monedas")
                            continue
                        
                        # Detectar fin de sección de movimientos
                        if in_movement_section and (
                            "INTEGRACIÓN DEL PAGO MÍNIMO" in line or 
                            "Extrafinanciamientos" in line or
                            "CRÉDITO" in line or
                            "DÉBITO" in line or
                            "Página" in line
                        ):
                            in_movement_section = False
                            print("Fin de sección de movimientos")
                            continue

                        # Procesar líneas de transacciones
                        if in_movement_section and line:
                            # Patrón mejorado para capturar transacciones con ambas monedas
                            # Formato: TIPO FECHA_CONSUMO/FECHA_OPERACION DESCRIPCION [MONTO_Q] [MONTO_USD]
                            transaction_match = re.match(
                                r'(\d{2})\s+'                           # Tipo de transacción (número)
                                r'(\w{3})/(\d{2})\s+'                   # Fecha consumo (MES/DIA)
                                r'(\w{3})/(\d{2})\s+'                   # Fecha operación (MES/DIA)
                                r'(.+?)\s+'                             # Descripción
                                r'([\d,]*\.?\d*-?)\s*'                  # Monto Quetzales (opcional)
                                r'([\d,]*\.?\d*-?)\s*$',                # Monto Dólares (opcional)
                                line
                            )

                            if transaction_match:
                                tipo, mes_consumo, dia_consumo, mes_operacion, dia_operacion, descripcion, monto_q_str, monto_usd_str = transaction_match.groups()
                                
                                # Construir fecha de consumo
                                meses = {
                                    'JUL': '07', 'AGO': '08', 'SEP': '09', 'OCT': '10',
                                    'NOV': '11', 'DIC': '12', 'ENE': '01', 'FEB': '02',
                                    'MAR': '03', 'ABR': '04', 'MAY': '05', 'JUN': '06'
                                }
                                
                                if mes_consumo in meses:
                                    fecha_consumo = f"{dia_consumo}/{meses[mes_consumo]}/2025"
                                else:
                                    fecha_consumo = f"{dia_consumo}/07/2025"
                                
                                descripcion = descripcion.strip()
                                
                                # Procesar monto en Quetzales
                                if monto_q_str and monto_q_str.strip():
                                    monto_q_str = monto_q_str.replace(',', '').strip()
                                    if monto_q_str and monto_q_str != '-':
                                        is_credit_q = monto_q_str.endswith('-')
                                        monto_q_str = monto_q_str.rstrip('-')
                                        
                                        try:
                                            monto_q = float(monto_q_str)
                                            if monto_q > 0:
                                                debito_q = 0.0 if is_credit_q else monto_q
                                                credito_q = monto_q if is_credit_q else 0.0
                                                
                                                transaction_q = {
                                                    'Fecha': fecha_consumo,
                                                    'Descripción': descripcion,
                                                    'Débito': debito_q,
                                                    'Crédito': credito_q
                                                }
                                                transactions_quetzales.append(transaction_q)
                                                print(f"Transacción Q agregada: {fecha_consumo} - {descripcion} - D:{debito_q} C:{credito_q}")
                                        except ValueError:
                                            pass
                                
                                # Procesar monto en Dólares
                                if monto_usd_str and monto_usd_str.strip():
                                    monto_usd_str = monto_usd_str.replace(',', '').strip()
                                    if monto_usd_str and monto_usd_str != '-':
                                        is_credit_usd = monto_usd_str.endswith('-')
                                        monto_usd_str = monto_usd_str.rstrip('-')
                                        
                                        try:
                                            monto_usd = float(monto_usd_str)
                                            if monto_usd > 0:
                                                debito_usd = 0.0 if is_credit_usd else monto_usd
                                                credito_usd = monto_usd if is_credit_usd else 0.0
                                                
                                                transaction_usd = {
                                                    'Fecha': fecha_consumo,
                                                    'Descripción': descripcion,
                                                    'Débito': debito_usd,
                                                    'Crédito': credito_usd
                                                }
                                                transactions_dolares.append(transaction_usd)
                                                print(f"Transacción USD agregada: {fecha_consumo} - {descripcion} - D:{debito_usd} C:{credito_usd}")
                                        except ValueError:
                                            pass
                            else:
                                # Patrón alternativo más simple para líneas sin el número inicial
                                alt_match = re.match(
                                    r'(\w{3})/(\d{2})\s+'                   # Fecha consumo (MES/DIA)
                                    r'(\w{3})/(\d{2})\s+'                   # Fecha operación (MES/DIA)
                                    r'(.+?)\s+'                             # Descripción
                                    r'([\d,]*\.?\d*-?)\s*'                  # Monto Quetzales (opcional)
                                    r'([\d,]*\.?\d*-?)\s*$',                # Monto Dólares (opcional)
                                    line
                                )
                                
                                if alt_match:
                                    mes_consumo, dia_consumo, mes_operacion, dia_operacion, descripcion, monto_q_str, monto_usd_str = alt_match.groups()
                                    
                                    # Procesar igual que el patrón principal
                                    meses = {
                                        'JUL': '07', 'AGO': '08', 'SEP': '09', 'OCT': '10',
                                        'NOV': '11', 'DIC': '12', 'ENE': '01', 'FEB': '02',
                                        'MAR': '03', 'ABR': '04', 'MAY': '05', 'JUN': '06'
                                    }
                                    
                                    if mes_consumo in meses:
                                        fecha_consumo = f"{dia_consumo}/{meses[mes_consumo]}/2025"
                                    else:
                                        fecha_consumo = f"{dia_consumo}/07/2025"
                                    
                                    descripcion = descripcion.strip()
                                    
                                    # Procesar Quetzales
                                    if monto_q_str and monto_q_str.strip():
                                        monto_q_str = monto_q_str.replace(',', '').strip()
                                        if monto_q_str and monto_q_str != '-':
                                            is_credit_q = monto_q_str.endswith('-')
                                            monto_q_str = monto_q_str.rstrip('-')
                                            
                                            try:
                                                monto_q = float(monto_q_str)
                                                if monto_q > 0:
                                                    debito_q = 0.0 if is_credit_q else monto_q
                                                    credito_q = monto_q if is_credit_q else 0.0
                                                    
                                                    transaction_q = {
                                                        'Fecha': fecha_consumo,
                                                        'Descripción': descripcion,
                                                        'Débito': debito_q,
                                                        'Crédito': credito_q
                                                    }
                                                    transactions_quetzales.append(transaction_q)
                                            except ValueError:
                                                pass
                                    
                                    # Procesar Dólares
                                    if monto_usd_str and monto_usd_str.strip():
                                        monto_usd_str = monto_usd_str.replace(',', '').strip()
                                        if monto_usd_str and monto_usd_str != '-':
                                            is_credit_usd = monto_usd_str.endswith('-')
                                            monto_usd_str = monto_usd_str.rstrip('-')
                                            
                                            try:
                                                monto_usd = float(monto_usd_str)
                                                if monto_usd > 0:
                                                    debito_usd = 0.0 if is_credit_usd else monto_usd
                                                    credito_usd = monto_usd if is_credit_usd else 0.0
                                                    
                                                    transaction_usd = {
                                                        'Fecha': fecha_consumo,
                                                        'Descripción': descripcion,
                                                        'Débito': debito_usd,
                                                        'Crédito': credito_usd
                                                    }
                                                    transactions_dolares.append(transaction_usd)
                                            except ValueError:
                                                pass

                    except Exception as e:
                        print(f"Error procesando línea {line_num}: {str(e)}")
                        continue

        # Verificar si se encontraron transacciones
        if not transactions_quetzales and not transactions_dolares:
            raise ValueError("No se encontraron transacciones válidas en el PDF")

        print(f"Total de transacciones en Quetzales: {len(transactions_quetzales)}")
        print(f"Total de transacciones en Dólares: {len(transactions_dolares)}")

        # Crear DataFrames separados
        sheets_data = {}
        
        if transactions_quetzales:
            df_q = pd.DataFrame(transactions_quetzales)
            df_q['Fecha_Sort'] = pd.to_datetime(df_q['Fecha'], format='%d/%m/%Y')
            df_q = df_q.sort_values('Fecha_Sort')
            df_q = df_q.drop('Fecha_Sort', axis=1)
            
            # Formatear columnas numéricas
            df_q_formatted = df_q.copy()
            df_q_formatted["Débito"] = df_q_formatted["Débito"].apply(lambda x: f'Q {x:,.2f}' if x > 0 else '')
            df_q_formatted["Crédito"] = df_q_formatted["Crédito"].apply(lambda x: f'Q {x:,.2f}' if x > 0 else '')
            
            sheets_data['Quetzales'] = df_q_formatted
        
        if transactions_dolares:
            df_usd = pd.DataFrame(transactions_dolares)
            df_usd['Fecha_Sort'] = pd.to_datetime(df_usd['Fecha'], format='%d/%m/%Y')
            df_usd = df_usd.sort_values('Fecha_Sort')
            df_usd = df_usd.drop('Fecha_Sort', axis=1)
            
            # Formatear columnas numéricas
            df_usd_formatted = df_usd.copy()
            df_usd_formatted["Débito"] = df_usd_formatted["Débito"].apply(lambda x: f'$ {x:,.2f}' if x > 0 else '')
            df_usd_formatted["Crédito"] = df_usd_formatted["Crédito"].apply(lambda x: f'$ {x:,.2f}' if x > 0 else '')
            
            sheets_data['Dólares'] = df_usd_formatted

        # Guardar a Excel con múltiples hojas
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            for sheet_name, df_sheet in sheets_data.items():
                df_sheet.to_excel(writer, index=False, sheet_name=sheet_name)
                
                # Obtener la hoja y ajustar formato
                worksheet = writer.sheets[sheet_name]
                
                # Ajustar el ancho de las columnas
                for idx, col in enumerate(df_sheet.columns):
                    max_length = max(
                        df_sheet[col].astype(str).apply(len).max(),
                        len(col)
                    ) + 2
                    
                    # Ajustes específicos por columna
                    if col == 'Descripción':
                        max_length = min(max_length, 50)  # Limitar ancho de descripción
                    elif col in ['Débito', 'Crédito']:
                        max_length = max(max_length, 18)  # Ancho mínimo para montos con símbolo
                    
                    worksheet.column_dimensions[chr(65 + idx)].width = max_length

        print(f"Archivo Excel creado exitosamente en: {excel_path}")
        
        # Mostrar resumen
        if transactions_quetzales:
            df_q_raw = pd.DataFrame(transactions_quetzales)
            total_debitos_q = df_q_raw[df_q_raw['Débito'] > 0]['Débito'].sum()
            total_creditos_q = df_q_raw[df_q_raw['Crédito'] > 0]['Crédito'].sum()
            print(f"Resumen Quetzales:")
            print(f"  Total débitos: Q {total_debitos_q:,.2f}")
            print(f"  Total créditos: Q {total_creditos_q:,.2f}")
            print(f"  Balance neto: Q {total_creditos_q - total_debitos_q:,.2f}")
        
        if transactions_dolares:
            df_usd_raw = pd.DataFrame(transactions_dolares)
            total_debitos_usd = df_usd_raw[df_usd_raw['Débito'] > 0]['Débito'].sum()
            total_creditos_usd = df_usd_raw[df_usd_raw['Crédito'] > 0]['Crédito'].sum()
            print(f"Resumen Dólares:")
            print(f"  Total débitos: $ {total_debitos_usd:,.2f}")
            print(f"  Total créditos: $ {total_creditos_usd:,.2f}")
            print(f"  Balance neto: $ {total_creditos_usd - total_debitos_usd:,.2f}")
        
        return excel_path

    except Exception as e:
        print(f"Error en la conversión: {str(e)}")
        raise