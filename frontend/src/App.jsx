import React, { useState } from 'react';
import axios from 'axios';

function App() {
  const [file, setFile] = useState(null);
  const [conversionType, setConversionType] = useState(''); // Estado para el tipo de conversión
  const [isLoading, setIsLoading] = useState(false);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleConversionChange = (e) => {
    setConversionType(e.target.value); // Actualiza el tipo de conversión seleccionado
  };

  const handleUpload = async () => {
    if (!file) {
      alert('Por favor, selecciona un archivo PDF');
      return;
    }
    if (!conversionType) {
      alert('Por favor, selecciona el tipo de conversión');
      return;
    }

    setIsLoading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('type', conversionType); // Agrega el tipo de conversión

    try {
      const response = await axios.post('http://localhost:5000/upload', formData, {
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${file.name.replace('.pdf', '.xlsx').replace('.PDF', '.xlsx')}`);
      document.body.appendChild(link);
      link.click();
    } catch (error) {
      alert('Error al procesar el archivo PDF');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ textAlign: 'center', marginTop: '50px', alignItems:"center" }}>
      <h1>Convertir PDF a Excel</h1>

      <div>
        <label>
          <input
            type="radio"
            value="gyt"
            checked={conversionType === 'gyt'}
            onChange={handleConversionChange}
          />
          GYT
        </label>
        <label style={{ marginLeft: '10px' }}>
          <input
            type="radio"
            value="bac"
            checked={conversionType === 'bac'}
            onChange={handleConversionChange}
          />
          BAC
        </label>
      </div>

      <input type="file" accept="application/pdf" onChange={handleFileChange} />
      <button onClick={handleUpload} disabled={!file || !conversionType || isLoading}>
        {isLoading ? 'Procesando...' : 'Subir y Convertir'}
      </button>
    </div>
  );
}

export default App;
