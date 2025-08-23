import React from 'react';
import { LayoutDashboard, Globe, CheckSquare, Settings, BookOpen, History, Send, Edit3, BarChart2, TrendingUp } from 'lucide-react';
import logo from '../assets/cpl-logo4.png';

const Sidebar = ({ onMenuItemClick, activeItem }) => {
  const menuItems = [
    { name: 'Dashboard', icon: LayoutDashboard },
    { name: 'Insights', icon: TrendingUp },
    { name: 'Performance', icon: BarChart2 },
    { name: 'Scraping Projects', icon: Globe },
    { name: 'Manual Editor', icon: Edit3 },
    { name: 'Content Library', icon: BookOpen },
    { name: 'Approval Queue', icon: CheckSquare },
    { name: 'Published Posts', icon: Send },
    { name: 'Action History', icon: History },
    { name: 'Settings', icon: Settings },
  ];

  return (
    // ... rest of the component remains the same
    <div className="w-64 bg-gray-800 text-white flex flex-col rounded-r-lg shadow-lg py-6 px-4">
      <div className="mb-8 px-4 flex justify-center">
        <img src={logo} alt="ContentPipeline Logo" className="h-30 w-auto object-contain"/>
      </div>
      <nav className="flex-1">
        <ul>
          {menuItems.map((item) => (
            <li key={item.name} className="mb-2">
              <button
                onClick={() => onMenuItemClick(item.name)}
                className={`flex items-center w-full px-4 py-2 rounded-lg text-left text-lg font-medium transition duration-200 ease-in-out
                  ${activeItem === item.name
                    ? 'bg-indigo-600 text-white shadow-md'
                    : 'text-gray-200 hover:bg-gray-700 hover:text-white'
                  }`}
              >
                <item.icon className="w-5 h-5 mr-3" />
                {item.name}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      <div className="mt-auto pt-6 border-t border-gray-700 text-center text-sm text-gray-400">
        <p>&copy; 2025 ContentGen</p>
      </div>
    </div>
  );
};

export default Sidebar;