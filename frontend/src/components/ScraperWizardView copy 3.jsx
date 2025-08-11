import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { PlusCircle, Trash2, ArrowRight, Target, Loader2, Save, List, MousePointerClick, Check, X } from 'lucide-react';

const apiClient = axios.create({
  baseURL: `http://${window.location.hostname}:8000`,
});

// --- Child component for Step 1 ---
const Step1_ProjectDetails = ({ projectName, setProjectName, projectType, setProjectType, onNext }) => {
    return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800">Step 1: Project Details</h2>
      <p className="text-gray-600 mt-1 mb-6">Give your project a name and choose its type. The type will determine the options in Step 3.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div>
          <label htmlFor="project-name" className="block text-sm font-medium text-gray-700 mb-1">Project Name</label>
          <input type="text" id="project-name" value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder="e.g., Latest Smartphone News" className="w-full p-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"/>
        </div>
        <div>
          <label htmlFor="project-type" className="block text-sm font-medium text-gray-700 mb-1">Project Type</label>
          <select id="project-type" value={projectType} onChange={(e) => setProjectType(e.target.value)} className="w-full p-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500">
            <option value="standard_article">Standard Article</option>
            <option value="phone_spec_scraper">Phone Spec Scraper</option>
          </select>
        </div>
      </div>
      <div className="mt-8 text-right">
        <button type="button" onClick={onNext} disabled={!projectName.trim()} className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-sm hover:bg-indigo-700 disabled:bg-gray-300 flex items-center gap-2 ml-auto">Next: Define URLs <ArrowRight className="w-5 h-5" /></button>
      </div>
    </div>
  );
};

// --- Child component for Step 2 ---
const Step2_LinkSelection = ({ urlInput, setUrlInput, onNext, onBack, projectType }) => {
    const [scrapeMode, setScrapeMode] = useState('interactive');
    const [capturedLinks, setCapturedLinks] = useState([]);
    const [previewHtml, setPreviewHtml] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [previewJobId, setPreviewJobId] = useState(null);
    const [currentPreviewBaseUrl, setCurrentPreviewBaseUrl] = useState(null);
    const intervalRef = useRef(null);
    const [selectionSuggestion, setSelectionSuggestion] = useState(null);

    const stopPolling = () => { if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; } };

    const handleFetchPreview = async () => {
        const urls = urlInput.split('\n').filter(Boolean);
        if (!urls[0]) { alert("Please provide at least one starting URL for the preview."); return; }
        const urlToFetch = urls[0];
        
        setCapturedLinks([]);
        setSelectionSuggestion(null);
        setCurrentPreviewBaseUrl(urlToFetch);
        setIsLoading(true); setPreviewHtml(""); stopPolling();
        try {
            const response = await apiClient.post("/api/request-page-preview/", { url: urlToFetch, project_type: projectType });
            setPreviewJobId(response.data.job_id);
        } catch (error) {
            setIsLoading(false); setPreviewHtml(`<div class='p-4 text-red-600'>Error starting preview job.</div>`);
        }
    };

    useEffect(() => {
        if (!previewJobId) return;
        const pollForResult = async () => {
            try {
                const response = await apiClient.get(`/api/get-preview-result/${previewJobId}`);
                const { status, html, error } = response.data;
                if (status === 'complete') { setPreviewHtml(html); setIsLoading(false); stopPolling(); }
                else if (status === 'failed') { setPreviewHtml(`<div class='p-4 text-red-600'><b>Preview failed.</b><br/>Error: ${error}</div>`); setIsLoading(false); stopPolling(); }
            } catch (err) { setIsLoading(false); stopPolling(); }
        };
        intervalRef.current = setInterval(pollForResult, 2500);
        return stopPolling;
    }, [previewJobId]);

    useEffect(() => {
        const handleMessage = (event) => {
            if (event.data?.type === 'selection-updated') {
                setCapturedLinks(event.data.elements);
                setSelectionSuggestion(null);
            } else if (event.data?.type === 'selection-suggestion') {
                setSelectionSuggestion(event.data);
            }
        };
        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, []);

    const handleNext = () => {
        if (scrapeMode === 'manual') {
            if (!urlInput.trim()) { alert("Please enter at least one URL in the list."); return; }
        } else {
            if (capturedLinks.length === 0) { alert("Please select at least one link from the preview."); return; }
            const base = currentPreviewBaseUrl || urlInput.split('\n')[0];
            const capturedUrls = capturedLinks.map(link => new URL(link.href, base).href);
            setUrlInput(capturedUrls.join('\n'));
        }
        onNext();
    };

    const handleSelectAll = () => {
        setCapturedLinks(selectionSuggestion.all);
        setSelectionSuggestion(null);
    };

    const handleSelectOne = () => {
        setCapturedLinks([selectionSuggestion.single]);
        setSelectionSuggestion(null);
    };

    return (
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Step 2: Define Target URLs</h2>
          <div className="flex rounded-lg p-1 bg-gray-200 w-fit mb-6">
              <button onClick={() => setScrapeMode('interactive')} className={`px-4 py-2 text-sm font-semibold rounded-md transition-colors flex items-center gap-2 ${scrapeMode === 'interactive' ? 'bg-white text-blue-600 shadow' : 'bg-transparent text-gray-600'}`}><MousePointerClick className="w-4 h-4" /> Interactive</button>
              <button onClick={() => setScrapeMode('manual')} className={`px-4 py-2 text-sm font-semibold rounded-md transition-colors flex items-center gap-2 ${scrapeMode === 'manual' ? 'bg-white text-blue-600 shadow' : 'bg-transparent text-gray-600'}`}><List className="w-4 h-4" /> Manual List</button>
          </div>

          {scrapeMode === 'manual' ? (
            <div>
                <label htmlFor="url-input" className="block text-sm font-medium text-gray-700 mb-1">URLs to Scrape (one per line)</label>
                <textarea id="url-input" value={urlInput} onChange={(e) => setUrlInput(e.target.value)} placeholder="https://www.example.com/page-1&#10;https://www.example.com/page-2" className="w-full h-64 p-2 border rounded-md font-mono text-sm"/>
            </div>
          ) : (
            <div className="relative">
              <p className="text-gray-600 mt-1 mb-4">Enter a starting URL below, fetch the preview, then click on links to process.</p>
              <div className="flex gap-4 mb-4">
                <input type="text" value={urlInput.split('\n')[0] || ''} onChange={e => setUrlInput(e.target.value)} placeholder="Enter a starting URL to preview..." className="w-full p-2 border rounded-md" />
                <button type="button" onClick={handleFetchPreview} disabled={isLoading} className="px-4 py-2 bg-blue-600 text-white font-semibold rounded-md shadow-sm hover:bg-blue-700 disabled:bg-gray-400 whitespace-nowrap">{isLoading ? <span className="flex items-center"><Loader2 className="animate-spin mr-2" /> Loading...</span> : "Fetch Preview"}</button>
              </div>
              <div className="border-2 border-gray-300 rounded-lg bg-gray-100 mb-6"><div className="w-full h-96 bg-white"><iframe srcDoc={previewHtml || "<p class='p-4 text-gray-500'>Click 'Fetch Preview'</p>"} title="Live Page Preview" className="w-full h-full" sandbox="allow-scripts allow-same-origin" /></div></div>
              
              {selectionSuggestion && (
                  <div className="absolute bottom-24 left-1/2 -translate-x-1/2 w-full max-w-lg bg-white p-4 rounded-lg shadow-2xl border-2 border-blue-500 animate-fade-in-up">
                      <p className="text-center font-semibold text-gray-800">Smart Selection</p>
                      <p className="text-center text-gray-600 my-2">We found <strong className="text-blue-600">{selectionSuggestion.count}</strong> similar links on the page.</p>
                      <div className="flex justify-center gap-4 mt-3">
                          <button onClick={handleSelectAll} className="flex-1 inline-flex items-center justify-center px-4 py-2 bg-blue-600 text-white font-semibold rounded-md hover:bg-blue-700"><Check className="w-5 h-5 mr-2" /> Select All ({selectionSuggestion.count})</button>
                          <button onClick={handleSelectOne} className="flex-1 inline-flex items-center justify-center px-4 py-2 bg-gray-200 text-gray-800 font-semibold rounded-md hover:bg-gray-300"><X className="w-5 h-5 mr-2" /> Just This One</button>
                      </div>
                  </div>
              )}

              <label className="block text-lg font-medium text-gray-700">Captured Links ({capturedLinks.length})</label>
              <p className="text-sm text-gray-500 mb-2">The URLs of the links you select will become the list of pages to scrape.</p>
            </div>
          )}

          <div className="mt-8 flex justify-between">
            <button type="button" onClick={onBack} className="px-6 py-2 bg-gray-200 text-gray-800 font-semibold rounded-md hover:bg-gray-300">Back</button>
            <button type="button" onClick={handleNext} className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-sm hover:bg-indigo-700 flex items-center gap-2">Next: Define Fields & Prompts <ArrowRight className="w-5 h-5" /></button>
          </div>
        </div>
    );
};

// --- Child component for Step 3 ---
const Step3_FieldsAndPrompts = ({ 
    selectedModelUrl, 
    elementRules, setElementRules, 
    onBack, onSaveProject, isSaving,
    projectType,
    llmPrompt, setLlmPrompt,
    wooPrompt, setWooPrompt,
    wpPrompt, setWpPrompt
}) => {
    const [previewHtml, setPreviewHtml] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [previewJobId, setPreviewJobId] = useState(null);
    const intervalRef = useRef(null);
    const stopPolling = () => { if (intervalRef.current) { clearInterval(intervalRef.current); } };

    useEffect(() => {
        const fetchPreview = async () => {
            if (!selectedModelUrl) return;
            setIsLoading(true); setPreviewHtml(""); stopPolling();
            try {
                const response = await apiClient.post("/api/request-page-preview/", { url: selectedModelUrl, project_type: projectType });
                setPreviewJobId(response.data.job_id);
            } catch (error) { setIsLoading(false); setPreviewHtml(`<div class='p-4 text-red-600'>Error starting preview job.</div>`); }
        };
        fetchPreview(); return stopPolling;
    }, [selectedModelUrl, projectType]);

    useEffect(() => {
        if (!previewJobId) return;
        const pollForResult = async () => {
            try {
                const response = await apiClient.get(`/api/get-preview-result/${previewJobId}`);
                const { status, html, error } = response.data;
                if (status === 'complete' || status === 'failed') {
                    setPreviewHtml(html || `<div class='p-4 text-red-600'><b>Preview failed.</b><br/>Error: ${error}</div>`);
                    setIsLoading(false); stopPolling();
                }
            } catch (err) { setIsLoading(false); stopPolling(); }
        };
        intervalRef.current = setInterval(pollForResult, 2000);
        return stopPolling;
    }, [previewJobId]);

    useEffect(() => {
        const handleMessage = (event) => {
            if (event.data && event.data.type === 'selection-updated') {
                const incomingElements = event.data.elements;
                setElementRules(prevRules => {
                    const nameMap = new Map(prevRules.map(r => [r.selector, r.name]));
                    return incomingElements.map((el, index) => ({ name: nameMap.get(el.selector) || `field_${index + 1}`, selector: el.selector, value: el.value }));
                });
            }
        };
        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, [setElementRules]);

    const handleRuleChange = (index, field, value) => { setElementRules(prevRules => prevRules.map((rule, i) => (i === index ? { ...rule, [field]: value } : rule))); };
    const handleRemoveRule = (indexToRemove) => { setElementRules(prevRules => prevRules.filter((_, index) => index !== indexToRemove)); };

    const isSaveDisabled = () => {
        if (isSaving || elementRules.length === 0) return true;
        if (projectType === 'phone_spec_scraper') {
            return !wooPrompt.trim() || !wpPrompt.trim();
        }
        return !llmPrompt.trim();
    };

    return (
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Step 3: Define Data Fields & AI Prompt</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="border-2 border-gray-300 rounded-lg bg-gray-100">
              <div className="w-full h-[30rem] bg-white">
                <iframe srcDoc={previewHtml || (isLoading ? "<p class='p-4 text-center'><span class='animate-spin inline-block w-6 h-6 border-4 border-current border-t-transparent text-blue-600 rounded-full'></span><br/>Loading...</p>" : "<p class='p-4 text-gray-500'>Preview will load here.</p>")} title="Live Detail Page Preview" className="w-full h-full" sandbox="allow-scripts allow-same-origin"/>
              </div>
            </div>
            <div>
              <div>
                <label className="block text-lg font-medium text-gray-700">Extraction Fields</label>
                <p className="text-sm text-gray-500 mb-2">Click in the preview to add rows. Edit field names to be simple, one-word placeholders (e.g., 'title', 'summary').</p>
                <div className="overflow-x-auto rounded-lg shadow-md border border-gray-200 bg-white max-h-60">
                  <table className="min-w-full table-fixed">
                    <thead className="bg-gray-50 sticky top-0"><tr><th className="w-1/3 px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Field Name</th><th className="w-2/3 px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Selector</th><th className="px-4 py-2"></th></tr></thead>
                    <tbody className="divide-y divide-gray-200">
                      {elementRules.length > 0 ? (elementRules.map((rule, index) => (
                        <tr key={rule.selector || index}>
                          <td className="px-4 py-2"><input type="text" value={rule.name} onChange={(e) => handleRuleChange(index, 'name', e.target.value)} className="w-full p-1 border border-gray-300 rounded-md font-mono text-sm"/></td>
                          <td className="px-4 py-2 whitespace-nowrap text-sm font-mono text-gray-600 truncate">{rule.selector}</td>
                          <td className="px-4 py-2 text-center"><button type="button" onClick={() => handleRemoveRule(index)} className="text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4"/></button></td>
                        </tr>
                      ))) : (<tr><td colSpan="3" className="px-4 py-3 text-sm text-center text-gray-400">Click an element...</td></tr>)}
                    </tbody>
                  </table>
                </div>
              </div>
              
              {projectType === 'phone_spec_scraper' ? (
                <div className="mt-6 space-y-4">
                    <div>
                        <label htmlFor="woo-prompt" className="block text-lg font-medium text-gray-700">WooCommerce Product Prompt</label>
                        <textarea id="woo-prompt" value={wooPrompt} onChange={(e) => setWooPrompt(e.target.value)} placeholder="Create a comprehensive product overview..." className="w-full h-32 p-2 border border-gray-300 rounded-md font-mono text-sm"/>
                    </div>
                    <div>
                        <label htmlFor="wp-prompt" className="block text-lg font-medium text-gray-700">WordPress Price Post Prompt</label>
                        <textarea id="wp-prompt" value={wpPrompt} onChange={(e) => setWpPrompt(e.target.value)} placeholder="Write a blog post about the price..." className="w-full h-32 p-2 border border-gray-300 rounded-md font-mono text-sm"/>
                    </div>
                </div>
              ) : (
                <div className="mt-6">
                    <label htmlFor="llm-prompt" className="block text-lg font-medium text-gray-700">LLM Prompt Template</label>
                    <textarea id="llm-prompt" value={llmPrompt} onChange={(e) => setLlmPrompt(e.target.value)} placeholder="Based on the article with title '{title}'..." className="w-full h-48 p-2 border border-gray-300 rounded-md font-mono text-sm"/>
                </div>
              )}
            </div>
          </div>
          <div className="mt-8 flex justify-between">
            <button type="button" onClick={onBack} className="px-6 py-2 bg-gray-200 text-gray-800 font-semibold rounded-md hover:bg-gray-300">Back</button>
            <button type="button" onClick={onSaveProject} disabled={isSaveDisabled()} className="px-8 py-3 bg-green-600 text-white font-bold text-lg rounded-full shadow-lg hover:bg-green-700 disabled:bg-gray-400 flex items-center gap-2">
                {isSaving ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
                {isSaving ? 'Saving...' : 'Save Project'}
            </button>
          </div>
        </div>
    );
};


const ScraperWizardView = ({ onProjectSaved, projectToEdit }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [isSaving, setIsSaving] = useState(false);
  
  const [projectName, setProjectName] = useState('');
  const [projectType, setProjectType] = useState('standard_article');
  const [urlInput, setUrlInput] = useState('');
  const [elementRules, setElementRules] = useState([]);
  const [llmPrompt, setLlmPrompt] = useState('');
  const [wooPrompt, setWooPrompt] = useState('');
  const [wpPrompt, setWpPrompt] = useState('');
  
  useEffect(() => {
    if (projectToEdit) {
      setProjectName(projectToEdit.project_name);
      setProjectType(projectToEdit.project_type);
      const config = projectToEdit.scrape_config;

      if (projectToEdit.project_type === 'phone_spec_scraper') {
        try {
          const prompts = JSON.parse(projectToEdit.llm_prompt_template);
          setWooPrompt(prompts.product_prompt || '');
          setWpPrompt(prompts.price_prompt || '');
        } catch (e) { console.error("Could not parse prompts:", e); }
      } else {
        setLlmPrompt(projectToEdit.llm_prompt_template);
      }
      setUrlInput(config.initial_urls.join('\n'));
      setElementRules(config.element_rules.map(rule => ({ ...rule, value: '' })));
    } else {
      resetWizardState();
    }
  }, [projectToEdit]);

  const resetWizardState = () => {
    setCurrentStep(1); setIsSaving(false); setProjectName('');
    setProjectType('standard_article'); setUrlInput('');
    setElementRules([]); setLlmPrompt('');
    setWooPrompt(''); setWpPrompt('');
  };

  const handleSaveProject = async () => {
    setIsSaving(true);
    
    const urls = urlInput.split('\n').filter(Boolean);
    const scrapeConfig = {
      scrape_type: 'direct', 
      initial_urls: urls,
      crawling_levels: [],
      final_urls: [],
      modelUrls: urls, 
      element_rules: elementRules.map(({ name, selector }) => ({ name, selector })),
    };

    let promptTemplate;
    if (projectType === 'phone_spec_scraper') {
        promptTemplate = JSON.stringify({
            product_prompt: wooPrompt,
            price_prompt: wpPrompt,
        });
    } else {
        promptTemplate = llmPrompt;
    }

    const projectData = {
      project_id: projectToEdit ? projectToEdit.project_id : undefined,
      project_name: projectName,
      project_type: projectType,
      scrape_config: scrapeConfig,
      llm_prompt_template: promptTemplate,
    };

    try {
      await apiClient.post("/api/projects", projectData);
      alert(`Project "${projectName}" saved successfully!`);
      onProjectSaved();
    } catch (error) {
      alert(`❌ Failed to save project:\n${error.response?.data?.detail || "An unknown error occurred."}`);
    } finally {
      setIsSaving(false);
    }
  };
  
  const renderStep = () => {
    const urls = urlInput.split('\n').filter(Boolean);
    switch (currentStep) {
      case 1:
        return <Step1_ProjectDetails 
                    projectName={projectName} setProjectName={setProjectName} 
                    projectType={projectType} setProjectType={setProjectType} 
                    onNext={() => setCurrentStep(2)} 
                />;
      case 2:
        return <Step2_LinkSelection 
                    urlInput={urlInput} setUrlInput={setUrlInput}
                    onNext={() => setCurrentStep(3)} 
                    onBack={() => setCurrentStep(1)} 
                    projectType={projectType}
                />;
      case 3:
        return <Step3_FieldsAndPrompts 
                    selectedModelUrl={urls[0]}
                    elementRules={elementRules} setElementRules={setElementRules} 
                    onBack={() => setCurrentStep(2)} 
                    onSaveProject={handleSaveProject} 
                    isSaving={isSaving}
                    projectType={projectType}
                    llmPrompt={llmPrompt} setLlmPrompt={setLlmPrompt}
                    wooPrompt={wooPrompt} setWooPrompt={setWooPrompt}
                    wpPrompt={wpPrompt} setWpPrompt={setWpPrompt}
                />;
      default:
        return <div>Error: Unknown Step</div>;
    }
  };
  
  return (
    <div className="w-full max-w-6xl">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-2">{projectToEdit ? 'Edit Project' : 'Create New Project'}</h2>
        <div className="flex justify-between items-center text-sm font-semibold text-gray-500">
          <span className={currentStep >= 1 ? 'text-indigo-600' : ''}>Step 1: Details</span>
          <span className={currentStep >= 2 ? 'text-indigo-600' : ''}>Step 2: URLs</span>
          <span className={currentStep >= 3 ? 'text-indigo-600' : ''}>Step 3: Fields & Prompt</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
          <div className="bg-indigo-600 h-2 rounded-full transition-all duration-500" style={{ width: `${((currentStep - 1) / 2) * 100}%` }}></div>
        </div>
      </div>
      {renderStep()}
    </div>
  );
};

export default ScraperWizardView;
