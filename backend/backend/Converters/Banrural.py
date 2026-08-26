"""
import pdfplumber
import pandas as pd
import re
import os

def convert_banrural(pdf_path, excel_path):

    try:
        data = {
            "Fecha": [],
            "Descripción": [],
            "Referencia": [],
            "Débito": [],
            "Crédito": []
        }
        
        # Limpia valores monetarios
        def clean_money(value):
            if isinstance(value, str):
                return float(value.replace(',', ''))
            return 0.0
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                # Dividir el texto en líneas
                lines = text.split('\n')
                
                # Procesar solo líneas que empiecen con fecha
                for line in lines:
                    # Si no comienza con una fecha en formato DD/MM/YYYY, la saltamos
                    if not re.match(r'^\d{2}/\d{2}/\d{4}', line):
                        continue
                    
                    # Buscar todos los valores monetarios (Q seguido de número)
                    q_values = re.findall(r'Q\s+([\d,.]+)', line)
                    
                    # Necesitamos al menos 2 valores Q (débito y crédito)
                    if len(q_values) < 2:
                        continue
                    
                    # Extraer la fecha (siempre al inicio de la línea)
                    fecha = line[:10]  # DD/MM/YYYY
                    
                    # Obtener los valores monetarios (débito y crédito)
                    debito = q_values[0]  # El primer valor Q es el débito
                    credito = q_values[1]  # El segundo valor Q es el crédito
                    
                    # Buscar un posible número de referencia
                    # Asumimos que viene después de la fecha y antes del primer Q
                    pre_q_text = line.split('Q')[0]
                    # Buscar todos los números de al menos 4 dígitos
                    numeros = re.findall(r'\b\d{4,}\b', pre_q_text[10:])  # Saltamos la fecha
                    
                    # Usamos el último número encontrado como referencia
                    referencia = numeros[-1] if numeros else ""
                    
                    # Para la descripción, tomamos todo lo que está después de la fecha
                    # y antes de la referencia o del primer valor Q
                    if referencia:
                        # Encontrar la posición de la referencia en el texto
                        ref_pos = pre_q_text.rfind(referencia)
                        if ref_pos > 10:  # Si la referencia está después de la fecha
                            # Texto entre la fecha y la referencia
                            descripcion_text = pre_q_text[10:ref_pos].strip()
                        else:
                            # Si no podemos ubicar bien la referencia, tomamos todo hasta el primer Q
                            descripcion_text = pre_q_text[10:].strip()
                    else:
                        # No hay referencia, tomamos todo hasta el primer Q
                        descripcion_text = pre_q_text[10:].strip()
                    
                    # Limpiar la descripción (quitar números de oficina y espacios extra)
                    # Asumimos que el primer número después de la fecha es la oficina
                    descripcion_parts = descripcion_text.split()
                    if descripcion_parts and descripcion_parts[0].isdigit():
                        descripcion = " ".join(descripcion_parts[1:])
                    else:
                        descripcion = descripcion_text
                    
                    # Agregar los datos extraídos
                    data["Fecha"].append(fecha)
                    data["Descripción"].append(descripcion)
                    data["Referencia"].append(referencia)
                    data["Débito"].append(clean_money(debito))
                    data["Crédito"].append(clean_money(credito))
        
        # Crear DataFrame
        df = pd.DataFrame(data)
        
        # Mantener los valores numéricos sin formato de moneda
        # df["Débito"] y df["Crédito"] ya son valores numéricos gracias a clean_money()
        
        # Guardar a Excel
        df.to_excel(excel_path, index=False)
        
        print(f"Archivo Excel guardado exitosamente en: {excel_path}")
        return excel_path
    
    except Exception as e:
        print(f"Error en la conversión de Banrural: {str(e)}")
        raise


# Ejemplo de uso
if __name__ == "__main__":
    # Ajusta estas rutas a tu entorno
    pdf_path = "C:/Users/eesan/Downloads/Movs_XXXXXX8734_01_02_2025_28_02_2025.pdf"
    excel_path = "C:/Users/eesan/Downloads/Movs_XXXXXX8734_01_02_2025_28_02_2025.xlsx"
    convert_banrural(pdf_path, excel_path)
    """

import pdfplumber
import pandas as pd
import re
import os
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def convert_banrural(pdf_path, excel_path):
    """
    Convierte un estado de cuenta de Banrural PDF a Excel extrayendo solo 
    Fecha, Descripción, Referencia, Débito y Crédito
    
    Args:
        pdf_path: Ruta al archivo PDF del estado de cuenta
        excel_path: Ruta donde se guardará el archivo Excel
    
    Returns:
        Ruta al archivo Excel generado
    """
    try:
        logger.info(f"Iniciando conversión de Banrural: {pdf_path} -> {excel_path}")
        
        # Verificar que las rutas no sean None
        if not pdf_path or not excel_path:
            raise ValueError("Las rutas de archivo no pueden ser None")

        data = {
            "Fecha": [],
            "Descripción": [],
            "Referencia": [],
            "Débito": [],
            "Crédito": []
        }
        
        # Limpia valores monetarios
        def clean_money(value):
            if isinstance(value, str):
                return float(value.replace(',', ''))
            return 0.0
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                # Dividir el texto en líneas
                lines = text.split('\n')
                
                # Procesar solo líneas que empiecen con fecha
                for line in lines:
                    # Si no comienza con una fecha en formato DD/MM/YYYY, la saltamos
                    if not re.match(r'^\d{2}/\d{2}/\d{4}', line):
                        continue
                    
                    # Buscar todos los valores monetarios (Q seguido de número)
                    q_values = re.findall(r'Q\s+([\d,.]+)', line)
                    
                    # Necesitamos al menos 2 valores Q (débito y crédito)
                    if len(q_values) < 2:
                        continue
                    
                    # Extraer la fecha (siempre al inicio de la línea)
                    fecha = line[:10]  # DD/MM/YYYY
                    
                    # Obtener los valores monetarios (débito y crédito)
                    debito = q_values[0]  # El primer valor Q es el débito
                    credito = q_values[1]  # El segundo valor Q es el crédito
                    
                    # Buscar un posible número de referencia
                    # Asumimos que viene después de la fecha y antes del primer Q
                    pre_q_text = line.split('Q')[0]
                    # Buscar todos los números de al menos 4 dígitos
                    numeros = re.findall(r'\b\d{4,}\b', pre_q_text[10:])  # Saltamos la fecha
                    
                    # Usamos el último número encontrado como referencia
                    referencia = numeros[-1] if numeros else ""
                    
                    # Para la descripción, tomamos todo lo que está después de la fecha
                    # y antes de la referencia o del primer valor Q
                    if referencia:
                        # Encontrar la posición de la referencia en el texto
                        ref_pos = pre_q_text.rfind(referencia)
                        if ref_pos > 10:  # Si la referencia está después de la fecha
                            # Texto entre la fecha y la referencia
                            descripcion_text = pre_q_text[10:ref_pos].strip()
                        else:
                            # Si no podemos ubicar bien la referencia, tomamos todo hasta el primer Q
                            descripcion_text = pre_q_text[10:].strip()
                    else:
                        # No hay referencia, tomamos todo hasta el primer Q
                        descripcion_text = pre_q_text[10:].strip()
                    
                    # Limpiar la descripción (quitar números de oficina y espacios extra)
                    # Asumimos que el primer número después de la fecha es la oficina
                    descripcion_parts = descripcion_text.split()
                    if descripcion_parts and descripcion_parts[0].isdigit():
                        descripcion = " ".join(descripcion_parts[1:])
                    else:
                        descripcion = descripcion_text
                    
                    # Agregar los datos extraídos
                    data["Fecha"].append(fecha)
                    data["Descripción"].append(descripcion)
                    data["Referencia"].append(referencia)
                    data["Débito"].append(clean_money(debito))
                    data["Crédito"].append(clean_money(credito))
        
        # Verificar si se encontraron datos
        if not any(data.values()):
            logger.error("No se encontraron datos válidos en el PDF")
            raise ValueError("No se encontraron datos válidos en el PDF")
        
        logger.info(f"Se encontraron {len(data['Fecha'])} transacciones")
        
        # Crear DataFrame
        df = pd.DataFrame(data)
        
        # Los valores numéricos ya están como números gracias a clean_money()
        # No aplicamos formato para mantenerlos como números puros
        
        # Guardar a Excel
        df.to_excel(excel_path, index=False)
        
        logger.info(f"Archivo Excel guardado exitosamente en: {excel_path}")
        return excel_path

    except Exception as e:
        logger.error(f"Error en la conversión de Banrural: {str(e)}")
        raise

if __name__ == "__main__":
    # Ejemplo de uso - solo para pruebas
    pdf_path = "estado_cuenta.pdf"
    excel_path = "estado_cuenta.xlsx"
    convert_banrural(pdf_path, excel_path)