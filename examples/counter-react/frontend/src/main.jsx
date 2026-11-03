import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

function App() {
  const [count, setCount] = useState('…');
  const [error, setError] = useState('');
  async function api(path, method = 'GET') {
    try {
      const response = await fetch(path, { method });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setCount((await response.json()).count);
      setError('');
    } catch (err) { setError(err.message); }
  }
  useEffect(() => { api('/api/count'); }, []);
  return <main><h1>React Counter</h1><div className="count">{count}</div>
    <button onClick={() => api('/api/count/increment', 'POST')}>+1</button>
    <button className="secondary" onClick={() => api('/api/count/reset', 'POST')}>Reset</button>
    <p>{error || 'One host • Python /api • Native Vite HMR'}</p></main>;
}

createRoot(document.getElementById('root')).render(<App />);
