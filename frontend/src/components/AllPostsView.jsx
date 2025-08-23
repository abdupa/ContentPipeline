import React, { useState, useEffect } from 'react';
import { BookOpen, Edit, Trash2, Loader2, AlertTriangle } from 'lucide-react';
import apiClient from '../apiClient';
import DataTable from './DataTable.jsx';

// Helper component for rendering the status badge
const StatusBadge = ({ status }) => {
  const isPublished = status === 'published';
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
        isPublished 
        ? 'bg-green-100 text-green-800' 
        : 'bg-yellow-100 text-yellow-800'
    }`}>
      <span className={`w-2 h-2 mr-1.5 rounded-full ${isPublished ? 'bg-green-500' : 'bg-yellow-500'}`}></span>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
};

const AllPostsView = ({ onEditDraft }) => {
  const [posts, setPosts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const fetchPosts = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/api/posts/with-stats');
      setPosts(response.data.map(post => ({ ...post, id: post.draft_id })));
    } catch (err) {
      setError('Failed to load posts. Please ensure the backend is running.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPosts();
  }, []);

  const handleDelete = async (postId, postTitle) => {
    if (window.confirm(`Are you sure you want to delete the post "${postTitle}"? This action cannot be undone.`)) {
      setDeletingId(postId);
      try {
        await apiClient.delete(`/api/posts/${postId}`);
        setPosts(prevPosts => prevPosts.filter(p => p.draft_id !== postId));
      } catch (err) {
        alert('Failed to delete the post. Please try again.');
        console.error(err);
      } finally {
        setDeletingId(null);
      }
    }
  };

  const columns = [
    { key: '#', label: '#', sortable: true },
    { key: 'post_title', label: 'Title', sortable: true },
    { 
      key: 'status', 
      label: 'Status', 
      sortable: true,
      render: (status) => <StatusBadge status={status} />
    },
    { key: 'clicks', label: 'Clicks', sortable: true },
    { key: 'impressions', label: 'Impressions', sortable: true },
    { 
      key: 'source_url', 
      label: 'Live URL', 
      sortable: false, // Sorting by URL isn't very useful
      render: (url) => (
        url && url !== 'manual' ? (
          <a 
            href={url} 
            target="_blank" 
            rel="noopener noreferrer" 
            className="text-indigo-600 hover:text-indigo-800 hover:underline truncate"
            onClick={(e) => e.stopPropagation()} // Prevents row click if we add it later
          >
            {/* Display a shortened version for cleanliness */}
            {url.replace(/^(https?:\/\/)?(www\.)?/, '').substring(0, 30)}...
          </a>
        ) : (
          <span className="text-gray-400">N/A</span>
        )
      )
    },
    {
      key: 'generated_at',
      label: 'Date Created',
      sortable: true,
      render: (value) => new Date(value).toLocaleDateString(),
    },
  ];

  const actions = (row) => (
    <div className="flex items-center space-x-2">
      <button
        onClick={() => onEditDraft(row.draft_id)}
        className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-gray-100 rounded-full"
        title="Edit Post"
      >
        <Edit className="w-4 h-4" />
      </button>
      <button
        onClick={() => handleDelete(row.draft_id, row.post_title)}
        disabled={deletingId === row.draft_id}
        className="p-2 text-gray-500 hover:text-red-600 hover:bg-gray-100 rounded-full disabled:cursor-not-allowed"
        title="Delete Post"
      >
        {deletingId === row.draft_id ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Trash2 className="w-4 h-4" />
        )}
      </button>
    </div>
  );  

  const formattedPosts = posts.map((post, index) => ({
    ...post,
    '#': index + 1,
    generated_at: new Date(post.generated_at).toLocaleDateString('en-CA'),
  }));

  return (
    <div className="w-full max-w-6xl">
      <div className="flex items-center mb-6">
        <BookOpen className="w-8 h-8 mr-3 text-indigo-600" />
        <div>
          <h1 className="text-3xl font-extrabold text-gray-800">Content Library</h1>
          <p className="text-lg text-gray-600">View and manage all your draft and published posts.</p>
        </div>
      </div>
      
      {error ? (
        <div className="bg-red-50 border-l-4 border-red-400 p-4">
          <div className="flex">
            <div className="py-1"><AlertTriangle className="h-6 w-6 text-red-500 mr-4" /></div>
            <div><p className="font-bold">Error</p><p className="text-sm">{error}</p></div>
          </div>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={formattedPosts}
          actions={actions}
          isLoading={isLoading}
        />
      )}
    </div>
  );
};

export default AllPostsView;