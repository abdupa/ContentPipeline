import React, { useState, useEffect } from 'react';
import { FileText, Edit, CheckSquare, Clock, Search, XCircle, BarChart2, AlertTriangle, Loader2 } from 'lucide-react';
import apiClient from '../apiClient';
import EnhancedLineChart from './EnhancedLineChart.jsx';
import StatCard from './StatCard.jsx';
import PriceIntegrityWidget from './PriceIntegrityWidget.jsx';

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
    return <div className="flex h-64 items-center justify-center"><Loader2 className="h-10 w-10 animate-spin text-indigo-600" /></div>;
  }
  
  if (error) {
     return (
      <div className="w-full max-w-4xl border-l-4 border-red-400 bg-red-50 p-4">
        <div className="flex">
          <div className="py-1"><AlertTriangle className="h-6 w-6 text-red-500 mr-4" /></div>
          <div><p className="font-bold">Error</p><p className="text-sm">{error}</p></div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-7xl">
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold text-gray-800 sm:text-3xl">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-600 sm:text-base">Your content performance at a glance.</p>
      </div>

      <section className="mb-8">
        <h2 className="mb-3 text-xl font-semibold text-gray-700 sm:text-2xl">Content Status Summary</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6 xl:gap-4">
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
        <h2 className="mb-3 text-xl font-semibold text-gray-700 sm:text-2xl">SEO Performance Overview (Last 30 Days)</h2>
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:p-5">
           <h3 className="mb-3 flex items-center text-base font-semibold text-gray-800 sm:text-lg">
             <BarChart2 className="mr-2 h-5 w-5 text-indigo-500"/>
             Organic Clicks & Impressions
           </h3>
          <div className="h-[260px] w-full sm:h-[320px]">
            <EnhancedLineChart data={chartData} />
          </div>
        </div>
      </section>
      <section className="mb-10">
         <PriceIntegrityWidget /> 
      </section>
    </div>
  );
};

export default DashboardView;
