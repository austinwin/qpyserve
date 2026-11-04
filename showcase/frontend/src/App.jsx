import React, {useEffect, useMemo, useRef, useState} from 'react';
import {useDispatch} from 'react-redux';
import {addDataToMap} from '@kepler.gl/actions';
import {processGeojson} from '@kepler.gl/processors';
import {Activity, ArrowDownToLine, ArrowRight, Check, ChevronDown, CircleAlert, Cloud, Code2, Copy, Database, FileCode2, FolderOpen, Github, Globe2, Layers, LoaderCircle, Map as MapIcon, Play, RotateCcw, Server, ShieldCheck, Sparkles, UploadCloud} from 'lucide-react';
import MapPanel from './MapPanel.jsx';

const REPO='https://github.com/austinwin/qpyserve/tree/showcase/render-live-demo/showcase';
const OPERATIONS={
  buffer:{title:'Buffer & dissolve',desc:'Create radius-based polygons around every feature in metres, with optional union.', param:'distance_m',label:'Buffer radius',unit:'metres',min:10,max:2500,step:50},
  density:{title:'Spatial density grid',desc:'Aggregate spatial features into a metre-based square grid and calculate site counts.',param:'cell_m',label:'Grid cell size',unit:'metres',min:150,max:4000,step:100},
  hull:{title:'Convex hull',desc:'Calculate the smallest convex boundary containing all input geometries.'}
};
const parseError=async r=>{let data;try{data=await r.json()}catch{};if(!r.ok)throw Error(typeof data?.detail==='string'?data.detail:'HTTP '+r.status);return data};
const asCount=n=>Number(n||0).toLocaleString();

export default function App(){
  const dispatch=useDispatch();
  const [view,setView]=useState('map');
  const [health,setHealth]=useState(null);
  const [demo,setDemo]=useState(null),[collection,setCollection]=useState(null);
  const [datasetName,setDatasetName]=useState('Synthetic Houston sites');
  const [operation,setOperation]=useState('buffer');
  const [distance,setDistance]=useState(450),[cell,setCell]=useState(1200),[dissolve,setDissolve]=useState(true);
  const [loading,setLoading]=useState(true),[running,setRunning]=useState(false),[error,setError]=useState('');
  const [result,setResult]=useState(null),[lastGeoJSON,setLastGeoJSON]=useState(null),[runCount,setRunCount]=useState(0);
  const [files,setFiles]=useState({}),[sourcePath,setSourcePath]=useState('geoengine.py'),[code,setCode]=useState(''),[sourceError,setSourceError]=useState(''),[copied,setCopied]=useState(false);
  const fileRef=useRef(null);
  const addLayer=(geojson,id,label,center)=>{
    const data=processGeojson(geojson);
    dispatch(addDataToMap({datasets:{info:{id,label},data},option:{centerMap:center,readOnly:false}}));
  };
  async function reset(){
    setLoading(true);setError('');
    try{
      const data=await parseError(await fetch('/api/sample?count=850'));
      setDemo(data);setCollection(data);setDatasetName('Synthetic Houston sites');setResult(null);setLastGeoJSON(null);
      addLayer(data,'synthetic-sites','Synthetic Houston sites',true);
    }catch(e){setError('Unable to load sample: '+e.message)}
    finally{setLoading(false)}
  }
  useEffect(()=>{
    reset();
    fetch('/api/health').then(parseError).then(setHealth).catch(()=>setHealth(null));
    fetch('/api/source-files').then(parseError).then(setFiles).catch(()=>{});
  },[]);
  useEffect(()=>{
    const ctrl=new AbortController();setCode('');setSourceError('');
    fetch('/api/source?path='+encodeURIComponent(sourcePath),{signal:ctrl.signal}).then(parseError).then(v=>setCode(v.content)).catch(e=>{if(e.name!=='AbortError')setSourceError(e.message)});
    return ()=>ctrl.abort();
  },[sourcePath]);
  const op=OPERATIONS[operation];
  async function uploadFile(e){
    const file=e.target.files?.[0]; if(!file)return;
    setError('');
    try{
      if(file.size>3*1024*1024)throw Error('File is over the 3 MB demo limit.');
      const geo=JSON.parse(await file.text());
      if(geo?.type!=='FeatureCollection'||!Array.isArray(geo.features)||geo.features.length===0)throw Error('Upload an EPSG:4326 GeoJSON FeatureCollection.');
      if(geo.features.length>2500)throw Error('Limit is 2500 features per file.');
      setCollection(geo);setDatasetName(file.name);setResult(null);setLastGeoJSON(null);
      addLayer(geo,'uploaded-'+Date.now(),file.name,true);
    }catch(err){setError(err.message)}
    e.target.value='';
  }
  async function run(){
    if(!collection)return;
    setRunning(true);setError('');setResult(null);
    try{
      const response=await fetch('/api/geoprocess',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({collection,operation,distance_m:Number(distance),cell_m:Number(cell),dissolve})
      });
      const data=await parseError(response);
      const next=runCount+1;setRunCount(next);setLastGeoJSON(data);setResult(data.metadata);
      addLayer(data,'result-'+next,op.title+' #'+next,false);
    }catch(e){setError(e.message)}finally{setRunning(false)}
  }
  function download(){
    if(!lastGeoJSON)return;
    const blob=new Blob([JSON.stringify(lastGeoJSON,null,2)],{type:'application/geo+json'});
    const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download='qpyserve-'+operation+'-result.geojson';a.click();URL.revokeObjectURL(u);
  }
  async function copy(){try{await navigator.clipboard.writeText(code);setCopied(true);setTimeout(()=>setCopied(false),1600)}catch{}}
  return <div className="shell">
    <aside className="sidebar">
      <div className="identity"><div className="mark"><Layers size={24}/></div><div><strong>QPyServe</strong><span>SPATIAL LAB <small>v1.1</small></span></div></div>
      <div className="navlist">
        <button className={'nav '+(view==='map'?'selected':'')} onClick={()=>setView('map')}><MapIcon size={17}/>Geospatial workspace</button>
        <button className={'nav '+(view==='source'?'selected':'')} onClick={()=>setView('source')}><Code2 size={17}/>Source code explorer</button>
      </div>
      <div className="nav-divider"/>
      <div className="sidebar-scroll">
      {view==='map'?<>
        <div className="pane-label"><span>01</span> DATASET</div>
        <div className="info-card"><div className="info-icon"><Database size={17}/></div><div className="info-main"><strong>{datasetName}</strong><small>{asCount(collection?.features.length)} features · EPSG:4326</small></div></div>
        <div className="inline-buttons"><button onClick={()=>fileRef.current?.click()}><UploadCloud size={15}/>Import GeoJSON</button><button onClick={reset}><RotateCcw size={15}/>Sample</button></div>
        <input ref={fileRef} type="file" accept=".json,.geojson,application/json,application/geo+json" hidden onChange={uploadFile}/>
        <p className="notice small">Sample data is simulated. No actual Houston Water assets or readings.</p>
        <div className="nav-divider"/>
        <div className="pane-label"><span>02</span> SERVER OPERATION</div>
        <label className="field-label" htmlFor="operation">Algorithm</label>
        <div className="select-wrap"><select id="operation" value={operation} onChange={e=>setOperation(e.target.value)}>{Object.entries(OPERATIONS).map(([k,v])=><option key={k} value={k}>{v.title}</option>)}</select><ChevronDown size={15}/></div>
        <p className="field-help">{op.desc}</p>
        {op.param&&<><div className="field-row"><label className="field-label" htmlFor="param">{op.label}</label><strong>{operation==='buffer'?asCount(distance):asCount(cell)} m</strong></div><input id="param" className="range" type="range" min={op.min} max={op.max} step={op.step} value={operation==='buffer'?distance:cell} onChange={e=>operation==='buffer'?setDistance(+e.target.value):setCell(+e.target.value)}/><div className="range-labels"><span>{op.min} m</span><span>{asCount(op.max)} m</span></div></>}
        {operation==='buffer'&&<label className="toggle-line"><input type="checkbox" checked={dissolve} onChange={e=>setDissolve(e.target.checked)}/><span>Dissolve overlapping buffers</span></label>}
        <button className="run-button" disabled={running||loading||!collection} onClick={run}>{running?<LoaderCircle className="spin" size={17}/>:<Play size={16} fill="currentColor"/>}{running?'Running in Python…':'Run geoprocessing'}<ArrowRight size={16}/></button>
        {error&&<div className="error"><CircleAlert size={16}/><span>{error}</span></div>}
        {result&&<div className="result-box"><div className="result-head"><Check size={16}/>Processing complete</div><div className="stat-row"><span>Input features</span><b>{asCount(result.input_features)}</b></div><div className="stat-row"><span>Output features</span><b>{asCount(result.output_features)}</b></div><div className="stat-row"><span>Backend compute</span><b>{result.elapsed_ms} ms</b></div><div className="stat-row"><span>Calculation CRS</span><b>{result.processing_crs}</b></div><button className="download" onClick={download}><ArrowDownToLine size={14}/>Download result GeoJSON</button></div>}
        <div className="nav-divider"/>
        <div className="pane-label"><span>03</span> DATA FLOW</div>
        <div className="flow-mini"><span><Globe2 size={15}/>React + Kepler.gl</span><i>↓ POST GeoJSON</i><span><Server size={15}/>FastAPI + Shapely</span><i>↓ Result GeoJSON</i><span><Layers size={15}/>New WebGL layer</span></div>
      </>:<>
        <div className="pane-label"><span>01</span> FILE GROUPS</div>
        {Object.entries(files).map(([group,entries])=><div className="filegroup" key={group}><div className="filegroup-title"><FolderOpen size={15}/>{group}</div>{entries.map(f=><button title={f.id} key={f.id} className={'fileitem '+(sourcePath===f.id?'active':'')} onClick={()=>setSourcePath(f.id)}><FileCode2 size={14}/>{f.name}</button>)}</div>)}
        <p className="notice small"><ShieldCheck size={14}/>Only explicitly allowlisted demo source can be viewed.</p>
      </>}
      </div>
      <div className="sidebar-foot"><span className={'led '+(health?'online':'')}/><div><strong>{health?'Backend connected':'Backend unavailable'}</strong><small>QPyServe + FastAPI</small></div></div>
    </aside>
    <main className="main">
      <header className="top"><div className="breadcrumb">Workspace <span>/</span> <strong>{view==='map'?'Geospatial Analysis':'Source Explorer'}</strong></div><div className="top-actions"><div className="top-status"><span className={'led '+(health?'online':'')}/>{health?'API online':'API offline'}</div><a href={REPO} target="_blank" rel="noreferrer"><Github size={16}/>GitHub <ArrowRight size={13}/></a></div></header>
      {view==='map'?<div className="workspace"><div className="map-top"><div><span className="eyebrow">WEBGL + PYTHON GEOPROCESSING</span><h1>Spatial analysis, <em>connected.</em></h1><p>Run geometry operations on the Python server and explore the results in Kepler.gl's interactive map.</p></div><div className="tech-pills"><span>Kepler.gl</span><span>Shapely</span><span>PyProj</span></div></div><div className="map-wrap">{loading&&<div className="map-loader"><LoaderCircle className="spin"/>Loading synthetic data…</div>}<MapPanel/><div className="map-badge"><span className="led online"/>Interactive Kepler.gl map · synthetic data</div></div><div className="under-map"><div><Activity size={16}/>Every operation is calculated by FastAPI, not by the browser.</div><div><ShieldCheck size={16}/>Free-hosted demo · 2,500-feature processing limit</div></div></div>:<div className="source-content"><span className="eyebrow">REAL DEPLOYED SOURCE</span><div className="source-title"><div><h1>Explore both sides <em>of the stack.</em></h1><p>Read the actual backend algorithms, API endpoints, React Kepler.gl integration and Docker build.</p></div><a href={REPO} target="_blank" rel="noreferrer"><Github size={15}/>View repository <ArrowRight size={14}/></a></div><div className="editor"><div className="editor-bar"><div><span>showcase / </span><b>{sourcePath}</b><small>{code.split('\n').length} lines · read-only</small></div><button onClick={copy} disabled={!code}>{copied?<Check size={14}/>:<Copy size={14}/>} {copied?'Copied':'Copy'}</button></div><div className="code-scroll">{sourceError?<div className="error">{sourceError}</div>:<pre>{code.split('\n').map((line,i)=><div className="code-line" key={i}><span className="line-num">{i+1}</span><span>{line||' '}</span></div>)}</pre>}</div></div></div>}
    </main>
  </div>;
}
