import {useEffect,useState} from 'react';
import {Activity,ArrowRight,Braces,CheckCircle2,ChevronDown,Code2,Copy,ExternalLink,FileCode2,Folder,GitBranch,Github,Gauge,Layers,Play,RefreshCw,Server,ShieldCheck,Terminal,Zap} from 'lucide-react';
const repo='https://github.com/austinwin/qpyserve/tree/showcase/render-live-demo/showcase';
const groups=[['backend','Backend',Server],['frontend','Frontend',Layers],['deployment','Deployment',Terminal]];
export default function App(){
  const [tab,setTab]=useState('play');
  const [health,setHealth]=useState(null);
  const [statusError,setStatusError]=useState('');
  const [flow,setFlow]=useState('4200'),[diameter,setDiameter]=useState('16');
  const [answer,setAnswer]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[duration,setDuration]=useState(0);
  const [files,setFiles]=useState({}),[path,setPath]=useState('main.py'),[code,setCode]=useState(''),[sourceError,setSourceError]=useState(''),[copied,setCopied]=useState(false);
  const [expanded,setExpanded]=useState({backend:true,frontend:true,deployment:true});
  async function refresh(){
    try{const r=await fetch('/api/health',{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);setHealth(await r.json());setStatusError('')}
    catch(e){setHealth(null);setStatusError(e.message)}
  }
  useEffect(()=>{refresh();fetch('/api/source-files').then(r=>r.json()).then(setFiles).catch(()=>{})},[]);
  useEffect(()=>{
    const controller=new AbortController();setSourceError('');setCode('');
    fetch('/api/source?path='+encodeURIComponent(path),{signal:controller.signal}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(r=>setCode(r.content)).catch(e=>{if(e.name!=='AbortError')setSourceError(e.message)});
    return ()=>controller.abort()
  },[path]);
  async function calculate(e){
    e.preventDefault();setAnswer(null);setError('');setBusy(true);const t=performance.now();
    try{const r=await fetch('/api/flow',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({flow_gpm:Number(flow),diameter_in:Number(diameter)})});const data=await r.json();setDuration(Math.round(performance.now()-t));if(!r.ok)throw Error(JSON.stringify(data.detail));setAnswer(data)}
    catch(e){setError(e.message)}finally{setBusy(false)}
  }
  async function copy(){try{await navigator.clipboard.writeText(code);setCopied(true);setTimeout(()=>setCopied(false),1300)}catch{}}
  const selected=groups.find(g=>(files[g[0]]||[]).some(f=>f.id===path));
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-symbol"><Braces size={23}/></span><div><strong>QPyServe</strong><small>LIVE SHOWCASE</small></div></div>
      <div className="sub-label">WORKSPACE</div>
      <button className={'nav '+(tab==='play'?'active':'')} onClick={()=>setTab('play')}><Gauge size={17}/>Playground<ArrowRight size={15} className="nav-end"/></button>
      <button className={'nav '+(tab==='code'?'active':'')} onClick={()=>setTab('code')}><Code2 size={17}/>Source explorer<ArrowRight size={15} className="nav-end"/></button>
      <div className="push"/>
      <div className="hint"><Zap size={19}/><div><b>One origin, two stacks</b><p>FastAPI powers the API. React powers this interface. QPyServe connects them.</p></div></div>
      <div className="side-status"><span className={'dot '+(health?'good':'')}/>{health?'Backend connected':'Backend unavailable'}<button onClick={refresh} title="Retry"><RefreshCw size={15}/></button></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="crumb">QPyServe <span>/</span> <b>{tab==='play'?'Playground':'Source explorer'}</b></div><div className="top-right"><span className={'pill '+(health?'green':'amber')}>{health?'● Live API':'○ Offline'}</span><a href="https://github.com/austinwin/qpyserve" target="_blank" rel="noreferrer"><Github size={17}/> <span>Framework</span><ExternalLink size={13}/></a></div></header>
      <div className="content">
      {tab==='play'?<>
        <div className="eyebrow"><i/>PRODUCTION DEPLOYMENT · REACT + FASTAPI</div>
        <div className="hero"><div><h1>One app.<br/><em>Both sides of the stack.</em></h1><p>A real QPyServe application hosted online. Run a calculation through Python, inspect the JSON response, then explore every public source file powering the demo.</p><div className="hero-buttons"><button className="button primary" onClick={()=>document.getElementById('api')?.scrollIntoView({behavior:'smooth'})}><Play size={16} fill="currentColor"/>Try the live API<ArrowRight size={16}/></button><button className="button secondary" onClick={()=>setTab('code')}><FileCode2 size={16}/>Browse source</button></div></div><div className="graphic"><div className="stack"><span className="react-logo">⚛</span><div><b>React</b><small>Vite frontend</small></div></div><div className="connector"><span/><b>ONE ORIGIN</b><span/></div><div className="stack bottom"><span className="python-logo">Py</span><div><b>FastAPI</b><small>Python backend</small></div></div></div></div>
        <div className="metrics"><div><label><Activity size={15}/>API Status</label><strong>{health?'Healthy':'Unavailable'}</strong><small>{health?'GET /api/health succeeded':statusError||'Checking…'}</small></div><div><label><RefreshCw size={15}/>Backend Uptime</label><strong>{health?Math.floor(health.uptime_seconds/60)+' min':'—'}</strong><small>Since process started</small></div><div><label><Layers size={15}/>Architecture</label><strong>2 layers</strong><small>React UI + FastAPI API</small></div></div>
        <div id="api" className="section-heading"><div><span className="section-kicker">INTERACTIVE TEST</span><h2>See Python work behind React</h2><p>Adjust the values and send a real POST request to the backend.</p></div><span className="pill"><Zap size={13}/>Live calculation</span></div>
        <div className="demo-grid"><form className="panel" onSubmit={calculate}><div className="panel-title"><strong><span className="method">POST</span>/api/flow</strong><small>Request body</small></div><div className="panel-body"><label>Flow rate <span>GPM</span></label><div className="input-wrap"><input type="number" min="0" max="200000" step="any" value={flow} onChange={e=>setFlow(e.target.value)} required/><span>gallons/min</span></div><label>Inside pipe diameter <span>inches</span></label><div className="input-wrap"><input type="number" min="0.01" max="144" step="any" value={diameter} onChange={e=>setDiameter(e.target.value)} required/><span>inches</span></div><div className="hint-line"><ShieldCheck size={15}/>Pydantic validates the request on the backend</div><button className="button primary wide" disabled={busy}>{busy?'Calculating…':<><Play size={15} fill="currentColor"/>Run calculation<ArrowRight size={16}/></>}</button></div></form>
        <div className="panel result-panel"><div className="panel-title"><strong><span className={'status-bullet '+(answer?'lit':'')}/>Backend response</strong><span className={'pill '+(answer?'green':'')}>{answer?'200 OK · '+duration+'ms':'JSON'}</span></div>{answer?<div className="result-content"><div className="numbers"><div><small>Average velocity</small><strong>{answer.velocity_fps} <span>ft/s</span></strong></div><div><small>Flow volume</small><strong>{answer.flow_mgd} <span>MGD</span></strong></div></div><pre className="json">{JSON.stringify(answer,null,2)}</pre></div>:<div className="empty"><span className="empty-symbol"><Terminal size={28}/></span><strong>{error?'Request failed':'Awaiting request'}</strong><p>{error||'Run the calculation to see actual JSON returned by Python.'}</p></div>}</div></div>
        <div className="cta"><div className="cta-icon"><Code2/></div><div><strong>Want to see exactly how this works?</strong><p>Browse real Python routes, React components, CSS and deployment configuration.</p></div><button className="button secondary" onClick={()=>setTab('code')}>Explore the code<ArrowRight size={15}/></button></div>
      </>:<>
        <div className="eyebrow"><i/>FULL SOURCE TRANSPARENCY</div>
        <div className="source-heading"><div><h1>Explore the <em>source code.</em></h1><p>Actual files read from the deployed application. Open the Python backend, React frontend, styles, and deployment configuration.</p></div><a href={repo} target="_blank" rel="noreferrer" className="button secondary"><Github size={16}/>Open on GitHub<ExternalLink size={13}/></a></div>
        <div className="explorer"><div className="file-sidebar"><div className="file-title"><Folder size={15}/>PROJECT FILES</div>{groups.map(([id,label,Icon])=><div key={id} className="file-group"><button className="group-button" onClick={()=>setExpanded(v=>({...v,[id]:!v[id]}))}><Icon size={15}/>{label}<ChevronDown className={!expanded[id]?'folded':''} size={13}/></button>{expanded[id]&&(files[id]||[]).map(f=><button key={f.id} className={'file-button '+(f.id===path?'picked':'')} onClick={()=>setPath(f.id)} title={f.id}><FileCode2 size={14}/><span>{f.name}</span></button>)}</div>)}</div><div className="code-area"><div className="code-header"><div><div className="code-path">{selected?.[1]||'Source'} <span>/</span> <strong>{path}</strong></div><small>{code.split('\n').length} lines · read-only</small></div><button className="button copy" onClick={copy} disabled={!code}>{copied?<CheckCircle2 size={15}/>:<Copy size={15}/>} {copied?'Copied':'Copy'}</button></div><div className="code-scroll">{sourceError?<p className="source-error">{sourceError}</p>:<pre className="code-text">{code.split('\n').map((line,i)=><span className="code-line" key={i}><span className="line-no">{i+1}</span><span className="line-text">{line||' '}</span></span>)}</pre>}</div></div></div>
        <div className="source-notice"><ShieldCheck size={17}/>The explorer displays an explicit allowlist of demo source files. It cannot browse arbitrary files or reveal server credentials.</div>
      </>}
      <footer><span><span className="dot good"/>Powered by QPyServe 0.4 · FastAPI · React</span><span>Full-stack deployment proof of concept</span></footer>
      </div>
    </main>
  </div>;
}
