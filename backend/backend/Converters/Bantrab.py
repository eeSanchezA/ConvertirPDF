import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime

def convert_bantrab(pdf_path, excel_path, month=None, year=None):
    try:
        # Verificar que se proporcionaron mes y año
        if month is None or year is None:
            raise ValueError("Mes y año son requeridos para convertir estados de cuenta de Bantrab")

        # Leer el PDF
        with pdfplumber.open(pdf_path) as pdf:
            texto = ''
            for pagina in pdf.pages:
                texto += pagina.extract_text() + '\n'
        
        print("Texto extraído del PDF:")
        print(texto)
        
        transacciones = []
        lineas = texto.split('\n')
        
        # Patrón para capturar transacciones
        patron = r'(\d{2})\s+([\w\s]+(?:DE INTERESES|[-\w\s]+))\s+(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+,\d+\.\d{2})'
        
        for linea in lineas:
            print(f"Analizando línea: {linea}")
            match = re.search(patron, linea.strip())
            if match:
                print(f"Coincidencia encontrada: {match.groups()}")
                dia, descripcion, valor1, valor2, saldo = match.groups()
                
                try:
                    # Determinar si es débito o crédito
                    if float(valor1.replace(',', '')) > 0:
                        debito = float(valor1.replace(',', ''))
                        credito = 0.0
                    else:
                        debito = 0.0
                        credito = float(valor2.replace(',', ''))
                    
                    fecha = f"{int(dia):02d}/{int(month):02d}/{year}"
                    
                    transacciones.append({
                        'Fecha': fecha,
                        'Descripción': descripcion.strip(),
                        'DÉBITOS': debito,
                        'CRÉDITOS': credito
                    })
                except ValueError as e:
                    print(f"Error procesando valores: {e}")
                    continue
        
        if not transacciones:
            raise ValueError("No se encontraron transacciones en el PDF")
        
        # Crear DataFrame
        df = pd.DataFrame(transacciones)
        
        # Formatear columnas numéricas
        df['DÉBITOS'] = df['DÉBITOS'].apply(lambda x: f'Q {x:,.2f}' if x > 0 else '')
        df['CRÉDITOS'] = df['CRÉDITOS'].apply(lambda x: f'Q {x:,.2f}' if x > 0 else '')
        
        # Guardar en Excel
        df.to_excel(excel_path, index=False)
        
        return excel_path
        
    except Exception as e:
        print(f"Error en la conversión: {str(e)}")
        raise