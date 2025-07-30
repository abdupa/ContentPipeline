import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import Sidebar from './components/Sidebar.jsx';
import InitialUploadView from './components/InitialUploadView.jsx';
import AnalysisResultsView from './components/AnalysisResultsView.jsx';
import ContentCompleteView from './components/ContentCompleteView.jsx';
import DashboardView from './components/DashboardView.jsx';
import ScraperWizardView from './components/ScraperWizardView.jsx'; // 1. Import the new component
import { HelpCircle, Bell, ChevronDown } from 'lucide-react';

const backendApiUrl = `http://${window.location.hostname}:8000`;

const apiClient = axios.create({
  baseURL: backendApiUrl,
});

const App = () => {
  const [currentView, setCurrentView] = useState('dashboard');
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedFileName, setSelectedFileName] = useState('');
  const [analysisResults, setAnalysisResults] = useState(null);
  const [jobDetails, setJobDetails] = useState(null);
  const [jobId, setJobId] = useState(null);
  const intervalRef = useRef(null);

  // --- Event Handlers ---
  const resetUploadState = () => {
    setCurrentView('initialUpload');
    setSelectedFile(null);
    setSelectedFileName('');
    setAnalysisResults(null);
    setJobDetails(null);
    setJobId(null);
  };

  const handleViewContent = () => {
    alert("This would navigate to a page showing all generated content.");
    setCurrentView('dashboard');
  };

  const handleDownloadResults = () => {
    if (!jobDetails || !jobDetails.results || jobDetails.results.length === 0) {
      alert("No results to download.");
      return;
    }
    const csvRows = [];
    csvRows.push(['Title', 'Status', 'Generated On', 'URL', 'Notes'].join(','));
    jobDetails.results.forEach(row => {
      const title = `"${(row.title || '').replace(/"/g, '""')}"`;
      const notes = `"${(row.notes || '').replace(/"/g, '""')}"`;
      csvRows.push([title, row.status, row.generatedOn, row.actions, notes].join(','));
    });
    const csvString = csvRows.join('\n');
    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.setAttribute('download', `job_${jobId}_results.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleMenuItemClick = (itemName) => {
    if (itemName === 'Upload CSV') {
      resetUploadState();
    } else if (itemName === 'Dashboard') {
      setCurrentView('dashboard');
    } else if (itemName === 'Scrape Content') { // 2. Add a case for the new view
      setCurrentView('scrapeContent');
    } else {
      alert(`Navigating to: ${itemName}`);
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      setSelectedFileName(file.name);
    }
  };

  const handleUploadAndAnalyze = async () => {
    if (!selectedFile) {
      alert("Please select a file first.");
      return;
    }
    const formData = new FormData();
    formData.append("file", selectedFile);
    try {
      const response = await apiClient.post('/upload-and-analyze/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setAnalysisResults(response.data);
      setJobId(response.data.job_id);
      setCurrentView('analysisResults');
    } catch (error) {
      alert(error.response?.data?.detail || "File analysis failed.");
    }
  };

  const handleStartGeneration = async () => {
    if (!jobId) {
      alert("No job ID found. Please try uploading again.");
      return;
    }
    try {
      await apiClient.post(`/start-content-generation/${jobId}`);
      setCurrentView('jobMonitoring');
    } catch (error) {
      alert(error.response?.data?.detail || "Could not start content generation.");
    }
  };

  // Polling Logic
  useEffect(() => {
    const stopPolling = () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
    if (currentView === 'jobMonitoring' && jobId) {
      const fetchJobStatus = async () => {
        try {
          const response = await apiClient.get(`/jobs/${jobId}/status`);
          setJobDetails(response.data);
          if (response.data.processed_rows === response.data.total_rows && response.data.total_rows > 0) {
            stopPolling();
          }
        } catch (error) {
          console.error("Error fetching job status:", error);
          stopPolling();
        }
      };
      stopPolling();
      fetchJobStatus();
      intervalRef.current = setInterval(fetchJobStatus, 3000);
    }
    return stopPolling;
  }, [currentView, jobId]);

  // Helper Function
  const getActiveSidebarItem = () => {
    if (['initialUpload', 'analysisResults', 'jobMonitoring'].includes(currentView)) {
      return 'Upload CSV';
    } else if (currentView === 'dashboard') {
      return 'Dashboard';
    } else if (currentView === 'scrapeContent') { // 3. Add a case to highlight the new menu item
      return 'Scrape Content';
    }
    return '';
  };
  
  // Render Logic
  const renderCurrentView = () => {
    switch (currentView) {
      case 'dashboard':
        return <DashboardView />;
      case 'initialUpload':
        return <InitialUploadView onFileSelect={handleFileSelect} onUpload={handleUploadAndAnalyze} selectedFileName={selectedFileName} />;
      case 'analysisResults':
        if (!analysisResults) return <div>Analyzing file...</div>;
        return <AnalysisResultsView 
                  analysisData={analysisResults}
                  onFileChange={resetUploadState}
                  onStartContentGeneration={handleStartGeneration} 
                />;
      case 'jobMonitoring':
        if (!jobDetails) return <div>Loading job details...</div>;
        
        const adaptedJobStatus = {
            totalPosts: jobDetails.total_rows,
            successfulPosts: jobDetails.processed_rows,
            errorsFound: (jobDetails.results || []).filter(r => r.status === 'Failed').length, 
        };
        const adaptedContentData = jobDetails.results || [];

        return <ContentCompleteView 
                  jobStatus={adaptedJobStatus} 
                  contentData={adaptedContentData}
                  onGenerateMore={resetUploadState}
                  onViewContent={handleViewContent}
                  handleDownloadResults={handleDownloadResults}
                />;
      
      case 'scrapeContent': // 4. Add a case to render the new component
        return <ScraperWizardView />;

      default:
        return <DashboardView />;
    }
  };

  // Main Render
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