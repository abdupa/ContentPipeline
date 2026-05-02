import React, { useEffect, useState } from 'react';
import { ArrowLeft, Loader2, PackageSearch, Save, WandSparkles } from 'lucide-react';
import apiClient from '../apiClient';

const STATUS_OPTIONS = [
  'candidate',
  'researching',
  'ready_for_scraper',
  'linked_existing',
  'rejected'
];

const TYPE_OPTIONS = [
  'unknown',
  'phone',
  'tablet',
  'accessory',
  'watch',
  'earbuds',
  'charger'
];

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

const Detail = ({ label, value, mono = false }) => (
  <div className="min-w-0">
    <dt className="text-[11px] font-bold uppercase text-gray-500">{label}</dt>
    <dd className={`${mono ? 'font-mono break-all' : 'break-words'} text-sm text-gray-800`}>{value || 'N/A'}</dd>
  </div>
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

const fieldClass = 'w-full min-w-0 rounded border border-gray-300 px-2 py-1.5 text-sm text-gray-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500';

const CandidateWooLinkSearch = ({ candidate, onLinked }) => {
  const [query, setQuery] = useState(candidate.linked_wc_name || candidate.canonical_name || candidate.parsed_name || '');
  const [results, setResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isActive, setIsActive] = useState(false);

  useEffect(() => {
    if (!isActive || query.trim().length < 3) {
      setResults([]);
      return;
    }

    let isCancelled = false;
    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const response = await apiClient.get('/api/products/search-live', {
          params: { q: query.trim(), limit: 8 }
        });
        if (!isCancelled) setResults(response.data || []);
      } catch (err) {
        if (!isCancelled) setResults([]);
      } finally {
        if (!isCancelled) setIsSearching(false);
      }
    }, 350);

    return () => {
      isCancelled = true;
      clearTimeout(timer);
    };
  }, [isActive, query]);

  const handleSelect = (product) => {
    setQuery(product.name);
    setIsActive(false);
    setResults([]);
    onLinked({
      linked_wc_id: product.id,
      linked_wc_name: product.name,
      linked_wc_slug: product.slug,
      status: 'linked_existing'
    });
  };

  return (
    <div className="relative min-w-[220px]">
      <input
        type="text"
        value={query}
        placeholder="Search Woo product"
        onChange={(event) => setQuery(event.target.value)}
        onFocus={() => setIsActive(true)}
        onBlur={() => setTimeout(() => setIsActive(false), 200)}
        className={fieldClass}
      />
      {candidate.linked_wc_id && (
        <p className="mt-1 font-mono text-xs text-gray-500">Linked WC ID: {candidate.linked_wc_id}</p>
      )}
      {isActive && (results.length > 0 || isSearching) && (
        <div className="absolute z-30 mt-1 max-h-56 w-full overflow-y-auto rounded-md border border-gray-300 bg-white shadow-lg">
          {isSearching && results.length === 0 ? (
            <div className="p-2 text-xs text-gray-500">Searching live WooCommerce...</div>
          ) : (
            <ul>
              {results.map(result => (
                <li
                  key={result.id}
                  onMouseDown={() => handleSelect(result)}
                  className="cursor-pointer p-2 text-sm hover:bg-indigo-500 hover:text-white"
                >
                  <span className="block break-words">{result.name}</span>
                  <span className="text-xs opacity-70">ID: {result.id}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

const ProductCandidateBucketView = ({ onBack }) => {
  const [candidates, setCandidates] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [savingIds, setSavingIds] = useState(new Set());

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

  const updateCandidateDraft = (candidateId, updates) => {
    setCandidates(prev => prev.map(candidate =>
      candidate.candidate_id === candidateId
        ? { ...candidate, ...updates }
        : candidate
    ));
  };

  const saveCandidate = async (candidate) => {
    setSavingIds(prev => new Set([...prev, candidate.candidate_id]));
    setError(null);
    try {
      const payload = {
        canonical_name: candidate.canonical_name || '',
        notes: candidate.notes || '',
        tags: candidate.tags || [],
        status: candidate.status || 'candidate',
        linked_wc_id: candidate.linked_wc_id || null,
        linked_wc_name: candidate.linked_wc_name || null,
        linked_wc_slug: candidate.linked_wc_slug || null
      };
      const response = await apiClient.patch(`/api/product-candidates/${candidate.candidate_id}`, payload);
      updateCandidateDraft(candidate.candidate_id, response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save candidate.');
    } finally {
      setSavingIds(prev => {
        const next = new Set(prev);
        next.delete(candidate.candidate_id);
        return next;
      });
    }
  };

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
        <div className="space-y-4">
          {candidates.map((candidate, index) => {
            const typeValue = candidate.tags?.[0] || 'unknown';
            const isSaving = savingIds.has(candidate.candidate_id);

            return (
              <article key={candidate.candidate_id} className="rounded-lg border border-gray-200 bg-white p-4 shadow-md">
                <div className="mb-4 flex flex-col gap-3 border-b border-gray-100 pb-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <span className="rounded bg-gray-100 px-2 py-1 text-xs font-bold text-gray-600">#{index + 1}</span>
                      <CandidateStatusBadge status={candidate.status} />
                      <AffiliateBadge diagnostics={candidate.affiliate_diagnostics} />
                    </div>
                    <h2 className="break-words text-base font-bold text-gray-900">{candidate.canonical_name || candidate.parsed_name}</h2>
                    <p className="mt-1 break-words text-sm text-gray-500">{candidate.parsed_name}</p>
                  </div>
                  <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4 lg:min-w-[520px]">
                    <Detail label="Source" value={sourceLabel(candidate.source)} />
                    <Detail label="Product ID" value={candidate.source_product_id} mono />
                    <Detail label="Regular" value={formatPrice(candidate.new_regular_price)} />
                    <Detail label="Sale" value={formatPrice(candidate.new_sale_price)} />
                  </dl>
                </div>

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_0.9fr]">
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <label className="block">
                      <span className="mb-1 block text-[11px] font-bold uppercase text-gray-500">Canonical Name</span>
                      <input
                        type="text"
                        value={candidate.canonical_name || ''}
                        onChange={(event) => updateCandidateDraft(candidate.candidate_id, { canonical_name: event.target.value })}
                        className={fieldClass}
                      />
                    </label>

                    <label className="block">
                      <span className="mb-1 block text-[11px] font-bold uppercase text-gray-500">Status</span>
                      <select
                        value={candidate.status || 'candidate'}
                        onChange={(event) => updateCandidateDraft(candidate.candidate_id, { status: event.target.value })}
                        className={fieldClass}
                      >
                        {STATUS_OPTIONS.map(status => (
                          <option key={status} value={status}>{status}</option>
                        ))}
                      </select>
                    </label>

                    <label className="block">
                      <span className="mb-1 block text-[11px] font-bold uppercase text-gray-500">Type</span>
                      <select
                        value={typeValue}
                        onChange={(event) => updateCandidateDraft(candidate.candidate_id, { tags: [event.target.value] })}
                        className={fieldClass}
                      >
                        {TYPE_OPTIONS.map(type => (
                          <option key={type} value={type}>{type}</option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <div>
                    <span className="mb-1 block text-[11px] font-bold uppercase text-gray-500">Link Existing Woo Product</span>
                    <CandidateWooLinkSearch
                      candidate={candidate}
                      onLinked={(updates) => updateCandidateDraft(candidate.candidate_id, updates)}
                    />
                  </div>

                  <label className="block lg:col-span-2">
                    <span className="mb-1 block text-[11px] font-bold uppercase text-gray-500">Notes</span>
                    <textarea
                      value={candidate.notes || ''}
                      onChange={(event) => updateCandidateDraft(candidate.candidate_id, { notes: event.target.value })}
                      rows={3}
                      className={fieldClass}
                    />
                  </label>
                </div>

                <div className="mt-4 flex flex-col gap-3 border-t border-gray-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0 font-mono text-xs text-gray-500">
                    Updated: {candidate.updated_at || candidate.created_at}
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <button
                      type="button"
                      disabled
                      title="Future module: send candidate to phone/spec scraper after review."
                      className="inline-flex items-center rounded-md bg-gray-100 px-3 py-1.5 text-xs font-semibold text-gray-500"
                    >
                      <WandSparkles className="mr-1.5 h-3.5 w-3.5" />
                      Scrape Later
                    </button>
                    <button
                      type="button"
                      onClick={() => saveCandidate(candidate)}
                      disabled={isSaving}
                      className="inline-flex items-center rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:bg-gray-400"
                    >
                      {isSaving ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Save className="mr-1.5 h-3.5 w-3.5" />}
                      Save
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ProductCandidateBucketView;
