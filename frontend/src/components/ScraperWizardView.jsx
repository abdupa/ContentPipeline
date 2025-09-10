import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { PlusCircle, Trash2, ArrowRight, Loader2, Save, List, MousePointerClick, Check, X } from 'lucide-react';

const apiClient = axios.create({
  baseURL: `http://${window.location.hostname}:8000`,
});

// --- SUB-COMPONENTS ---

const Step1_ProjectDetails = ({ projectName, setProjectName, projectType, setProjectType, onNext }) => {
    return (
        <div>
            <h2 className="text-2xl font-bold text-gray-800">Step 1: Project Details</h2>
            <p className="text-gray-600 mt-1 mb-6">Give your project a name and choose its type.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Project Name</label>
                    <input type="text" value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder="e.g., GSMArena News" className="w-full p-2 border border-gray-300 rounded-md"/>
                </div>
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Project Type</label>
                    <select value={projectType} onChange={(e) => setProjectType(e.target.value)} className="w-full p-2 border border-gray-300 rounded-md">
                        <option value="standard_article">Standard Article</option>
                        <option value="phone_spec_scraper">Phone Spec Scraper</option>
                        <option value="brightdata_mcp">Bright Data MCP (URL List)</option>
                    </select>
                </div>
            </div>
            <div className="mt-8 text-right"><button onClick={onNext} disabled={!projectName.trim()} className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-md">Next <ArrowRight className="inline"/></button></div>
        </div>
    );
};

const Step2_LinkSelection = ({ initialUrl, projectType, onNext, onBack }) => {
    const [urlInput, setUrlInput] = useState(initialUrl);
    const [linkSelector, setLinkSelector] = useState('');
    const [modelUrl, setModelUrl] = useState('');
    const [previewHtml, setPreviewHtml] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [previewJobId, setPreviewJobId] = useState(null);
    const intervalRef = useRef(null);

    const stopPolling = () => { if (intervalRef.current) clearInterval(intervalRef.current); };

    const handleFetchPreview = async () => {
        const urlToFetch = urlInput.split('\n')[0];
        if (!urlToFetch) { alert("Please provide a starting URL."); return; }
        setIsLoading(true); setPreviewHtml(""); stopPolling(); setLinkSelector(''); setModelUrl('');
        try {
            const response = await apiClient.post("/api/request-page-preview/", { url: urlToFetch, project_type: projectType });
            setPreviewJobId(response.data.job_id);
        } catch (error) { setIsLoading(false); }
    };

    useEffect(() => {
        if (!previewJobId) return;
        const poll = setInterval(async () => {
            const response = await apiClient.get(`/api/get-preview-result/${previewJobId}`);
            if (response.data.status === 'complete' || response.data.status === 'failed') {
                setPreviewHtml(response.data.html || `<div class='p-4 text-red-600'>Preview failed.</div>`);
                setIsLoading(false); clearInterval(poll);
            }
        }, 2500);
        intervalRef.current = poll;
        return stopPolling;
    }, [previewJobId]);

    useEffect(() => {
        const handleMessage = (event) => {
            if (event.data?.type === 'selection-suggestion' && event.data.single) {
                const sampleLink = event.data.single;
                const base = urlInput.split('\n')[0];
                const absoluteUrl = new URL(sampleLink.href, base).href;
                setModelUrl(absoluteUrl);
                setLinkSelector(sampleLink.selector);
            }
        };
        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, [urlInput]);

    const handleNext = () => {
        if (!linkSelector || !modelUrl) { alert("Please select a sample article link from the preview to proceed."); return; }
        onNext({ sourceUrl: urlInput, modelUrl: modelUrl, linkSelector: linkSelector });
    };

    return (
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Step 2: Define Source & Pattern</h2>
          <p className="text-gray-600 mt-1 mb-4">Enter the main news page URL, fetch a preview, then click a single article link. This provides a sample for Step 3 and automatically determines the CSS selector for all similar links.</p>
          <div className="flex gap-4 mb-4">
            <input type="text" value={urlInput} onChange={e => setUrlInput(e.target.value)} placeholder="e.g., https://www.gsmarena.com/news.php3" className="w-full p-2 border rounded-md" />
            <button onClick={handleFetchPreview} disabled={isLoading} className="px-4 py-2 bg-blue-600 text-white rounded-md">{isLoading ? 'Loading...' : "Fetch Preview"}</button>
          </div>
          <div className="border-2 rounded-lg bg-gray-100 mb-6"><div className="w-full h-96 bg-white"><iframe srcDoc={previewHtml || "<p class='p-4'>Click 'Fetch Preview'</p>"} title="Live Page Preview" className="w-full h-full" sandbox="allow-scripts allow-same-origin" /></div></div>
          
          <label className="block text-lg font-medium">Link Selector Pattern</label>
          <div className="w-full p-2 mt-2 bg-gray-100 rounded-md font-mono text-sm text-gray-700">
            {linkSelector || <span className="text-gray-400">Not yet defined. Click a link in the preview.</span>}
          </div>
          <div className="mt-8 flex justify-between">
            <button onClick={onBack} className="px-6 py-2 bg-gray-200 rounded-md">Back</button>
            <button onClick={handleNext} className="px-6 py-2 bg-indigo-600 text-white rounded-md">Next: Define Fields</button>
          </div>
        </div>
    );
};

const Step2_BrightDataConfig = ({ urlInput, setUrlInput, onBack, onSaveProject, isSaving }) => {
    return (
        <div>
            <h2 className="text-2xl font-bold text-gray-800">Step 2: Provide Product URLs</h2>
            <p className="text-gray-600 mt-1 mb-6">Enter the list of product URLs (one per line) you want to scrape for pricing.</p>
            <div>
                <label htmlFor="brightdata-urls" className="block text-sm font-medium text-gray-700 mb-1">Product URLs</label>
                <textarea 
                    id="brightdata-urls" 
                    value={urlInput} 
                    onChange={(e) => setUrlInput(e.target.value)} 
                    placeholder="e.g., https://www.lazada.com.ph/products/product-a.html&#10;https://www.shopee.ph/product-b" 
                    className="w-full h-64 p-2 border rounded-md font-mono text-sm"
                />
            </div>
            <div className="mt-8 flex justify-between">
                <button onClick={onBack} className="px-6 py-2 bg-gray-200 rounded-md">Back</button>
                <button onClick={onSaveProject} disabled={isSaving || !urlInput.trim()} className="px-8 py-3 bg-green-600 text-white rounded-full flex items-center gap-2">
                    {isSaving ? <Loader2 className="animate-spin" /> : <Save />} {isSaving ? 'Saving...' : 'Save Project'}
                </button>
            </div>
        </div>
    );
};

const Step3_FieldsAndPrompts = ({ modelUrl, projectType, elementRules, setElementRules, llmPrompt, setLlmPrompt, onBack, onSaveProject, isSaving }) => {
    const [previewHtml, setPreviewHtml] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [previewJobId, setPreviewJobId] = useState(null);
    const intervalRef = useRef(null);

    useEffect(() => {
        const fetchPreview = async () => {
            if (!modelUrl) return;
            setIsLoading(true); setPreviewHtml("");
            try {
                const response = await apiClient.post("/api/request-page-preview/", { url: modelUrl, project_type: projectType });
                setPreviewJobId(response.data.job_id);
            } catch (error) { setIsLoading(false); }
        };
        fetchPreview();
    }, [modelUrl, projectType]);

    useEffect(() => {
        if (!previewJobId) return;
        const poll = setInterval(async () => {
            const response = await apiClient.get(`/api/get-preview-result/${previewJobId}`);
            if (response.data.status === 'complete' || response.data.status === 'failed') {
                setPreviewHtml(response.data.html || `<div class='p-4 text-red-600'>Preview failed.</div>`);
                setIsLoading(false); clearInterval(poll);
            }
        }, 2000);
        intervalRef.current = poll;
        return () => clearInterval(intervalRef.current);
    }, [previewJobId]);

    useEffect(() => {
        const handleMessage = (event) => {
            if (event.data?.type === 'selection-updated') {
                setElementRules(prevRules => {
                    const newRules = [...prevRules];
                    event.data.elements.forEach(el => {
                        if (!newRules.some(r => r.selector === el.selector)) {
                           newRules.push({ name: `field_${newRules.length + 1}`, selector: el.selector, value: el.value });
                        }
                    });
                    return newRules;
                });
            }
        };
        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, [setElementRules]);
    
    return (
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Step 3: Define Data Fields & AI Prompt</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="border-2 rounded-lg bg-gray-100"><div className="w-full h-[30rem] bg-white"><iframe srcDoc={previewHtml || (isLoading ? "Loading..." : "<p>Preview will load here.</p>")} title="Live Detail Page Preview" className="w-full h-full" sandbox="allow-scripts allow-same-origin"/></div></div>
            <div>
              <div>
                <label className="block text-lg font-medium">Extraction Fields</label>
                <p className="text-sm text-gray-500 mb-2">Click in the preview to add fields.</p>
                <div className="overflow-x-auto rounded-lg shadow-md border max-h-60">
                  <table className="min-w-full"><thead className="bg-gray-50 sticky top-0"><tr><th>Field Name</th><th>Selector</th><th></th></tr></thead><tbody>
                      {elementRules.map((rule, index) => (<tr key={rule.selector || index}><td><input type="text" value={rule.name} onChange={(e) => setElementRules(prev => prev.map((r, i) => i === index ? {...r, name: e.target.value} : r))} className="w-full p-1 border rounded-md"/></td><td>{rule.selector}</td><td><button onClick={() => setElementRules(prev => prev.filter((_, i) => i !== index))}><Trash2/></button></td></tr>))}
                  </tbody></table>
                </div>
              </div>
              <div className="mt-6">
                  <label htmlFor="llm-prompt" className="block text-lg font-medium">LLM Prompt Template</label>
                  <textarea id="llm-prompt" value={llmPrompt} onChange={(e) => setLlmPrompt(e.target.value)} className="w-full h-48 p-2 border rounded-md"/>
              </div>
            </div>
          </div>
          <div className="mt-8 flex justify-between">
            <button onClick={onBack} className="px-6 py-2 bg-gray-200 rounded-md">Back</button>
            <button onClick={onSaveProject} disabled={isSaving} className="px-8 py-3 bg-green-600 text-white rounded-full flex items-center gap-2">
                {isSaving ? <Loader2 className="animate-spin" /> : <Save />} {isSaving ? 'Saving...' : 'Save Project'}
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
    const [linkSelector, setLinkSelector] = useState('');
    const [selectedModelUrl, setSelectedModelUrl] = useState('');
    const [elementRules, setElementRules] = useState([]);
    const [llmPrompt, setLlmPrompt] = useState('');
    const [collectorId, setCollectorId] = useState('');
  
    useEffect(() => {
      if (projectToEdit) {
        setProjectName(projectToEdit.project_name);
        setProjectType(projectToEdit.project_type);
        const config = projectToEdit.scrape_config;
        if (projectToEdit.project_type === 'brightdata_collector') {
            setCollectorId(config.collector_id || '');
        } else {
            setUrlInput(config.initial_urls.join('\n'));
            setLinkSelector(config.link_selector || '');
            setSelectedModelUrl(config.modelUrls?.[0] || '');
            setElementRules(config.element_rules.map(rule => ({ ...rule, value: '' })));
            setLlmPrompt(projectToEdit.llm_prompt_template);
        }
      }
    }, [projectToEdit]);

    const handleSaveProject = async () => {
        setIsSaving(true);
        let scrapeConfig;
        let template = llmPrompt;

        if (projectType === 'brightdata_mcp') {
            scrapeConfig = { 
                initial_urls: urlInput.split('\n').filter(Boolean)
            };
            template = ''; // No prompt needed
        } else {
            scrapeConfig = {
                scrape_type: 'dynamic_crawl',
                initial_urls: urlInput.split('\n').filter(Boolean),
                link_selector: linkSelector,
                element_rules: elementRules.map(({ name, selector }) => ({ name, selector })),
                modelUrls: [selectedModelUrl],
            };
        }

        const projectData = {
            project_id: projectToEdit ? projectToEdit.project_id : undefined,
            project_name: projectName,
            project_type: projectType,
            scrape_config: scrapeConfig,
            llm_prompt_template: template,
        };
        
        try {
            await apiClient.post("/api/projects", projectData);
            onProjectSaved();
        } catch (error) {
            alert(`Failed to save project.`);
        } finally {
            setIsSaving(false);
        }
    };
  
    const renderStep = () => {
      switch (currentStep) {
        case 1:
          return <Step1_ProjectDetails {...{projectName, setProjectName, projectType, setProjectType}} onNext={() => setCurrentStep(2)} />;
        case 2:
          if (projectType === 'brightdata_mcp') {
            return <Step2_BrightDataConfig 
                        urlInput={urlInput}
                        setUrlInput={setUrlInput}
                        onBack={() => setCurrentStep(1)}
                        onSaveProject={handleSaveProject}
                        isSaving={isSaving}
                    />;
          }
          return <Step2_LinkSelection 
                      initialUrl={urlInput}
                      projectType={projectType} 
                      onNext={(payload) => {
                          setUrlInput(payload.sourceUrl);
                          setSelectedModelUrl(payload.modelUrl);
                          setLinkSelector(payload.linkSelector);
                          setCurrentStep(3);
                      }} 
                      onBack={() => setCurrentStep(1)} 
                  />;
        case 3:
            return <Step3_FieldsAndPrompts 
                        modelUrl={selectedModelUrl}
                        projectType={projectType}
                        elementRules={elementRules} setElementRules={setElementRules} 
                        llmPrompt={llmPrompt} setLlmPrompt={setLlmPrompt}
                        onBack={() => setCurrentStep(2)} 
                        onSaveProject={handleSaveProject} 
                        isSaving={isSaving}
                    />;
        default:
          return <div>Error</div>;
      }
    };
  
    return (
      <div className="w-full max-w-6xl">
        <div className="mb-6">
          <h2 className="text-2xl font-bold">{projectToEdit ? `Edit Project: "${projectName}"` : 'Create New Project'}</h2>
        </div>
        {renderStep()}
      </div>
    );
};

export default ScraperWizardView;