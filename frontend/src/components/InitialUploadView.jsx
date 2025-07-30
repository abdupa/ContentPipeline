import React from 'react';
import { Upload } from 'lucide-react';

// Add 'onUpload' to the list of props the component accepts
const InitialUploadView = ({ onFileSelect, selectedFileName, onUpload }) => {
  return (
    <div className="bg-white p-8 rounded-lg shadow-xl w-full max-w-2xl border border-gray-200 text-center">
      <h1 className="text-3xl font-extrabold text-gray-800 mb-4">Create Content from CSV</h1>
      <p className="text-lg text-gray-600 mb-8">Quickly generate new content by uploading a CSV file.</p>

      <section className="mb-8 p-6 bg-blue-50 rounded-lg border border-blue-200">
        <h2 className="text-xl font-semibold text-gray-700 mb-4">Upload Your File</h2>
        <p className="text-gray-600 mb-6">Supported file types: CSV. Max file size: 50MB.</p>
        <div className="flex flex-col items-center justify-center space-y-4">
          <label htmlFor="csv-upload" className="cursor-pointer">
            <div className="px-8 py-3 bg-blue-600 text-white font-bold rounded-full shadow-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-75 transition duration-200 ease-in-out transform hover:scale-105 inline-flex items-center">
              <Upload className="w-5 h-5 mr-2" />
              Browse Files
            </div>
            <input
              id="csv-upload"
              type="file"
              accept=".csv"
              className="hidden"
              onChange={onFileSelect}
            />
          </label>
          <p className="text-gray-700 text-lg font-medium">
            {selectedFileName || "No file selected"}
          </p>
        </div>
      </section>

      {/* Change the onClick handler to use the 'onUpload' prop */}
      <button
        onClick={onUpload} 
        disabled={!selectedFileName}
        className={`w-full px-8 py-3 font-bold rounded-full shadow-lg transition duration-200 ease-in-out
          ${selectedFileName
            ? 'bg-green-600 text-white hover:bg-green-700 focus:ring-green-500 transform hover:scale-105'
            : 'bg-gray-300 text-gray-500 cursor-not-allowed'
          }`}
      >
        Upload & Analyze
      </button>
    </div>
  );
};

export default InitialUploadView;