import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Loader2, Edit, AlertTriangle } from 'lucide-react';

const apiClient = axios.create({
  baseURL: `http://${window.location.hostname}:8000`,
});

const ApprovalQueueView = ({ onEditDraft }) => {
  const [drafts, setDrafts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDrafts = async () => {
      try {
        setIsLoading(true);
        const response = await apiClient.get('/api/drafts');
        setDrafts(response.data);
        setError(null);
      } catch (err) {
        console.error("Failed to fetch drafts:", err);
        setError("Could not load drafts. Please ensure the backend is running and jobs have completed.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchDrafts();
  }, []);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="w-12 h-12 animate-spin text-indigo-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border-l-4 border-red-400 p-4 w-full max-w-4xl">
        <div className="flex">
          <div className="py-1"><AlertTriangle className="h-6 w-6 text-red-500 mr-4" /></div>
          <div>
            <p className="font-bold">Error</p>
            <p className="text-sm">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-6xl">
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold text-gray-800">Approval Queue</h1>
        <p className="text-lg text-gray-600">Review, edit, and publish AI-generated content.</p>
      </div>

      {drafts.length === 0 ? (
        <div className="text-center py-16 border-2 border-dashed border-gray-300 rounded-lg">
          <h3 className="text-xl font-semibold text-gray-700">No Drafts Found</h3>
          <p className="text-gray-500 mt-2">Run a scraping project to generate new content drafts.</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="p-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <input type="checkbox" className="h-4 w-4 text-indigo-600 border-gray-300 rounded" />
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {drafts.map((draft) => (
                <tr key={draft.draft_id}>
                  <td className="p-4"><input type="checkbox" className="h-4 w-4 text-indigo-600 border-gray-300 rounded" /></td>
                  <td className="px-6 py-4 whitespace-nowrap font-medium text-gray-900">{draft.post_title}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{draft.post_category}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800">
                      {draft.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <button onClick={() => onEditDraft(draft.draft_id)} className="text-indigo-600 hover:text-indigo-900 flex items-center">
                      <Edit className="w-4 h-4 mr-1" /> Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default ApprovalQueueView;