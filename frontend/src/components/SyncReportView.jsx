import React, { useState, useEffect } from 'react';
import { Loader2, CheckCircle, XCircle, AlertTriangle, FileText, ArrowLeft } from 'lucide-react';
import apiClient from '../apiClient';

const SyncReportView = ({ jobId, onBack }) => {
  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchReport = async () => {
      if (!jobId) {
        setError("No Job ID provided.");
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      try {
        const response = await apiClient.get(`/api/audit/log/${jobId}`);
        setReport(response.data);
      } catch (err) {
        setError("Failed to fetch the audit report. It may have expired (logs are kept for 24 hours).");
        console.error("Error fetching audit report:", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchReport();
  }, [jobId]);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'Price Updated':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'Synced':
        return <CheckCircle className="w-5 h-5 text-blue-500" />;
      case 'Error':
        return <XCircle className="w-5 h-5 text-red-500" />;
      default:
        return <AlertTriangle className="w-5 h-5 text-gray-500" />;
    }
  };

  if (isLoading) {
    return <div className="flex justify-center items-center h-64"><Loader2 className="w-12 h-12 animate-spin text-indigo-600" /></div>;
  }

  if (error) {
    return (
      <div className="w-full max-w-2xl p-4 bg-red-50 text-red-700 border border-red-200 rounded-lg">
        <h3 className="font-bold flex items-center"><AlertTriangle className="w-5 h-5 mr-2" /> Error</h3>
        <p>{error}</p>
        <button onClick={onBack} className="mt-4 px-4 py-2 bg-gray-200 text-gray-800 rounded-md">Back to Job Status</button>
      </div>
    );
  }
  
  if (!report || report.length === 0) {
    return (
        <div className="w-full max-w-2xl text-center">
            <FileText className="w-12 h-12 mx-auto text-gray-400 mb-4" />
            <h2 className="text-xl font-semibold text-gray-700">No Sync Details Found</h2>
            <p className="text-gray-500 mt-2">The audit log for this job is empty or could not be found.</p>
            <button onClick={onBack} className="mt-6 px-4 py-2 bg-indigo-600 text-white rounded-md flex items-center mx-auto">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Job Status
            </button>
        </div>
    );
  }

  return (
    <div className="w-full max-w-5xl">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-800">Sync Audit Report</h1>
          <p className="text-lg text-gray-600 font-mono">Job ID: {jobId}</p>
        </div>
        <button onClick={onBack} className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300">
            Back to Job Status
        </button>
      </div>

      <div className="overflow-x-auto rounded-lg shadow-md border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase w-12">#</th>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase w-1/2">Product Name</th>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase">Status</th>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {report.map((item, index) => (
              <tr key={index}>
                <td className="p-4 text-sm text-gray-500 font-mono">{index + 1}</td>
                <td className="p-4 text-sm text-gray-800 font-medium">
                  {item.name}
                  <p className="text-xs text-gray-500 font-mono">WC ID: {item.wc_id}</p>
                </td>
                <td className="p-4 text-sm text-gray-700">
                  <span className="flex items-center">
                    {getStatusIcon(item.status)}
                    <span className="ml-2">{item.status}</span>
                  </span>
                </td>
                <td className="p-4 text-sm text-gray-600 font-mono">{item.details}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default SyncReportView;