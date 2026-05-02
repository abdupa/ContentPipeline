import React, { useEffect, useState } from 'react';
import { ArrowLeft, Loader2, PackageSearch, WandSparkles } from 'lucide-react';
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

const sourceLabel = (source) => source ? source.charAt(0).toUpperCase() + source.slice(1) : 'Source';

const CandidateStatusBadge = ({ status }) => (
  <span className="inline-flex rounded-full bg-indigo-100 px-2 py-1 text-xs font-semibold text-indigo-700">
    {status || 'candidate'}
  </span>
);

const AffiliateBadge = ({ diagnostics }) => {
  const label = diagnostics?.label || 'Not Checked';
  const status = diagnostics?.status || 'unknown';
  const color = status === 'valid'
    ? 'bg-emerald-100 text-emerald-800'
    : status === 'missing_config' || status === 'fallback'
      ? 'bg-amber-100 text-amber-800'
      : status === 'parse_failed' || status === 'missing_link'
        ? 'bg-red-100 text-red-800'
        : 'bg-gray-100 text-gray-700';

  return (
    <span title={diagnostics?.detail || label} className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${color}`}>
      {label}
    </span>
  );
};

const ProductCandidateBucketView = ({ onBack }) => {
  const [candidates, setCandidates] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchCandidates = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await apiClient.get('/api/product-candidates');
        setCandidates(response.data || []);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load product candidates.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchCandidates();
  }, []);

  if (isLoading) {
    return <div className="flex justify-center p-6"><Loader2 className="h-10 w-10 animate-spin text-indigo-600" /></div>;
  }

  return (
    <div className="w-full max-w-screen-xl">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <PackageSearch className="mt-1 h-7 w-7 shrink-0 text-indigo-600" />
          <div>
            <h1 className="text-2xl font-extrabold text-gray-800 sm:text-3xl">Product Candidate Bucket</h1>
            <p className="text-sm text-gray-600 sm:text-base">Unmatched marketplace products saved for research or product creation.</p>
          </div>
        </div>
        <button onClick={onBack} className="inline-flex w-full items-center justify-center rounded-md bg-gray-200 px-4 py-2 text-sm font-semibold text-gray-800 sm:w-auto">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Tools
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {candidates.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-white p-8 text-center text-gray-500">
          No product candidates yet.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-md">
          <table className="min-w-[1050px] divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase text-gray-600">Status</th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase text-gray-600">Product</th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase text-gray-600">Source</th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase text-gray-600">Product ID</th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase text-gray-600">Price</th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase text-gray-600">Affiliate</th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase text-gray-600">Nearest Match</th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase text-gray-600">Future Scrape</th>
                <th className="px-4 py-3 text-left text-xs font-bold uppercase text-gray-600">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {candidates.map(candidate => (
                <tr key={candidate.candidate_id}>
                  <td className="px-4 py-3 align-top"><CandidateStatusBadge status={candidate.status} /></td>
                  <td className="px-4 py-3 align-top">
                    <p className="break-words text-sm font-semibold text-gray-900">{candidate.canonical_name || candidate.parsed_name}</p>
                    <p className="mt-1 break-words text-xs text-gray-500">{candidate.parsed_name}</p>
                  </td>
                  <td className="px-4 py-3 align-top text-sm text-gray-700">{sourceLabel(candidate.source)}</td>
                  <td className="px-4 py-3 align-top font-mono text-xs text-gray-600 break-all">{candidate.source_product_id || 'N/A'}</td>
                  <td className="px-4 py-3 align-top text-sm text-gray-700">
                    <p>Regular: {formatPrice(candidate.new_regular_price)}</p>
                    <p>Sale: {formatPrice(candidate.new_sale_price)}</p>
                  </td>
                  <td className="px-4 py-3 align-top">
                    <AffiliateBadge diagnostics={candidate.affiliate_diagnostics} />
                  </td>
                  <td className="px-4 py-3 align-top text-sm text-gray-600">{candidate.nearest_match || 'N/A'}</td>
                  <td className="px-4 py-3 align-top">
                    <button
                      type="button"
                      disabled
                      title="Future module: send candidate to phone/spec scraper after review."
                      className="inline-flex items-center rounded-md bg-gray-100 px-3 py-1.5 text-xs font-semibold text-gray-500"
                    >
                      <WandSparkles className="mr-1.5 h-3.5 w-3.5" />
                      Scrape Later
                    </button>
                  </td>
                  <td className="px-4 py-3 align-top font-mono text-xs text-gray-500">{candidate.updated_at || candidate.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default ProductCandidateBucketView;
