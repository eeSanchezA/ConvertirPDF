import React, { useEffect, useState } from 'react';
import axios from 'axios';
import * as XLSX from 'xlsx';

const PREVIEW_ROW_LIMIT = 100;

const BANKS = [
  { value: 'gyt', label: 'G&T' },
  { value: 'bac', label: 'BAC' },
  { value: 'bac_tarjeta', label: 'BAC Tarjeta' },
  { value: 'banrural', label: 'Banrural' },
  { value: 'bam', label: 'BAM' },
  { value: 'bantrab', label: 'Bantrab' },
  { value: 'interbanco', label: 'Interbanco' },
  { value: 'bi', label: 'Banco Industrial' },
];

const MONTHS = [
  { value: '1', label: 'Enero' },
  { value: '2', label: 'Febrero' },
  { value: '3', label: 'Marzo' },
  { value: '4', label: 'Abril' },
  { value: '5', label: 'Mayo' },
  { value: '6', label: 'Junio' },
  { value: '7', label: 'Julio' },
  { value: '8', label: 'Agosto' },
  { value: '9', label: 'Septiembre' },
  { value: '10', label: 'Octubre' },
  { value: '11', label: 'Noviembre' },
  { value: '12', label: 'Diciembre' },
];

async function buildExcelPreview(blob, fileName) {
  const buffer = await blob.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: 'array' });
  const sheetName = workbook.SheetNames[0];
  const sheet = workbook.Sheets[sheetName];
  const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' });

  if (!rows.length) {
    throw new Error('El Excel generado está vacío.');
  }

  const headers = rows[0].map((cell) => String(cell ?? ''));
  const dataRows = rows.slice(1).filter((row) => row.some((cell) => String(cell ?? '').trim() !== ''));

  return {
    fileName,
    blob,
    sheetName,
    headers,
    rows: dataRows.slice(0, PREVIEW_ROW_LIMIT),
    totalRows: dataRows.length,
    truncated: dataRows.length > PREVIEW_ROW_LIMIT,
  };
}

function App() {
  const [file, setFile] = useState(null);
  const [conversionType, setConversionType] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [month, setMonth] = useState('');
  const [year, setYear] = useState(new Date().getFullYear());
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState(null);
  const [preview, setPreview] = useState(null);
  const [pointer, setPointer] = useState({ x: 50, y: 40, active: false });

  useEffect(() => {
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) return undefined;

    let frame = 0;
    const onMove = (e) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const x = (e.clientX / window.innerWidth) * 100;
        const y = (e.clientY / window.innerHeight) * 100;
        setPointer({ x, y, active: true });
      });
    };

    const onLeave = () => {
      setPointer((prev) => ({ ...prev, active: false }));
    };

    window.addEventListener('pointermove', onMove, { passive: true });
    document.documentElement.addEventListener('mouseleave', onLeave);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('pointermove', onMove);
      document.documentElement.removeEventListener('mouseleave', onLeave);
    };
  }, []);

  useEffect(() => {
    if (!preview) return undefined;

    const onKeyDown = (e) => {
      if (e.key === 'Escape') closePreview();
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [preview]);

  const needsPeriod = conversionType === 'bantrab' || conversionType === 'interbanco';

  const canSubmit =
    Boolean(file) &&
    Boolean(conversionType) &&
    !isLoading &&
    (!needsPeriod || (Boolean(month) && Boolean(year)));

  const setPdfFile = (selected) => {
    setStatus(null);
    setPreview(null);
    if (!selected) {
      setFile(null);
      return;
    }
    if (selected.type !== 'application/pdf' && !selected.name.toLowerCase().endsWith('.pdf')) {
      setStatus({ type: 'error', message: 'Solo se admiten archivos PDF.' });
      setFile(null);
      return;
    }
    setFile(selected);
  };

  const handleFileChange = (e) => {
    setPdfFile(e.target.files?.[0] ?? null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    setPdfFile(e.dataTransfer.files?.[0] ?? null);
  };

  const readBlobMessage = async (blob) => {
    const text = await blob.text();
    try {
      const data = JSON.parse(text);
      return data.error || text;
    } catch {
      return text.trim() || 'Error al procesar el archivo PDF.';
    }
  };

  const closePreview = () => setPreview(null);

  const downloadPreview = () => {
    if (!preview) return;
    const url = window.URL.createObjectURL(preview.blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', preview.fileName);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    setStatus({ type: 'success', message: 'Archivo Excel descargado.' });
  };

  const handleUpload = async () => {
    if (!file) {
      setStatus({ type: 'error', message: 'Selecciona un archivo PDF.' });
      return;
    }
    if (!conversionType) {
      setStatus({ type: 'error', message: 'Selecciona el banco.' });
      return;
    }
    if (needsPeriod && (!month || !year)) {
      setStatus({
        type: 'error',
        message: `Selecciona el mes y año para ${conversionType === 'bantrab' ? 'Bantrab' : 'Interbanco'}.`,
      });
      return;
    }

    setIsLoading(true);
    setStatus(null);
    setPreview(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('type', conversionType);
    if (needsPeriod) {
      formData.append('month', month);
      formData.append('year', year);
    }

    try {
      const response = await axios.post(`${import.meta.env.VITE_API_URL}/upload`, formData, {
        responseType: 'blob',
      });

      const contentType = response.headers['content-type'];
      if (contentType && contentType.indexOf('application/json') !== -1) {
        const message = await readBlobMessage(response.data);
        setStatus({ type: 'error', message });
        return;
      }

      const excelBlob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const excelName = file.name.replace(/\.pdf$/i, '.xlsx');
      const previewData = await buildExcelPreview(excelBlob, excelName);

      setPreview(previewData);
      setStatus({
        type: 'success',
        message: `Conversión lista. ${previewData.totalRows} filas — revisa la vista previa.`,
      });
    } catch (error) {
      if (error.response?.data) {
        const message = await readBlobMessage(error.response.data);
        setStatus({ type: 'error', message });
      } else {
        setStatus({ type: 'error', message: 'Error de conexión con el servidor.' });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const bgStyle = {
    '--mx': `${pointer.x}%`,
    '--my': `${pointer.y}%`,
    '--parallax-x': `${(pointer.x - 50) * 0.35}px`,
    '--parallax-y': `${(pointer.y - 40) * 0.35}px`,
  };

  return (
    <div className={`app${pointer.active ? ' app--pointer' : ''}`} style={bgStyle}>
      <div className="bg" aria-hidden="true">
        <div className="bg__spotlight" />
        <div className="bg__orb bg__orb--1" />
        <div className="bg__orb bg__orb--2" />
        <div className="bg__orb bg__orb--3" />
        <div className="bg__grid" />
      </div>

      <div className="shell">
        <header className="brand">
          <div className="brand__badge">
            <span className="brand__badge-dot" />
            Conversor bancario
          </div>
          <h1 className="brand__title">
            PDF a <span className="brand__title-accent">Excel</span>
          </h1>
          <p className="brand__subtitle">Convierte estados de cuenta en segundos</p>
        </header>

        <main className="panel">
          <div className="panel__header">
            <div className="panel__icon" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <path d="M14 2v6h6M8 13h8M8 17h5" />
              </svg>
            </div>
            <div>
              <p className="panel__heading">Nueva conversión</p>
              <p className="panel__desc">Selecciona banco, sube el PDF y revisa antes de descargar</p>
            </div>
          </div>

          <div className="field">
            <label className="field__label" htmlFor="bank-select">
              Banco
            </label>
            <select
              id="bank-select"
              className="select"
              value={conversionType}
              onChange={(e) => {
                setConversionType(e.target.value);
                setStatus(null);
              }}
            >
              <option value="" disabled>
                Seleccionar banco…
              </option>
              {BANKS.map((bank) => (
                <option key={bank.value} value={bank.value}>
                  {bank.label}
                </option>
              ))}
            </select>
          </div>

          {needsPeriod && (
            <div className="field">
              <label className="field__label">Periodo</label>
              <div className="field__row">
                <select
                  className="select"
                  value={month}
                  onChange={(e) => setMonth(e.target.value)}
                  aria-label="Mes"
                >
                  <option value="">Mes…</option>
                  {MONTHS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
                <input
                  className="input"
                  type="number"
                  value={year}
                  onChange={(e) => setYear(e.target.value)}
                  min="2000"
                  max="2100"
                  aria-label="Año"
                  placeholder="Año"
                />
              </div>
            </div>
          )}

          <div className="field">
            <span className="field__label">Archivo PDF</span>
            <label
              className={[
                'dropzone',
                isDragging ? 'dropzone--active' : '',
                file ? 'dropzone--filled' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
            >
              <input
                id="file-input"
                className="dropzone__input"
                type="file"
                accept="application/pdf,.pdf"
                onChange={handleFileChange}
              />
              <div className="dropzone__icon-wrap" aria-hidden="true">
                <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
              </div>
              <p className="dropzone__title">
                {file ? file.name : 'Arrastra el PDF o haz clic'}
              </p>
              <p className="dropzone__hint">Solo archivos PDF</p>
            </label>
            {file && (
              <div className="file-chip">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
                <span>Archivo listo</span>
              </div>
            )}
          </div>

          <button
            type="button"
            className="btn"
            onClick={handleUpload}
            disabled={!canSubmit}
          >
            {isLoading ? (
              <>
                <span className="btn__spinner" aria-hidden="true" />
                Procesando…
              </>
            ) : (
              'Convertir a Excel'
            )}
          </button>

          {status && (
            <div className={`status status--${status.type}`} role="status">
              {status.message}
            </div>
          )}
        </main>

        <p className="footer-note">
          G&T <span>·</span> BAC <span>·</span> Banrural <span>·</span> BAM <span>·</span> Bantrab <span>·</span> Interbanco <span>·</span> BI
        </p>
      </div>

      {preview && (
        <div className="preview-overlay" role="dialog" aria-modal="true" aria-labelledby="preview-title">
          <div className="preview-modal">
            <div className="preview-modal__header">
              <div>
                <h2 id="preview-title" className="preview-modal__title">Vista previa</h2>
                <p className="preview-modal__meta">
                  {preview.fileName} · {preview.totalRows} filas · hoja «{preview.sheetName}»
                </p>
              </div>
              <button type="button" className="preview-modal__close" onClick={closePreview} aria-label="Cerrar vista previa">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            {preview.truncated && (
              <p className="preview-modal__note">
                Mostrando las primeras {PREVIEW_ROW_LIMIT} filas de {preview.totalRows}.
              </p>
            )}

            <div className="preview-table-wrap">
              <table className="preview-table">
                <thead>
                  <tr>
                    {preview.headers.map((header, index) => (
                      <th key={`${header}-${index}`}>{header || `Col ${index + 1}`}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {preview.headers.map((_, colIndex) => (
                        <td key={colIndex}>{row[colIndex] ?? ''}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="preview-modal__actions">
              <button type="button" className="btn btn--ghost" onClick={closePreview}>
                Cerrar
              </button>
              <button type="button" className="btn btn--inline" onClick={downloadPreview}>
                Descargar Excel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
