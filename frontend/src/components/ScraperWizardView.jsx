import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { PlusCircle, Trash2, ArrowRight, Target, Loader2 } from 'lucide-react';
import JobStatusView from './JobStatusView';

// Define the API client for communication with the backend
const apiClient = axios.create({
  baseURL: `http://${window.location.hostname}:8000`,
});

// --- Component for Step 1: URL Input ---
const Step1_UrlInput = ({ urlInput, setUrlInput, onNext }) => {
  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800">Step 1: Enter Website URLs</h2>
      <p className="text-gray-600 mt-1 mb-6">Provide the list of pages to crawl, one URL per line.</p>
      <textarea
        value={urlInput}
        onChange={(e) => setUrlInput(e.target.value)}
        placeholder="https://www.gsmarena.com/"
        className="w-full h-40 p-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500 font-mono text-sm"
      />
      <div className="mt-8 text-right">
        <button type="button" onClick={onNext} disabled={!urlInput.trim()} className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-sm hover:bg-indigo-700 disabled:bg-gray-300 flex items-center gap-2">Next: Define Links <ArrowRight className="w-5 h-5" /></button>
      </div>
    </div>
  );
};


// --- Component for Step 2: Link Selection ---
const Step2_LinkSelection = ({
  urls,
  scrapeMode, setScrapeMode,
  crawlingLevels, setCrawlingLevels,
  capturedLinks, setCapturedLinks,
  finalCrawlSelections, setFinalCrawlSelections,
  setSelectedModelUrl, onNext, onBack
}) => {
  const [activeCrawlIndex, setActiveCrawlIndex] = useState(0);
  const [previewHtml, setPreviewHtml] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [previewJobId, setPreviewJobId] = useState(null);
  const [currentPreviewBaseUrl, setCurrentPreviewBaseUrl] = useState(null);
  const intervalRef = useRef(null);

  // This logic now correctly determines if we are on the final level of a multi-step crawl.
  const isFinalCrawlLevel = scrapeMode === 'crawl' && crawlingLevels.length > 1 && activeCrawlIndex === crawlingLevels.length - 1;

  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  const handleFetchPreview = async () => {
    let urlToFetch;
    if (scrapeMode === 'direct' || activeCrawlIndex === 0) {
      if (!urls[0]) { alert("Please enter a URL in Step 1."); return; }
      urlToFetch = urls[0];
    } else {
      const prevLevel = crawlingLevels[activeCrawlIndex - 1];
      if (!prevLevel || !prevLevel.previewUrl) {
        alert("Please define a link for the previous level first to load the next preview.");
        return;
      }
      urlToFetch = prevLevel.previewUrl;
    }
    
    setCurrentPreviewBaseUrl(urlToFetch);
    setIsLoading(true);
    setPreviewHtml("");
    stopPolling();
    try {
      const response = await apiClient.post("/api/request-page-preview/", { url: urlToFetch });
      setPreviewJobId(response.data.job_id);
    } catch (error) {
      console.error("Error starting preview job:", error);
      setIsLoading(false);
      setPreviewHtml(`<div class='p-4 text-red-600'>Error starting preview job. Check console for details.</div>`);
    }
  };

  // This is the complete and corrected polling logic.
  useEffect(() => {
    if (!previewJobId) return;

    const pollForResult = async () => {
      try {
        const response = await apiClient.get(`/api/get-preview-result/${previewJobId}`);
        const { status, html, error } = response.data;
        if (status === 'complete') {
          setPreviewHtml(html);
          setIsLoading(false);
          stopPolling();
        } else if (status === 'failed') {
          setPreviewHtml(`<div class='p-4 text-red-600'><b>Preview generation failed.</b><br/>Error: ${error}</div>`);
          setIsLoading(false);
          stopPolling();
        }
      } catch (err) {
        console.error(`Error while polling for job ${previewJobId}:`, err);
        setIsLoading(false);
        stopPolling();
      }
    };
    
    pollForResult();
    intervalRef.current = setInterval(pollForResult, 2500);

    return stopPolling;
  }, [previewJobId]);

  useEffect(() => {
    const handleMessage = (event) => {
      if (event.data && event.data.type === 'selection-updated') {
        const elements = event.data.elements;

        if (scrapeMode === 'direct') {
          setCapturedLinks(elements);
        } else if (isFinalCrawlLevel) {
          setFinalCrawlSelections(elements);
          const lastElement = elements[elements.length - 1];
          if (lastElement) {
            setCrawlingLevels(prev => prev.map((l, i) => i === activeCrawlIndex ? { ...l, selector: lastElement.selector } : l));
          }
        } else {
          if (elements.length === 0) return;
          const latestElement = elements[elements.length - 1];
          const base = currentPreviewBaseUrl || urls[0];
          const newPreviewUrl = latestElement.href ? new URL(latestElement.href, base).href : null;
          setCrawlingLevels(prev => prev.map((l, i) => i === activeCrawlIndex ? { ...l, selector: latestElement.selector, previewUrl: newPreviewUrl } : l));
        }
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [scrapeMode, urls, activeCrawlIndex, isFinalCrawlLevel, currentPreviewBaseUrl, setCrawlingLevels, setCapturedLinks, setFinalCrawlSelections]);

  const handleNext = () => {
    let urlForStep3 = null;
    let baseForStep3 = null;

    if (scrapeMode === 'direct') {
      if (capturedLinks.length === 0) { alert("Please select at least one link."); return; }
      urlForStep3 = capturedLinks[0].href;
      baseForStep3 = urls[0];
    } else if (scrapeMode === 'crawl') {
      const intermediateLevels = crawlingLevels.slice(0, -1);
      if (intermediateLevels.some(l => !l.selector)) {
        alert("Please define a link for all intermediate crawl levels first.");
        return;
      }
      if (finalCrawlSelections.length === 0) { alert("Please select at least one item on the final crawl level."); return; }
      
      urlForStep3 = finalCrawlSelections[0].href;
      baseForStep3 = currentPreviewBaseUrl;
    } else { return; }

    if (urlForStep3 && baseForStep3) {
      const absoluteUrl = new URL(urlForStep3, baseForStep3).href;
      setSelectedModelUrl(absoluteUrl);
      onNext();
    } else {
      alert("Could not determine a valid URL for the next step.");
    }
  };
  
  const addCrawlingLevel = () => { setCrawlingLevels(prev => [...prev, { name: `Level ${prev.length + 1}`, selector: '', previewUrl: null }]); };
  const removeCrawlingLevel = (indexToRemove) => { setCrawlingLevels(prev => prev.filter((_, index) => index !== indexToRemove)); };

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800">Step 2: Define Links to Scrape</h2>
      <div className="my-6">
        <label className="block text-lg font-medium text-gray-700 mb-2">Scraping Mode</label>
        <div className="flex rounded-lg p-1 bg-gray-200 w-fit">
          <button onClick={() => { setScrapeMode('direct'); setCrawlingLevels([{ name: 'Level 1', selector: '', previewUrl: null }]); }} className={`px-4 py-2 text-sm font-semibold rounded-md transition-colors ${scrapeMode === 'direct' ? 'bg-white text-blue-600 shadow' : 'bg-transparent text-gray-600'}`}>Direct Selection</button>
          <button onClick={() => { setScrapeMode('crawl'); setCrawlingLevels([{ name: 'Level 1', selector: '', previewUrl: null }]); }} className={`px-4 py-2 text-sm font-semibold rounded-md transition-colors ${scrapeMode === 'crawl' ? 'bg-white text-blue-600 shadow' : 'bg-transparent text-gray-600'}`}>Crawling Path</button>
        </div>
      </div>
      {scrapeMode === 'direct' ? (
        <div>
          <p className="text-gray-600 mt-1 mb-6">Click on one or more links that lead directly to the pages you want to scrape.</p>
          <div className="mb-4">
            <button type="button" onClick={handleFetchPreview} disabled={isLoading} className="px-4 py-2 bg-blue-600 text-white font-semibold rounded-md shadow-sm hover:bg-blue-700 disabled:bg-gray-400">{isLoading ? <span className="flex items-center"><Loader2 className="animate-spin mr-2" /> Generating Preview...</span> : "Fetch Live Preview"}</button>
          </div>
          <div className="border-2 border-gray-300 rounded-lg bg-gray-100 mb-6">
            <div className="w-full h-96 bg-white"><iframe srcDoc={previewHtml || "<p class='p-4 text-gray-500'>Click 'Fetch Live Preview'</p>"} title="Live Page Preview" className="w-full h-full" sandbox="allow-scripts allow-same-origin" /></div>
          </div>
          <div className="mt-6">
            <label className="block text-lg font-medium text-gray-700">Captured Links ({capturedLinks.length})</label>
            <div className="overflow-x-auto rounded-lg shadow-md border border-gray-200 bg-white max-h-60">
              <table className="min-w-full"><thead className="bg-gray-50 sticky top-0"><tr><th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Element Text</th><th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Selector</th></tr></thead><tbody className="divide-y divide-gray-200">{capturedLinks.length > 0 ? (capturedLinks.map((item, index) => (<tr key={item.selector || index}><td className="px-4 py-2 whitespace-nowrap text-sm font-medium text-gray-800">{item.value}</td><td className="px-4 py-2 whitespace-nowrap text-sm font-mono text-gray-600">{item.selector}</td></tr>))) : (<tr><td colSpan="2" className="px-4 py-3 text-sm text-center text-gray-400">Click a link in the preview above to capture it.</td></tr>)}</tbody></table>
            </div>
          </div>
        </div>
      ) : (
        <div>
          <p className="text-gray-600 mt-1 mb-6">Define a path to the page containing your items. On the final level, you can select multiple items.</p>
          <div className="flex flex-col md:flex-row gap-6">
            <div className="w-full md:w-1/3">
              <label className="block text-lg font-medium text-gray-700 mb-2">Crawling Levels</label>
              <div className="space-y-3">{crawlingLevels.map((level, index) => (<div key={index} onClick={() => setActiveCrawlIndex(index)} className={`p-3 rounded-lg border-2 cursor-pointer transition-all ${activeCrawlIndex === index ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white'}`}><div className="flex justify-between items-center mb-2"><h4 className="font-semibold text-gray-700">{level.name}</h4>{crawlingLevels.length > 1 && (<button onClick={(e) => { e.stopPropagation(); removeCrawlingLevel(index); }} className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-100 rounded-full"><Trash2 className="w-4 h-4"/></button>)}</div><input type="text" readOnly value={level.selector} placeholder="Click in preview to select" className="w-full p-2 border border-gray-300 rounded-md font-mono text-sm bg-gray-100"/>{level.previewUrl && <p className="text-xs text-green-600 mt-1 truncate">Next Preview: {level.previewUrl}</p>}</div>))}<button onClick={addCrawlingLevel} className="w-full mt-3 inline-flex items-center justify-center text-sm font-medium text-blue-600 hover:text-blue-800 border-2 border-dashed border-gray-300 hover:border-blue-500 rounded-lg p-3"><PlusCircle className="w-5 h-5 mr-2" />Add Level</button></div>
            </div>
            <div className="w-full md:w-2/3">
              <div className="mb-4"><button type="button" onClick={handleFetchPreview} disabled={isLoading} className="px-4 py-2 bg-blue-600 text-white font-semibold rounded-md shadow-sm hover:bg-blue-700 disabled:bg-gray-400">{isLoading ? <span className="flex items-center"><Loader2 className="animate-spin mr-2"/> Generating...</span> : `Fetch Preview for Level ${activeCrawlIndex + 1}`}</button></div>
              <div className="border-2 border-gray-300 rounded-lg bg-gray-100"><div className="w-full h-96 bg-white"><iframe srcDoc={previewHtml || "<p class='p-4 text-gray-500'>Click 'Fetch Preview'</p>"} title="Live Page Preview" className="w-full h-full" sandbox="allow-scripts allow-same-origin" /></div></div>
            </div>
          </div>
          {isFinalCrawlLevel && (
            <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <h3 className="text-lg font-medium text-blue-800">Final Item Selection</h3>
                <p className="text-blue-700">You are on the final level. Click all the items you want to scrape from the preview.</p>
                <p className="text-lg font-bold text-blue-900 mt-2">{finalCrawlSelections.length} items selected.</p>
            </div>
          )}
        </div>
      )}
      <div className="mt-8 flex justify-between">
        <button type="button" onClick={onBack} className="px-6 py-2 bg-gray-200 text-gray-800 font-semibold rounded-md hover:bg-gray-300">Back</button>
        <button type="button" onClick={handleNext} className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-sm hover:bg-indigo-700 flex items-center gap-2">Next: Select Elements <ArrowRight className="w-5 h-5" /></button>
      </div>
    </div>
  );
};


// --- Component for Step 3: Element Selection ---
const Step3_ElementSelection = ({ selectedModelUrl, elementRules, setElementRules, onBack, onFinish }) => {
  const [previewHtml, setPreviewHtml] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [previewJobId, setPreviewJobId] = useState(null);
  const intervalRef = useRef(null);

  const stopPolling = () => { if (intervalRef.current) { clearInterval(intervalRef.current); } };

  useEffect(() => {
    const fetchPreview = async () => {
      if (!selectedModelUrl) return;
      setIsLoading(true);
      setPreviewHtml("");
      stopPolling();
      try {
        const response = await apiClient.post("/api/request-page-preview/", { url: selectedModelUrl });
        setPreviewJobId(response.data.job_id);
      } catch (error) {
        console.error("Error starting Step 3 preview job:", error);
        setIsLoading(false);
        setPreviewHtml(`<div class='p-4 text-red-600'>Error starting preview job.</div>`);
      }
    };
    fetchPreview();
    return stopPolling;
  }, [selectedModelUrl]);

  useEffect(() => {
    if (!previewJobId) return;
    const pollForResult = async () => {
      try {
        const response = await apiClient.get(`/api/get-preview-result/${previewJobId}`);
        const { status, html, error } = response.data;
        if (status === 'complete' || status === 'failed') {
          setPreviewHtml(html || `<div class='p-4 text-red-600'><b>Preview generation failed.</b><br/>Error: ${error}</div>`);
          setIsLoading(false);
          stopPolling();
        }
      } catch (err) {
        setIsLoading(false);
        stopPolling();
      }
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
          return incomingElements.map((el, index) => ({
            name: nameMap.get(el.selector) || el.value?.substring(0, 50) || `Field ${index + 1}`,
            selector: el.selector,
            value: el.value,
          }));
        });
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [setElementRules]);

  const handleRuleChange = (index, field, value) => {
    setElementRules(prevRules => prevRules.map((rule, i) => (i === index ? { ...rule, [field]: value } : rule)));
  };

  const handleRemoveRule = (indexToRemove) => {
    setElementRules(prevRules => prevRules.filter((_, index) => index !== indexToRemove));
  };
    
  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800">Step 3: Define Data Fields</h2>
      <p className="text-gray-600 mt-1 mb-6">Click on an element in the preview (e.g., title, price) to add it as a field to extract.</p>
      <div className="border-2 border-gray-300 rounded-lg bg-gray-100 mb-6">
        <div className="w-full h-[30rem] bg-white">
          <iframe srcDoc={previewHtml || (isLoading ? "<p class='p-4 text-center'><span class='animate-spin inline-block w-6 h-6 border-4 border-current border-t-transparent text-blue-600 rounded-full' role='status' aria-label='loading'></span><br/>Loading Preview...</p>" : "<p class='p-4 text-gray-500'>Preview will load here.</p>")} title="Live Detail Page Preview" className="w-full h-full" sandbox="allow-scripts allow-same-origin"/>
        </div>
      </div>
      <div>
        <label className="block text-lg font-medium text-gray-700">Extraction Fields</label>
        <p className="text-sm text-gray-500 mb-2">Click in the preview to add rows. Edit the field names as needed.</p>
        <div className="overflow-x-auto rounded-lg shadow-md border border-gray-200 bg-white max-h-96">
          <table className="min-w-full table-fixed">
            <thead className="bg-gray-50 sticky top-0">
              <tr>
                <th className="w-4/12 px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Field Name (Editable)</th>
                <th className="w-3/12 px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Element Value</th>
                <th className="w-4/12 px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">CSS Path</th>
                <th className="w-1/12 px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {elementRules.length > 0 ? (
                elementRules.map((rule, index) => (
                  <tr key={rule.selector || index}>
                    <td className="px-4 py-2"><input type="text" value={rule.name} onChange={(e) => handleRuleChange(index, 'name', e.target.value)} className="w-full p-1 border border-gray-300 rounded-md"/></td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700 truncate">{rule.value}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-sm font-mono text-gray-600 truncate">{rule.selector}</td>
                    <td className="px-4 py-2 text-center"><button type="button" onClick={() => handleRemoveRule(index)} className="text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4"/></button></td>
                  </tr>
                ))
              ) : (
                <tr><td colSpan="4" className="px-4 py-3 text-sm text-center text-gray-400">Click an element in the preview to add the first rule.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <div className="mt-8 flex justify-between">
        <button type="button" onClick={onBack} className="px-6 py-2 bg-gray-200 text-gray-800 font-semibold rounded-md hover:bg-gray-300">Back</button>
        <button type="button" onClick={onFinish} disabled={elementRules.length === 0} className="px-8 py-3 bg-green-600 text-white font-bold text-lg rounded-full shadow-lg hover:bg-green-700 disabled:bg-gray-400 flex items-center gap-2">Finish & Start Extraction <Target className="w-5 h-5" /></button>
      </div>
    </div>
  );
};


// --- Main Wizard View ---
const ScraperWizardView = () => {
  const [activeJobId, setActiveJobId] = useState(null);
  const [currentStep, setCurrentStep] = useState(1);
  const [urlInput, setUrlInput] = useState('');
  const [scrapeMode, setScrapeMode] = useState('direct');
  const [crawlingLevels, setCrawlingLevels] = useState([{ name: 'Level 1', selector: '', previewUrl: null }]);
  const [capturedLinks, setCapturedLinks] = useState([]);
  const [selectedModelUrl, setSelectedModelUrl] = useState('');
  const [elementRules, setElementRules] = useState([]);
  const [finalCrawlSelections, setFinalCrawlSelections] = useState([]);

  const handleFinish = async () => {
    let finalConfig;
    if (!urlInput.trim()) { alert("Please provide a URL in Step 1."); return; }
    
    if (scrapeMode === 'direct') {
      if (capturedLinks.length === 0) { alert("Error: In 'Direct Selection' mode, you must select at least one link."); return; }
      const baseOrigin = new URL(urlInput.split('\n')[0]).origin;
      finalConfig = {
        scrape_type: 'direct',
        modelUrls: [...new Set(capturedLinks.map(link => new URL(link.href, baseOrigin).href))],
        element_rules: elementRules.filter(rule => rule.name && rule.selector),
      };
    } else { // Crawl mode
      if (finalCrawlSelections.length === 0) { alert("Error: In 'Crawling Path' mode, you must select at least one item on the final level."); return; }
      finalConfig = {
        scrape_type: 'crawl',
        initial_urls: urlInput.split('\n').filter(Boolean),
        crawling_levels: crawlingLevels.slice(0, -1).map(({ name, selector }) => ({ name, selector })),
        // This now correctly uses the full selectedModelUrl as the base for resolving relative links.
        final_urls: [...new Set(finalCrawlSelections.map(link => new URL(link.href, selectedModelUrl).href))],
        element_rules: elementRules.filter(rule => rule.name && rule.selector),
      };
    }

    console.log("🚀 [FINISH] Submitting job with final configuration:", finalConfig);
    try {
      const response = await apiClient.post("/api/start-wizard-scrape", finalConfig);
      setActiveJobId(response.data.job_id);
    } catch (error) {
      console.error("❌ [FINISH] Failed to start scraping job:", error);
      const errorDetail = error.response?.data?.detail || "An unknown error occurred.";
      alert(`❌ Failed to start scraping job:\n${errorDetail}`);
    }
  };

  const resetWizard = () => {
      setActiveJobId(null);
      setCurrentStep(1);
      setUrlInput('');
      setCapturedLinks([]);
      setElementRules([]);
      setSelectedModelUrl('');
      setScrapeMode('direct');
      setCrawlingLevels([{ name: 'Level 1', selector: '', previewUrl: null }]);
      setFinalCrawlSelections([]);
  };

  if (activeJobId) { return <JobStatusView jobId={activeJobId} onReset={resetWizard} />; }

  const renderStep = () => {
    const urls = urlInput.split('\n').filter(Boolean);
    switch (currentStep) {
      case 1:
        return <Step1_UrlInput urlInput={urlInput} setUrlInput={setUrlInput} onNext={() => setCurrentStep(2)} />;
      case 2:
        return <Step2_LinkSelection 
                  urls={urls} 
                  scrapeMode={scrapeMode} setScrapeMode={setScrapeMode}
                  crawlingLevels={crawlingLevels} setCrawlingLevels={setCrawlingLevels}
                  capturedLinks={capturedLinks} setCapturedLinks={setCapturedLinks} 
                  finalCrawlSelections={finalCrawlSelections} setFinalCrawlSelections={setFinalCrawlSelections}
                  setSelectedModelUrl={setSelectedModelUrl} 
                  onNext={() => setCurrentStep(3)} 
                  onBack={() => setCurrentStep(1)} 
                />;
      case 3:
        return <Step3_ElementSelection selectedModelUrl={selectedModelUrl} onBack={() => setCurrentStep(2)} onFinish={handleFinish} elementRules={elementRules} setElementRules={setElementRules} />;
      default:
        return <Step1_UrlInput urlInput={urlInput} setUrlInput={setUrlInput} onNext={() => setCurrentStep(2)} />;
    }
  };
  
  return (
    <div className="bg-white p-6 sm:p-8 rounded-lg shadow-xl w-full max-w-4xl border border-gray-200">
      <div className="mb-6"><div className="flex justify-between items-center text-sm font-semibold text-gray-500"><span className={currentStep >= 1 ? 'text-indigo-600' : ''}>Step 1: URLs</span><span className={currentStep >= 2 ? 'text-indigo-600' : ''}>Step 2: Links</span><span className={currentStep >= 3 ? 'text-indigo-600' : ''}>Step 3: Elements</span></div><div className="w-full bg-gray-200 rounded-full h-2 mt-1"><div className="bg-indigo-600 h-2 rounded-full transition-all duration-500" style={{ width: `${((currentStep - 1) / 2) * 100}%` }}></div></div></div>
      {renderStep()}
    </div>
  );
};

export default ScraperWizardView;