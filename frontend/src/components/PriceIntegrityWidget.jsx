import React, { useState, useEffect, useRef } from 'react';
import { ShieldCheck, ShieldAlert, Play, Loader2, AlertTriangle, CheckCircle, Search } from 'lucide-react';
import apiClient from '../apiClient';

const PriceIntegrityWidget = () => {
  const [status, setStatus] = useState('idle'); // 'idle' | 'scanning' | 'complete'
  const [results, setResults] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  
  // We use a ref for the interval so we can clear it reliably
  const pollInterval = useRef(null);

  // 1. THIS FUNCTION ONLY RUNS ON CLICK
  const startScan = async (dryRun) => {
    setStatus('scanning');
    setResults([]);
    setSummary(null);
    setError(null);

    try {
      // Trigger the specific endpoint with dry_run param
      const response = await apiClient.post(`/api/tools/cleanup-prices?dry_run=${dryRun}`);
      const newJobId = response.data.job_id;
      
      // Only NOW do we start asking the backend for updates
      pollInterval.current = setInterval(() => checkStatus(newJobId), 2000);
      
    } catch (err) {
      setError("Failed to start scan. Please check backend connection.");
      setStatus('idle');
    }
  };

  const checkStatus = async (id) => {
    try {
      const response = await apiClient.get(`/api/jobs/${id}`);
      const jobData = response.data;

      // Update the terminal log view
      if (jobData.results && jobData.results.length > 0) {
        setResults(jobData.results);
      }

      // Stop polling when done
      if (jobData.status === 'complete') {
        clearInterval(pollInterval.current);
        setStatus('complete');
        setSummary(jobData.summary);
      } else if (jobData.status === 'failed') {
        clearInterval(pollInterval.current);
        setStatus('idle'); // Return to idle so user can try again
        setError(jobData.error || "Task failed.");
      }
    } catch (err) {
      console.error("Polling error:", err); // Silent console error
    }
  };

  // Cleanup: Stop polling if user leaves page
  useEffect(() => {
    return () => clearInterval(pollInterval.current);
  }, []);

  // Visual Logic
  const hasIssues = results.some(r => r.includes("Found Product"));
  const isCritical = results.some(r => r.includes("100%") || r.includes("90%"));
  
  // Dynamic Border Color
  let borderColor = "border-gray-300"; // Default idle
  if (status === 'scanning') borderColor = "border-blue-400";
  else if (status === 'complete' && hasIssues) borderColor = isCritical ? "border-red-500" : "border-yellow-400";
  else if (status === 'complete' && !hasIssues) borderColor = "border-green-500";

  return (
    <div className={`bg-white p-6 rounded-lg shadow-md border-l-4 ${borderColor} mb-8`}>
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
        
        {/* HEADER SECTION */}
        <div>
          <h2 className="text-xl font-semibold text-gray-800 flex items-center">
            {isCritical && status === 'complete' ? <ShieldAlert className="w-6 h-6 mr-2 text-red-500"/> : 
             !hasIssues && status === 'complete' ? <ShieldCheck className="w-6 h-6 mr-2 text-green-600"/> :
             <Search className="w-6 h-6 mr-2 text-gray-500"/>}
            Price Integrity Monitor
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Manual audit tool. Detects products with &gt;50% fake discounts.
          </p>
        </div>
        
        {/* ACTION BUTTONS */}
        <div className="flex gap-3">
          {/* Button 1: Test Scan (Always visible if not scanning) */}
          {status !== 'scanning' && (
            <button 
              onClick={() => startScan(true)}
              className="flex items-center px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded hover:bg-gray-50 text-sm font-medium transition shadow-sm"
            >
              <Play className="w-4 h-4 mr-2 text-gray-500" />
              Test Scan (Dry Run)
            </button>
          )}

          {/* Button 2: Fix All (Only visible if issues found AND scan is done) */}
          {status === 'complete' && hasIssues && (
            <button 
              onClick={() => startScan(false)}
              className="flex items-center px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 text-sm font-medium transition shadow-sm animate-pulse"
            >
              <AlertTriangle className="w-4 h-4 mr-2" />
              Fix All ({results.length})
            </button>
          )}

          {/* Loading State */}
          {status === 'scanning' && (
             <span className="flex items-center px-4 py-2 bg-indigo-50 text-indigo-700 rounded border border-indigo-100 text-sm font-medium">
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Scanning Store...
             </span>
          )}
        </div>
      </div>

      {/* TERMINAL OUTPUT (Only appears when active/done) */}
      {(results.length > 0 || status === 'scanning') && (
        <div className="bg-gray-900 text-green-400 p-4 rounded-md font-mono text-xs max-h-48 overflow-y-auto shadow-inner">
          {results.length === 0 && status === 'scanning' && <p className="animate-pulse">... Initializing Bulk Scan ...</p>}
          
          {results.map((line, idx) => (
            <div key={idx} className="mb-1 border-b border-gray-800 pb-1 last:border-0 hover:bg-gray-800">
              {line}
            </div>
          ))}
          
          {status === 'complete' && summary && (
             <div className="mt-2 pt-2 border-t border-gray-700 text-white font-bold">
               &gt; {summary}
             </div>
          )}
        </div>
      )}

      {/* CLEAN STATE MESSAGE */}
      {status === 'complete' && !hasIssues && (
        <div className="flex items-center justify-center h-16 bg-green-50 rounded border border-green-100 text-green-700 text-sm">
          <CheckCircle className="w-5 h-5 mr-2" />
          Scan Complete. No pricing issues found.
        </div>
      )}
      
       {/* ERROR MESSAGE */}
       {error && (
        <div className="mt-4 bg-red-50 text-red-700 p-3 rounded text-sm border border-red-200">
          Error: {error}
        </div>
      )}
    </div>
  );
};

export default PriceIntegrityWidget;