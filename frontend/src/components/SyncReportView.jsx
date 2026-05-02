import React, { useState, useEffect } from 'react';
import { Loader2, CheckCircle, XCircle, AlertTriangle, FileText, ArrowLeft } from 'lucide-react';
import apiClient from '../apiClient';

const formatPrice = (value) => {
  if (value === null || value === undefined || value === '') return 'N/A';
  const parsed = Number(value);
  if (Number.isNaN(parsed)) return String(value);
  return `₱${parsed.toLocaleString('en-PH', {
    minimumFractionDigits: parsed % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2
  })}`;
};

const getPriceDelta = (before, after) => {
  const beforeNum = Number(before);
  const afterNum = Number(after);
  if (Number.isNaN(beforeNum) || Number.isNaN(afterNum)) return null;
  return afterNum - beforeNum;
};

const PriceChange = ({ before, after }) => {
  const delta = getPriceDelta(before, after);
  const deltaClass = delta === null || delta === 0
    ? 'text-gray-500'
    : delta > 0
      ? 'text-red-600'
      : 'text-green-700';
  const deltaLabel = delta === null
    ? null
    : `${delta > 0 ? '+' : ''}${formatPrice(delta)}`;

  return (
    <div className="min-w-[150px]">
      <div className="flex flex-wrap items-center gap-1.5 text-sm">
        <span className="font-medium text-gray-500">{formatPrice(before)}</span>
        <span className="text-gray-400">→</span>
        <span className="font-semibold text-gray-900">{formatPrice(after)}</span>
      </div>
      {deltaLabel && (
        <div className={`mt-1 text-xs font-semibold ${deltaClass}`}>
          {delta === 0 ? 'No price change' : deltaLabel}
        </div>
      )}
    </div>
  );
};

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
      <div className="w-full max-w-2xl rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
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
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-800">Sync Audit Report</h1>
          <p className="break-all font-mono text-sm sm:text-base text-gray-600">Job ID: {jobId}</p>
        </div>
        <button onClick={onBack} className="w-full sm:w-auto px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300">
            Back to Job Status
        </button>
      </div>

      <div className="space-y-3 md:hidden">
        {report.map((item, index) => (
          <article key={index} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-start justify-between gap-3">
              <span className="text-xs font-bold text-gray-500">#{index + 1}</span>
              <span className="flex items-center rounded-full bg-gray-50 px-2 py-1 text-xs font-semibold text-gray-700">
                {getStatusIcon(item.status)}
                <span className="ml-2">{item.status}</span>
              </span>
            </div>
            <h2 className="break-words text-sm font-semibold text-gray-900">{item.name}</h2>
            <p className="mt-1 break-all font-mono text-xs text-gray-500">WC ID: {item.wc_id}</p>
            <div className="mt-3 rounded-md bg-gray-50 p-3">
              <p className="mb-1 text-[11px] font-bold uppercase text-gray-500">Price Change</p>
              <PriceChange before={item.price_before} after={item.price_after} />
            </div>
            <p className="mt-3 whitespace-pre-wrap break-words text-sm text-gray-600">{item.details}</p>
          </article>
        ))}
      </div>

      <div className="hidden overflow-x-auto rounded-lg shadow-md border border-gray-200 bg-white md:block">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase w-12">#</th>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase">Product Name</th>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase">Status</th>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase">Price Change</th>
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
                <td className="p-4 text-sm text-gray-700">
                  <PriceChange before={item.price_before} after={item.price_after} />
                </td>
                <td className="p-4 text-sm text-gray-600 break-words">{item.details}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default SyncReportView;
