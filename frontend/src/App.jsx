import React from 'react';
// --- THE FIX: Updated the import to use the new .jsx file extension ---
import TwitterScraperWizard from './TwitterScraperWizard.jsx'; 
import './App.css'; // Your main css file for basic styles

function App() {
  // This is now the main entry point for your focused feature.
  // We've removed the sidebar, header, and routing to keep it simple.
  return (
    <div className="App">
      <main>
        {/* The only thing this app does is render the Twitter Scraper Wizard */}
        <TwitterScraperWizard />
      </main>
    </div>
  );
}

export default App;
