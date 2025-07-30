import React, { useState } from 'react';
import { CheckCircle, XCircle, ChevronDown, Download } from 'lucide-react';

const AnalysisResultsView = ({ onFileChange, onStartContentGeneration, analysisData }) => {
  const [errorsVisible, setErrorsVisible] = useState(false);

  const {
    fileName = 'N/A',
    totalRows = 0,
    requiredColumnsPresent = false,
    dataValidationErrors = [],
  } = analysisData || {};

  const hasCriticalErrors = dataValidationErrors.length > 0 || !requiredColumnsPresent;

  const handleDownloadErrorLog = () => {
    const errorCsvRows = ["Row Number,Error Description"];
    dataValidationErrors.forEach(error => {
        const match = error.match(/Row (\d+):/);
        const rowNum = match ? match[1] : "N/A";
        errorCsvRows.push(`${rowNum},"${error.replace(/"/g, '""')}"`);
    });
    const csvString = errorCsvRows.join('\n');
    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.setAttribute('download', `error_log_${fileName}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="bg-white p-8 rounded-lg shadow-xl w-full max-w-2xl border border-gray-200">
      <h1 className="text-3xl font-extrabold text-gray-800 mb-4 text-center">File Analysis Complete</h1>
      
      <section className="mb-8 p-6 bg-blue-50 rounded-lg border border-blue-200 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          {hasCriticalErrors ? (
            <XCircle className="text-red-500 w-6 h-6" />
          ) : (
            <CheckCircle className="text-green-500 w-6 h-6" />
          )}
          <span className="font-semibold text-gray-800 text-lg">{fileName}</span>
        </div>
        <button
          onClick={onFileChange}
          className="px-4 py-2 bg-gray-200 text-gray-700 rounded-full text-sm font-semibold hover:bg-gray-300"
        >
          Change File
        </button>
      </section>

      <section className="mb-8 p-6 bg-gray-50 rounded-lg border border-gray-200 text-left">
        <h2 className="text-xl font-semibold text-gray-700 mb-4">Validation Summary</h2>
        <div className="space-y-3">
          <p className="text-gray-700 text-lg"><strong>Total Rows Detected:</strong> {totalRows}</p>
          <p className="text-gray-700 text-lg flex items-center">
            <strong className="mr-2">Required Columns:</strong>
            {requiredColumnsPresent ? 
              <span className="flex items-center text-green-700"><CheckCircle className="w-5 h-5 mr-1" /> All present</span> :
              <span className="flex items-center text-red-700"><XCircle className="w-5 h-5 mr-1" /> Missing columns</span>
            }
          </p>
          <p className="text-gray-700 text-lg flex items-center">
            <strong className="mr-2">Data Validation:</strong>
            {dataValidationErrors.length === 0 ?
              <span className="flex items-center text-green-700"><CheckCircle className="w-5 h-5 mr-1" /> No issues found</span> :
              <span className="flex items-center text-red-700"><XCircle className="w-5 h-5 mr-1" /> {dataValidationErrors.length} errors found</span>
            }
          </p>
        </div>

        {dataValidationErrors.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-300">
            <button onClick={() => setErrorsVisible(!errorsVisible)} className="text-blue-600 hover:underline font-semibold text-sm flex items-center">
              {errorsVisible ? "Hide" : "View"} Error Details <ChevronDown className={`w-4 h-4 ml-1 transition-transform ${errorsVisible ? 'rotate-180' : ''}`} />
            </button>
            {errorsVisible && (
              <div className="mt-2 p-3 bg-red-50 rounded-md border border-red-200 max-h-40 overflow-y-auto">
                <ul className="list-disc list-inside text-sm text-red-800 space-y-1">
                  {dataValidationErrors.map((error, index) => <li key={index}>{error}</li>)}
                </ul>
              </div>
            )}
            <div className="mt-4 text-right">
              <button onClick={handleDownloadErrorLog} className="inline-flex items-center text-sm px-4 py-2 bg-gray-200 text-gray-800 font-semibold rounded-full hover:bg-gray-300">
                <Download className="w-4 h-4 mr-2"/> Download Error Log
              </button>
            </div>
          </div>
        )}
      </section>

      <button
        type="button"
        onClick={onStartContentGeneration}
        disabled={hasCriticalErrors}
        className={`w-full px-8 py-3 font-bold rounded-full shadow-lg transition duration-200
          ${!hasCriticalErrors ? 'bg-green-600 text-white hover:bg-green-700 transform hover:scale-105' : 'bg-gray-300 text-gray-500 cursor-not-allowed'}`}
      >
        Start Content Generation
      </button>
    </div>
  );
};

export default AnalysisResultsView;