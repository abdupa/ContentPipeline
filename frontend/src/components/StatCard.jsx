import React from 'react';

const StatCard = ({ title, value, icon: Icon, color, onClick }) => {
  const colorStyles = {
    blue: 'bg-blue-50 border-blue-200 text-blue-800 hover:bg-blue-100',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-800 hover:bg-yellow-100',
    green: 'bg-green-50 border-green-200 text-green-800 hover:bg-green-100',
    purple: 'bg-purple-50 border-purple-200 text-purple-800 hover:bg-purple-100',
    indigo: 'bg-indigo-50 border-indigo-200 text-indigo-800 hover:bg-indigo-100',
    red: 'bg-red-50 border-red-200 text-red-800 hover:bg-red-100',
  };

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className={`p-4 rounded-lg shadow-md border text-left transition duration-200 hover:shadow-lg hover:-translate-y-1 flex flex-col justify-between ${colorStyles[color]} disabled:opacity-50 disabled:cursor-not-allowed`}
    >
      <div className="flex justify-between items-start">
        <p className="text-base font-semibold">{title}</p>
        {Icon && <Icon className="w-5 h-5 opacity-70" />}
      </div>
      <p className="text-4xl sm:text-5xl font-bold mt-2">{value ?? 'N/A'}</p>
    </button>
  );
};

export default StatCard;