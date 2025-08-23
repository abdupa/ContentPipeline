import React, { useState, useEffect, useRef } from 'react';
import apiClient from './apiClient'; // Correctly imported from our new central file
import Sidebar from './components/Sidebar.jsx';
import DashboardView from './components/DashboardView.jsx';
import ScraperWizardView from './components/ScraperWizardView.jsx';
import ProjectsView from './components/ProjectsView.jsx';
import JobStatusView from './components/JobStatusView.jsx';
import ApprovalQueueView from './components/ApprovalQueueView.jsx';
import ContentEditorView from './components/ContentEditorView.jsx';
import AllPostsView from './components/AllPostsView.jsx';
import ActionHistoryView from './components/ActionHistoryView.jsx';
import { HelpCircle, Bell, ChevronDown } from 'lucide-react';
import PublishedPostsView from './components/PublishedPostsView.jsx';
import ManualEditorView from './components/ManualEditorView.jsx';
import SettingsView from './components/SettingsView.jsx';
import PerformanceView from './components/PerformanceView.jsx';
import InsightsView from './components/InsightsView.jsx';


const App = () => {
  const [currentView, setCurrentView] = useState('dashboard');
  const [activeScrapeJobId, setActiveScrapeJobId] = useState(null);
  const [projectToEdit, setProjectToEdit] = useState(null);
  const [draftToEditId, setDraftToEditId] = useState(null);
  const intervalRef = useRef(null);

  // --- NEW: This hook runs once on initial load to check the URL ---
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.has('status')) {
      // If we are coming back from the Google OAuth flow,
      // force the view to the settings page.
      setCurrentView('settings');
    }
  }, []); // The empty array ensures this runs only once.

  const handleMenuItemClick = (itemName) => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (itemName === 'Dashboard') setCurrentView('dashboard');
    else if (itemName === 'Insights') setCurrentView('insights');
    else if (itemName === 'Performance') setCurrentView('performance');
    else if (itemName === 'Scraping Projects') setCurrentView('projects');
    else if (itemName === 'Manual Editor') setCurrentView('manualEditor');
    else if (itemName === 'Content Library') setCurrentView('allPosts');
    else if (itemName === 'Approval Queue') setCurrentView('approvalQueue');
    else if (itemName === 'Published Posts') setCurrentView('publishedPosts'); // <-- NEW
    else if (itemName === 'Action History') setCurrentView('actionHistory');
    else if (itemName === 'Settings') setCurrentView('settings');
    else alert(`Navigating to: ${itemName}`);
  };

  const onManualJobStarted = (jobId) => {
    setActiveScrapeJobId(jobId);
    setCurrentView('scrapeJobStatus');
  };

  const handleRunProject = async (projectId, options) => {
    try {
      const response = await apiClient.post(`/api/projects/${projectId}/run`, options);
      setActiveScrapeJobId(response.data.job_id);
      setCurrentView('scrapeJobStatus');
    } catch (error) {
      let errorMessage = "An unknown error occurred. Please check the backend logs.";
      if (error.response?.data?.detail) {
          const detail = error.response.data.detail;
          if (typeof detail === 'string') {
              errorMessage = detail;
          } else if (Array.isArray(detail)) {
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
    if (currentView === 'insights') return 'Insights';
    if (currentView === 'performance') return 'Performance';
    if (['projects', 'scrapeWizard', 'scrapeJobStatus'].includes(currentView)) return 'Scraping Projects';
    if (['approvalQueue', 'contentEditor'].includes(currentView)) return 'Approval Queue';
    if (currentView === 'manualEditor') return 'Manual Editor';
    if (currentView === 'allPosts') return 'Content Library';
    if (currentView === 'publishedPosts') return 'Published Posts'; // <-- NEW
    if (currentView === 'actionHistory') return 'Action History';
    if (currentView === 'settings') return 'Settings';
    return 'Dashboard';
  };
  
  const renderCurrentView = () => {
    switch (currentView) {
      case 'dashboard':
        return <DashboardView handleMenuItemClick={handleMenuItemClick} />;
      case 'insights':
        return <InsightsView />;
      case 'performance':
        return <PerformanceView />;
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
      case 'manualEditor': // <-- NEW
        return <ManualEditorView onJobStarted={onManualJobStarted} />;
      case 'publishedPosts': // <-- NEW
        return <PublishedPostsView onEditDraft={handleEditDraft} />;
      case 'allPosts':
        return <AllPostsView onEditDraft={handleEditDraft} />;
      case 'approvalQueue':
        return <ApprovalQueueView onEditDraft={handleEditDraft} />;
      case 'actionHistory':
        return <ActionHistoryView />;
      case 'settings': // <-- ADD THIS
        return <SettingsView />;
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