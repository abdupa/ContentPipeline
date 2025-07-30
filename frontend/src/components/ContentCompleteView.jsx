import React from 'react';
import { CheckCircle, AlertCircle, Download, PlusCircle, ListTodo, Loader2 } from 'lucide-react';

// It now accepts the new handler functions as props
const ContentCompleteView = ({ jobStatus, contentData = [], handleDownloadResults, onGenerateMore, onViewContent }) => {
  const isComplete = jobStatus.successfulPosts === jobStatus.totalPosts;
  const progress = jobStatus.totalPosts > 0 ? (jobStatus.successfulPosts / jobStatus.totalPosts) * 100 : 0;

  const formatTimestamp = (isoString) => {
    if (!isoString) return 'N/A';
    return new Date(isoString).toLocaleString();
  };

  return (
    <div className="bg-white p-8 rounded-lg shadow-xl w-full max-w-4xl border border-gray-200">
      <h1 className="text-3xl font-extrabold text-gray-800 mb-8 text-center">
        {isComplete ? 'Content Generation Complete!' : 'Content Generation Progress'}
      </h1>

      {/* Progress Bar Section (from previous step) */}
      <section className="mb-8">
        {/* <h2 className="text-2xl font-semibold text-gray-700 mb-4">Job Progress</h2> */}
        {/* --- NEW: Conditional Progress Display --- */}
      {isComplete ? (
        <div className="text-center">
          <div className="flex items-center justify-center text-2xl font-semibold text-green-600">
            <CheckCircle className="w-8 h-8 mr-2" />
            <span>Job Complete!</span>
          </div>
          <p className="text-lg text-gray-600 mt-2">{jobStatus.successfulPosts}/{jobStatus.totalPosts} posts processed successfully.</p>
        </div>
      ) : (
        <div>
          <div className="mt-4 text-center text-lg text-gray-600 font-medium">
            <div className="flex items-center justify-center">
              <Loader2 className="w-6 h-6 mr-2 animate-spin" />
              <span>Processing post {jobStatus.successfulPosts + 1} of {jobStatus.totalPosts}...</span>
            </div>
          </div>
        </div>
      )}
      </section>

      {/* Generated Content Summary Table */}
      <section className="mb-8">
        <h2 className="text-2xl font-semibold text-gray-700 mb-4">Generated Content Summary</h2>
        <div className="overflow-x-auto rounded-lg shadow-md border border-gray-200">
          {/* ... table JSX remains the same ... */}
          <table className="min-w-full bg-white rounded-lg">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Count</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Post Title</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Generated On</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Notes</th> {/* <-- Add this header */}
                
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {contentData.map((item, index) => (
                <tr key={`${item.title}-${index}`} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{index + 1}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{item.title || 'N/A'}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${ item.status === 'Complete' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800' }`}>
                      {item.status || 'Pending'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatTimestamp(item.generatedOn)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    {item.actions ? (<a href={item.actions} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">View/Edit</a>) : (<span className="text-gray-400">N/A</span>)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{item.notes || ''}</td> {/* <-- Add this cell */}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* --- ADDED BACK: Download Results Button --- */}
        <div className="mt-6 text-right">
          <button
            onClick={handleDownloadResults}
            className="inline-flex items-center px-6 py-2 bg-purple-600 text-white font-semibold rounded-full shadow-md hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-opacity-75 transition duration-200 ease-in-out transform hover:scale-105"
          >
            <Download className="w-5 h-5 mr-2" />
            Download Results (CSV)
          </button>
        </div>
      </section>

      {/* --- ADDED BACK: What's Next? Section --- */}
      <section className="p-6 bg-gradient-to-r from-green-50 to-teal-50 rounded-lg shadow-md border border-green-200">
        <h2 className="text-2xl font-semibold text-gray-700 mb-4 text-center">What's Next?</h2>
        <div className="flex flex-col sm:flex-row justify-center space-y-4 sm:space-y-0 sm:space-x-4">
          <button
            onClick={onGenerateMore}
            className="flex-1 px-8 py-3 bg-blue-600 text-white font-bold rounded-full shadow-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-75 transition duration-200 ease-in-out transform hover:scale-105 flex items-center justify-center"
          >
            <PlusCircle className="w-5 h-5 mr-2" />
            Generate More Content
          </button>
          <button
            onClick={onViewContent}
            className="flex-1 px-8 py-3 bg-gray-700 text-white font-bold rounded-full shadow-lg hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-600 focus:ring-opacity-75 transition duration-200 ease-in-out transform hover:scale-105 flex items-center justify-center"
          >
            <ListTodo className="w-5 h-5 mr-2" />
            View All Generated Content
          </button>
        </div>
      </section>
    </div>
  );
};

export default ContentCompleteView;