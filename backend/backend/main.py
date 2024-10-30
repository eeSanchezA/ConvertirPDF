from flask import Flask, request, send_file, jsonify
import os
from flask_cors import CORS
from Converters.GyT import convert_gyt  # Función GYT personalizada
from Converters.Bac import convert_pdf_to_excel  # Conversión común

app = Flask(__name__)
CORS(app)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo'}), 400

    file = request.files['file']
    conversion_type = request.form.get('type')  # Obtén el tipo de conversión

    if file.filename == '':
        return jsonify({'error': 'Archivo no válido'}), 400

    pdf_path = os.path.join('uploads', file.filename)
    file.save(pdf_path)

    excel_path = pdf_path.replace('.pdf', '.xlsx').replace('.PDF', '.xlsx')
    if conversion_type == 'gyt':
        convert_gyt(pdf_path, excel_path)
    elif conversion_type == 'bac':
        convert_pdf_to_excel(pdf_path, excel_path)
    else:
        return jsonify({'error': 'Tipo de conversión no válido'}), 400

    return send_file(excel_path, as_attachment=True)
   

    return send_file(excel_path, as_attachment=True)

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
