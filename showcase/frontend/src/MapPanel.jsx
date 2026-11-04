import React, {useEffect, useRef, useState} from 'react';
import KeplerGl from '@kepler.gl/components';

const STYLES=[{
  id:'carto-light',
  label:'Carto Light',
  url:window.location.origin+'/basemap.json',
  icon:'https://basemaps.cartocdn.com/light_all/4/3/6.png',
}];

export default function MapPanel(){
  const node=useRef(null);
  const [size,setSize]=useState({width:950,height:520});
  useEffect(()=>{
    const el=node.current;if(!el)return;
    const observer=new ResizeObserver(([entry])=>{
      const b=entry.contentRect;
      if(b.width>0&&b.height>0)setSize({width:Math.floor(b.width),height:Math.floor(b.height)});
    });
    observer.observe(el);
    return ()=>observer.disconnect();
  },[]);
  return <div className="kepler-root" ref={node}>
    <KeplerGl id="spatial" width={size.width} height={size.height}
      mapboxApiAccessToken="" mapStyles={STYLES} mapStylesReplaceDefault={true} />
  </div>;
}
