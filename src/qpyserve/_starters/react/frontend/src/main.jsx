import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

function App() {
  const [result, setResult] = useState('Ready');

  async function callPython() {
    setResult('Loading...');
    try {
      const response = await fetch('/api/hello');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const { message, time } = await response.json();
      setResult(`${message}\n${time}`);
    } catch (error) {
      setResult(`API error: ${error.message}`);
    }
  }

  return (
    <main>
      <h1>QPyServe is running.</h1>
      <p>One Python command, a full React frontend, and a real API.</p>
      <button type="button" onClick={callPython}>Call Python API</button>
      <output role="status" aria-live="polite">{result}</output>
      <p><a href="/docs">API documentation</a></p>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
