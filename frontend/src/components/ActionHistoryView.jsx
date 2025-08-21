import React, { useState, useEffect } from 'react';
import { History, Loader2, AlertTriangle, FileText, Edit, Play, Trash2, Send, RefreshCw, Image as ImageIcon } from 'lucide-react';
import apiClient from '../apiClient';

// A helper component to render a specific icon for each action type
const ActionIcon = ({ actionType }) => {
  const iconProps = { className: "w-6 h-6 text-white" };
  let iconElement = <FileText {...iconProps} />;
  let bgColor = 'bg-gray-400';

  if (actionType.includes('CREATED')) bgColor = 'bg-green-500';
  if (actionType.includes('EDITED')) bgColor = 'bg-blue-500';
  if (actionType.includes('DELETED')) bgColor = 'bg-red-500';
  if (actionType.includes('RUN')) bgColor = 'bg-indigo-500';
  if (actionType.includes('PUBLISHED')) bgColor = 'bg-purple-500';
  if (actionType.includes('REGENERATED')) bgColor = 'bg-yellow-500';

  if (actionType.includes('PROJECT')) iconElement = <FileText {...iconProps} />;
  if (actionType.includes('DRAFT') || actionType.includes('POST')) iconElement = <FileText {...iconProps} />;
  if (actionType.includes('EDITED')) iconElement = <Edit {...iconProps} />;
  if (actionType.includes('RUN')) iconElement = <Play {...iconProps} />;
  if (actionType.includes('DELETED')) iconElement = <Trash2 {...iconProps} />;
  if (actionType.includes('PUBLISHED')) iconElement = <Send {...iconProps} />;
  if (actionType.includes('CONTENT_REGENERATED')) iconElement = <RefreshCw {...iconProps} />;
  if (actionType.includes('IMAGE_REGENERATED')) iconElement = <ImageIcon {...iconProps} />;
  
  return (
    <div className={`flex items-center justify-center w-12 h-12 rounded-full ${bgColor}`}>
      {iconElement}
    </div>
  );
};

// Main view component
const ActionHistoryView = () => {
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // In ActionHistoryView.jsx

  useEffect(() => {
    const fetchHistory = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await apiClient.get('/api/account/history');
        setHistory(response.data);
      } catch (err) {
        setError('Failed to load action history.');
        console.error("Error fetching history:", err); // <-- NEW LOG
      } finally {
        setIsLoading(false);
      }
    };
    fetchHistory();
  }, []);

  // Helper to format the action text for display
  const formatActionText = (item) => {
    const title = item.details?.title || item.details?.name || '';
    const formattedTitle = title ? `"${title}"` : '';

    switch (item.action) {
      case 'PROJECT_CREATED':
        return <>You created project {formattedTitle}</>;
      case 'PROJECT_EDITED':
        return <>You updated project {formattedTitle}</>;
      case 'PROJECT_RUN_STARTED':
        return <>You started a run for project {formattedTitle}</>;
      case 'DRAFT_CREATED':
        return <>A new draft {formattedTitle} was created</>;
      case 'DRAFT_EDITED':
        return <>You saved changes to draft {formattedTitle}</>;
      case 'DRAFT_PUBLISHED':
        return <>You published post {formattedTitle}</>;
      case 'POST_DELETED':
        return <>You deleted post {formattedTitle}</>;
      case 'CONTENT_REGENERATED':
        return <>You regenerated content for {formattedTitle}</>;
      case 'IMAGE_REGENERATED':
        return <>You regenerated the image for {formattedTitle}</>;
      default:
        return item.action.replace(/_/g, ' ').toLowerCase();
    }
  };

  if (isLoading) {
    return <div className="flex justify-center items-center h-64"><Loader2 className="w-12 h-12 animate-spin text-indigo-600" /></div>;
  }

  if (error) {
    return (
      <div className="bg-red-50 border-l-4 border-red-400 p-4">
        <div className="flex">
          <div className="py-1"><AlertTriangle className="h-6 w-6 text-red-500 mr-4" /></div>
          <div><p className="font-bold">Error</p><p className="text-sm">{error}</p></div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl">
      <div className="flex items-center mb-6">
        <History className="w-8 h-8 mr-3 text-indigo-600" />
        <div>
          <h1 className="text-3xl font-extrabold text-gray-800">Action History</h1>
          <p className="text-lg text-gray-600">A log of recent activity in the application.</p>
        </div>
      </div>
      
      <div className="bg-white p-6 rounded-lg shadow-xl border border-gray-200">
        <div className="flow-root">
          <ul className="-mb-8">
            {history.length > 0 ? history.map((item, index) => (
              <li key={index}>
                <div className="relative pb-8">
                  {/* Render the vertical line for all but the last item */}
                  {index !== history.length - 1 ? (
                    <span className="absolute top-5 left-5 -ml-px h-full w-0.5 bg-gray-200" aria-hidden="true" />
                  ) : null}
                  <div className="relative flex items-start space-x-4">
                    {/* Icon */}
                    <ActionIcon actionType={item.action} />
                    <div className="min-w-0 flex-1 pt-1.5">
                      {/* Action Text */}
                      <p className="text-md text-gray-700">
                        {formatActionText(item)}
                      </p>
                      {/* Timestamp */}
                      <p className="mt-1 text-sm text-gray-500">
                        {new Date(item.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
              </li>
            )) : (
              <p className="text-center text-gray-500 py-8">No actions have been recorded yet.</p>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default ActionHistoryView;