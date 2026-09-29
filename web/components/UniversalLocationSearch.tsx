'use client';

import {useEffect,useMemo,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import {Clock3,LocateFixed,MapPin,Search} from 'lucide-react';
import {gaonApi,PlaceSuggestion,Serviceability} from '@/lib/api';

const RECENTS='gaonone_recent_locations_v1';
type Recent={label:string;latitude:number;longitude:number;serviceable?:boolean;serviceArea?:string};
const sessionId=()=>typeof crypto!=='undefined'&&'randomUUID'in crypto?crypto.randomUUID():`${Date.now()}-${Math.random().toString(36).slice(2)}`;
function readRecents():Recent[]{try{return JSON.parse(localStorage.getItem(RECENTS)||'[]').slice(0,5)}catch{return[]}}
function remember(location:Recent){const next=[location,...readRecents().filter(x=>Math.abs(x.latitude-location.latitude)>0.00001||Math.abs(x.longitude-location.longitude)>0.00001)].slice(0,5);localStorage.setItem(RECENTS,JSON.stringify(next));return next}
const optionStyle={width:'100%',display:'flex',alignItems:'center',gap:10,textAlign:'left' as const,padding:'12px 10px',border:0,background:'transparent',cursor:'pointer'};

export function UniversalLocationSearch({compact=false}:{compact?:boolean}){
 const router=useRouter();
 const session=useRef(sessionId());
 const autocompleteRequest=useRef(0);
 const locationRequest=useRef(0);
 const[q,setQ]=useState('');
 const[items,setItems]=useState<PlaceSuggestion[]>([]);
 const[recents,setRecents]=useState<Recent[]>([]);
 const[focused,setFocused]=useState(false);
 const[busy,setBusy]=useState(false);
 const[message,setMessage]=useState('');
 const normalized=q.trim();

 useEffect(()=>setRecents(readRecents()),[]);
 useEffect(()=>{
  const requestId=++autocompleteRequest.current;
  const query=normalized;
  if(query.length<2){setItems([]);return}
  const timer=window.setTimeout(async()=>{
   try{
    const next=await gaonApi.placeAutocomplete(query,session.current);
    if(requestId!==autocompleteRequest.current)return;
    setItems(next);
    setMessage('');
   }catch(e:any){
    if(requestId!==autocompleteRequest.current)return;
    setItems([]);
    setMessage(e.status===401?'Log in to search locations, or use Current location.':e.message);
   }
  },250);
  return()=>window.clearTimeout(timer);
 },[normalized]);

 const hint=useMemo(()=>compact?'Search area, colony, town, city or pincode':'Search any area, colony, neighbourhood, town, city, landmark or pincode',[compact]);
 function isCurrent(requestId:number){return requestId===locationRequest.current}
 function beginLocationRequest(){
  const requestId=++locationRequest.current;
  autocompleteRequest.current+=1;
  setItems([]);
  setFocused(false);
 setBusy(true);
 return requestId;
}
 function changeQuery(next:string){
  if(busy){
   locationRequest.current+=1;
   setBusy(false);
  }
  setQ(next);
 }
 function go(location:Recent,coverage:Serviceability){const saved={...location,serviceable:coverage.serviceable,serviceArea:coverage.service_area_name};setRecents(remember(saved));const next=new URLSearchParams({lat:String(location.latitude),lng:String(location.longitude),location:location.label,serviceable:coverage.serviceable?'1':'0'});if(coverage.service_area_name)next.set('service_area',coverage.service_area_name);router.push(`/market?${next}`)}
 async function resolve(label:string,latitude:number,longitude:number,requestId:number){
  try{
   const coverage=await gaonApi.serviceability(latitude,longitude);
   if(!isCurrent(requestId))return;
   go({label,latitude,longitude},coverage);
   setMessage('');
   setBusy(false);
  }catch(e:any){
   if(!isCurrent(requestId))return;
   setMessage(e.message);
   setBusy(false);
  }
 }
 async function select(item:PlaceSuggestion){
  const requestId=beginLocationRequest();
  try{
   const place=await gaonApi.placeDetails(item.place_id,session.current);
   if(!isCurrent(requestId))return;
   await resolve(place.formatted_address||item.text,place.latitude,place.longitude,requestId);
   if(isCurrent(requestId))session.current=sessionId();
  }catch(e:any){
   if(!isCurrent(requestId))return;
   setMessage(e.message);
   setBusy(false);
  }
 }
 function selectRecent(item:Recent){const requestId=beginLocationRequest();void resolve(item.label,item.latitude,item.longitude,requestId)}
 function current(){
  if(!navigator.geolocation){setMessage('Location is not supported by this browser.');return}
  const requestId=beginLocationRequest();
  navigator.geolocation.getCurrentPosition(async p=>{
   let locationLabel='Current location';
   try{const place=await gaonApi.reverseGeocode(p.coords.latitude,p.coords.longitude);if(place.formatted_address)locationLabel=place.formatted_address}catch{}
   if(!isCurrent(requestId))return;
   await resolve(locationLabel,p.coords.latitude,p.coords.longitude,requestId);
  },()=>{
   if(!isCurrent(requestId))return;
   setBusy(false);
   setMessage('Location permission was not granted. Search for your area instead.');
  },{enableHighAccuracy:false,timeout:10000});
 }
 const showRecents=focused&&normalized.length<2&&recents.length>0;
 return <div style={{position:'relative',width:'100%'}}><div className="search" style={{width:'100%'}}><MapPin size={20}/><input value={q} onFocus={()=>setFocused(true)} onBlur={()=>setTimeout(()=>setFocused(false),150)} onChange={e=>changeQuery(e.target.value)} placeholder={hint} aria-label="Search location" autoComplete="off"/><button className="btn" type="button" onClick={current} disabled={busy} aria-label="Use current location"><LocateFixed size={18}/></button></div>{(items.length>0||showRecents)&&<div className="panel" style={{position:'absolute',zIndex:20,left:0,right:0,top:'calc(100% + 6px)',padding:6,maxHeight:320,overflowY:'auto'}}>{showRecents&&<div className="muted small" style={{padding:'7px 10px',fontWeight:700}}>RECENT LOCATIONS</div>}{showRecents&&recents.map(item=><button key={`${item.latitude}-${item.longitude}`} type="button" disabled={busy} onMouseDown={e=>e.preventDefault()} onClick={()=>selectRecent(item)} style={optionStyle}><Clock3 size={16}/><span>{item.label}</span></button>)}{items.map(item=><button key={item.place_id} type="button" disabled={busy} onMouseDown={e=>e.preventDefault()} onClick={()=>void select(item)} style={optionStyle}><Search size={16}/><span>{item.text}</span></button>)}</div>}{message&&<div className="muted small" style={{marginTop:8}}>{message}</div>}</div>;
}
