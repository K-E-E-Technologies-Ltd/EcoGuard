import React,{useEffect,useRef,useState} from 'react';
import {Button,Icon,Badge,Empty} from './ui';
import type {GeoData,GeoFeature} from '../lib/types';
import 'leaflet/dist/leaflet.css';
export function MapPanel({data,onSelect,large=false}:{data:GeoData;onSelect:(feature:GeoFeature)=>void;large?:boolean}){
 const ref=useRef<HTMLDivElement>(null),mapRef=useRef<any>(null);const [ready,setReady]=useState(false),[offline,setOffline]=useState(false),[zoom,setZoom]=useState(1);
 // No credentials or sensitive information go to a tile provider. Coordinates stay inside the application.
 // Default: a neutral spatial canvas. Optional OSM tiles require enabling VITE_MAP_TILES=osm.
 useEffect(()=>{let active=true;setReady(false);setOffline(false);
  import('leaflet').then(module=>{
   if(!active||!ref.current)return;const L=module.default||module;
   const map=L.map(ref.current,{attributionControl:true,scrollWheelZoom:false}).setView([.3,31.1],7);mapRef.current=map;
   if(import.meta.env.VITE_MAP_TILES==='osm')L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
   else map.attributionControl.addAttribution('EcoGuard spatial view • no basemap loaded');
   data.features.forEach(f=>{
    const p=f.geometry.coordinates;
    const color=f.properties.category==='wildlife'?'#a85615':f.properties.category==='flood'?'#286581':'#1c694c';
    const marker=L.circleMarker([p[1],p[0]],{radius:10,color:'#fff',weight:3,fillColor:color,fillOpacity:1}).addTo(map);
    const el=document.createElement('span');el.textContent=f.properties.title;
    marker.bindTooltip(el);marker.on('click',()=>onSelect(f));
   });
   if(data.features.length){map.fitBounds(data.features.map(f=>[f.geometry.coordinates[1],f.geometry.coordinates[0]] as [number,number]),{padding:[45,45],maxZoom:10});}
   setReady(true);setTimeout(()=>map.invalidateSize(),50);
  }).catch(()=>{if(active)setOffline(true);});
  return()=>{active=false;mapRef.current?.remove();mapRef.current=null;};
 },[JSON.stringify(data.features)]);
 const fs=data.features;const lons=fs.map(f=>f.geometry.coordinates[0]),lats=fs.map(f=>f.geometry.coordinates[1]);
 const minLon=Math.min(...lons,30),maxLon=Math.max(...lons,32.8),minLat=Math.min(...lats,0),maxLat=Math.max(...lats,1.2);
 return <div className={'map-panel '+(large?'large':'')}><div ref={ref} className={'leaflet-container-host '+(offline?'hidden':'')} />
 {offline&&<div className="spatial-fallback"><div className="spatial-grid" style={{transform:`scale(${zoom})`}}>{fs.map((f,i)=><button className={'spatial-pin '+f.properties.category} key={f.id} style={{left:`${10+80*(f.geometry.coordinates[0]-minLon)/(maxLon-minLon||1)}%`,top:`${85-70*(f.geometry.coordinates[1]-minLat)/(maxLat-minLat||1)}%`}} aria-label={f.properties.title} title={f.properties.title} onClick={()=>onSelect(f)}><Icon name={f.properties.category==='wildlife'?'paw':f.properties.category==='flood'?'drop':'leaf'} size={17}/><span>{i+1}</span></button>)}</div><div className="mapzoom"><button aria-label="Zoom in" onClick={()=>setZoom(Math.min(zoom+.25,2))}>+</button><button aria-label="Zoom out" onClick={()=>setZoom(Math.max(zoom-.25,.75))}>−</button><button aria-label="Reset spatial view" onClick={()=>setZoom(1)}>↺</button></div></div>}
 {!ready&&!offline&&<span className="map-loading">Preparing map…</span>}
 <div className="map-top"><Badge>{data.features.length} mapped records</Badge></div>
 <div className="map-caption">{offline?'Offline spatial view • no basemap':import.meta.env.VITE_MAP_TILES==='osm'?'Map data: OpenStreetMap contributors':'Spatial view • enable a basemap in configuration'} • Community markers show area centres, not animal positions.</div>
 </div>;
}
