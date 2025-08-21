// In frontend/src/components/DashboardView.jsx

import React, { useState, useEffect } from 'react';
import { FileText, Edit, CheckSquare, Clock, Search, XCircle, BarChart2 } from 'lucide-react';
import apiClient from '../apiClient';
import EnhancedLineChart from './EnhancedLineChart.jsx';
import StatCard from './StatCard.jsx'; // We'll create this next

const DashboardView = ({ handleMenuItemClick }) => { // <-- Accept the handler
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setIsLoading(true);
        const response = await apiClient.get('/api/dashboard/stats');
        setStats(response.data);
      } catch (err) {
        console.error("Failed to fetch dashboard stats:", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchStats();
  }, []);

  // --- UPDATED: This now uses the real navigation handler ---
  const handleCardClick = (cardName) => {
    if (cardName === 'Total Posts') {
      handleMenuItemClick('Content Library');
    } else if (cardName === 'Drafts') {
      handleMenuItemClick('Approval Queue');
    } else if (cardName === 'Published') {
      handleMenuItemClick('Published Posts'); // <-- UPDATED
    } else {
      alert(`Navigation for ${cardName} is not yet implemented.`);
    }
  };

  const contentStats = [
    { title: 'Total Posts', value: stats?.total_posts, icon: FileText, color: 'blue' },
    { title: 'Drafts', value: stats?.draft_posts, icon: Edit, color: 'yellow' },
    { title: 'Published', value: stats?.published_posts, icon: CheckSquare, color: 'green' },
    { title: 'Scheduled', value: stats?.scheduled_posts, icon: Clock, color: 'purple' },
    { title: 'GSC Indexed', value: stats?.indexed, icon: Search, color: 'indigo' },
    { title: 'Not Indexed', value: stats?.not_indexed, icon: XCircle, color: 'red' },
  ];

  const chartData = [
    // ... chart data remains the same for now
    { date: '2025-06-15', sessions: 100, impressions: 800 }, { date: '2025-06-22', sessions: 220, impressions: 1300 },
    { date: '2025-06-29', sessions: 320, impressions: 1800 }, { date: '2025-07-06', sessions: 450, impressions: 2450 },
  ];

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
              value={isLoading ? '...' : stat.value}
              icon={stat.icon}
              color={stat.color}
              onClick={() => handleCardClick(stat.title)}
            />
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-2xl font-semibold text-gray-700 mb-4">SEO Performance Overview</h2>
        <div className="bg-white p-6 rounded-lg shadow-md border border-gray-200">
           <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
             <BarChart2 className="w-6 h-6 mr-2 text-indigo-500"/>
             Organic Traffic & Impressions
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