from flask import Flask, request, send_file, jsonify
import os
from io import BytesIO
from flask_cors import CORS
import logging
import traceback
from Converters.GyT import convert_gyt
from Converters.Bac import convert_pdf_to_excel
from Converters.Banrural import convert_banrural
from Converters.Bam import convert_bam_pdf_to_excel
from Converters.Bantrab import convert_bantrab
from Converters.Interbanco import convert_interbanco
from Converters.BI import convert_bi
from Converters.BacTarjeta import convert_bac_statement_to_excel
from Converters.BITarjeta import convert_bi_tarjeta


# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

@app.route('/upload', methods=['POST'])
def upload_file():
    pdf_path = None
    excel_path = None
    
    try:
        # Validar archivo
        if 'file' not in request.files:
            logger.error("No se encontró archivo en la petición")
            return jsonify({'error': 'No se envió ningún archivo'}), 400
        
        file = request.files['file']
        conversion_type = request.form.get('type')
        
        if file.filename == '':
            logger.error("Nombre de archivo vacío")
            return jsonify({'error': 'Archivo no válido'}), 400
        
        # Validar tipo de conversión
        if not conversion_type:
            logger.error("Tipo de conversión no especificado")
            return jsonify({'error': 'Tipo de conversión no especificado'}), 400
            
        # Validar extensión del archivo
        if not file.filename.lower().endswith('.pdf'):
            logger.error("El archivo no es un PDF")
            return jsonify({'error': 'El archivo debe ser un PDF'}), 400

        # Crear un nombre de archivo seguro
        safe_filename = "".join(c for c in file.filename if c.isalnum() or c in ('-', '_', '.'))
        
        # Crear directorio de uploads
        upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        pdf_path = os.path.join(upload_dir, safe_filename)
        excel_path = pdf_path.replace('.pdf', '.xlsx').replace('.PDF', '.xlsx')
        
        logger.info(f"Guardando PDF en: {pdf_path}")
        file.save(pdf_path)
        
        if not os.path.exists(pdf_path):
            logger.error("El archivo PDF no se guardó correctamente")
            return jsonify({'error': 'Error al guardar el archivo PDF'}), 500
        
        logger.info(f"Iniciando conversión tipo: {conversion_type}")
        
        # Realizar la conversión según el tipo
        if conversion_type in ['bantrab', 'interbanco']:
            # Obtener y validar mes y año para Bantrab e Interbanco
            month = request.form.get('month')
            year = request.form.get('year')
            
            if not month or not year:
                logger.error(f"Mes o año no proporcionados para {conversion_type}")
                return jsonify({'error': f'Mes y año son requeridos para {conversion_type}'}), 400
            
            try:
                month = int(month)
                year = int(year)
                if not (1 <= month <= 12 and 2000 <= year <= 2100):
                    raise ValueError("Valores fuera de rango")
            except ValueError:
                logger.error("Valores de mes o año inválidos")
                return jsonify({'error': 'Valores de mes o año inválidos'}), 400
            
            if conversion_type == 'bantrab':
                excel_path = convert_bantrab(pdf_path, excel_path, month, year)
            else:  # interbanco
                excel_path = convert_interbanco(pdf_path, excel_path, month, year)
        else:
            # Conversiones sin mes/año
            conversion_functions = {
                'gyt': convert_gyt,
                'bac': convert_pdf_to_excel,
                'banrural': convert_banrural,
                'bi': convert_bi,
                'bi_tarjeta': convert_bi_tarjeta,
                'bac_tarjeta': convert_bac_statement_to_excel,
                'bam': convert_bam_pdf_to_excel,
            }
            
            if conversion_type not in conversion_functions:
                logger.error(f"Tipo de conversión no válido: {conversion_type}")
                return jsonify({'error': 'Tipo de conversión no válido'}), 400
                
            excel_path = conversion_functions[conversion_type](pdf_path, excel_path)
        
        if not os.path.exists(excel_path):
            logger.error("El archivo Excel no se creó correctamente")
            return jsonify({'error': 'Error al crear el archivo Excel'}), 500

        with open(excel_path, 'rb') as excel_file:
            excel_bytes = excel_file.read()

        download_name = os.path.basename(excel_path)
        logger.info("Conversión exitosa, enviando archivo")
        return send_file(
            BytesIO(excel_bytes),
            as_attachment=True,
            download_name=download_name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        
    except Exception as e:
        logger.error(f"Error en la conversión: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error en la conversión: {str(e)}'}), 500
        
    finally:
        # Limpiar archivos temporales
        try:
            if pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)
                logger.debug(f"Archivo PDF temporal eliminado: {pdf_path}")
            if excel_path and os.path.exists(excel_path):
                os.remove(excel_path)
                logger.debug(f"Archivo Excel temporal eliminado: {excel_path}")
        except Exception as e:
            logger.error(f"Error al limpiar archivos temporales: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)