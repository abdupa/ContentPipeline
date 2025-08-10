import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Loader2, Save, RefreshCw, Send, ArrowLeft, Eye, History, Image as ImageIcon, RotateCcw } from 'lucide-react';

const apiClient = axios.create({
  baseURL: `http://${window.location.hostname}:8000`,
});

const previewHtmlInNewTab = (htmlContent, title) => {
  const newWindow = window.open();
  newWindow.document.write(htmlContent);
  newWindow.document.title = title;
  newWindow.document.close();
};

const toBase64 = file => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = error => reject(error);
});

const ContentEditorView = ({ draftId, onBack }) => {
  const [draft, setDraft] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isRegeneratingImage, setIsRegeneratingImage] = useState(false);
  const [error, setError] = useState(null);
  const imagePollInterval = useRef(null);

  const fetchDraft = async () => {
    if (!draftId) return;
    try {
      setIsLoading(true);
      const response = await apiClient.get(`/api/drafts/${draftId}`);
      setDraft(response.data);
    } catch (err) {
      setError("Failed to load draft content.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDraft();
    return () => {
      if (imagePollInterval.current) {
        clearInterval(imagePollInterval.current);
      }
    };
  }, [draftId]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setDraft(prev => ({ ...prev, [name]: value }));
  };

  const handleSaveDraft = async () => {
    setIsSaving(true);
    try {
      await apiClient.put(`/api/drafts/${draft.draft_id}`, draft);
      alert("Draft saved successfully!");
    } catch (err) {
      alert("Error saving draft.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleRegenerate = async () => {
    if (window.confirm("Are you sure? This will regenerate the AI content, overwriting the current version (which will be saved to history). The image will NOT be regenerated.")) {
      setIsRegenerating(true);
      try {
        await apiClient.post(`/api/drafts/${draft.draft_id}/regenerate`);
        setTimeout(() => {
          fetchDraft();
          setIsRegenerating(false);
          alert("Regeneration complete! The content has been updated.");
        }, 5000);
      } catch (err) {
        alert("Failed to start regeneration task.");
        setIsRegenerating(false);
      }
    }
  };

  const handleRegenerateImage = async () => {
      setIsRegeneratingImage(true);
      try {
        const response = await apiClient.post(`/api/drafts/${draft.draft_id}/regenerate-image`);
        const { job_id } = response.data;

        imagePollInterval.current = setInterval(async () => {
          try {
            const statusResponse = await apiClient.get(`/api/jobs/status/${job_id}`);
            const { status, error } = statusResponse.data;

            if (status === 'complete') {
              clearInterval(imagePollInterval.current);
              setIsRegeneratingImage(false);
              fetchDraft();
            } else if (status === 'failed') {
              clearInterval(imagePollInterval.current);
              setIsRegeneratingImage(false);
              alert(`Image regeneration failed: ${error}`);
            }
          } catch (pollError) {
            clearInterval(imagePollInterval.current);
            setIsRegeneratingImage(false);
            alert("Error checking image generation status.");
          }
        }, 2000);

      } catch (err) {
        alert("Failed to start image regeneration task.");
        setIsRegeneratingImage(false);
      }
  };

  const handleImageUpload = async (event) => {
    const file = event.target.files[0];
    if (file) {
        const base64 = await toBase64(file);
        setDraft(prev => ({ ...prev, featured_image_b64: base64 }));
    }
  };

  // --- NEW: Function to restore an old image ---
  const handleRestoreImage = (imageB64) => {
    if (window.confirm("Are you sure you want to restore this image? It will replace the current featured image.")) {
      setDraft(prev => ({ ...prev, featured_image_b64: imageB64 }));
    }
  };
  
  const handlePublish = async () => {
    if (window.confirm("Are you sure you want to publish this post to WordPress?")) {
      setIsSaving(true);
      try {
        const response = await apiClient.post(`/api/drafts/${draft.draft_id}/publish`);
        alert(`Post published successfully!\nURL: ${response.data.url}`);
        onBack();
      } catch (err) {
        alert(`Error publishing post: ${err.response?.data?.detail || 'Unknown error'}`);
      } finally {
        setIsSaving(false);
      }
    }
  };

  if (isLoading) return <div className="flex justify-center items-center h-64"><Loader2 className="w-12 h-12 animate-spin text-indigo-600" /></div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!draft) return <div>No draft selected.</div>;

  return (
    <div className="w-full max-w-6xl">
      <div className="mb-4">
        <button onClick={onBack} className="flex items-center text-sm font-semibold text-gray-600 hover:text-gray-900">
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Library
        </button>
      </div>
      <h1 className="text-3xl font-extrabold text-gray-800 mb-6">Content Editor</h1>
      
      <div className="bg-white p-6 rounded-lg shadow-xl border border-gray-200 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div><label className="block font-medium text-gray-700">Post Title</label><input type="text" name="post_title" value={draft.post_title} onChange={handleInputChange} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>
          <div><label className="block font-medium text-gray-700">Slug</label><input type="text" name="slug" value={draft.slug} onChange={handleInputChange} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div><label className="block font-medium text-gray-700">Focus Keyphrase</label><input type="text" name="focus_keyphrase" value={draft.focus_keyphrase} onChange={handleInputChange} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>
          <div><label className="block font-medium text-gray-700">Category</label><input type="text" name="post_category" value={draft.post_category} onChange={handleInputChange} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>
        </div>
        <div><label className="block font-medium text-gray-700">Tags (comma-separated)</label><input type="text" name="post_tags" value={Array.isArray(draft.post_tags) ? draft.post_tags.join(', ') : draft.post_tags} onChange={e => setDraft(prev => ({...prev, post_tags: e.target.value.split(',').map(t => t.trim())}))} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>
        <div><label className="block font-medium text-gray-700">SEO Title</label><input type="text" name="seo_title" value={draft.seo_title} onChange={handleInputChange} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>
        <div><label className="block font-medium text-gray-700">Meta Description</label><textarea name="meta_description" value={draft.meta_description} onChange={handleInputChange} rows="2" className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>
        <div><label className="block font-medium text-gray-700">Post Excerpt</label><textarea name="post_excerpt" value={draft.post_excerpt} onChange={handleInputChange} rows="3" className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>

        <div className="pt-6 border-t">
            <label className="block text-lg font-semibold text-gray-700 mb-2">Featured Image</label>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="md:col-span-1">
                    {isRegeneratingImage ? (
                        <div className="w-full h-48 bg-gray-100 rounded-lg flex items-center justify-center"><Loader2 className="w-10 h-10 animate-spin text-indigo-500"/></div>
                    ) : draft.featured_image_b64 ? (
                        <img src={`data:image/png;base64,${draft.featured_image_b64}`} alt="Featured Image Preview" className="rounded-lg border w-full h-auto object-cover"/>
                    ) : (
                        <div className="w-full h-48 bg-gray-100 rounded-lg flex items-center justify-center text-gray-500"><ImageIcon className="w-10 h-10"/></div>
                    )}
                </div>
                <div className="md:col-span-2 space-y-4">
                    <div>
                        <label className="block font-medium text-gray-700">Image Prompt</label>
                        <textarea name="featured_image_prompt" value={draft.featured_image_prompt} onChange={handleInputChange} rows="2" className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/>
                        <button onClick={handleRegenerateImage} disabled={isRegeneratingImage} className="mt-2 inline-flex items-center bg-indigo-600 text-white px-3 py-2 rounded-md text-sm font-semibold hover:bg-indigo-700 disabled:bg-gray-400">
                            {isRegeneratingImage ? <Loader2 className="w-4 h-4 mr-2 animate-spin"/> : <RefreshCw className="w-4 h-4 mr-2"/>} Regenerate Image
                        </button>
                    </div>
                    <div>
                        <label className="block font-medium text-gray-700">Or Upload Your Own</label>
                        <input type="file" accept="image/*" onChange={handleImageUpload} className="block text-sm mt-1 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"/>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label className="block font-medium text-gray-700">Image Title</label>
                            <input type="text" name="image_title" value={draft.image_title} onChange={handleInputChange} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/>
                        </div>
                        <div>
                            <label className="block font-medium text-gray-700">ALT Text</label>
                            <input type="text" name="image_alt_text" value={draft.image_alt_text} onChange={handleInputChange} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        {draft.image_history && draft.image_history.length > 0 && (
          <div className="pt-6 border-t">
            <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
              <History className="w-5 h-5 mr-2 text-gray-500"/>
              Featured Image History
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {draft.image_history.slice().reverse().map((entry, index) => (
                <div key={index} className="relative group border rounded-lg overflow-hidden">
                  <img src={`data:image/png;base64,${entry.featured_image_b64}`} alt={entry.image_title} className="w-full h-32 object-cover"/>
                  <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-60 transition-all flex flex-col items-center justify-center p-2">
                    <button
                      onClick={() => handleRestoreImage(entry.featured_image_b64)}
                      className="text-white opacity-0 group-hover:opacity-100 transition-opacity text-sm font-semibold bg-blue-600 px-3 py-1 rounded-full flex items-center mb-1"
                    >
                      <RotateCcw className="w-3 h-3 mr-1"/> Restore
                    </button>
                    <p className="text-white text-xs text-center opacity-0 group-hover:opacity-100 transition-opacity">
                      {new Date(entry.generated_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-4 border-t">
            <div>
                <div className="flex justify-between items-center mb-1">
                    <label className="block font-medium text-gray-700">Original Scraped Content (Read-only)</label>
                    <button onClick={() => previewHtmlInNewTab(draft.original_content.article_html, 'Original Content Preview')} className="text-sm text-blue-600 hover:underline flex items-center"><Eye className="w-4 h-4 mr-1"/>Preview</button>
                </div>
                <textarea readOnly value={draft.original_content.article_html || 'Original content not available.'} className="w-full border p-2 rounded h-96 font-mono text-xs bg-gray-50 border-gray-300"/>
            </div>
            <div>
                <div className="flex justify-between items-center mb-1">
                    <label className="block font-medium text-gray-700">AI-Generated HTML (Editable)</label>
                    <button onClick={() => previewHtmlInNewTab(draft.post_content_html, 'AI Content Preview')} className="text-sm text-blue-600 hover:underline flex items-center"><Eye className="w-4 h-4 mr-1"/>Preview</button>
                </div>
                <textarea name="post_content_html" value={draft.post_content_html} onChange={handleInputChange} className="w-full border p-2 rounded h-96 font-mono text-xs border-gray-300"/>
            </div>
        </div>

        <div className="flex items-center gap-4 pt-4 border-t border-gray-200">
          <button onClick={handleSaveDraft} disabled={isSaving || isRegenerating} className="inline-flex items-center bg-green-600 text-white px-4 py-2 rounded-md font-semibold hover:bg-green-700 disabled:bg-gray-400">
            {isSaving ? <Loader2 className="w-5 h-5 mr-2 animate-spin"/> : <Save className="w-5 h-5 mr-2"/>} Save Draft
          </button>
          <button onClick={handleRegenerate} disabled={isSaving || isRegenerating} className="inline-flex items-center bg-yellow-500 text-white px-4 py-2 rounded-md font-semibold hover:bg-yellow-600 disabled:bg-gray-400">
            {isRegenerating ? <Loader2 className="w-5 h-5 mr-2 animate-spin"/> : <RefreshCw className="w-5 h-5 mr-2"/>} Regenerate Content
          </button>
          <button onClick={handlePublish} disabled={isSaving || isRegenerating} className="inline-flex items-center bg-blue-600 text-white px-4 py-2 rounded-md font-semibold hover:bg-blue-700 disabled:bg-gray-400 ml-auto">
            {isSaving ? <Loader2 className="w-5 h-5 mr-2 animate-spin"/> : <Send className="w-5 h-5 mr-2"/>} Publish
          </button>
        </div>

        {draft.content_history && draft.content_history.length > 0 && (
          <div className="pt-6 border-t mt-6">
            <h3 className="text-xl font-semibold text-gray-700 mb-4 flex items-center">
              <History className="w-5 h-5 mr-2 text-gray-500"/>
              Content Generation History
            </h3>
            <div className="space-y-3 max-h-60 overflow-y-auto pr-2 border rounded-lg p-3 bg-gray-50">
              {draft.content_history.slice().reverse().map((entry, index) => (
                <div key={index} className="bg-white p-3 rounded-lg border border-gray-200 flex justify-between items-center shadow-sm">
                  <div>
                    <p className="font-semibold text-gray-800">{entry.post_title}</p>
                    <p className="text-sm text-gray-500">
                      Generated on: {new Date(entry.generated_at).toLocaleString()}
                    </p>
                  </div>
                  <button
                    onClick={() => previewHtmlInNewTab(entry.post_content_html, `History Preview - ${entry.post_title}`)}
                    className="inline-flex items-center px-3 py-1.5 bg-white text-gray-700 text-sm font-semibold rounded-md border border-gray-300 hover:bg-gray-100 shadow-sm"
                  >
                    <Eye className="w-4 h-4 mr-2" />
                    Preview
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ContentEditorView;
