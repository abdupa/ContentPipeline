import React, { useState, useEffect } from 'react';
import { TrendingUp, BarChart2, Globe, Search, Loader2, AlertTriangle } from 'lucide-react';
import apiClient from '../apiClient';

const InsightsView = () => {
  const [insights, setInsights] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchInsights = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await apiClient.get('/api/gsc/insights');
        setInsights(response.data);
      } catch (err) {
        setError('Failed to load GSC Insights. Please ensure a GSC data fetch has completed.');
        console.error("Insights fetch error:", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchInsights();
  }, []);

  if (isLoading) {
    return <div className="flex justify-center items-center h-64"><Loader2 className="w-12 h-12 animate-spin text-indigo-600" /></div>;
  }
  
  if (error) {
     return (
      <div className="bg-red-50 border-l-4 border-red-400 p-4 w-full max-w-4xl">
        <div className="flex"><div className="py-1"><AlertTriangle className="h-6 w-6 text-red-500 mr-4" /></div><div><p className="font-bold">Error</p><p className="text-sm">{error}</p></div></div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-6xl space-y-8">
      <div className="flex items-center">
        <TrendingUp className="w-8 h-8 mr-3 text-indigo-600" />
        <div>
          <h1 className="text-3xl font-extrabold text-gray-800">GSC Insights</h1>
          <p className="text-lg text-gray-600">
            A high-level overview of your site's performance. 
            <span className="text-sm ml-2">
              (Last updated: {insights.last_updated ? new Date(insights.last_updated).toLocaleString() : 'Never'})
            </span>
          </p>
        </div>
      </div>

      {/* Top Content */}
      <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200">
        <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
          <BarChart2 className="w-6 h-6 mr-2 text-blue-500"/> Top Content (Last 28 Days)
        </h3>
        <ul className="divide-y divide-gray-200">
          {insights.top_content.map((page, index) => (
            <li key={index} className="py-3 flex justify-between items-center">
              <div>
                <p className="text-sm font-medium text-indigo-600 truncate">{page.keys[0]}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-semibold">{page.clicks.toLocaleString()} Clicks</p>
                <p className="text-xs text-gray-500">{page.impressions.toLocaleString()} Impressions</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {/* Top Queries & Countries */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200">
          <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
            <Search className="w-6 h-6 mr-2 text-green-500"/> Top Queries
          </h3>
          <ul className="divide-y divide-gray-200">
            {insights.top_queries.map((query, index) => (
              <li key={index} className="py-3">
                <p className="text-sm font-medium text-gray-800">{query.keys[0]}</p>
                <p className="text-xs text-gray-500">{query.clicks.toLocaleString()} Clicks</p>
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200">
          <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
            <Globe className="w-6 h-6 mr-2 text-purple-500"/> Top Countries
          </h3>
          <ul className="divide-y divide-gray-200">
            {insights.top_countries.map((country, index) => (
              <li key={index} className="py-3">
                <p className="text-sm font-medium text-gray-800">{country.keys[0]}</p>
                 <p className="text-xs text-gray-500">{country.clicks.toLocaleString()} Clicks</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default InsightsView;