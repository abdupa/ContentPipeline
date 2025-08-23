import React, { useState, useEffect } from 'react';
import { FileText, Edit, CheckSquare, Clock, Search, XCircle, BarChart2, AlertTriangle, Loader2 } from 'lucide-react';
import apiClient from '../apiClient';
import EnhancedLineChart from './EnhancedLineChart.jsx';
import StatCard from './StatCard.jsx';

const DashboardView = ({ handleMenuItemClick }) => {
  const [stats, setStats] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [statsResponse, chartResponse] = await Promise.all([
          apiClient.get('/api/dashboard/stats'),
          apiClient.get('/api/dashboard/seo-performance-graph')
        ]);
        setStats(statsResponse.data);
        setChartData(chartResponse.data);
      } catch (err) {
        setError("Failed to load dashboard data. Please ensure the backend is running and GSC is connected.");
        console.error("Dashboard fetch error:", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchDashboardData();
  }, []);

  const handleCardClick = (cardName) => {
    if (cardName === 'Total Posts') handleMenuItemClick('Content Library');
    else if (cardName === 'Drafts') handleMenuItemClick('Approval Queue');
    else if (cardName === 'Published') handleMenuItemClick('Published Posts');
    else alert(`Navigation for ${cardName} is not yet implemented.`);
  };

  const contentStats = [
    { title: 'Total Posts', value: stats?.total_posts, icon: FileText, color: 'blue', onClick: () => handleCardClick('Total Posts') },
    { title: 'Drafts', value: stats?.draft_posts, icon: Edit, color: 'yellow', onClick: () => handleCardClick('Drafts') },
    { title: 'Published', value: stats?.published_posts, icon: CheckSquare, color: 'green', onClick: () => handleCardClick('Published') },
    { title: 'Scheduled', value: stats?.scheduled_posts, icon: Clock, color: 'purple', onClick: null },
    { title: 'GSC Indexed', value: stats?.indexed, icon: Search, color: 'indigo', onClick: null },
    { title: 'Not Indexed', value: stats?.not_indexed, icon: XCircle, color: 'red', onClick: null },
  ];

  if (isLoading) {
    return <div className="flex justify-center items-center h-64"><Loader2 className="w-12 h-12 animate-spin text-indigo-600" /></div>;
  }
  
  if (error) {
     return (
      <div className="bg-red-50 border-l-4 border-red-400 p-4 w-full max-w-4xl">
        <div className="flex">
          <div className="py-1"><AlertTriangle className="h-6 w-6 text-red-500 mr-4" /></div>
          <div><p className="font-bold">Error</p><p className="text-sm">{error}</p></div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-6xl">
      <h1 className="text-3xl font-extrabold text-gray-800 mb-2">Dashboard</h1>
      <p className="text-lg text-gray-600 mb-8">Your content performance at a glance.</p>

      <section className="mb-10">
        <h2 className="text-2xl font-semibold text-gray-700 mb-4">Content Status Summary</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 sm:gap-6">
          {contentStats.map((stat) => (
            <StatCard
              key={stat.title}
              title={stat.title}
              value={stat.value}
              icon={stat.icon}
              color={stat.color}
              onClick={stat.onClick}
            />
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-semibold text-gray-700 mb-4">SEO Performance Overview (Last 30 Days)</h2>
        <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200">
           <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
             <BarChart2 className="w-6 h-6 mr-2 text-indigo-500"/>
             Organic Clicks & Impressions
           </h3>
          <div className="w-full h-[350px]">
            <EnhancedLineChart data={chartData} />
          </div>
        </div>
      </section>
    </div>
  );
};

export default DashboardView;