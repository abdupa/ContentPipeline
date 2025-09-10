import React, { useState, useEffect } from 'react';
import { Smartphone, Loader2, AlertTriangle } from 'lucide-react';
import apiClient from '../apiClient';
import DataTable from './DataTable.jsx';

const ProductDatabaseView = () => {
  const [products, setProducts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProducts = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await apiClient.get('/api/products');
        // Add a simple 'id' for the table key, using the index
        setProducts(response.data.map((prod, index) => ({ ...prod, id: index })));
      } catch (err) {
        setError('Failed to load product database.');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchProducts();
  }, []);

  // Define the columns for our data table
  const columns = [
    { key: 'name', label: 'Model Name', sortable: true, width: '50%' },
    { key: 'price', label: 'Price', sortable: true, width: '25%' },
    { key: 'brand', label: 'Brand', sortable: true, width: '25%' },
  ];

  if (error) {
     return (
      <div className="bg-red-50 border-l-4 border-red-400 p-4 w-full max-w-4xl">
        <div className="flex"><div className="py-1"><AlertTriangle className="h-6 w-6 text-red-500 mr-4" /></div><div><p className="font-bold">Error</p><p className="text-sm">{error}</p></div></div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-6xl">
      <div className="flex items-center mb-6">
        <Smartphone className="w-8 h-8 mr-3 text-indigo-600" />
        <div>
          <h1 className="text-3xl font-extrabold text-gray-800">Product Database</h1>
          <p className="text-lg text-gray-600">Search and sort all phone models in the local database.</p>
        </div>
      </div>
      
      <DataTable
        columns={columns}
        data={products}
        isLoading={isLoading}
      />
    </div>
  );
};

export default ProductDatabaseView;