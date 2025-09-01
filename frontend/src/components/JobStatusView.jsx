import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Loader2, CheckCircle, XCircle, FileDown, Info, CheckSquare, Download } from 'lucide-react';
import apiClient from '../apiClient'; // Ensure this path is correct for your project structure

const JobStatusView = ({ jobId, onReset, onNavigateToQueue }) => {
  const [jobData, setJobData] = useState(null);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await apiClient.get(`/api/jobs/status/${jobId}`);
        setJobData(response.data);

        if (response.data.status === 'complete' || response.data.status === 'failed') {
          clearInterval(intervalRef.current);
        }
      } catch (err) {
        setError('Failed to fetch job status. The job may have expired or an error occurred.');
        clearInterval(intervalRef.current);
      }
    };

    if (jobId) {
        fetchStatus(); // Initial fetch
        intervalRef.current = setInterval(fetchStatus, 3000);
    }
    
    return () => {
        if(intervalRef.current) {
            clearInterval(intervalRef.current);
        }
    };
  }, [jobId]);

  // --- CORRECTED: Only one handleDownloadCsv function ---
  const handleDownloadCsv = () => {
    // This function now correctly points to the new, dynamic download endpoint for inspection results.
    // For scraper results, we would need a different mechanism if we wanted to keep both.
    // For now, this will serve the primary purpose for the Tools section.
    window.open(`${apiClient.defaults.baseURL}/api/tools/download-inspection-result/${jobId}`);
  };

  const renderResultsTable = () => {
    const hasResults = jobData && jobData.results && jobData.results.length > 0;
    
    if (!hasResults || (jobData.results[0] && jobData.results[0].draft_id)) {
      // Don't render a table for manual generation jobs or if there are no results.
      if (jobData && jobData.status === 'complete') {
        return (
          <div className="text-center py-8 text-gray-600 bg-gray-50 rounded-lg">
            <Info className="w-8 h-8 mx-auto mb-2 text-blue-500" />
            <p className="font-semibold">No new articles were processed for this run.</p>
          </div>
        );
      }
      return <p className="text-gray-500 text-center py-8">Waiting for results...</p>;
    }
    
    const headers = Object.keys(jobData.results[0]);

    return (
      <div className="overflow-x-auto rounded-lg shadow-md border border-gray-200 bg-white max-h-[30rem]">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
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
                <td className="px-4 py-3 whitespace-nowrap text-sm font-semibold text-gray-600">{index + 1}</td>
                {headers.map(header => (
                  <td key={`${index}-${header}`} className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                    {row[header]}
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
          <h2 className="text-2xl font-bold text-gray-800">{jobData.project_name || jobData.job_id.includes('inspect') ? 'Site Inspection' : "Job Status"}</h2>
          <p className="text-sm text-gray-500 font-mono">ID: {jobId}</p>
        </div>
        <button onClick={onReset} className="px-4 py-2 bg-gray-200 text-gray-800 font-semibold rounded-md hover:bg-gray-300">Back</button>
      </div>

      {['processing', 'discovering', 'scraping', 'starting'].includes(jobData.status) ? (
         <div className="mb-6">
          <div className="flex justify-between items-center mb-1">
            <span className="text-lg font-semibold text-indigo-600 flex items-center"><Loader2 className="animate-spin mr-2" /> {jobData.status.charAt(0).toUpperCase() + jobData.status.slice(1)}...</span>
            <span className="text-lg font-semibold text-gray-700">{jobData.processed_urls || 0} / {jobData.total_urls || '?'}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4">
            <div className="bg-indigo-600 h-4 rounded-full transition-all duration-500" style={{ width: `${progressPercent}%` }}></div>
          </div>
        </div>
      ) : null}

      {/* --- CORRECTED JSX and LOGIC for complete status --- */}
      {jobData.status === 'complete' && (
        <div className="mb-6 p-4 bg-green-50 text-green-700 rounded-lg flex items-center justify-between">
            <div className="flex items-center">
                <CheckCircle className="mr-3" />
                <span className="text-lg font-semibold">Job Complete!</span>
            </div>
            
            {/* Logic to show the correct button */}
            {jobId.includes('inspect') ? (
                <button onClick={handleDownloadCsv} className="px-4 py-2 bg-blue-600 text-white font-semibold rounded-md hover:bg-blue-700 flex items-center gap-2">
                    <Download className="w-5 h-5"/> Download Inspection CSV
                </button>
            ) : jobId.includes('manual') ? (
                <button onClick={onNavigateToQueue} className="px-4 py-2 bg-green-600 text-white font-semibold rounded-md hover:bg-green-700 flex items-center gap-2">
                    <CheckSquare className="w-5 h-5"/> View Draft in Approval Queue
                </button>
            ) : (
                // This can be a placeholder or a different action for scraper jobs
                 <button onClick={onNavigateToQueue} className="px-4 py-2 bg-green-600 text-white font-semibold rounded-md hover:bg-green-700 flex items-center gap-2">
                    <CheckSquare className="w-5 h-5"/> View Generated Drafts
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
      
      {jobData.project_name && renderResultsTable()}
    </div>
  );
};

export default JobStatusView;