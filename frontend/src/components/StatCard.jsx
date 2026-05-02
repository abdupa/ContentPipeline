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
      className={`min-h-[112px] rounded-lg border p-3 text-left shadow-sm transition duration-200 hover:shadow-md hover:-translate-y-0.5 flex flex-col justify-between ${colorStyles[color]} disabled:opacity-60 disabled:cursor-not-allowed`}
    >
      <div className="flex justify-between items-start gap-2">
        <p className="text-sm font-semibold leading-tight">{title}</p>
        {Icon && <Icon className="w-4 h-4 shrink-0 opacity-70" />}
      </div>
      <p className="mt-2 text-3xl font-bold leading-none sm:text-4xl">{value ?? 'N/A'}</p>
    </button>
  );
};

export default StatCard;
