import React, { useState, useEffect } from 'react';
import apiClient from './apiClient';
import Sidebar from './components/Sidebar.jsx';
import DashboardView from './components/DashboardView.jsx';
import ScraperWizardView from './components/ScraperWizardView.jsx';
import ProjectsView from './components/ProjectsView.jsx';
import JobStatusView from './components/JobStatusView.jsx';
import ApprovalQueueView from './components/ApprovalQueueView.jsx';
import ContentEditorView from './components/ContentEditorView.jsx';
import AllPostsView from './components/AllPostsView.jsx';
import ActionHistoryView from './components/ActionHistoryView.jsx';
import PublishedPostsView from './components/PublishedPostsView.jsx';
import ManualEditorView from './components/ManualEditorView.jsx';
import SettingsView from './components/SettingsView.jsx';
import PerformanceView from './components/PerformanceView.jsx';
import InsightsView from './components/InsightsView.jsx';
import ToolsView from './components/ToolsView.jsx';
import PriceUpdateReviewView from './components/PriceUpdateReviewView.jsx';
import SyncReportView from './components/SyncReportView.jsx';
import { HelpCircle, Bell, ChevronDown } from 'lucide-react';

const App = () => {
  const [currentView, setCurrentView] = useState('dashboard');
  const [activeJobId, setActiveJobId] = useState(null);
  const [projectToEdit, setProjectToEdit] = useState(null);
  const [draftToEditId, setDraftToEditId] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.has('status')) {
      setCurrentView('settings');
    }
  }, []);

  const handleMenuItemClick = (itemName) => {
    if (itemName === 'Dashboard') setCurrentView('dashboard');
    else if (itemName === 'Insights') setCurrentView('insights');
    else if (itemName === 'Performance') setCurrentView('performance');
    else if (itemName === 'Scraping Projects') setCurrentView('projects');
    else if (itemName === 'Manual Editor') setCurrentView('manualEditor');
    else if (itemName === 'Product Database') setCurrentView('productDatabase');
    else if (itemName === 'Content Library') setCurrentView('allPosts');
    else if (itemName === 'Approval Queue') setCurrentView('approvalQueue');
    else if (itemName === 'Published Posts') setCurrentView('publishedPosts');
    else if (itemName === 'Action History') setCurrentView('actionHistory');
    else if (itemName === 'Tools') setCurrentView('tools');
    else if (itemName === 'Settings') setCurrentView('settings');
  };

  const onJobStarted = (jobId, originView = 'projects') => {
    setActiveJobId(jobId);
    localStorage.setItem('jobOriginView', originView);
    setCurrentView('scrapeJobStatus');
  };

  const handleRunProject = async (projectId, options) => {
    // --- NEW: Handle direct job_id passthrough from sync button ---
    if (options && options.job_id) {
        onJobStarted(options.job_id, 'projects');
        return;
    }
    try {
      const response = await apiClient.post(`/api/projects/${projectId}/run`, options);
      onJobStarted(response.data.job_id, 'projects');
    } catch (error) {
      alert(`Failed to start project run: ${error.response?.data?.detail || 'Unknown error'}`);
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
    const origin = localStorage.getItem('jobOriginView');
    if (currentView === 'scrapeJobStatus') {
        if (origin === 'tools') return 'Tools';
        return 'Scraping Projects';
    }
    // ... (rest of the function is the same, this is a simplified version)
    return 'Dashboard'; // Fallback
  };
  
  const renderCurrentView = () => {
    switch (currentView) {
      case 'dashboard': return <DashboardView handleMenuItemClick={handleMenuItemClick} />;
      case 'insights': return <InsightsView />;
      case 'performance': return <PerformanceView />;
      case 'projects': return <ProjectsView onCreateNew={() => setCurrentView('scrapeWizard')} onRunProject={handleRunProject} onEditProject={handleEditProject} />;
      case 'scrapeWizard': return <ScraperWizardView projectToEdit={projectToEdit} onProjectSaved={() => setCurrentView('projects')} />;
      // case 'scrapeJobStatus': return <JobStatusView jobId={activeJobId} onReset={setCurrentView} onNavigateToQueue={() => setCurrentView('approvalQueue')} onNavigateToReview={(jobId) => { setActiveJobId(jobId); setCurrentView('priceReview'); }} onNavigateToReport={(jobId) => { setActiveJobId(jobId); setCurrentView('syncReport'); }} />;
      case 'scrapeJobStatus': return <JobStatusView 
        jobId={activeJobId} 
        onReset={setCurrentView} 
        onNavigateToQueue={() => setCurrentView('approvalQueue')} 
        onNavigateToReview={(jobId) => { setActiveJobId(jobId); setCurrentView('priceReview'); }}
        onNavigateToReport={(jobId) => { setActiveJobId(jobId); setCurrentView('syncReport'); }} // <-- ADD THIS PROP
      />;
      case 'manualEditor': return <ManualEditorView onJobStarted={(jobId) => onJobStarted(jobId, 'manualEditor')} />;
      case 'priceReview': return <PriceUpdateReviewView jobId={activeJobId} onJobStarted={onJobStarted} onBack={() => setCurrentView('tools')} />;
      case 'syncReport': return <SyncReportView jobId={activeJobId} onBack={() => setCurrentView('scrapeJobStatus')} />;
      case 'productDatabase': return <ProductDatabaseView />;
      case 'publishedPosts': return <PublishedPostsView onEditDraft={handleEditDraft} />;
      case 'allPosts': return <AllPostsView onEditDraft={handleEditDraft} />;
      case 'approvalQueue': return <ApprovalQueueView onEditDraft={handleEditDraft} />;
      case 'actionHistory': return <ActionHistoryView />;
      case 'tools': return <ToolsView onJobStarted={onJobStarted} onNavigateToReview={(jobId) => { setActiveJobId(jobId); setCurrentView('priceReview'); }} />;
      case 'settings': return <SettingsView />;
      case 'contentEditor': return <ContentEditorView draftId={draftToEditId} onBack={() => setCurrentView('approvalQueue')} />;
      default: return <DashboardView />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex font-sans">
      <Sidebar onMenuItemClick={handleMenuItemClick} activeItem={getActiveSidebarItem()} />
      <div className="flex-1 flex flex-col">
        <header className="bg-white shadow-sm p-4 flex items-center justify-between border-b border-gray-200">
          <div className="text-2xl font-extrabold text-gray-800 tracking-tight">ContentGen.ai</div>
          <div className="flex items-center space-x-4">
             {/* Header buttons */}
          </div>
        </header>
        <main className="flex-1 flex items-start justify-center p-4 sm-p-8 overflow-auto">{renderCurrentView()}</main>
      </div>
    </div>
  );
};

export default App;