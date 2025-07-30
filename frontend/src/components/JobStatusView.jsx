import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Loader2, CheckCircle, XCircle, FileDown } from 'lucide-react';

const apiClient = axios.create({
  baseURL: `http://${window.location.hostname}:8000`,
});

const JobStatusView = ({ jobId, onReset }) => {
  const [jobData, setJobData] = useState(null);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await apiClient.get(`/api/get-scrape-job-status/${jobId}`);
        setJobData(response.data);

        if (response.data.status === 'complete' || response.data.status === 'failed') {
          clearInterval(intervalRef.current);
        }
      } catch (err) {
        setError('Failed to fetch job status. The job may have expired or an error occurred.');
        clearInterval(intervalRef.current);
      }
    };

    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 3000);
    return () => clearInterval(intervalRef.current);
  }, [jobId]);

  const handleDownloadCsv = () => {
    if (!jobData || !jobData.results || jobData.results.length === 0) return;
    
    // --- NEW: Generate timestamp for the download ---
    const now = new Date();
    const timestamp = now.toISOString(); // For the data column (e.g., 2025-07-11T05:00:00.000Z)
    const fileTimestamp = now.toLocaleString('sv').replace(/ /g, '_').replace(/:/g, '-'); // For the filename (e.g., 2025-07-11_13-00-00)

    const results = jobData.results;
    
    // --- UPDATED: Add 'DateTime' to the beginning of the headers ---
    const headers = ['DateTime', ...Object.keys(results[0])];
    
    let csvContent = headers.join(',') + '\n';

    results.forEach(row => {
      // --- UPDATED: Prepend the timestamp to each row's values ---
      const rowValues = headers.map(header => {
        if (header === 'DateTime') {
          return `"${timestamp}"`;
        }
        let value = row[header] ? `"${row[header].toString().replace(/"/g, '""')}"` : '';
        return value;
      });
      csvContent += rowValues.join(',') + '\n';
    });

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    // --- UPDATED: Add the timestamp to the filename ---
    link.setAttribute('download', `scrape_results_${fileTimestamp}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const renderResultsTable = () => {
    if (!jobData || !jobData.results || !jobData.results.length === 0) {
      return <p className="text-gray-500">No results to display.</p>;
    }
    
    // Get headers dynamically from the first result object
    const headers = Object.keys(jobData.results[0]);

    return (
      <div className="overflow-x-auto rounded-lg shadow-md border border-gray-200 bg-white max-h-[30rem]">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              {/* --- NEW: Add Count # column header --- */}
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">#</th>
              
              {headers.map(header => (
                <th key={header} className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                  {header.replace(/_/g, ' ').replace(/(?:^|\s)\S/g, a => a.toUpperCase())}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {jobData.results.map((row, index) => (
              <tr key={index}>
                {/* --- NEW: Add Count # cell --- */}
                <td className="px-4 py-3 whitespace-nowrap text-sm font-semibold text-gray-600">{index + 1}</td>

                {headers.map(header => (
                  <td key={`${index}-${header}`} className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                    {/* Format the timestamp for better readability, show other data normally */}
                    {header === 'scraped_at' ? new Date(row[header]).toLocaleString() : row[header]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  if (error) return <div className="p-4 text-center text-red-600 bg-red-50 rounded-lg">{error}</div>;
  if (!jobData) return <div className="flex justify-center items-center p-8"><Loader2 className="animate-spin mr-2" /> Loading job status...</div>;
  
  const progressPercent = jobData.total_urls > 0 ? (jobData.processed_urls / jobData.total_urls) * 100 : 0;
  
  return (
    <div className="bg-white p-8 rounded-lg shadow-xl w-full max-w-5xl border border-gray-200">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Scraping Job Status</h2>
          <p className="text-sm text-gray-500 font-mono">ID: {jobId}</p>
        </div>
        <button onClick={onReset} className="px-4 py-2 bg-gray-200 text-gray-800 font-semibold rounded-md hover:bg-gray-300">Start New Job</button>
      </div>

      {jobData.status === 'processing' && (
         <div className="mb-6">
          <div className="flex justify-between items-center mb-1">
            <span className="text-lg font-semibold text-indigo-600 flex items-center"><Loader2 className="animate-spin mr-2" /> Processing...</span>
            <span className="text-lg font-semibold text-gray-700">{jobData.processed_urls} / {jobData.total_urls}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4">
            <div className="bg-indigo-600 h-4 rounded-full transition-all duration-500" style={{ width: `${progressPercent}%` }}></div>
          </div>
        </div>
      )}

      {jobData.status === 'complete' && (
        <div className="mb-6 p-4 bg-green-50 text-green-700 rounded-lg flex items-center justify-between">
            <div className="flex items-center">
                <CheckCircle className="mr-3" />
                <span className="text-lg font-semibold">Job Complete! Extracted {jobData.results.length} items.</span>
            </div>
            {jobData.results && jobData.results.length > 0 && (
                <button onClick={handleDownloadCsv} className="px-4 py-2 bg-green-600 text-white font-semibold rounded-md hover:bg-green-700 flex items-center gap-2">
                  <FileDown className="w-5 h-5"/>
                  Download CSV
                </button>
            )}
        </div>
      )}
      
      {jobData.status === 'failed' && (
        <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-lg flex items-center">
          <XCircle className="mr-3" />
          <span className="text-lg font-semibold">Job Failed: {jobData.error || 'An unknown error occurred.'}</span>
        </div>
      )}
      
      {jobData.results && jobData.results.length > 0 && renderResultsTable()}
    </div>
  );
};

export default JobStatusView;