import React from 'react';
import { LayoutDashboard, Globe, CheckSquare, Settings, BookOpen, History, Send } from 'lucide-react';

// const Sidebar = ({ onMenuItemClick, activeItem }) => {
//   // --- UPDATED MENU ITEMS ---
//   const menuItems = [
//     { name: 'Dashboard', icon: LayoutDashboard },
//     { name: 'Scrape Content', icon: Globe },
//     { name: 'Content Library', icon: BookOpen },
//     { name: 'Approval Queue', icon: CheckSquare },
//     { name: 'Action History', icon: History },
//     { name: 'Settings', icon: Settings },
//   ];

const Sidebar = ({ onMenuItemClick, activeItem }) => {
  const menuItems = [
    { name: 'Dashboard', icon: LayoutDashboard },
    { name: 'Scrape Content', icon: Globe },
    { name: 'Content Library', icon: BookOpen },
    { name: 'Approval Queue', icon: CheckSquare },
    { name: 'Published Posts', icon: Send }, // <-- NEW
    { name: 'Action History', icon: History },
    { name: 'Settings', icon: Settings },
  ];

  return (
    // ... rest of the component remains the same
    <div className="w-64 bg-gray-800 text-white flex flex-col rounded-r-lg shadow-lg py-6 px-4">
      <div className="mb-8 px-4 flex justify-center">
        <img src="https://placehold.co/150x50/1f2937/a78bfa?text=ContentPipeline" alt="AI ContentGen Logo" className="h-12 w-auto object-contain"/>
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