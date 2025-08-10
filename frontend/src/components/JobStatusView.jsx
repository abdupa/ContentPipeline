import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Loader2, CheckCircle, XCircle, FileDown, Info } from 'lucide-react';

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

  const handleDownloadCsv = () => {
    if (!jobData || !jobData.results || jobData.results.length === 0) return;
    
    const now = new Date();
    const fileTimestamp = now.toLocaleString('sv').replace(/ /g, '_').replace(/:/g, '-');

    const results = jobData.results;
    const headers = Object.keys(results[0]);
    let csvContent = headers.join(',') + '\n';

    results.forEach(row => {
      const rowValues = headers.map(header => {
        let value = row[header] ? `"${row[header].toString().replace(/"/g, '""')}"` : '';
        return value;
      });
      csvContent += rowValues.join(',') + '\n';
    });

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `job_results_${fileTimestamp}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const renderResultsTable = () => {
    const hasResults = jobData && jobData.results && jobData.results.length > 0;
    
    if (!hasResults) {
      // *** THE FIX: Check job status before showing the message ***
      if (jobData && jobData.status === 'complete') {
        return (
          <div className="text-center py-8 text-gray-600 bg-gray-50 rounded-lg">
            <Info className="w-8 h-8 mx-auto mb-2 text-blue-500" />
            <p className="font-semibold">No new articles were processed.</p>
            <p className="text-sm">This can happen if all discovered articles were filtered by date or were already processed in a previous run.</p>
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
          <h2 className="text-2xl font-bold text-gray-800">{jobData.project_name || "Scraping Job Status"}</h2>
          <p className="text-sm text-gray-500 font-mono">ID: {jobId}</p>
        </div>
        <button onClick={onReset} className="px-4 py-2 bg-gray-200 text-gray-800 font-semibold rounded-md hover:bg-gray-300">Back to Projects</button>
      </div>

      {['processing', 'scraping', 'starting'].includes(jobData.status) ? (
         <div className="mb-6">
          <div className="flex justify-between items-center mb-1">
            <span className="text-lg font-semibold text-indigo-600 flex items-center"><Loader2 className="animate-spin mr-2" /> {jobData.status.charAt(0).toUpperCase() + jobData.status.slice(1)}...</span>
            <span className="text-lg font-semibold text-gray-700">{jobData.processed_urls} / {jobData.total_urls || '?'}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4">
            <div className="bg-indigo-600 h-4 rounded-full transition-all duration-500" style={{ width: `${progressPercent}%` }}></div>
          </div>
        </div>
      ) : null}

      {jobData.status === 'complete' && (
        <div className="mb-6 p-4 bg-green-50 text-green-700 rounded-lg flex items-center justify-between">
            <div className="flex items-center">
                <CheckCircle className="mr-3" />
                <span className="text-lg font-semibold">Job Complete! Processed {jobData.total_urls} articles and generated {jobData.results.length} new drafts.</span>
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
      
      {renderResultsTable()}
    </div>
  );
};

export default JobStatusView;
