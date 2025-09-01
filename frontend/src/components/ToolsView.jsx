import React, { useState } from 'react';
import { Wrench, HardHat, Loader2 } from 'lucide-react';
import apiClient from '../apiClient';

const ToolsView = ({ onJobStarted }) => {
  const [url, setUrl] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleInspect = async () => {
    if (!url || !username || !password) {
      alert('Please fill in all fields.');
      return;
    }
    setIsLoading(true);
    try {
      const payload = { url, username, password };
      const response = await apiClient.post('/api/tools/inspect-wordpress', payload);
      onJobStarted(response.data.job_id, 'tools'); // Pass job ID and origin
    } catch (err) {
      alert(`Failed to start inspection task: ${err.response?.data?.detail || 'Unknown error'}`);
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    const origin = localStorage.getItem('jobOriginView') || 'projects';
    onReset(origin); // Pass the origin view back to the App component
  };

  return (
    <div className="w-full max-w-4xl">
      <button onClick={handleBack} className="px-4 py-2 bg-gray-200 text-gray-800 font-semibold rounded-md hover:bg-gray-300">Back</button>
      <div className="flex items-center mb-6">
        <Wrench className="w-8 h-8 mr-3 text-indigo-600" />
        <div>
          <h1 className="text-3xl font-extrabold text-gray-800">Tools</h1>
          <p className="text-lg text-gray-600">Utilities for managing and analyzing your content sources.</p>
        </div>
      </div>

      <div className="bg-white p-6 rounded-lg shadow-xl border border-gray-200">
        <h2 className="text-xl font-semibold text-gray-700 mb-4 flex items-center">
          <HardHat className="w-6 h-6 mr-2 text-yellow-500" />
          WordPress Site Inspector
        </h2>
        <p className="text-sm text-gray-500 mb-4">
          Connect to a WordPress site to fetch a complete list of all its posts, pages, and categories. 
          This is useful for building a content map for SEO.
        </p>
        <div className="border-t pt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Site URL</label>
            <input type="text" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.your-wordpress-site.com" className="w-full p-2 border rounded-md"/>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">WordPress Username</label>
            <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="your_wp_username" className="w-full p-2 border rounded-md"/>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Application Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••••••••••" className="w-full p-2 border rounded-md"/>
          </div>
          <div className="text-right">
            <button onClick={handleInspect} disabled={isLoading} className="inline-flex items-center px-6 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-sm hover:bg-indigo-700 disabled:bg-gray-400">
              {isLoading ? <Loader2 className="w-5 h-5 mr-2 animate-spin"/> : null}
              {isLoading ? 'Inspecting...' : 'Start Inspection'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ToolsView;