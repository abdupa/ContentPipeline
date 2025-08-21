import React, { useState } from 'react';
import { Edit3, Wand, Loader2 } from 'lucide-react';
import apiClient from '../apiClient';

// A default prompt to guide the user
const defaultPrompt = `You are an expert tech journalist and SEO specialist. Your task is to write a high-quality, original blog post based on the provided topic, keywords, and notes. The final output must be a single, valid JSON object with all the required fields for a WordPress post.

Topic: {topic}
Keywords: {keywords}
Notes:
{notes}
`;

const ManualEditorView = ({ onJobStarted }) => {
  const [topic, setTopic] = useState('');
  const [keywords, setKeywords] = useState('');
  const [notes, setNotes] = useState('');
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [isLoading, setIsLoading] = useState(false);

  const handleGenerate = async () => {
    if (!topic.trim()) {
      alert('Please provide a topic for the post.');
      return;
    }
    setIsLoading(true);
    try {
      const payload = { topic, keywords, notes, prompt };
      const response = await apiClient.post('/api/drafts/manual', payload);
      // Pass the job ID up to the parent to navigate to the status screen
      onJobStarted(response.data.job_id);
    } catch (err) {
      alert(`Failed to start generation task: ${err.response?.data?.detail || 'Unknown error'}`);
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-4xl">
      <div className="flex items-center mb-6">
        <Edit3 className="w-8 h-8 mr-3 text-indigo-600" />
        <div>
          <h1 className="text-3xl font-extrabold text-gray-800">Manual Editor</h1>
          <p className="text-lg text-gray-600">Create a new post from scratch with AI assistance.</p>
        </div>
      </div>

      <div className="bg-white p-6 rounded-lg shadow-xl border border-gray-200 space-y-6">
        <div>
          <label htmlFor="topic" className="block text-sm font-medium text-gray-700 mb-1">
            Topic / Post Title <span className="text-red-500">*</span>
          </label>
          <input type="text" id="topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g., The Future of Foldable Phones" className="w-full p-2 border border-gray-300 rounded-md"/>
        </div>
        <div>
          <label htmlFor="keywords" className="block text-sm font-medium text-gray-700 mb-1">
            Keywords (comma-separated) <span className="text-gray-500 text-sm font-normal">(optional)</span>
          </label>
          <input type="text" id="keywords" value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="e.g., foldable, samsung, apple, 2026" className="w-full p-2 border border-gray-300 rounded-md"/>
        </div>
        <div>
          <label htmlFor="notes" className="block text-sm font-medium text-gray-700 mb-1">
            Source Material / Notes <span className="text-gray-500 text-sm font-normal">(optional)</span>
          </label>
          <textarea id="notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows="8" placeholder="Paste your outline, bullet points, or rough ideas here..." className="w-full p-2 border border-gray-300 rounded-md"/>
        </div>
        <div>
          <label htmlFor="prompt" className="block text-sm font-medium text-gray-700 mb-1">AI Prompt Template (Editable)</label>
          <textarea id="prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} rows="10" className="w-full p-2 border border-gray-300 rounded-md font-mono text-xs"/>
        </div>
        <div className="pt-4 text-right">
          <button onClick={handleGenerate} disabled={isLoading} className="inline-flex items-center px-6 py-3 bg-indigo-600 text-white font-bold rounded-full shadow-lg hover:bg-indigo-700 disabled:bg-gray-400">
            {isLoading ? <Loader2 className="w-5 h-5 mr-2 animate-spin"/> : <Wand className="w-5 h-5 mr-2" />}
            {isLoading ? 'Generating...' : 'Generate Draft'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ManualEditorView;