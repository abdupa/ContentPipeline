// src/components/DashboardView.jsx
import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import EnhancedLineChart from './EnhancedLineChart.jsx'; // Import the new ENHANCED chart

const DashboardView = () => {
  // Data for summary cards
  const contentStats = [
    { title: 'Total Posts', value: 500, color: 'blue' }, { title: 'Drafts', value: 120, color: 'yellow' },
    { title: 'Published', value: 350, color: 'green' }, { title: 'Scheduled', value: 30, color: 'purple' },
    { title: 'GSC Indexed', value: 280, color: 'indigo' }, { title: 'Not Indexed (GSC)', value: 70, color: 'red' },
  ];

  // Data for the D3 chart
  const chartData = [
    { date: '2025-06-15', sessions: 100, impressions: 800 }, { date: '2025-06-22', sessions: 220, impressions: 1300 },
    { date: '2025-06-29', sessions: 320, impressions: 1800 }, { date: '2025-07-06', sessions: 450, impressions: 2450 },
  ];

  const handleCardClick = (cardName) => {
    alert(`Navigating to ${cardName}`);
  };

  const colorStyles = {
    blue: 'bg-blue-50 border-blue-200 text-blue-700 hover:bg-blue-100',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-700 hover:bg-yellow-100',
    green: 'bg-green-50 border-green-200 text-green-700 hover:bg-green-100',
    purple: 'bg-purple-50 border-purple-200 text-purple-700 hover:bg-purple-100',
    indigo: 'bg-indigo-50 border-indigo-200 text-indigo-700 hover:bg-indigo-100',
    red: 'bg-red-50 border-red-200 text-red-700 hover:bg-red-100',
  };

  return (
    <div className="bg-white p-6 sm:p-8 rounded-lg shadow-xl w-full max-w-6xl border border-gray-200">
      <h1 className="text-3xl font-extrabold text-gray-800 mb-2">Dashboard</h1>
      <p className="text-lg text-gray-600 mb-8">Your content performance at a glance.</p>

      {/* Content Overview Section */}
      <section className="mb-10">
        <h2 className="text-2xl font-semibold text-gray-700 mb-4">Content Status Summary</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 sm:gap-6">
          {contentStats.map((stat) => (
            <button key={stat.title} type="button" onClick={() => handleCardClick(stat.title)}
              className={`p-4 rounded-lg shadow-md border text-center transition duration-200 hover:shadow-lg hover:-translate-y-1 ${colorStyles[stat.color]}`}>
              <p className="text-4xl sm:text-5xl font-bold mb-2">{stat.value}</p>
              <p className="text-base font-semibold">{stat.title}</p>
            </button>
          ))}
        </div>
      </section>

      {/* SEO Performance Section with ENHANCED Chart */}
      <section>
        <h2 className="text-2xl font-semibold text-gray-700 mb-4">SEO Performance Overview</h2>
        <div className="bg-gray-50 p-6 rounded-lg shadow-md border border-gray-200">
          <h3 className="text-xl font-semibold text-gray-800 mb-4">Organic Traffic & Impressions</h3>
          <div className="w-full h-[350px]">
            <EnhancedLineChart data={chartData} />
          </div>
          <div className="mt-6 flex justify-center">
            <button onClick={() => alert('Navigating to detailed SEO report')}
              className="inline-flex items-center px-6 py-2 bg-indigo-600 text-white font-semibold rounded-full shadow-md hover:bg-indigo-700">
              View Detailed SEO Report
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};

export default DashboardView;