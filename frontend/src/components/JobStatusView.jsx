import React, { useState, useEffect, useRef } from 'react';
import { Loader2, CheckCircle, XCircle, FileDown, Info, CheckSquare, Download, GitPullRequest } from 'lucide-react';
import apiClient from '../apiClient';

const JobStatusView = ({ jobId, onReset, onNavigateToQueue, onNavigateToReview }) => {
  const [jobData, setJobData] = useState(null);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    const fetchStatus = async () => {
      if (!jobId) return;
      try {
        const response = await apiClient.get(`/api/jobs/status/${jobId}`);
        setJobData(response.data);
        if (response.data.status === 'complete' || response.data.status === 'failed') {
          clearInterval(intervalRef.current);
        }
      } catch (err) {
        setError('Failed to fetch job status.');
        console.error("Error fetching job status:", err.response || err); // Detailed Log
        clearInterval(intervalRef.current);
      }
    };
    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 3000);
    return () => clearInterval(intervalRef.current);
  }, [jobId]);

  const handleDownloadCsv = () => {
    window.open(`${apiClient.defaults.baseURL}/api/tools/download-inspection-result/${jobId}`);
  };

  const handleBack = () => {
    onReset(localStorage.getItem('jobOriginView') || 'projects');
  };

  if (!jobData) return <div className="flex justify-center p-8"><Loader2 className="animate-spin" /> Loading job status...</div>;

  return (
    <div className="bg-white p-8 rounded-lg shadow-xl w-full max-w-5xl border border-gray-200">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">{jobData.project_name || "Job Status"}</h2>
          <p className="text-sm text-gray-500 font-mono">ID: {jobId}</p>
        </div>
        <button onClick={handleBack} className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md">Back</button>
      </div>

      {['processing', 'discovering', 'scraping', 'starting'].includes(jobData.status) && (
         <div className="mb-6">
          <div className="flex justify-between items-center mb-1">
            <span className="text-lg font-semibold text-indigo-600 flex items-center"><Loader2 className="animate-spin mr-2" /> {jobData.status.charAt(0).toUpperCase() + jobData.status.slice(1)}...</span>
          </div>
         </div>
      )}

      {jobData.status === 'complete' && (
        <div className="mb-6 p-4 bg-green-50 text-green-700 rounded-lg flex items-center justify-between">
            <div className="flex items-center">
                <CheckCircle className="mr-3" />
                <span className="text-lg font-semibold">
                  {/* This message now handles all job types */}
                  {jobId.includes('import')
                    ? "Import complete. Products are staged for review."
                    : jobId.includes('inspect')
                      ? "Site inspection complete."
                      : `Job Complete!`
                  }
                </span>
            </div>
            
            {/* This logic now correctly shows the button for each job type */}
            {jobId.includes('import') ? (
                <button onClick={() => onNavigateToReview(jobId)} className="px-4 py-2 bg-purple-600 text-white font-semibold rounded-md hover:bg-purple-700 flex items-center gap-2">
                    <GitPullRequest className="w-5 h-5"/> Review Staged Updates
                </button>
            ) : jobId.includes('inspect') ? (
                <button onClick={handleDownloadCsv} className="px-4 py-2 bg-blue-600 text-white font-semibold rounded-md hover:bg-blue-700 flex items-center gap-2">
                    <Download className="w-5 h-5"/> Download Inspection CSV
                </button>
            ) : (
                <button onClick={onNavigateToQueue} className="px-4 py-2 bg-green-600 text-white font-semibold rounded-md hover:bg-green-700 flex items-center gap-2">
                    <CheckSquare className="w-5 h-5"/> View Drafts in Approval Queue
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
    </div>
  );
};

export default JobStatusView;