import React, { useState, useEffect } from 'react';
import { Check, X, Loader2, GitPullRequest, Send, Save, AlertCircle } from 'lucide-react';
import apiClient from '../apiClient';

/**
 * NEW: A dedicated, "smart" component for the UNMATCHED row's action cell.
 * It handles its own search state and renders the clean, on-demand search UI.
 */
const UnmatchedActionCell = ({ product, dbCache, onLinkProduct, onSetAction }) => {
  const [searchQuery, setSearchQuery] = useState(product.nearest_match || product.parsed_name);
  const [isActive, setIsActive] = useState(false);

  // Filter the DB cache based on this row's unique search query
  const searchResults = (isActive && searchQuery.length > 2) ? 
    dbCache.filter(item => 
      item.name.toLowerCase().includes(searchQuery.toLowerCase())
    ).slice(0, 5) // Only show top 5 results
    : [];

  const handleSelectResult = (dbProduct) => {
    // Call the main component's handler to update the parent state
    onLinkProduct(product.slug, dbProduct);
    setSearchQuery(dbProduct.name); // Update local query
    setIsActive(false); // Close the dropdown
  };

  return (
    <div className="flex flex-col space-y-2">
      {/* 1. The Dynamic Search Box Component */}
      <div className="relative">
        <input 
          type="text" 
          value={searchQuery}
          placeholder="Type to search your database..."
          onChange={(e) => setSearchQuery(e.target.value)}
          onFocus={() => setIsActive(true)}
          onBlur={() => setTimeout(() => setIsActive(false), 200)} // Use timeout to allow click
          className={`w-full p-2 border rounded-md text-sm ${
            product.action === 'link' ? 'border-green-500 bg-green-50' : 'border-gray-300'
          }`}
        />
        {/* --- Autocomplete Results Dropdown --- */}
        {searchResults.length > 0 && (
          <div className="absolute z-20 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
            <ul>
              {searchResults.map(result => (
                <li 
                  key={result.id}
                  onClick={() => handleSelectResult(result)}
                  className="p-2 text-sm hover:bg-indigo-500 hover:text-white cursor-pointer"
                >
                  {result.name} <span className="text-xs opacity-70">(ID: {result.id})</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* 2. The Action Buttons */}
      <div className="flex space-x-2">
        <button 
          onClick={() => onSetAction(product.slug, 'ignore')}
          className={`px-3 py-2 text-xs font-medium rounded-md flex-1 ${
            product.action === 'ignore' ? 'bg-red-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-red-500 hover:text-white'
          }`}
        >
          Ignore
        </button>
      </div>
    </div>
  );
};


/**
 * Main View Component
 */
const PriceUpdateReviewView = ({ jobId, onJobStarted, onBack }) => {
  const [stagedProducts, setStagedProducts] = useState([]);
  const [localDbCache, setLocalDbCache] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!jobId) {
        setError("No import job ID provided.");
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

        const productsWithAction = stagedResponse.data.map(p => ({
          ...p,
          action: p.status === 'MATCHED' ? 'approve' : 'ignore',
          linked_db_id: null,
        }));
        setStagedProducts(productsWithAction);
        setLocalDbCache(dbResponse.data);

      } catch (err) {
        setError("Failed to load component data. The job may have expired or the DB is down.");
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [jobId]);

  // --- State Handlers ---

  const handleInputChange = (slug, field, value) => {
    setStagedProducts(prev =>
      prev.map(p => (p.slug === slug ? { ...p, [field]: value } : p))
    );
  };

  const handleActionChange = (slug, newAction) => {
    setStagedProducts(prev =>
      prev.map(p => (p.slug === slug ? { ...p, action: newAction } : p))
    );
  };
  
  const handleSelectSearchResult = (slug, selectedProductFromDb) => {
    setStagedProducts(prev =>
      prev.map(p => 
        p.slug === slug 
        ? { 
            ...p, 
            action: 'link', // Set the action to "link"
            parsed_name: selectedProductFromDb.name, // Update the main editable name
            linked_db_id: selectedProductFromDb.id,  // This is the CRITICAL ID
            slug: selectedProductFromDb.slug
          } 
        : p
      )
    );
  };

  const handleSaveChanges = async () => {
    setIsSaving(true);
    try {
        await apiClient.put(`/api/import/staged-data/${jobId}`, stagedProducts);
        alert("Your changes have been saved temporarily.");
    } catch (err) {
        alert("Failed to save changes.");
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
  
  const getStatusColor = (status, action) => {
    if (action === 'link') return 'bg-green-100 text-green-800';
    if (status === 'MATCHED') return 'bg-green-100 text-green-800';
    if (status === 'UNMATCHED') return 'bg-blue-100 text-blue-800';
    return 'bg-gray-100 text-gray-800';
  };

  // --- MAIN RENDER ---
  if (isLoading) return <div className="flex justify-center p-8"><Loader2 className="w-12 h-12 animate-spin text-indigo-600" /></div>;
  if (error) return (
    <div className="w-full max-w-2xl p-4 bg-red-50 text-red-700 border border-red-200 rounded-lg">
      <h3 className="font-bold flex items-center"><AlertCircle className="w-5 h-5 mr-2" /> Error Loading Data</h3>
      <p>{error}</p>
      <button onClick={onBack} className="mt-4 px-4 py-2 bg-gray-200 text-gray-800 rounded-md">Back to Tools</button>
    </div>
  );

  return (
    <div className="w-full max-w-screen-2xl mx-auto">
      {/* ... (Header JSX is unchanged) ... */}
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center">
            <GitPullRequest className="w-8 h-8 mr-3 text-indigo-600" />
            <div>
                <h1 className="text-3xl font-extrabold text-gray-800">Review Price Updates</h1>
                <p className="text-lg text-gray-600">Approve or Link changes before syncing. Found {stagedProducts.length} items.</p>
            </div>
        </div>
        <div>
            <button onClick={onBack} className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md mr-4">Back to Tools</button>
            <button onClick={handleSaveChanges} disabled={isSaving || isSyncing} className="inline-flex items-center px-4 py-2 bg-blue-600 text-white font-semibold rounded-md shadow-sm hover:bg-blue-700 disabled:bg-gray-400 mr-4">
                {isSaving ? <Loader2 className="w-5 h-5 mr-2 animate-spin"/> : <Save className="w-5 h-5 mr-2" />}
                Save Changes
            </button>
            <button onClick={handleSyncToWooCommerce} disabled={isSaving || isSaving} className="inline-flex items-center px-6 py-2 bg-green-600 text-white font-semibold rounded-md shadow-sm hover:bg-green-700 disabled:bg-gray-400">
                {isSyncing ? <Loader2 className="w-5 h-5 mr-2 animate-spin"/> : <Send className="w-5 h-5 mr-2" />}
                Sync Actions to WooCommerce
            </button>
        </div>
      </div>
      
      <div className="overflow-x-auto rounded-lg shadow-md border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase" style={{width: '220px'}}>Action</th>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase" style={{width: '30%'}}>Product Name / Link Target</th>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase">Status</th>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase">Sheet Product ID</th>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase">Sheet Shop ID</th>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase">Current DB Price</th>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase" style={{width: '150px'}}>Sheet Regular Price</th>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase" style={{width: '150px'}}>Sheet Sale Price</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {stagedProducts.map(product => (
              <tr key={product.slug} className={`${product.status === 'MATCHED' ? 'bg-white' : 'bg-blue-50'} relative`}>
                <td className="p-4">
                  {product.status === 'MATCHED' ? (
                    <label className="flex items-center space-x-2 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={product.action === 'approve'}
                        onChange={(e) => handleActionChange(product.slug, e.target.checked ? 'approve' : 'ignore')}
                        className="h-4 w-4 rounded border-gray-300 text-indigo-600"
                      />
                      <span className="text-sm font-medium text-green-700">Approve Update</span>
                    </label>
                  ) : (
                    <UnmatchedActionCell 
                      product={product} 
                      dbCache={localDbCache}
                      onSetAction={handleActionChange}
                      onLinkProduct={handleSelectSearchResult}
                    />
                  )}
                </td>
                <td className="p-4 text-sm text-gray-800">
                  {product.action === 'link' ? (
                      <div>
                        <span className="font-bold text-green-700">LINKED TO:</span>
                        <p className="text-gray-900">{product.parsed_name}</p>
                        <span className="text-xs text-gray-400 font-mono">(DB ID: {product.linked_db_id})</span>
                      </div>
                  ) : (
                    <input 
                      type="text" 
                      value={product.parsed_name} 
                      onChange={(e) => handleInputChange(product.slug, 'parsed_name', e.target.value)}
                      className="w-full p-2 border rounded-md"
                    />
                  )}
                </td>
                <td className="p-4">
                  <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(product.status, product.action)}`}>
                    {product.action === 'link' ? 'MANUAL LINK' : product.status}
                  </span>
                </td>
                <td className="p-4 text-sm text-gray-500 font-mono">{product.shopee_id || product.lazada_id || 'N/A'}</td>
                <td className="p-4 text-sm text-gray-500 font-mono">{product.shop_id || 'N/A'}</td>
                <td className="p-4 text-sm text-gray-500">{product.current_price || 'N/A'}</td>
                <td className="p-4">
                   <input 
                      type="number" 
                      value={product.new_regular_price || ''} 
                      onChange={(e) => handleInputChange(product.slug, 'new_regular_price', parseFloat(e.target.value))}
                      placeholder="N/A"
                      className="w-full p-2 border rounded-md"
                  />
                </td>
                <td className="p-4">
                   <input 
                      type="number" 
                      value={product.new_sale_price || ''} 
                      onChange={(e) => handleInputChange(product.slug, 'new_sale_price', parseFloat(e.target.value))}
                      placeholder="N/A"
                      className="w-full p-2 border rounded-md"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PriceUpdateReviewView;