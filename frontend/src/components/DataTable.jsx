import React, { useState, useMemo } from 'react';
import { ArrowUpDown, Search, Frown, Loader2 } from 'lucide-react'; // <-- ADD Loader2 here

const DataTable = ({ columns, data, actions, isLoading, error }) => {
  // State for managing search and sorting
  const [searchTerm, setSearchTerm] = useState('');
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'ascending' });

  // Memoized calculations for filtering and sorting to optimize performance
  const processedData = useMemo(() => {
    let filteredData = [...data];

    // 1. Apply search filter
    if (searchTerm) {
      filteredData = filteredData.filter(item =>
        columns.some(column =>
          String(item[column.key]).toLowerCase().includes(searchTerm.toLowerCase())
        )
      );
    }

    // 2. Apply sorting
    if (sortConfig.key) {
      filteredData.sort((a, b) => {
        if (a[sortConfig.key] < b[sortConfig.key]) {
          return sortConfig.direction === 'ascending' ? -1 : 1;
        }
        if (a[sortConfig.key] > b[sortConfig.key]) {
          return sortConfig.direction === 'ascending' ? 1 : -1;
        }
        return 0;
      });
    }

    return filteredData;
  }, [data, searchTerm, sortConfig, columns]);

  // Handler for changing the sort column and direction
  const handleSort = (key) => {
    let direction = 'ascending';
    if (sortConfig.key === key && sortConfig.direction === 'ascending') {
      direction = 'descending';
    }
    setSortConfig({ key, direction });
  };

  if (error) {
    return <div className="text-red-600 bg-red-50 p-4 rounded-lg text-center">{error}</div>;
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-xl border border-gray-200">
      {/* Search Bar */}
      <div className="mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search all columns..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full max-w-sm p-2 pl-10 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
          />
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {columns.map((col) => (
                <th 
                  key={col.key} 
                  // --- FROM ---
                  // className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  // --- TO ---
                  className="px-4 py-3 text-left text-xs font-bold text-gray-600 uppercase tracking-wider">
                  {col.sortable ? (
                    <button onClick={() => handleSort(col.key)} className="flex items-center gap-2 hover:text-gray-800">
                      {col.label}
                      <ArrowUpDown className="w-4 h-4" />
                    </button>
                  ) : (
                    col.label
                  )}
                </th>
              ))}
              {actions && 
                <th className="px-4 py-3 text-left text-xs font-bold text-gray-600 uppercase tracking-wider">
                  Actions
                </th>
              }
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {isLoading ? (
              <tr>
                <td colSpan={columns.length + (actions ? 1 : 0)} className="text-center p-16 text-gray-500">
                  <div className="flex justify-center items-center">
                    <Loader2 className="w-10 h-10 animate-spin text-indigo-600" />
                  </div>
                </td>
              </tr>
            ) : processedData.length > 0 ? (
              processedData.map((row, index) => (
                <tr key={row.id || index} className="hover:bg-gray-50">
                  {columns.map(col => (
                    <td key={col.key} className="px-4 py-4 whitespace-nowrap text-sm text-gray-700">
                      {/* --- NEW: Use a render function if it exists --- */}
                      {col.render ? col.render(row[col.key], row) : row[col.key]}
                    </td>
                  ))}
                  {actions && <td className="px-4 py-4 whitespace-nowrap text-sm font-medium">{actions(row)}</td>}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length + (actions ? 1 : 0)} className="text-center p-16 text-gray-500">
                  <Frown className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                  No results found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default DataTable;