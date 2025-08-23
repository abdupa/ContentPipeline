import React, { useState, useEffect, useCallback } from 'react';
import { BarChart2, Loader2, AlertTriangle } from 'lucide-react';
import apiClient from '../apiClient';
import EnhancedLineChart from './EnhancedLineChart.jsx';
import StatCard from './StatCard.jsx';

// Helper to calculate start date based on a range string (e.g., '28d')
const getStartDate = (range) => {
  const endDate = new Date();
  let startDate = new Date();
  
  if (range.endsWith('d')) {
    startDate.setDate(endDate.getDate() - parseInt(range));
  } else if (range.endsWith('m')) {
    startDate.setMonth(endDate.getMonth() - parseInt(range));
  }
  
  return startDate.toISOString().split('T')[0]; // Format as YYYY-MM-DD
};

const PerformanceView = () => {
  const [performanceData, setPerformanceData] = useState({ summary: {}, daily_data: [] });
  const [timeRange, setTimeRange] = useState('1d'); // Default to 28 days
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPerformanceData = useCallback(async (range) => {
    setIsLoading(true);
    setError(null);
    try {
      const startDate = getStartDate(range);
      const endDate = new Date().toISOString().split('T')[0];
      
      const response = await apiClient.get(`/api/gsc/performance?start_date_str=${startDate}&end_date_str=${endDate}`);
      setPerformanceData(response.data);
    } catch (err) {
      setError('Failed to load performance data. Ensure GSC is connected and data has been fetched.');
      console.error("Performance fetch error:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPerformanceData(timeRange);
  }, [timeRange, fetchPerformanceData]);

  const summaryStats = [
    { title: 'Total Clicks', value: performanceData.summary.total_clicks, color: 'indigo' },
    { title: 'Total Impressions', value: performanceData.summary.total_impressions, color: 'teal' },
  ];

  const timeRanges = [
    { label: 'Last 24 Hours', value: '1d' },
    { label: 'Last 7 Days', value: '7d' },
    { label: 'Last 28 Days', value: '28d' },
    { label: 'Last 3 Months', value: '3m' },
  ];

  if (error) {
     return (
      <div className="bg-red-50 border-l-4 border-red-400 p-4 w-full max-w-4xl">
        <div className="flex"><div className="py-1"><AlertTriangle className="h-6 w-6 text-red-500 mr-4" /></div><div><p className="font-bold">Error</p><p className="text-sm">{error}</p></div></div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-6xl">
      <div className="flex items-center mb-6">
        <BarChart2 className="w-8 h-8 mr-3 text-indigo-600" />
        <div>
          <h1 className="text-3xl font-extrabold text-gray-800">Performance Report</h1>
          <p className="text-lg text-gray-600">Analyze your site's SEO performance over time.</p>
        </div>
      </div>

      {/* Time Range Selector */}
      <div className="mb-6 flex items-center gap-2">
        {timeRanges.map(range => (
          <button 
            key={range.value}
            onClick={() => setTimeRange(range.value)}
            className={`px-4 py-2 text-sm font-semibold rounded-full transition-colors ${
              timeRange === range.value 
              ? 'bg-indigo-600 text-white shadow' 
              : 'bg-white text-gray-600 hover:bg-gray-100'
            }`}
          >
            {range.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex justify-center items-center h-64"><Loader2 className="w-12 h-12 animate-spin text-indigo-600" /></div>
      ) : (
        <div className="space-y-8">
          {/* Summary Stat Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {summaryStats.map(stat => (
              <StatCard key={stat.title} title={stat.title} value={stat.value} color={stat.color} />
            ))}
          </div>

          {/* Performance Chart */}
          <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200">
            <h3 className="text-xl font-semibold text-gray-800 mb-4">Daily Clicks & Impressions</h3>
            <div className="w-full h-[350px]">
              <EnhancedLineChart data={performanceData.daily_data} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PerformanceView;