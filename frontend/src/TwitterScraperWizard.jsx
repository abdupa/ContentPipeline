/*
  This is the focused React component for the Twitter Scraper feature.
  Place this file in your frontend/src/ directory.
*/

import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

// --- API Helper ---
const apiClient = axios.create({
  baseURL: 'http://localhost:8000', // Your FastAPI backend URL
});

const startScrapeTask = (profileUrl) => {
  return apiClient.post('/api/v1/scrape-twitter', { profile_url: profileUrl });
};

const getTaskStatus = (taskId) => {
  return apiClient.get(`/api/v1/task-status/${taskId}`);
};


// --- The Main React Component ---
const TwitterScraperWizard = () => {
  const [profileUrl, setProfileUrl] = useState('https://x.com/nikitabier');
  const [tasks, setTasks] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  
  const pollingIntervals = useRef({});

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!profileUrl.trim()) {
      alert('Please enter a profile URL.');
      return;
    }
    setIsLoading(true);
    try {
      const response = await startScrapeTask(profileUrl);
      const newTaskId = response.data.task_id;
      // Replace previous tasks to only show the current one
      setTasks([{ id: newTaskId, status: 'PENDING', result: null }]);
    } catch (error) {
      console.error('Error starting scrape task:', error);
      alert('Failed to start the scraping task. Please check the backend server.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // This effect handles polling for task status updates
    tasks.forEach(task => {
      if ((task.status === 'PENDING' || task.status === 'PROGRESS') && !pollingIntervals.current[task.id]) {
        pollingIntervals.current[task.id] = setInterval(async () => {
          try {
            const response = await getTaskStatus(task.id);
            
            // --- NEW: Log the entire API response to the browser console ---
            console.log('API Response:', response.data); 
            
            const { status, result } = response.data;

            setTasks(prevTasks => prevTasks.map(t => 
              t.id === task.id ? { ...t, status: status, result: result } : t
            ));

            if (status === 'SUCCESS' || status === 'FAILURE') {
              clearInterval(pollingIntervals.current[task.id]);
              delete pollingIntervals.current[task.id];
            }
          } catch (error) {
            console.error(`Error fetching status for task ${task.id}:`, error);
            clearInterval(pollingIntervals.current[task.id]);
            delete pollingIntervals.current[task.id];
          }
        }, 3000); // Poll every 3 seconds
      }
    });

    return () => {
      Object.values(pollingIntervals.current).forEach(clearInterval);
    };
  }, [tasks]);


  const renderTaskResult = (task) => {
    if (!task) return null;

    return (
      <div key={task.id} style={styles.taskCard}>
        <div style={styles.taskHeader}>
          <span style={styles.taskId}>Task ID: {task.id}</span>
          <span style={{...styles.statusBadge, ...styles[task.status.toLowerCase()]}}>
            {task.status}
          </span>
        </div>
        
        {task.status === 'PROGRESS' && (
          <p style={styles.progressText}>{task.result?.status || 'Processing...'}</p>
        )}

        {task.status === 'SUCCESS' && task.result?.data && (
          <div>
            <p>Successfully extracted {task.result.count} posts.</p>
            <div style={styles.tableContainer}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>Post Text</th>
                  </tr>
                </thead>
                <tbody>
                  {task.result.data.map((post, index) => (
                    <tr key={index}>
                      <td style={styles.td}>{post.text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {task.status === 'FAILURE' && (
          <div style={styles.errorBox}>
            <p><strong>Error:</strong> {task.result?.error || 'An unknown error occurred.'}</p>
          </div>
        )}
      </div>
    );
  };

  return (
    <div style={styles.container}>
      {/* This component is now self-contained and doesn't need the main app's structure */}
      <div style={styles.card}>
        <form onSubmit={handleSubmit}>
          <label htmlFor="profileUrl" style={styles.label}>
            Enter X/Twitter Profile URL:
          </label>
          <input
            type="text"
            id="profileUrl"
            value={profileUrl}
            onChange={(e) => setProfileUrl(e.target.value)}
            style={styles.input}
          />
          <button type="submit" style={styles.button} disabled={isLoading}>
            {isLoading ? 'Starting...' : 'Scrape All Posts'}
          </button>
        </form>
      </div>

      {tasks.length > 0 && (
        <div style={styles.resultsSection}>
          <h2 style={styles.subtitle}>Job Status</h2>
          {tasks.map(task => renderTaskResult(task))}
        </div>
      )}
    </div>
  );
};

// Basic CSS-in-JS for styling
const styles = {
  container: { fontFamily: 'sans-serif', padding: '20px', maxWidth: '900px', margin: '0 auto' },
  subtitle: { color: '#444' },
  card: { background: '#fff', padding: '20px', borderRadius: '8px', boxShadow: '0 2px 10px rgba(0,0,0,0.1)' },
  label: { display: 'block', marginBottom: '10px', fontWeight: 'bold' },
  input: { width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box', marginBottom: '15px' },
  button: { width: '100%', padding: '12px', background: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '16px' },
  resultsSection: { marginTop: '30px' },
  taskCard: { background: '#f9f9f9', padding: '15px', borderRadius: '8px', marginBottom: '15px', border: '1px solid #eee' },
  taskHeader: { display: 'flex', alignItems: 'center', marginBottom: '10px' },
  taskId: { color: '#555', fontSize: '14px' },
  statusBadge: { marginLeft: '15px', padding: '4px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 'bold' },
  pending: { background: '#e0e0e0', color: '#555' },
  progress: { background: '#d1ecf1', color: '#0c5460' },
  success: { background: '#d4edda', color: '#155724' },
  failure: { background: '#f8d7da', color: '#721c24' },
  progressText: { color: '#0c5460' },
  errorBox: { background: '#f8d7da', color: '#721c24', padding: '10px', borderRadius: '4px' },
  tableContainer: { maxHeight: '400px', overflowY: 'auto', border: '1px solid #ddd' },
  table: { width: '100%', borderCollapse: 'collapse' },
  th: { background: '#f2f2f2', padding: '8px', borderBottom: '1px solid #ddd', textAlign: 'left' },
  td: { padding: '8px', borderBottom: '1px solid #ddd' },
};

export default TwitterScraperWizard;
