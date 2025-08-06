import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { PlusCircle, Play, Edit, Trash2, Loader2, AlertTriangle } from 'lucide-react';

const apiClient = axios.create({
  baseURL: `http://${window.location.hostname}:8000`,
});

const ProjectsView = ({ onCreateNew, onRunProject, onEditProject }) => {
  const [projects, setProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
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

    fetchProjects();
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
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-800">Scraping Projects</h1>
          <p className="text-lg text-gray-600">Manage and run your saved scraping configurations.</p>
        </div>
        <button
          onClick={onCreateNew}
          className="inline-flex items-center px-6 py-3 bg-indigo-600 text-white font-bold rounded-full shadow-lg hover:bg-indigo-700 transition transform hover:scale-105"
        >
          <PlusCircle className="w-5 h-5 mr-2" /> Create New Project
        </button>
      </div>

      {projects.length === 0 ? (
        <div className="text-center py-16 border-2 border-dashed border-gray-300 rounded-lg">
          <h3 className="text-xl font-semibold text-gray-700">No Projects Found</h3>
          <p className="text-gray-500 mt-2">Get started by creating your first scraping project.</p>
          <button
            onClick={onCreateNew}
            className="mt-4 inline-flex items-center px-5 py-2.5 bg-indigo-100 text-indigo-700 font-semibold rounded-lg hover:bg-indigo-200"
          >
            Create New Project
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project) => (
            <div key={project.project_id} className="bg-white p-6 rounded-lg shadow-lg border border-gray-200 flex flex-col">
              <div className="flex-grow">
                <div className="flex justify-between items-start">
                  <span className={`px-2 py-1 text-xs font-semibold rounded-full ${project.project_type === 'News' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'}`}>
                    {project.project_type}
                  </span>
                  <span className="text-xs text-gray-500">ID: {project.project_id}</span>
                </div>
                <h3 className="text-xl font-bold text-gray-800 mt-3">{project.project_name}</h3>
                <p className="text-sm text-gray-600 mt-2 mb-4">
                  {project.scrape_config.initial_urls[0]}
                </p>
              </div>
              <div className="pt-4 border-t border-gray-200 flex items-center justify-between">
                <button
                  onClick={() => onRunProject(project.project_id)}
                  className="inline-flex items-center px-4 py-2 bg-green-600 text-white font-semibold rounded-md hover:bg-green-700 text-sm"
                >
                  <Play className="w-4 h-4 mr-2" />Run
                </button>
                <div className="flex items-center space-x-2">
                  <button onClick={() => onEditProject(project)} className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-gray-100 rounded-full"><Edit className="w-4 h-4" /></button>
                  <button className="p-2 text-gray-500 hover:text-red-600 hover:bg-gray-100 rounded-full"><Trash2 className="w-4 h-4" /></button>
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