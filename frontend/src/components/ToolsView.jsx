import React, { useState } from 'react';
import { Wrench, HardHat, Loader2, Table } from 'lucide-react';
import apiClient from '../apiClient';

const ToolsView = ({ onJobStarted, onNavigateToReview }) => {
  // State for WordPress Inspector
  const [url, setUrl] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isInspecting, setIsInspecting] = useState(false); // Corrected variable name

  // State for Google Sheets Importer
  const [sheetUrl, setSheetUrl] = useState('');
  const [isImporting, setIsImporting] = useState(false);

  const handleInspect = async () => {
    if (!url || !username || !password) {
      alert('Please fill in all WordPress fields.');
      return;
    }
    setIsInspecting(true); // Use the correct setter
    try {
      const payload = { url, username, password };
      const response = await apiClient.post('/api/tools/inspect-wordpress', payload);
      onJobStarted(response.data.job_id, 'tools');
    } catch (err) {
      alert(`Failed to start inspection task: ${err.response?.data?.detail || 'Unknown error'}`);
    } finally {
        setIsInspecting(false); // Use the correct setter
    }
  };

  const handleImport = async () => {
    if (!sheetUrl.trim()) {
      alert('Please provide a Google Sheet URL.');
      return;
    }
    setIsImporting(true);
    try {
      const payload = { sheet_url: sheetUrl };
      const response = await apiClient.post('/api/import/google-sheet', payload);
      
      // --- THE FIX: This now correctly navigates to the new review page ---
      onJobStarted(response.data.job_id, 'tools');

    } catch (err) {
      alert(`Failed to start import task: ${err.response?.data?.detail || 'Unknown error'}`);
      // Only set loading to false if there's an error, otherwise we navigate away.
      setIsImporting(false);
    }
  };

  const handleLazadaImport = async () => {
    setIsImporting(true); // Or use a new loading state for this button
    try {
      // Call our new, hardcoded Lazada endpoint
      const response = await apiClient.post('/api/import/run-lazada-importer');
      onJobStarted(response.data.job_id, 'tools');
    } catch (err) {
      alert(`Failed to start Lazada import task: ${err.response?.data?.detail || 'Unknown error'}`);
      setIsImporting(false);
    }
  };

  const handleShopeeImport = async () => {
    setIsImporting(true); // We can reuse the same loading state
    try {
      // Call the new Shopee endpoint we created
      const response = await apiClient.post('/api/import/run-shopee-importer'); 
      onJobStarted(response.data.job_id, 'tools');
    } catch (err) {
      alert(`Failed to start Shopee import task: ${err.response?.data?.detail || 'Unknown error'}`);
      setIsImporting(false);
    }
  };

  return (
    <div className="w-full max-w-4xl">
      <div className="flex items-center mb-6">
        <Wrench className="w-8 h-8 mr-3 text-indigo-600" />
        <div>
          <h1 className="text-3xl font-extrabold text-gray-800">Tools</h1>
          <p className="text-lg text-gray-600">Utilities for managing and analyzing your content sources.</p>
        </div>
      </div>

      <div className="space-y-8">
        {/* --- Google Sheets Importer Tool --- */}
        <div className="bg-white p-6 rounded-lg shadow-xl border border-gray-200">
          <h2 className="text-xl font-semibold text-gray-700 mb-4 flex items-center">
            <Table className="w-6 h-6 mr-2 text-green-500" />
            Price Importers
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Run the importers to fetch the latest prices from your hardcoded Shopee and Lazada Google Sheets.
          </p>
          <div className="border-t pt-4 flex justify-end space-x-4">
            {/* --- Shopee Button --- */}
            <button 
              onClick={handleShopeeImport} // We will create this handler next
              disabled={isImporting} 
              className="inline-flex items-center px-6 py-2 bg-orange-500 text-white font-semibold rounded-md shadow-sm hover:bg-orange-600 disabled:bg-gray-400"
            >
              {isImporting ? <Loader2 className="w-5 h-5 mr-2 animate-spin"/> : null}
              Run Shopee Importer
            </button>
            
            {/* --- Lazada Button --- */}
            <button 
              onClick={handleLazadaImport} // This should already exist
              disabled={isImporting} 
              className="inline-flex items-center px-6 py-2 bg-blue-500 text-white font-semibold rounded-md shadow-sm hover:bg-blue-600 disabled:bg-gray-400"
            >
              {isImporting ? <Loader2 className="w-5 h-5 mr-2 animate-spin"/> : null}
              Run Lazada Importer
            </button>
          </div>
        </div>
        {/* --- WordPress Site Inspector --- */}
        <div className="bg-white p-6 rounded-lg shadow-xl border border-gray-200">
          <h2 className="text-xl font-semibold text-gray-700 mb-4 flex items-center">
            <HardHat className="w-6 h-6 mr-2 text-yellow-500" />
            WordPress Site Inspector
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Connect to a WordPress site to fetch a complete list of all its posts, pages, and categories.
          </p>
          <div className="border-t pt-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Site URL</label>
              <input type="text" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.your-wordpress-site.com" className="w-full p-2 border rounded-md"/>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">WordPress Username</label>
              <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="your_wp_username" className="w-full p-2 border rounded-md"/>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Application Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••••••••••" className="w-full p-2 border rounded-md"/>
            </div>
            <div className="text-right">
              {/* --- CORRECTED BUTTON --- */}
              <button onClick={handleInspect} disabled={isInspecting} className="inline-flex items-center px-6 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-sm hover:bg-indigo-700 disabled:bg-gray-400">
                {isInspecting ? <Loader2 className="w-5 h-5 mr-2 animate-spin"/> : null}
                {isInspecting ? 'Inspecting...' : 'Start Inspection'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ToolsView;