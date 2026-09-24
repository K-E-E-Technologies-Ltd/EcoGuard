import React, {useState,useEffect} from 'react';
import type {ReactNode} from 'react';
export function Icon({name='leaf',size=21}:{name?:string;size?:number}){
 const paths:Record<string,ReactNode>={
 leaf:<><path d="M20 3C7 2 3 7 4 14s11 9 14 1c2-5 1-8 2-12Z"/><path d="m3 21 11-12"/></>,
 paw:<><ellipse cx="12" cy="16" rx="6" ry="4.5"/><ellipse cx="4" cy="9" rx="2" ry="3"/><ellipse cx="9" cy="5" rx="2" ry="3"/><ellipse cx="16" cy="5" rx="2" ry="3"/><ellipse cx="21" cy="10" rx="2" ry="3"/></>,
 home:<><path d="m3 10 9-7 9 7v11h-6v-7H9v7H3Z"/></>,
 grid:<><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
 bell:<><path d="M5 10a7 7 0 0 1 14 0v6l2 3H3l2-3Z"/><path d="M9 22h6"/></>,
 map:<><path d="m2 5 6-2 8 3 6-3v16l-6 3-8-3-6 2Zm6-2v16m8-13v16"/></>,
 drop:<><path d="M12 2C9 7 4 11 4 16a8 8 0 0 0 16 0c0-5-5-9-8-14Z"/></>,
 check:<path d="m4 12 5 5L20 6"/>,
 camera:<><path d="M3 7h4l2-3h6l2 3h4v14H3Z"/><circle cx="12" cy="13" r="4"/></>,
 file:<><path d="M5 2h10l5 5v15H5Z"/><path d="M14 2v6h6M8 12h9M8 16h9"/></>,
 user:<><circle cx="12" cy="7" r="4"/><path d="M3 22v-3a9 9 0 0 1 18 0v3"/></>,
 chat:<path d="M3 3h18v14H9l-6 4Z"/>,
 chart:<><path d="M3 3v18h18M7 16v-4m5 4V6m5 10V9"/></>,
 search:<><circle cx="10" cy="10" r="7"/><path d="m16 16 6 6"/></>,
 settings:<><circle cx="12" cy="12" r="4"/><path d="M12 1v3m0 16v3M1 12h3m16 0h3M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/></>,
 arrow:<path d="M3 12h18m-6-6 6 6-6 6"/>,
 back:<path d="M21 12H3m6-6-6 6 6 6"/>,
 plus:<path d="M12 3v18M3 12h18"/>,
 upload:<><path d="M12 17V3m-5 5 5-5 5 5M3 16v5h18v-5"/></>,
 lock:<><rect x="4" y="10" width="16" height="12" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4"/></>,
 help:<><circle cx="12" cy="12" r="10"/><path d="M9 8a3 3 0 0 1 6 0c0 2-3 2-3 5m0 3v2"/></>,
 logout:<><path d="M10 3H3v18h7m2-9h10m-5-5 5 5-5 5"/></>,
 wifi:<><path d="M2 7a17 17 0 0 1 20 0M5 11a12 12 0 0 1 14 0m-10 4a5 5 0 0 1 6 0m-3 4v1"/></>,
 menu:<path d="M3 6h18M3 12h18M3 18h18"/>,
 close:<path d="m5 5 14 14M5 19 19 5"/>,
 };
 return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]||paths.leaf}</svg>;
}
export const categoryIcon=(category:string)=>category==='wildlife'?'paw':category==='flood'?'drop':'leaf';
export const nice=(text:string)=>text.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
export const date=(text?:string|null)=>text?new Intl.DateTimeFormat('en-UG',{dateStyle:'medium',timeStyle:'short'}).format(new Date(text)):'Not yet';
export function Button({children,variant='',icon,...props}:React.ButtonHTMLAttributes<HTMLButtonElement>&{variant?:string;icon?:string}){return <button type="button" className={'btn '+variant} {...props}>{icon&&<Icon name={icon} size={18}/>} {children}</button>;}
export function Brand(){return <a className="brand" href="#/community/home"><span className="mark"><Icon name="leaf"/></span><span>EcoGuard<small>UGANDA</small></span></a>;}
export function Badge({children,tone=''}:{children:ReactNode;tone?:string}){return <span className={'tag '+tone}>{children}</span>;}
export function State({state}:{state:string}){return <Badge tone={['verified','published','closed','completed'].includes(state)?'green':['rejected','retracted','failed'].includes(state)?'red':['under_review','needs_evidence','submitted','unavailable'].includes(state)?'amber':'gray'}>{nice(state)}</Badge>;}
export function Card({children,className=''}:{children:ReactNode;className?:string}){return <section className={'card '+className}>{children}</section>;}
export function Notice({children,tone=''}:{children:ReactNode;tone?:string}){return <div className={'notice '+tone}>{children}</div>;}
export function Empty({title='Nothing here yet',children,action}:{title?:string;children?:ReactNode;action?:ReactNode}){return <div className="empty"><span className="iconbox"><Icon name="leaf" size={27}/></span><h3>{title}</h3><p>{children||'New records will appear here when they are available.'}</p>{action}</div>;}
export function Loading(){return <div role="status" className="loading"><span className="spinner"/>Loading your workspace…</div>;}
export function ErrorBox({message,retry}:{message:string;retry?:()=>void}){return <div role="alert" className="notice red">{message}{retry&&<Button variant="ghost small" onClick={retry}>Retry</Button>}</div>;}
export function Field({label,children,hint}:{label:string;children:ReactNode;hint?:string}){return <label className="field"><span>{label}</span>{children}{hint&&<small>{hint}</small>}</label>;}
export function PageHead({label,title,subtitle,action}:{label?:string;title:string;subtitle?:string;action?:ReactNode}){return <div className="pagehead"><div>{label&&<div className="eyebrow">{label}</div>}<h1>{title}</h1>{subtitle&&<p>{subtitle}</p>}</div>{action}</div>;}
const banners=[{key:'wildlife',heading:'Every sighting can make a difference.',text:'Turn your observations into a clearer path from report to response.',asset:'elephant',cta:'Report a wildlife sighting',route:'upload'}, {key:'wetland',heading:'Healthy wetlands. Stronger communities.',text:'Share observations and follow a human review, all in one place.',asset:'wetland',cta:'Report a wetland concern',route:'wetland'}, {key:'flood',heading:'Useful information. Reviewed before sharing.',text:'Read sourced flood advisories and report changing water conditions.',asset:'flood',cta:'Read flood information',route:'flood'}];
export function Hero({mobile=false,onNavigate}:{mobile?:boolean;onNavigate:(page:string)=>void}){
 const [i,setI]=useState(0),[paused,setPaused]=useState(window.matchMedia('(prefers-reduced-motion: reduce)').matches);
 useEffect(()=>{if(paused)return;const timer=setInterval(()=>setI(n=>(n+1)%banners.length),6500);return()=>clearInterval(timer);},[paused]);
 const b=banners[i];
 return <section className={'hero '+(mobile?'compact':'')} aria-label="Featured work areas"><div className="hero-photo" style={{backgroundImage:`url(/assets/${b.asset}.jpg)`}}/><div className="hero-content"><div className="eyebrow">{b.key==='wildlife'?'WILDLIFE FIRST':'CONNECTED COMMUNITIES'}</div><h2>{b.heading}</h2><p>{b.text}</p><Button onClick={()=>onNavigate(b.route)} icon={categoryIcon(b.key)}>{b.cta}</Button></div><div className="carouselnav"><button aria-label="Previous banner" onClick={()=>setI((i+2)%3)}>‹</button>{banners.map((x,k)=><button key={x.key} aria-label={`Show ${x.key} banner`} aria-pressed={i===k} className={'carodot '+(i===k?'active':'')} onClick={()=>setI(k)}/>)}<button aria-label="Next banner" onClick={()=>setI((i+1)%3)}>›</button><button aria-label={paused?'Play banner':'Pause banner'} onClick={()=>setPaused(!paused)}>{paused?'▶':'Ⅱ'}</button></div><span className="image-credit">Concept illustration</span></section>;
}
export function ImageView({url,label='Private evidence',fallback='elephant',className=''}:{url?:string;label?:string;fallback?:string;className?:string}){return <div className={'imageview '+className}><img src={url||`/assets/${fallback}.jpg`} alt={url?label:'Illustrative nature artwork; not an incident photograph'} loading="lazy"/><span>{url?label:'Concept illustration • not incident evidence'}</span></div>;}
