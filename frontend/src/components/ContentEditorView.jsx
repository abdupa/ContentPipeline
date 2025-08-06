import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Loader2, Save, RefreshCw, Send, ArrowLeft, Eye } from 'lucide-react';

const apiClient = axios.create({
  baseURL: `http://${window.location.hostname}:8000`,
});

// NEW: Helper function to preview HTML in a new tab
const previewHtmlInNewTab = (htmlContent, title) => {
  const newWindow = window.open();
  newWindow.document.write(htmlContent);
  newWindow.document.title = title;
  newWindow.document.close();
};

const ContentEditorView = ({ draftId, onBack }) => {
  const [draft, setDraft] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
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
    fetchDraft();
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
  
  const handlePublish = async () => {
    if (window.confirm("Are you sure you want to publish this post?")) {
      setIsSaving(true);
      try {
        await apiClient.post(`/api/drafts/${draft.draft_id}/publish`);
        alert("Post published successfully!");
        onBack();
      } catch (err) {
        alert("Error publishing post.");
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
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Approval Queue
        </button>
      </div>
      <h1 className="text-3xl font-extrabold text-gray-800 mb-6">Edit AI-Generated Content</h1>
      
      <div className="bg-white p-6 rounded-lg shadow-xl border border-gray-200 space-y-6">
        {/* --- Metadata fields (no change) --- */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div><label className="block font-medium text-gray-700">Post Title</label><input type="text" name="post_title" value={draft.post_title} onChange={handleInputChange} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>
          <div><label className="block font-medium text-gray-700">Slug</label><input type="text" name="slug" value={draft.slug} onChange={handleInputChange} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div><label className="block font-medium text-gray-700">SEO Title</label><input type="text" name="seo_title" value={draft.seo_title} onChange={handleInputChange} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>
          <div><label className="block font-medium text-gray-700">Meta Description</label><input type="text" name="meta_description" value={draft.meta_description} onChange={handleInputChange} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div><label className="block font-medium text-gray-700">Category</label><input type="text" name="post_category" value={draft.post_category} onChange={handleInputChange} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>
          <div><label className="block font-medium text-gray-700">Tags (comma-separated)</label><input type="text" name="post_tags" value={Array.isArray(draft.post_tags) ? draft.post_tags.join(', ') : draft.post_tags} onChange={e => setDraft(prev => ({...prev, post_tags: e.target.value.split(',').map(t => t.trim())}))} className="w-full border px-3 py-2 rounded mt-1 border-gray-300"/></div>
        </div>

        {/* --- NEW: Content Comparison Section --- */}
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
          <button onClick={handleSaveDraft} disabled={isSaving} className="inline-flex items-center bg-green-600 text-white px-4 py-2 rounded-md font-semibold hover:bg-green-700 disabled:bg-gray-400">
            {isSaving ? <Loader2 className="w-5 h-5 mr-2 animate-spin"/> : <Save className="w-5 h-5 mr-2"/>} Save Draft
          </button>
          <button disabled={isSaving} className="inline-flex items-center bg-yellow-500 text-white px-4 py-2 rounded-md font-semibold hover:bg-yellow-600 disabled:bg-gray-400">
            <RefreshCw className="w-5 h-5 mr-2"/> Regenerate with AI
          </button>
          <button onClick={handlePublish} disabled={isSaving} className="inline-flex items-center bg-blue-600 text-white px-4 py-2 rounded-md font-semibold hover:bg-blue-700 disabled:bg-gray-400 ml-auto">
            <Send className="w-5 h-5 mr-2"/> Publish
          </button>
        </div>
      </div>
    </div>
  );
};

export default ContentEditorView;