import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import Sidebar from './components/Sidebar.jsx';
import DashboardView from './components/DashboardView.jsx';
import ScraperWizardView from './components/ScraperWizardView.jsx';
import ProjectsView from './components/ProjectsView.jsx';
import JobStatusView from './components/JobStatusView.jsx';
import ApprovalQueueView from './components/ApprovalQueueView.jsx';
import ContentEditorView from './components/ContentEditorView.jsx';
import { HelpCircle, Bell, ChevronDown } from 'lucide-react';

const backendApiUrl = `http://${window.location.hostname}:8000`;

const apiClient = axios.create({
  baseURL: backendApiUrl,
});

const App = () => {
  const [currentView, setCurrentView] = useState('dashboard');
  const [activeScrapeJobId, setActiveScrapeJobId] = useState(null);
  const [projectToEdit, setProjectToEdit] = useState(null);
  const [draftToEditId, setDraftToEditId] = useState(null);
  const intervalRef = useRef(null);

  const handleMenuItemClick = (itemName) => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (itemName === 'Dashboard') setCurrentView('dashboard');
    else if (itemName === 'Scrape Content') setCurrentView('projects');
    else if (itemName === 'Approval Queue') setCurrentView('approvalQueue');
    else alert(`Navigating to: ${itemName}`);
  };

  const handleRunProject = async (projectId, options) => {
    try {
      const response = await apiClient.post(`/api/projects/${projectId}/run`, options);
      setActiveScrapeJobId(response.data.job_id);
      setCurrentView('scrapeJobStatus');
    } catch (error) {
      // *** THE FIX: Improved error message handling ***
      let errorMessage = "An unknown error occurred. Please check the backend logs.";
      if (error.response?.data?.detail) {
          const detail = error.response.data.detail;
          if (typeof detail === 'string') {
              errorMessage = detail;
          } else if (Array.isArray(detail)) {
              // Format FastAPI validation errors for readability
              errorMessage = detail.map(err => `Error in field '${err.loc[1]}': ${err.msg}`).join('\n');
          } else {
              errorMessage = JSON.stringify(detail);
          }
      }
      alert(`Failed to start project run:\n\n${errorMessage}`);
    }
  };

  const handleEditProject = (project) => {
    setProjectToEdit(project);
    setCurrentView('scrapeWizard');
  };
  
  const handleEditDraft = (draftId) => {
    setDraftToEditId(draftId);
    setCurrentView('contentEditor');
  };

  const getActiveSidebarItem = () => {
    if (['projects', 'scrapeWizard', 'scrapeJobStatus'].includes(currentView)) return 'Scrape Content';
    if (['approvalQueue', 'contentEditor'].includes(currentView)) return 'Approval Queue';
    return 'Dashboard';
  };
  
  const renderCurrentView = () => {
    switch (currentView) {
      case 'dashboard':
        return <DashboardView />;
      case 'projects':
        return <ProjectsView 
                  onCreateNew={() => { setProjectToEdit(null); setCurrentView('scrapeWizard'); }} 
                  onRunProject={handleRunProject}
                  onEditProject={handleEditProject}
                />;
      case 'scrapeWizard':
        return <ScraperWizardView 
                  projectToEdit={projectToEdit}
                  onProjectSaved={() => { setProjectToEdit(null); setCurrentView('projects'); }} 
                />;
      case 'scrapeJobStatus':
        return <JobStatusView jobId={activeScrapeJobId} onReset={() => setCurrentView('projects')} />;
      case 'approvalQueue':
        return <ApprovalQueueView onEditDraft={handleEditDraft} />;
      case 'contentEditor':
        return <ContentEditorView draftId={draftToEditId} onBack={() => setCurrentView('approvalQueue')} />;
      default:
        return <DashboardView />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex font-sans">
      <Sidebar onMenuItemClick={handleMenuItemClick} activeItem={getActiveSidebarItem()} />
      <div className="flex-1 flex flex-col">
        <header className="bg-white shadow-sm p-4 flex items-center justify-between border-b border-gray-200">
          <div className="text-2xl font-extrabold text-gray-800 tracking-tight">ContentGen.ai</div>
          <div className="flex items-center space-x-4">
            <button className="hidden sm:inline-flex items-center px-4 py-2 bg-gray-100 text-gray-700 rounded-full text-sm font-semibold hover:bg-gray-200"><HelpCircle className="w-4 h-4 mr-1" />Help</button>
            <button className="relative p-2 rounded-full hover:bg-gray-100"><Bell className="w-6 h-6 text-gray-600" /><span className="absolute top-1 right-1 block h-2 w-2 rounded-full bg-red-500 border-2 border-white"></span></button>
            <div className="relative">
              <button className="flex items-center space-x-2 p-1.5 rounded-full hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-400">
                <img src="https://placehold.co/32x32/6366f1/ffffff?text=A" alt="User Avatar" className="w-8 h-8 rounded-full border-2 border-indigo-500" />
                <span className="text-gray-700 font-medium hidden md:block">Abe</span>
                <ChevronDown className="w-4 h-4 text-gray-500" />
              </button>
            </div>
          </div>
        </header>
        <main className="flex-1 flex items-start justify-center p-4 sm:p-8 overflow-auto">{renderCurrentView()}</main>
      </div>
    </div>
  );
};

export default App;
