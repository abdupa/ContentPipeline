import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { PlusCircle, Play, Edit, Trash2, Loader2, AlertTriangle, RefreshCw, X, Smartphone, Newspaper } from 'lucide-react';
import apiClient from '../apiClient'; // Make sure this import path is correct

const RunWithOptionsModal = ({ project, onClose, onConfirm }) => {
  const today = new Date().toISOString().split('T')[0];
  const [targetDate, setTargetDate] = useState(today);
  const [limit, setLimit] = useState('');
  
  // --- NEW STATE for discovery ---
  const [discoveredArticles, setDiscoveredArticles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedUrls, setSelectedUrls] = useState(new Set());

  // Fetch new articles when the modal opens
  useEffect(() => {
    const discover = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await apiClient.post(`/api/projects/${project.project_id}/discover-new-articles`);
        setDiscoveredArticles(response.data);
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to discover new articles. Check the project configuration.");
      } finally {
        setIsLoading(false);
      }
    };
    discover();
  }, [project.project_id]);

  const handleCheckboxChange = (url) => {
    setSelectedUrls(prev => {
      const newSet = new Set(prev);
      if (newSet.has(url)) {
        newSet.delete(url);
      } else {
        newSet.add(url);
      }
      return newSet;
    });
  };

  const handleRun = () => {
    onConfirm(project.project_id, {
      target_date: targetDate,
      limit: limit ? parseInt(limit, 10) : null,
      // Pass the selected URLs to the backend if any are selected
      custom_url_list: selectedUrls.size > 0 ? Array.from(selectedUrls) : null,
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
      <div className="bg-white rounded-lg shadow-2xl p-6 w-full max-w-2xl">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-gray-800">Run Options for "{project.project_name}"</h2>
          <button onClick={onClose}><X className="w-6 h-6" /></button>
        </div>
        
        {/* --- Article Selection UI --- */}
        <div className="mb-4 p-4 border rounded-lg">
          <h3 className="font-semibold text-gray-700 mb-2">Select New Articles to Process</h3>
          <p className="text-sm text-gray-500 mb-3">Leave all unchecked to run on all newly discovered articles, or select specific ones to process.</p>
          {isLoading ? (
            <div className="flex justify-center items-center h-48"><Loader2 className="animate-spin text-indigo-600" /></div>
          ) : error ? (
            <div className="text-red-500 text-center h-48 flex justify-center items-center">{error}</div>
          ) : discoveredArticles.length === 0 ? (
            <p className="text-gray-500 text-center h-48 flex justify-center items-center">No new articles found to process.</p>
          ) : (
            <div className="max-h-60 overflow-y-auto space-y-2 pr-2">
              {discoveredArticles.map(article => (
                <label key={article.source_url} className="flex items-center p-2 rounded-md hover:bg-gray-100 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedUrls.has(article.source_url)}
                    onChange={() => handleCheckboxChange(article.source_url)}
                    className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span className="ml-3 text-sm text-gray-800">{article.title}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="target-date" className="block text-sm font-medium text-gray-700 mb-1">Target Date</label>
            <input type="date" id="target-date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} className="w-full p-2 border rounded-md"/>
          </div>
          <div>
            <label htmlFor="limit" className="block text-sm font-medium text-gray-700 mb-1">Article Limit</label>
            <input type="number" id="limit" value={limit} onChange={(e) => setLimit(e.target.value)} placeholder="Leave blank for all" className="w-full p-2 border rounded-md"/>
          </div>
        </div>

        <div className="mt-6 flex justify-end space-x-3">
          <button onClick={onClose} className="px-4 py-2 bg-gray-200 rounded-md">Cancel</button>
          <button onClick={handleRun} className="px-6 py-2 bg-green-600 text-white rounded-md">
            <Play className="w-5 h-5 inline mr-2" /> 
            {selectedUrls.size > 0 ? `Start Run (${selectedUrls.size} Selected)` : 'Start Run (All New)'}
          </button>
        </div>
      </div>
    </div>
  );
};


const ProjectsView = ({ onCreateNew, onRunProject, onEditProject }) => {
  const [projects, setProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [projectToRun, setProjectToRun] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const fetchProjects = async () => {
    try {
      setIsLoading(true);
      const response = await apiClient.get('/api/projects');
      setProjects(response.data);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch projects:", err);
      setError("Could not load projects. Please ensure the backend is running.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleDeleteProject = async (projectId, projectName) => {
    if (window.confirm(`Are you sure you want to delete the project "${projectName}"? This action cannot be undone.`)) {
        setDeletingId(projectId);
        try {
            await apiClient.delete(`/api/projects/${projectId}`);
            fetchProjects();
        } catch (err) {
            alert(`Failed to delete project: ${err.response?.data?.detail || 'Unknown error'}`);
            console.error(err);
        } finally {
            setDeletingId(null);
        }
    }
  };

  const handleRunClick = (project) => {
    // --- THE FIX: Add the 'brightdata_mcp' type to this condition ---
    if (project.project_type === 'phone_spec_scraper' || project.project_type === 'brightdata_mcp') {
      // For phone scrapers and Bright Data jobs, run immediately without a modal.
      if (window.confirm(`Are you sure you want to run the job "${project.project_name}"?`)) {
        onRunProject(project.project_id, {}); // Pass empty options
      }
    } else {
      // For standard articles, open the interactive options modal.
      setProjectToRun(project);
      setIsModalOpen(true);
    }
  };

  const handleCloseModal = () => {
    setProjectToRun(null);
    setIsModalOpen(false);
  };

  const handleConfirmRun = (projectId, options) => {
    onRunProject(projectId, options);
    handleCloseModal();
  };

  const handleRefreshDatabase = async () => {
    if (window.confirm("This will start a full sync with your live WordPress site. This may take a few minutes. Continue?")) {
        setIsRefreshing(true);
        try {
            // --- FIX: Call the correct endpoint that triggers our modified task ---
            await apiClient.post('/api/data/refresh-products');
            alert("Database refresh task started! It will run in the background. Please check the Celery logs for progress.");
            // This task is a background sync and doesn't return a job ID, so we just show an alert.
        } catch (err) {
            alert("Failed to start the sync task. Check the backend logs.");
        } finally {
            setIsRefreshing(false);
        }
    }
  };


  if (isLoading) {
    return <div className="flex justify-center items-center h-64"><Loader2 className="w-12 h-12 animate-spin text-indigo-600" /></div>;
  }
  if (error) {
    return (
      <div className="bg-red-50 border-l-4 border-red-400 p-4 w-full max-w-4xl">
        <div className="flex">
          <div className="py-1"><AlertTriangle className="h-6 w-6 text-red-500 mr-4" /></div>
          <div><p className="font-bold">Error</p><p className="text-sm">{error}</p></div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-6xl">
      {isModalOpen && (
        <RunWithOptionsModal
          project={projectToRun}
          onClose={handleCloseModal}
          onConfirm={handleConfirmRun}
        />
      )}

      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-800">Scraping Projects</h1>
          <p className="text-lg text-gray-600">Manage and run your saved scraping configurations.</p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={handleRefreshDatabase}
            disabled={isRefreshing}
            className="inline-flex items-center px-4 py-2 bg-gray-100 text-gray-700 font-semibold rounded-full shadow-sm hover:bg-gray-200 disabled:bg-gray-200 disabled:cursor-not-allowed transition"
          >
            {isRefreshing ? <Loader2 className="w-5 h-5 mr-2 animate-spin"/> : <RefreshCw className="w-5 h-5 mr-2"/>}
            {isRefreshing ? 'Refreshing...' : 'Refresh Product DB'}
          </button>

          <button onClick={onCreateNew} className="inline-flex items-center px-6 py-3 bg-indigo-600 text-white font-bold rounded-full shadow-lg hover:bg-indigo-700 transition transform hover:scale-105">
            <PlusCircle className="w-5 h-5 mr-2" /> Create New Project
          </button>
        </div>
      </div>

      {projects.length === 0 ? (
        <div className="text-center py-16 border-2 border-dashed border-gray-300 rounded-lg">
          <h3 className="text-xl font-semibold text-gray-700">No Projects Found</h3>
          <p className="text-gray-500 mt-2">Get started by creating your first scraping project.</p>
          <button onClick={onCreateNew} className="mt-4 inline-flex items-center px-5 py-2.5 bg-indigo-100 text-indigo-700 font-semibold rounded-lg hover:bg-indigo-200">
            Create New Project
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project) => (
            <div key={project.project_id} className="bg-white p-6 rounded-lg shadow-lg border border-gray-200 flex flex-col">
              <div className="flex-grow">
                <div className="flex justify-between items-start">
                  <span className={`inline-flex items-center px-2.5 py-1 text-xs font-semibold rounded-full ${
                    project.project_type === 'phone_spec_scraper' 
                    ? 'bg-purple-100 text-purple-800' 
                    : 'bg-blue-100 text-blue-800'
                  }`}>
                    {project.project_type === 'phone_spec_scraper' 
                      ? <Smartphone className="w-3.5 h-3.5 mr-1.5"/> 
                      : <Newspaper className="w-3.5 h-3.5 mr-1.5"/>
                    }
                    {project.project_type === 'phone_spec_scraper' ? 'Phone Scraper' : 'Standard Article'}
                  </span>
                  <span className="text-xs text-gray-500">ID: {project.project_id}</span>
                </div>
                <h3 className="text-xl font-bold text-gray-800 mt-3">{project.project_name}</h3>
                <p className="text-sm text-gray-600 mt-2 mb-4 truncate" title={project.scrape_config.initial_urls.join(', ')}>
                  {project.scrape_config.initial_urls[0] || 'No initial URL'}
                </p>
              </div>
              <div className="pt-4 border-t border-gray-200 flex items-center justify-between">
                <button
                  onClick={() => handleRunClick(project)}
                  className="inline-flex items-center px-4 py-2 bg-green-600 text-white font-semibold rounded-md hover:bg-green-700 text-sm"
                >
                  <Play className="w-4 h-4 mr-2" />Run
                </button>
                <div className="flex items-center space-x-2">
                  <button onClick={() => onEditProject(project)} className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-gray-100 rounded-full"><Edit className="w-4 h-4" /></button>
                  
                  <button 
                    onClick={() => handleDeleteProject(project.project_id, project.project_name)}
                    disabled={deletingId === project.project_id}
                    className="p-2 text-gray-500 hover:text-red-600 hover:bg-gray-100 rounded-full disabled:cursor-not-allowed"
                  >
                    {deletingId === project.project_id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                        <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ProjectsView;