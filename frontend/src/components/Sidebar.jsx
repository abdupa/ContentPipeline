import React from 'react';
import { LayoutDashboard, Upload, Globe, Edit, Zap, Users } from 'lucide-react';

const Sidebar = ({ onMenuItemClick, activeItem }) => {
  const menuItems = [
    { name: 'Dashboard', icon: LayoutDashboard },
    { name: 'Upload CSV', icon: Upload },
    { name: 'Scrape Content', icon: Globe },
    { name: 'Manual Content', icon: Edit },
    { name: 'Integrations', icon: Zap },
    { name: 'Users/Settings', icon: Users },
  ];

  return (
    <div className="w-64 bg-gray-800 text-white flex flex-col rounded-r-lg shadow-lg py-6 px-4">
      <div className="mb-8">
        <div className="mb-8 px-4 flex justify-center">
          <img src="/autoscale_small.png" alt="AI ContentGen  Logo" className="h-12 w-auto object-contain"/>
      </div>
        {/* <h2 className="text-2xl font-bold text-center text-indigo-300">ContentGen</h2> */}
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