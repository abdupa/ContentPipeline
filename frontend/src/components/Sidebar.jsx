import React from 'react';
import { LayoutDashboard, Globe, CheckSquare, Settings, BookOpen, History, Send, Edit3, BarChart2, TrendingUp, Wrench, Smartphone } from 'lucide-react';
import logo from '../assets/react.svg';

const Sidebar = ({ onMenuItemClick, activeItem }) => {
  const menuItems = [
    { name: 'Dashboard', icon: LayoutDashboard },
    { name: 'Insights', icon: TrendingUp },
    { name: 'Performance', icon: BarChart2 },
    { name: 'Scraping Projects', icon: Globe },
    { name: 'Manual Editor', icon: Edit3 },
    { name: 'Product Database', icon: Smartphone },
    { name: 'Content Library', icon: BookOpen },
    { name: 'Approval Queue', icon: CheckSquare },
    { name: 'Published Posts', icon: Send },
    { name: 'Action History', icon: History },
    { name: 'Tools', icon: Wrench },
    { name: 'Settings', icon: Settings },
  ];

  return (
    // ... rest of the component remains the same
    <div className="hidden lg:flex w-56 xl:w-60 shrink-0 bg-gray-800 text-white flex-col rounded-r-lg shadow-lg py-5 px-3">
      <div className="mb-6 px-3 flex justify-center">
        <img src={logo} alt="ContentPipeline Logo" className="h-16 w-auto object-contain"/>
      </div>
      <nav className="flex-1">
        <ul className="space-y-1">
          {menuItems.map((item) => (
            <li key={item.name}>
              <button
                onClick={() => onMenuItemClick(item.name)}
                className={`flex items-center w-full px-3 py-2 rounded-md text-left text-sm font-medium transition duration-200 ease-in-out
                  ${activeItem === item.name
                    ? 'bg-indigo-600 text-white shadow-md'
                    : 'text-gray-200 hover:bg-gray-700 hover:text-white'
                  }`}
              >
                <item.icon className="w-4 h-4 mr-3 shrink-0" />
                {item.name}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      <div className="mt-auto pt-5 border-t border-gray-700 text-center text-xs text-gray-400">
        <p>&copy; 2025 ContentGen</p>
      </div>
    </div>
  );
};

export default Sidebar;
