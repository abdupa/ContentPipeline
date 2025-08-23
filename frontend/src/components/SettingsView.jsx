import React, { useState, useEffect } from 'react';
import { Settings, CheckCircle, XCircle, Globe, Loader2, Database, Download } from 'lucide-react';
import apiClient from '../apiClient';

const SettingsView = () => {
  const [gscSites, setGscSites] = useState([]);
  const [activeSite, setActiveSite] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState(null);
  const [saveStatus, setSaveStatus] = useState('');
  const [backupMessage, setBackupMessage] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('status') === 'success') {
      setConnectionStatus('success');
      window.history.replaceState(null, '', window.location.pathname);
    } else if (params.get('status') === 'error') {
      setConnectionStatus('error');
      window.history.replaceState(null, '', window.location.pathname);
    }

    const fetchInitialData = async () => {
      setIsLoading(true);
      try {
        const [sitesResponse, activeSiteResponse] = await Promise.all([
          apiClient.get('/api/gsc/sites'),
          apiClient.get('/api/gsc/active-site')
        ]);
        
        const gscSitesData = sitesResponse.data;
        let currentActiveSite = activeSiteResponse.data.site_url;

        setGscSites(gscSitesData);
        
        if (gscSitesData.length > 0) {
          setConnectionStatus('success');
          // --- THE FIX: If no site is currently active, save the first one as the default ---
          if (!currentActiveSite && gscSitesData[0]?.siteUrl) {
            currentActiveSite = gscSitesData[0].siteUrl;
            setActiveSite(currentActiveSite);
            // Silently save this default selection to the backend
            await apiClient.post('/api/gsc/active-site', { site_url: currentActiveSite });
          } else {
            setActiveSite(currentActiveSite);
          }
        }
      } catch (err) {
        if (err.response?.status !== 401) {
          setError('Failed to fetch Google Search Console data.');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchInitialData();
  }, []);

  const handleFetchInsightsNow = async () => {
    setBackupMessage(''); // Clear any previous messages
    try {
      const response = await apiClient.post('/api/gsc/fetch-insights-now');
      alert(response.data.message);
    } catch (err) {
      alert('Error: Failed to queue the GSC insights fetch task.');
    }
  };

  const handleSyncNow = async () => {
    setBackupMessage(''); // Reuse the backup message state for feedback
    try {
      const response = await apiClient.post('/api/sync/wordpress');
      alert(response.data.message);
    } catch (err) {
      alert('Error: Failed to queue the WordPress sync task.');
    }
  };
  
  const handleFetchNow = async () => {
    setBackupMessage(''); // Clear any previous messages
    try {
      const response = await apiClient.post('/api/gsc/fetch-now');
      alert(response.data.message); // Simple alert for confirmation
    } catch (err) {
      alert('Error: Failed to queue the GSC fetch task.');
    }
  };
  
  const handleConnect = () => {
    window.location.href = `${apiClient.defaults.baseURL}/api/auth/google`;
  };

  const handleSiteSelectionChange = async (e) => {
    const newSiteUrl = e.target.value;
    setActiveSite(newSiteUrl);
    setSaveStatus('Saving...');
    try {
      await apiClient.post('/api/gsc/active-site', { site_url: newSiteUrl });
      setSaveStatus('Saved!');
      setTimeout(() => setSaveStatus(''), 2000);
    } catch (err) {
      setSaveStatus('Failed to save.');
    }
  };

  const handleCreateBackup = async () => {
    setBackupMessage('Starting backup...');
    try {
      const response = await apiClient.post('/api/database/backup');
      setBackupMessage(response.data.message);
    } catch (err) {
      setBackupMessage('Error: Failed to start backup.');
    }
  };
  
  const handleDownloadBackup = () => {
    window.open(`${apiClient.defaults.baseURL}/api/database/backup/download`, '_blank');
  };

  const renderConnectionStatus = () => {
    if (connectionStatus === 'success') {
      return (
        <div className="mt-4 p-3 bg-green-50 text-green-700 rounded-lg flex items-center">
          <CheckCircle className="w-5 h-5 mr-2" />
          Successfully connected to Google Search Console.
        </div>
      );
    }
    if (connectionStatus === 'error') {
      return (
        <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg flex items-center">
          <XCircle className="w-5 h-5 mr-2" />
          Failed to connect to Google. Please try again.
        </div>
      );
    }
    return null;
  };

  return (
    <div className="w-full max-w-4xl">
      <div className="flex items-center mb-6">
        <Settings className="w-8 h-8 mr-3 text-indigo-600" />
        <div>
          <h1 className="text-3xl font-extrabold text-gray-800">Settings</h1>
          <p className="text-lg text-gray-600">Manage application settings and external connections.</p>
        </div>
      </div>

      <div className="bg-white p-6 rounded-lg shadow-xl border border-gray-200 space-y-8">
        <div>
          <h2 className="text-xl font-semibold text-gray-700 mb-4">Integrations</h2>
          <div className="border-t pt-4">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="font-bold text-gray-800">Google Search Console</h3>
                <p className="text-sm text-gray-500">Connect your account to fetch live SEO and indexing data.</p>
              </div>
              {connectionStatus !== 'success' && (
                <button 
                  onClick={handleConnect}
                  className="px-4 py-2 bg-blue-600 text-white font-semibold rounded-md shadow-sm hover:bg-blue-700"
                >
                  Connect to Google
                </button>
              )}
            </div>
            {renderConnectionStatus()}
          </div>
        </div>

        {connectionStatus === 'success' && (
          <div>
            <h2 className="text-xl font-semibold text-gray-700 mb-4">Configuration</h2>
            <div className="border-t pt-4">
              <label htmlFor="gsc-site" className="block text-sm font-medium text-gray-700 mb-2">
                Primary Search Console Site
              </label>
              <p className="text-sm text-gray-500 mb-2">Select the website you want to track in this application.</p>
              {isLoading ? (
                <Loader2 className="animate-spin" />
              ) : (
                <div className="flex items-center gap-4">
                  <select 
                    id="gsc-site" 
                    value={activeSite}
                    onChange={handleSiteSelectionChange}
                    className="w-full max-w-md p-2 border border-gray-300 rounded-md"
                  >
                    {gscSites.length > 0 ? (
                      gscSites.map(site => (
                        <option key={site.siteUrl} value={site.siteUrl}>
                          {site.siteUrl}
                        </option>
                      ))
                    ) : (
                      <option disabled>No sites found in your GSC account.</option>
                    )}
                  </select>
                  {saveStatus && <span className="text-sm text-gray-500">{saveStatus}</span>}
                </div>
              )}
            </div>
          </div>
        )}

        <div>
          <h2 className="text-xl font-semibold text-gray-700 mb-4">Database Management</h2>
          <div className="border-t pt-4">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="font-bold text-gray-800">Manual Backup</h3>
                <p className="text-sm text-gray-500">Create and download a snapshot of the application database.</p>
              </div>
              <div className="flex gap-2">
                <button onClick={handleCreateBackup} className="inline-flex items-center px-4 py-2 bg-gray-600 text-white font-semibold rounded-md shadow-sm hover:bg-gray-700">
                  <Database className="w-4 h-4 mr-2" /> Generate Backup
                </button>
                <button onClick={handleDownloadBackup} className="inline-flex items-center px-4 py-2 bg-green-600 text-white font-semibold rounded-md shadow-sm hover:bg-green-700">
                  <Download className="w-4 h-4 mr-2" /> Download
                </button>
              </div>
            </div>
            {backupMessage && (
              <div className="mt-4 p-3 bg-blue-50 text-blue-700 rounded-lg text-sm">
                {backupMessage}
              </div>
            )}
          </div>
        </div>
      </div>
      <div className="mt-6 border-t pt-4">
          <h3 className="font-bold text-gray-800">Manual Data Fetch</h3>
          <p className="text-sm text-gray-500 mb-2">
            Manually trigger the daily task to fetch the latest GSC data. This is useful for testing or after publishing new content.
          </p>
          <button 
            onClick={handleFetchNow} 
            className="px-4 py-2 bg-teal-600 text-white font-semibold rounded-md shadow-sm hover:bg-teal-700"
          >
            Fetch GSC Data Now
          </button>
      </div>
      <div className="mt-6 border-t pt-4">
          <h3 className="font-bold text-gray-800">Sync with Live Site</h3>
          <p className="text-sm text-gray-500 mb-2">
            Manually sync this application with your live WordPress posts and products to import new content and archive deleted items.
          </p>
          <button 
            onClick={handleSyncNow} 
            className="px-4 py-2 bg-teal-600 text-white font-semibold rounded-md shadow-sm hover:bg-teal-700"
          >
            Sync WordPress Now
          </button>
      </div>
      <div className="mt-6 border-t pt-4">
          <h3 className="font-bold text-gray-800">Fetch Site-Wide Insights</h3>
          <p className="text-sm text-gray-500 mb-2">
            Manually trigger the weekly task to get the latest site-wide insights (top pages, queries, etc.).
          </p>
          <button 
            onClick={handleFetchInsightsNow} 
            className="px-4 py-2 bg-teal-600 text-white font-semibold rounded-md shadow-sm hover:bg-teal-700"
          >
            Fetch Insights Now
          </button>
        </div>
    </div>
  );
};

export default SettingsView;