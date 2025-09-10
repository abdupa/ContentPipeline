import React, { useState, useEffect } from 'react';
import { Check, X, Loader2, GitPullRequest, Send, Save, AlertCircle } from 'lucide-react';
import apiClient from '../apiClient';

/**
 * This is the new, "smart" action cell for our UNMATCHED products.
 * It combines the backend's best guess with a fully dynamic client-side search.
 */
const UnmatchedActionCell = ({ product, dbCache, onActionChange, onLinkProduct, onSearchChange }) => {
  
  // Filter the DB cache based on this row's unique search query
  const searchResults = (product.searchQuery && product.searchQuery.length > 2) ? 
    dbCache.filter(item => 
      item.name.toLowerCase().includes(product.searchQuery.toLowerCase())
    ).slice(0, 5) // Only show top 5 results
    : [];

  const handleSelectResult = (dbProduct) => {
    // This calls the main component's handler to update the state for this row
    onLinkProduct(product.slug, dbProduct);
  };

  return (
    <div className="flex flex-col space-y-2">
      {/* 1. The Dynamic Search Box Component */}
      <div className="relative">
        <input 
          type="text" 
          value={product.searchQuery}
          placeholder="Type to search your database..."
          onChange={(e) => onSearchChange(product.slug, e.target.value)}
          className={`w-full p-2 border rounded-md text-sm ${
            product.action === 'link' ? 'border-green-500 bg-green-50' : 'border-gray-300'
          }`}
        />
        {/* --- Autocomplete Results Dropdown --- */}
        {searchResults.length > 0 && product.action !== 'link' && (
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
          onClick={() => onActionChange(product.slug, 'ignore')}
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
  const [localDbCache, setLocalDbCache] = useState([]); // <-- NEW: Holds our entire product DB for searching
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  // --- NEW: Upgraded useEffect to fetch BOTH data sources ---
  useEffect(() => {
    const fetchData = async () => {
      if (!jobId) {
        setError("No import job ID provided.");
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setError(null); // Clear previous errors
      try {
        // Make two API calls in parallel
        const [stagedResponse, dbResponse] = await Promise.all([
          apiClient.get(`/api/import/staged-data/${jobId}`), // Call 1: Get products to review
          apiClient.get('/api/products')                    // Call 2: Get entire DB for linking
        ]);
        console.log("DATA RECEIVED FROM API:", stagedResponse.data);

        // Set the state for our staged products (with default actions & search query)
        const productsWithAction = stagedResponse.data.map(p => ({
          ...p,
          action: p.status === 'MATCHED' ? 'approve' : 'ignore',
          searchQuery: p.nearest_match || p.parsed_name, // Pre-fill search with "best guess" or parsed name
          linked_db_id: null, // This will store the WC ID we link to
        }));
        console.log("DATA SET TO REACT STATE:", productsWithAction);
        setStagedProducts(productsWithAction);

        // Set the state for our new searchable DB cache
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

  // --- NEW: Set of state handlers for our dynamic UI ---

  // Handles simple field updates (like the name or price inputs)
  const handleInputChange = (slug, field, value) => {
    setStagedProducts(prev =>
      prev.map(p => (p.slug === slug ? { ...p, [field]: value } : p))
    );
  };

  // Handles setting a simple action (Approve checkbox toggle, Ignore button)
  const handleActionChange = (slug, newAction) => {
    setStagedProducts(prev =>
      prev.map(p => (p.slug === slug ? { ...p, action: newAction } : p))
    );
  };
  
  // Handles the user typing in any search box
  const handleSearchQueryChange = (slug, newQuery) => {
    setStagedProducts(prev =>
      prev.map(p => 
        p.slug === slug 
        ? { 
            ...p, 
            searchQuery: newQuery,
            action: 'ignore',     // Reset action to 'ignore' while they are searching
            linked_db_id: null    // Clear any previous link
          } 
        : p
      )
    );
  };

  // Handles when the user CLICKS a product from the search results dropdown
  const handleSelectSearchResult = (slug, selectedProductFromDb) => {
    setStagedProducts(prev =>
      prev.map(p => 
        p.slug === slug 
        ? { 
            ...p, 
            action: 'link', // Set the action to "link"
            searchQuery: selectedProductFromDb.name, // Set search box text to the "truth" name
            parsed_name: selectedProductFromDb.name, // ALSO update the main editable name
            linked_db_id: selectedProductFromDb.id,  // This is the CRITICAL ID to pass to the backend
            slug: selectedProductFromDb.slug       // Update the slug to match the DB truth
          } 
        : p
      )
    );
  };

  // Save changes does not change, just saves the current state to Redis
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

  // --- NEW: Upgraded Sync function ---
  const handleSyncToWooCommerce = async () => {
    // Filter for any product where the action is NOT "ignore"
    const productsToSync = stagedProducts.filter(p => p.action !== 'ignore');

    if (productsToSync.length === 0) {
      alert("Please select an action (like 'Approve' or manually link a product) for at least one item.");
      return;
    }
    
    // Final check for any item that is set to 'link' but has no ID (meaning user typed but didn't select)
    const linkedWithoutId = productsToSync.find(p => p.action === 'link' && !p.linked_db_id);
    if (linkedWithoutId) {
        alert(`Error: The product "${linkedWithoutId.parsed_name}" has an action set to 'Link' but no database item was selected. Please select a product from the search results or set it to 'Ignore'.`);
        return;
    }

    if (window.confirm(`Are you sure you want to sync ${productsToSync.length} products?`)) {
      setIsSyncing(true);
      try {
        // Send the complete product list, now with all our new action data
        const response = await apiClient.post('/api/import/process-staged-data', {
          job_id: jobId,
          approved_products: productsToSync // This payload now contains "action", "linked_db_id", etc.
        });
        onJobStarted(response.data.job_id, 'tools'); 
      } catch (err) {
        alert(`Failed to start the final sync task. ${err.response?.data?.detail || ''}`);
        setIsSyncing(false);
      }
    }
  };
  
  const getStatusColor = (status, action) => {
    if (action === 'link') return 'bg-green-100 text-green-800'; // Linked is a type of "Matched"
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
    <div className="w-full max-w-screen-2xl mx-auto"> {/* <-- Made wider */}
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
            <button onClick={handleSyncToWooCommerce} disabled={isSyncing || isSaving} className="inline-flex items-center px-6 py-2 bg-green-600 text-white font-semibold rounded-md shadow-sm hover:bg-green-700 disabled:bg-gray-400">
                {isSyncing ? <Loader2 className="w-5 h-5 mr-2 animate-spin"/> : <Send className="w-5 h-5 mr-2" />}
                Sync Actions to WooCommerce
            </button>
        </div>
      </div>
      
      {/* --- NEW, FINAL TABLE STRUCTURE --- */}
      <div className="overflow-x-auto rounded-lg shadow-md border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-4 text-left text-xs font-bold text-gray-600 uppercase" style={{width: '200px'}}>Action</th>
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
            {stagedProducts.map(product => {
              // Get the "truth" product from our cache if one is linked
              const linkedProduct = (product.action === 'link' && product.linked_db_id) 
                ? localDbCache.find(p => p.id === product.linked_db_id)
                : null;

              return (
                <tr key={product.slug} className={product.status === 'MATCHED' ? 'bg-white' : 'bg-blue-50'}>
                  
                  {/* === ACTION CELL === */}
                  <td className="p-4">
                    {product.status === 'MATCHED' ? (
                      <label className="flex items-center space-x-2 cursor-pointer">
                        <input 
                          type="checkbox" 
                          checked={product.action === 'approve'}
                          onChange={(e) => handleActionChange(product.slug, e.target.checked ? 'approve' : 'ignore')}
                          className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="text-sm font-medium text-green-700">Approve Update</span>
                      </label>
                    ) : (
                      <UnmatchedActionCell 
                        product={product} 
                        dbCache={localDbCache}
                        onActionChange={handleActionChange}
                        onLinkProduct={handleSelectSearchResult}
                        onSearchChange={handleSearchQueryChange}
                      />
                    )}
                  </td>
                  
                  {/* === DYNAMIC NAME / SEARCH CELL === */}
                  <td className="p-4 text-sm text-gray-800">
                    {product.action === 'link' && linkedProduct ? (
                        <div>
                          <span className="font-bold text-green-700">LINKED TO:</span>
                          <p className="text-gray-900">{linkedProduct.name}</p>
                          <span className="text-xs text-gray-400 font-mono">(DB ID: {linkedProduct.id})</span>
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
                  
                  {/* === OTHER DATA CELLS === */}
                  <td className="p-4">
                    <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(product.status, product.action)}`}>
                      {product.action === 'link' ? 'MANUAL LINK' : product.status}
                    </span>
                  </td>
                  <td className="p-4 text-sm text-gray-500 font-mono">{product.shopee_id || product.lazada_id || 'N/A'}</td>
                  <td className="p-4 text-sm text-gray-500 font-mono">{product.shop_id || 'N/A'}</td>
                  <td className="p-4 text-sm text-gray-500">{product.current_price || 'N/A'}</td>
                  <td className="p-4 text-sm font-semibold text-gray-900">
                     <input 
                        type="number" 
                        value={product.new_regular_price || ''} 
                        onChange={(e) => handleInputChange(product.slug, 'new_regular_price', parseFloat(e.target.value))}
                        placeholder="Regular Price"
                        className="w-full p-2 border rounded-md"
                    />
                  </td>

                  {/* === NEW: Cell for Sheet Sale Price === */}
                  <td className="p-4 text-sm font-semibold text-gray-900">
                     <input 
                        type="number" 
                        value={product.new_sale_price || ''} 
                        onChange={(e) => handleInputChange(product.slug, 'new_sale_price', parseFloat(e.target.value))}
                        placeholder="Sale Price"
                        className="w-full p-2 border rounded-md"
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