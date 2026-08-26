import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime


def convert_interbanco(pdf_path, excel_path, month=None, year=None):
    """Convierte un estado de cuenta Interbanco en PDF a Excel.

    Args:
        pdf_path (str): Ruta al archivo PDF.
        excel_path (str): Ruta de salida para el archivo Excel.
        month (int): Mes (1-12) de las transacciones.
        year (int): Año de las transacciones (ej. 2025).

    Returns:
        str: Ruta del archivo Excel generado.
    """
    if month is None or year is None:
        raise ValueError("Mes y año son requeridos para convertir estados de cuenta de Interbanco")

    try:
        # Extraer todo el texto del PDF
        texto_completo = ''
        with pdfplumber.open(pdf_path) as pdf:
            for i, pagina in enumerate(pdf.pages, 1):
                texto_pagina = pagina.extract_text() or ''
                texto_completo += texto_pagina + '\n'

        # Guardar copia del texto para depuración
        try:
            with open('pdf_texto_completo.txt', 'w', encoding='utf-8') as f:
                f.write(texto_completo)
        except Exception:
            # No crítico si falla guardar
            pass

        transacciones = []

        # Patrón: DÍA + descripción intermedia + monto1 [monto2] + saldo
        patron_general = re.compile(r'^(\d{1,2})\s+(.+?)\s+([\d,]+\.\d{2})(?:\s+([\d,]+\.\d{2}))?\s+([\d,]+\.\d{2})$')

        for linea in texto_completo.splitlines():
            linea_strip = linea.strip()
            if not linea_strip or len(linea_strip) < 6:
                continue

            # Filtrar líneas que empiezan con día
            if not re.match(r'^\d{1,2}\s+', linea_strip):
                continue

            match = patron_general.match(linea_strip)
            if not match:
                continue

            try:
                dia = match.group(1)
                texto_medio = match.group(2).strip()
                monto1 = match.group(3)
                monto2 = match.group(4)  # Puede ser None
                saldo = match.group(5)

                fecha = f"{int(dia):02d}/{int(month):02d}/{int(year)}"

                # Separar documento (primer token) y descripción (resto)
                partes = texto_medio.split()
                documento = partes[0] if partes else ''
                descripcion = ' '.join(partes[1:]).strip() if len(partes) > 1 else texto_medio

                monto1_float = float(monto1.replace(',', ''))
                saldo_float = float(saldo.replace(',', ''))

                debito = 0.0
                credito = 0.0

                if monto2:
                    # Dos montos antes del saldo: débitos y créditos separados
                    monto2_float = float(monto2.replace(',', ''))
                    debito = monto1_float
                    credito = monto2_float
                else:
                    # Un solo monto: intentar decidir según palabras clave
                    palabras_credito = ['DEPOSITO', 'DEPÓSITO', 'INTERES', 'INTERÉS', 'TRANSFERENCIA RECIBIDA', 'ABONO', 'INGRESO']
                    es_credito = any(palabra in descripcion.upper() for palabra in palabras_credito)
                    if es_credito:
                        credito = monto1_float
                    else:
                        debito = monto1_float

                transacciones.append({
                    'Fecha': fecha,
                    'Descripción': descripcion if descripcion else documento,
                    'Documento': documento,
                    'Débito': debito,
                    'Crédito': credito,
                    'Saldo': saldo_float
                })

            except Exception as e:
                # Ignorar línea si no puede parsearse
                print(f"Error procesando línea: {linea_strip} -> {e}")
                continue

        if not transacciones:
            print("\n⚠ No se encontraron transacciones. Revisar 'pdf_texto_completo.txt' para depuración.")
            raise ValueError("No se encontraron transacciones en el PDF")

        # Crear DataFrame
        df = pd.DataFrame(transacciones)

        # Formateos para exportación
        df['Débito_fmt'] = df['Débito'].apply(lambda x: f'Q {x:,.2f}' if x and x > 0 else '')
        df['Crédito_fmt'] = df['Crédito'].apply(lambda x: f'Q {x:,.2f}' if x and x > 0 else '')
        df['Saldo_fmt'] = df['Saldo'].apply(lambda x: f'Q {x:,.2f}')

        df_export = df[['Fecha', 'Descripción', 'Documento', 'Débito_fmt', 'Crédito_fmt', 'Saldo_fmt']].copy()
        df_export.columns = ['Fecha', 'Descripción', 'Documento', 'Débito', 'Crédito', 'Saldo']

        # Guardar en Excel con formato si xlsxwriter está disponible
        with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
            df_export.to_excel(writer, sheet_name='Estado de Cuenta', index=False)

            workbook = writer.book
            worksheet = writer.sheets['Estado de Cuenta']

            formato_moneda = workbook.add_format({'num_format': 'Q#,##0.00', 'align': 'right'})
            formato_fecha = workbook.add_format({'num_format': 'dd/mm/yyyy', 'align': 'center'})
            formato_header = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})

            # Aplicar formato al header
            worksheet.set_row(0, None, formato_header)

            # Columnas
            worksheet.set_column('A:A', 12, formato_fecha)
            worksheet.set_column('B:B', 50)
            worksheet.set_column('C:C', 20)
            worksheet.set_column('D:F', 15, formato_moneda)

        print(f"\n✓ Archivo Excel creado exitosamente: {excel_path}")
        return excel_path

    except Exception as e:
        print(f"❌ Error en la conversión: {e}")
        import traceback
        traceback.print_exc()
        raise