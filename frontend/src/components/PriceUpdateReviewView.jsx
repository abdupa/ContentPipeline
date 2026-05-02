// frontend/src/components/PriceUpdateReviewView.jsx

import React, { useState, useEffect } from 'react';
import { Loader2, GitPullRequest, Send, Save, AlertCircle, Trash2 } from 'lucide-react';
import apiClient from '../apiClient';

const getMarketplaceId = (product) => product.shopee_id || product.lazada_id || null;

const getSourceLabel = (product) => {
  if (product.source) return product.source.charAt(0).toUpperCase() + product.source.slice(1);
  if (product.shopee_id) return 'Shopee';
  if (product.lazada_id) return 'Lazada';
  return 'Source';
};

const getSourceIdLabel = (product) => `${getSourceLabel(product)} ID`;

const getMatchLabel = (matchedBy) => ({
  marketplace_id: 'Marketplace ID',
  exact_name: 'Exact Name',
  manual_link: 'Manual Link',
  legacy_matched: 'Matched',
  unmatched: 'Unmatched'
}[matchedBy] || 'Unknown');

const normalizeText = (value) => String(value || '').trim().toLowerCase();

const getDbMarketplaceId = (dbProduct, source) => {
  if (!dbProduct) return null;
  const sourceKey = source || (dbProduct.shopee_id ? 'shopee' : dbProduct.lazada_id ? 'lazada' : null);
  if (sourceKey === 'shopee') {
    return dbProduct.shopee_id || dbProduct.linked_sources?.shopee?.product_id || null;
  }
  if (sourceKey === 'lazada') {
    return dbProduct.lazada_id || dbProduct.linked_sources?.lazada?.product_id || null;
  }
  return null;
};

const inferMatchedBy = (product, dbProduct) => {
  if (product.matched_by && product.matched_by !== 'unmatched') return product.matched_by;
  if (product.action === 'link' || product.linked_db_id) return 'manual_link';
  if (product.status !== 'MATCHED') return product.matched_by || 'unmatched';

  const sourceId = String(getMarketplaceId(product) || '');
  const dbSourceId = String(getDbMarketplaceId(dbProduct, product.source) || '');
  if (sourceId && dbSourceId && sourceId === dbSourceId) return 'marketplace_id';
  if (dbProduct && normalizeText(product.parsed_name) === normalizeText(dbProduct.name)) return 'exact_name';

  return 'legacy_matched';
};

const getReviewSourceLabel = (products) => {
  const sources = [...new Set(products.map(p => getSourceLabel(p)).filter(label => label !== 'Source'))];
  if (sources.length === 1) return sources[0];
  if (sources.length > 1) return sources.join(' + ');
  return 'Marketplace';
};

const getRowKey = (product, index) => {
  if (product.row_key) return product.row_key;
  const source = product.source || 'source';
  const marketplaceId = getMarketplaceId(product) || product.slug || 'row';
  const shopId = product.shop_id || 'shop';
  return `${source}-${marketplaceId}-${shopId}-${index}`;
};

const formatValue = (value) => {
  if (value === null || value === undefined || value === '') return 'N/A';
  return value;
};

const parsePriceInput = (value) => {
  if (value === '') return null;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
};

const denseInputClass = 'w-full min-w-0 rounded border border-gray-300 px-2 py-1.5 text-sm text-gray-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500';
const priceInputClass = `${denseInputClass} text-right`;

const StatusBadge = ({ status, action }) => {
  const label = action === 'link' ? 'MANUAL LINK' : status;
  const color = action === 'link' || status === 'MATCHED'
    ? 'bg-green-100 text-green-800'
    : status === 'UNMATCHED'
      ? 'bg-blue-100 text-blue-800'
      : 'bg-gray-100 text-gray-800';

  return (
    <span className={`inline-flex rounded-full px-2 py-1 text-[11px] font-semibold ${color}`}>
      {label}
    </span>
  );
};

const StockStatusBadge = ({ status }) => {
  if (!status) return null;

  const isOutOfStock = status === 'out_of_stock';
  const bgColor = isOutOfStock ? 'bg-red-100' : 'bg-green-100';
  const textColor = isOutOfStock ? 'text-red-800' : 'text-green-800';
  const text = isOutOfStock ? 'Out of Stock' : 'In Stock';

  return (
    <span className={`inline-flex rounded-full px-2 py-1 text-[11px] font-medium ${bgColor} ${textColor}`}>
      {text}
    </span>
  );
};

const MatchSourceBadge = ({ matchedBy }) => {
  const normalized = matchedBy || 'unmatched';
  const color = normalized === 'marketplace_id'
    ? 'bg-emerald-100 text-emerald-800'
    : normalized === 'exact_name'
      ? 'bg-amber-100 text-amber-800'
      : normalized === 'manual_link'
        ? 'bg-indigo-100 text-indigo-800'
        : normalized === 'legacy_matched'
          ? 'bg-slate-100 text-slate-700'
        : 'bg-gray-100 text-gray-700';

  return (
    <span className={`inline-flex rounded-full px-2 py-1 text-[11px] font-medium ${color}`}>
      {getMatchLabel(normalized)}
    </span>
  );
};

const DetailLine = ({ label, value, mono = false }) => (
  <div className="min-w-0">
    <dt className="text-[11px] font-semibold uppercase text-gray-500">{label}</dt>
    <dd className={`${mono ? 'font-mono break-all' : 'break-words'} text-sm text-gray-800`}>
      {formatValue(value)}
    </dd>
  </div>
);

const UnmatchedActionCell = ({ product, dbCache, onLinkProduct, onSetAction }) => {
  const [searchQuery, setSearchQuery] = useState(product.nearest_match || product.parsed_name);
  const [isActive, setIsActive] = useState(false);

  const searchResults = (isActive && searchQuery.length > 2)
    ? dbCache.filter(item =>
        item.name.toLowerCase().includes(searchQuery.toLowerCase())
      ).slice(0, 10)
    : [];

  const handleSelectResult = (dbProduct) => {
    onLinkProduct(product.row_key, dbProduct);
    setSearchQuery(dbProduct.name);
    setIsActive(false);
  };

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="relative">
        <input
          type="text"
          value={searchQuery}
          placeholder="Search database"
          onChange={(e) => setSearchQuery(e.target.value)}
          onFocus={() => setIsActive(true)}
          onBlur={() => setTimeout(() => setIsActive(false), 200)}
          className={`w-full min-w-0 rounded border px-2 py-1.5 text-sm ${
            product.action === 'link' ? 'border-green-500 bg-green-50' : 'border-gray-300'
          }`}
        />
        {searchResults.length > 0 && (
          <div className="absolute z-30 mt-1 max-h-60 w-full overflow-y-auto rounded-md border border-gray-300 bg-white shadow-lg">
            <ul>
              {searchResults.map(result => (
                <li
                  key={result.id}
                  onMouseDown={() => handleSelectResult(result)}
                  className="cursor-pointer p-2 text-sm hover:bg-indigo-500 hover:text-white"
                >
                  <span className="block break-words">{result.name}</span>
                  <span className="text-xs opacity-70">ID: {result.id}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <button
        onClick={() => onSetAction(product.row_key, 'ignore')}
        className={`w-full rounded-md px-3 py-1.5 text-xs font-medium ${
          product.action === 'ignore'
            ? 'bg-red-600 text-white'
            : 'bg-gray-200 text-gray-700 hover:bg-red-500 hover:text-white'
        }`}
      >
        Ignore
      </button>
    </div>
  );
};

const MatchedActionCell = ({ product, onSetAction, onUnlink }) => (
  <div className="flex min-w-0 flex-col gap-2">
    <label className="flex cursor-pointer items-center gap-2">
      <input
        type="checkbox"
        checked={product.action === 'approve'}
        onChange={(e) => onSetAction(product.row_key, e.target.checked ? 'approve' : 'ignore')}
        className="h-4 w-4 rounded border-gray-300 text-indigo-600"
      />
      <span className="text-sm font-medium text-green-700">Approve</span>
    </label>

    <button
      onClick={() => onUnlink(product)}
      className="flex w-full items-center justify-center rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-600 hover:bg-red-100"
    >
      <Trash2 className="mr-1 h-3 w-3" />
      Reset
    </button>
  </div>
);

const ProductActions = ({ product, dbCache, onSetAction, onLinkProduct, onUnlink }) => (
  product.status === 'MATCHED' ? (
    <MatchedActionCell product={product} onSetAction={onSetAction} onUnlink={onUnlink} />
  ) : (
    <UnmatchedActionCell
      product={product}
      dbCache={dbCache}
      onSetAction={onSetAction}
      onLinkProduct={onLinkProduct}
    />
  )
);

const PriceReviewCard = ({ product, index, dbCache, onSetAction, onLinkProduct, onUnlink, onInputChange }) => {
  const marketplaceId = getMarketplaceId(product);

  return (
    <article className={`rounded-lg border p-4 shadow-sm ${product.status === 'MATCHED' ? 'border-gray-200 bg-white' : 'border-blue-200 bg-blue-50'}`}>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-gray-500">#{index + 1}</span>
          <StatusBadge status={product.status} action={product.action} />
          <MatchSourceBadge matchedBy={product.matched_by} />
          <StockStatusBadge status={product.stock_status} />
        </div>
        <span className="shrink-0 rounded bg-gray-100 px-2 py-1 text-xs font-semibold text-gray-700">
          {getSourceLabel(product)}
        </span>
      </div>

      <div className="mb-4">
        <label className="mb-1 block text-[11px] font-semibold uppercase text-gray-500">
          Product Name / Link Target
        </label>
        {product.action === 'link' ? (
          <div className="rounded border border-green-200 bg-green-50 px-3 py-2">
            <span className="text-[11px] font-bold text-green-700">LINKED TO</span>
            <p className="break-words text-sm font-medium text-gray-900">{product.parsed_name}</p>
            <span className="font-mono text-xs text-gray-500">DB ID: {product.linked_db_id}</span>
          </div>
        ) : (
          <input
            type="text"
            value={product.parsed_name}
            onChange={(e) => onInputChange(product.row_key, 'parsed_name', e.target.value)}
            className={denseInputClass}
          />
        )}
      </div>

      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <DetailLine label="Match Source" value={getMatchLabel(product.matched_by)} />
        <DetailLine label={getSourceIdLabel(product)} value={marketplaceId} mono />
        <DetailLine label="Shop ID" value={product.shop_id} mono />
        <DetailLine label="Current DB Price" value={product.current_price} />
        <DetailLine label="Nearest Match" value={product.nearest_match} />
      </dl>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-[11px] font-semibold uppercase text-gray-500">Sheet Regular Price</span>
          <input
            type="number"
            value={product.new_regular_price ?? ''}
            onChange={(e) => onInputChange(product.row_key, 'new_regular_price', parsePriceInput(e.target.value))}
            placeholder="N/A"
            className={priceInputClass}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-[11px] font-semibold uppercase text-gray-500">Sheet Sale Price</span>
          <input
            type="number"
            value={product.new_sale_price ?? ''}
            onChange={(e) => onInputChange(product.row_key, 'new_sale_price', parsePriceInput(e.target.value))}
            placeholder="N/A"
            className={priceInputClass}
          />
        </label>
      </div>

      <div className="mt-4 border-t border-gray-200 pt-3">
        <ProductActions
          product={product}
          dbCache={dbCache}
          onSetAction={onSetAction}
          onLinkProduct={onLinkProduct}
          onUnlink={onUnlink}
        />
      </div>
    </article>
  );
};

const PriceUpdateReviewView = ({ jobId, onJobStarted, onBack }) => {
  const [stagedProducts, setStagedProducts] = useState([]);
  const [localDbCache, setLocalDbCache] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const reviewSourceLabel = getReviewSourceLabel(stagedProducts);

  const fetchData = async () => {
    if (!jobId) {
      setError('No import job ID provided.');
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const [stagedResponse, dbResponse] = await Promise.all([
        apiClient.get(`/api/import/staged-data/${jobId}`),
        apiClient.get('/api/products')
      ]);

      const dbById = new Map(dbResponse.data.map(item => [item.id, item]));
      const productsWithAction = stagedResponse.data.map((p, index) => {
        const targetDbId = p.linked_db_id || p.matched_db_id || null;
        const dbProduct = targetDbId ? dbById.get(targetDbId) : null;
        const product = {
          ...p,
          action: p.action || (p.status === 'MATCHED' ? 'approve' : 'ignore'),
          linked_db_id: p.linked_db_id || null,
        };
        return {
          ...product,
          matched_by: inferMatchedBy(product, dbProduct),
          row_key: getRowKey(product, index)
        };
      });
      setStagedProducts(productsWithAction);
      setLocalDbCache(dbResponse.data);
    } catch (err) {
      setError('Failed to load component data. The job may have expired or the DB is down.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [jobId]);

  const handleInputChange = (rowKey, field, value) => {
    setStagedProducts(prev =>
      prev.map(p => (p.row_key === rowKey ? { ...p, [field]: value } : p))
    );
  };

  const handleActionChange = (rowKey, newAction) => {
    setStagedProducts(prev =>
      prev.map(p => (p.row_key === rowKey ? { ...p, action: newAction } : p))
    );
  };

  const handleSelectSearchResult = (rowKey, selectedProductFromDb) => {
    setStagedProducts(prev =>
      prev.map(p =>
        p.row_key === rowKey
          ? {
              ...p,
              action: 'link',
              parsed_name: selectedProductFromDb.name,
              linked_db_id: selectedProductFromDb.id,
              slug: selectedProductFromDb.slug,
              matched_by: 'manual_link'
            }
          : p
      )
    );
  };

  const handleUnlink = async (product) => {
    const productId = product.matched_db_id || product.linked_db_id;
    if (!productId) {
      alert('Cannot reset this product because no WooCommerce product ID is linked.');
      return;
    }

    if (!window.confirm(`Are you sure you want to delete the price mapping for "${product.parsed_name}"?`)) {
      return;
    }
    try {
      await apiClient.post('/api/unlink-product', {
        product_id: productId
      });

      alert('Unlinked successfully. Reloading data...');
      fetchData();
    } catch (error) {
      console.error('Error:', error);
      const msg = error.response?.data?.detail || 'Failed to unlink.';
      alert(`Error: ${msg}`);
    }
  };

  const handleSaveChanges = async () => {
    setIsSaving(true);
    try {
      await apiClient.put(`/api/import/staged-data/${jobId}`, stagedProducts);
      alert('Your changes have been saved temporarily.');
    } catch (err) {
      alert('Failed to save changes.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleSyncToWooCommerce = async () => {
    const productsToSync = stagedProducts.filter(p => p.action !== 'ignore');
    if (productsToSync.length === 0) {
      alert("Please select an action (like 'Approve' or manually link a product) for at least one item.");
      return;
    }
    const linkedWithoutId = productsToSync.find(p => p.action === 'link' && !p.linked_db_id);
    if (linkedWithoutId) {
      alert(`Error: The product "${linkedWithoutId.parsed_name}" has an action set to 'Link' but no database item was selected.`);
      return;
    }
    if (window.confirm(`Are you sure you want to sync ${productsToSync.length} products?`)) {
      setIsSyncing(true);
      try {
        const response = await apiClient.post('/api/import/process-staged-data', {
          job_id: jobId,
          approved_products: productsToSync
        });
        onJobStarted(response.data.job_id, 'tools');
      } catch (err) {
        alert(`Failed to start the final sync task. ${err.response?.data?.detail || ''}`);
        setIsSyncing(false);
      }
    }
  };

  if (isLoading) {
    return <div className="flex justify-center p-6"><Loader2 className="h-10 w-10 animate-spin text-indigo-600" /></div>;
  }

  if (error) {
    return (
      <div className="w-full max-w-2xl rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
        <h3 className="flex items-center font-bold"><AlertCircle className="mr-2 h-5 w-5" /> Error Loading Data</h3>
        <p className="mt-2 text-sm">{error}</p>
        <button onClick={onBack} className="mt-4 rounded-md bg-gray-200 px-4 py-2 text-gray-800">Back to Tools</button>
      </div>
    );
  }

  return (
    <div className="w-full max-w-screen-2xl mx-auto">
      <div className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <GitPullRequest className="mt-1 h-7 w-7 shrink-0 text-indigo-600" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-extrabold text-gray-800 sm:text-3xl">Review {reviewSourceLabel} Price Updates</h1>
              <span className="rounded-full bg-indigo-100 px-2.5 py-1 text-xs font-semibold text-indigo-700">
                {reviewSourceLabel}
              </span>
            </div>
            <p className="text-sm text-gray-600 sm:text-base">Approve or link changes before syncing. Found {stagedProducts.length} items.</p>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 xl:flex xl:justify-end">
          <button onClick={onBack} className="rounded-md bg-gray-200 px-4 py-2 text-sm font-semibold text-gray-800">
            Back to Tools
          </button>
          <button
            onClick={handleSaveChanges}
            disabled={isSaving || isSyncing}
            className="inline-flex items-center justify-center rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:bg-gray-400"
          >
            {isSaving ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <Save className="mr-2 h-5 w-5" />}
            Save Changes
          </button>
          <button
            onClick={handleSyncToWooCommerce}
            disabled={isSaving || isSyncing}
            className="inline-flex items-center justify-center rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-green-700 disabled:bg-gray-400"
          >
            {isSyncing ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <Send className="mr-2 h-5 w-5" />}
            Sync to WooCommerce
          </button>
        </div>
      </div>

      <div className="space-y-3 lg:hidden">
        {stagedProducts.map((product, index) => (
          <PriceReviewCard
            key={product.row_key}
            product={product}
            index={index}
            dbCache={localDbCache}
            onSetAction={handleActionChange}
            onLinkProduct={handleSelectSearchResult}
            onUnlink={handleUnlink}
            onInputChange={handleInputChange}
          />
        ))}
      </div>

      <div className="hidden overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-md lg:block">
        <table className="min-w-[1180px] divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="w-12 px-3 py-3 text-left text-xs font-bold uppercase text-gray-600">#</th>
              <th className="w-[190px] px-3 py-3 text-left text-xs font-bold uppercase text-gray-600">Action</th>
              <th className="w-[320px] px-3 py-3 text-left text-xs font-bold uppercase text-gray-600">Product / Link Target</th>
              <th className="w-[120px] px-3 py-3 text-left text-xs font-bold uppercase text-gray-600">Status</th>
              <th className="w-[135px] px-3 py-3 text-left text-xs font-bold uppercase text-gray-600">Matched By</th>
              <th className="w-[110px] px-3 py-3 text-left text-xs font-bold uppercase text-gray-600">Stock</th>
              <th className="w-[190px] px-3 py-3 text-left text-xs font-bold uppercase text-gray-600">Product ID</th>
              <th className="w-[130px] px-3 py-3 text-left text-xs font-bold uppercase text-gray-600">Shop ID</th>
              <th className="w-[120px] px-3 py-3 text-right text-xs font-bold uppercase text-gray-600">Current</th>
              <th className="w-[135px] px-3 py-3 text-right text-xs font-bold uppercase text-gray-600">Regular</th>
              <th className="w-[135px] px-3 py-3 text-right text-xs font-bold uppercase text-gray-600">Sale</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {stagedProducts.map((product, index) => {
              const marketplaceId = getMarketplaceId(product);
              return (
                <tr key={product.row_key} className={product.status === 'MATCHED' ? 'bg-white' : 'bg-blue-50'}>
                  <td className="border-r border-gray-100 px-3 py-3 text-sm font-bold text-gray-500">{index + 1}</td>
                  <td className="px-3 py-3 align-top">
                    <ProductActions
                      product={product}
                      dbCache={localDbCache}
                      onSetAction={handleActionChange}
                      onLinkProduct={handleSelectSearchResult}
                      onUnlink={handleUnlink}
                    />
                  </td>
                  <td className="px-3 py-3 align-top text-sm text-gray-800">
                    {product.action === 'link' ? (
                      <div className="min-w-0">
                        <span className="text-[11px] font-bold text-green-700">LINKED TO</span>
                        <p className="break-words font-medium text-gray-900">{product.parsed_name}</p>
                        <span className="font-mono text-xs text-gray-400">DB ID: {product.linked_db_id}</span>
                      </div>
                    ) : (
                      <input
                        type="text"
                        value={product.parsed_name}
                        onChange={(e) => handleInputChange(product.row_key, 'parsed_name', e.target.value)}
                        className={denseInputClass}
                      />
                    )}
                  </td>
                  <td className="px-3 py-3 align-top"><StatusBadge status={product.status} action={product.action} /></td>
                  <td className="px-3 py-3 align-top"><MatchSourceBadge matchedBy={product.matched_by} /></td>
                  <td className="px-3 py-3 align-top"><StockStatusBadge status={product.stock_status} /></td>
                  <td className="px-3 py-3 align-top font-mono text-xs text-gray-600 break-all" title={marketplaceId || 'N/A'}>
                    <span className="mb-1 block text-[10px] font-sans font-semibold uppercase text-gray-400">{getSourceIdLabel(product)}</span>
                    {formatValue(marketplaceId)}
                  </td>
                  <td className="px-3 py-3 align-top font-mono text-xs text-gray-600 break-all" title={product.shop_id || 'N/A'}>{formatValue(product.shop_id)}</td>
                  <td className="px-3 py-3 align-top text-right text-sm text-gray-600">{formatValue(product.current_price)}</td>
                  <td className="px-3 py-3 align-top">
                    <input
                      type="number"
                      value={product.new_regular_price ?? ''}
                      onChange={(e) => handleInputChange(product.row_key, 'new_regular_price', parsePriceInput(e.target.value))}
                      placeholder="N/A"
                      className={priceInputClass}
                    />
                  </td>
                  <td className="px-3 py-3 align-top">
                    <input
                      type="number"
                      value={product.new_sale_price ?? ''}
                      onChange={(e) => handleInputChange(product.row_key, 'new_sale_price', parsePriceInput(e.target.value))}
                      placeholder="N/A"
                      className={priceInputClass}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PriceUpdateReviewView;
