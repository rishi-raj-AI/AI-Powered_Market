'use client';

import {useEffect,useMemo,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import {Clock3,LocateFixed,MapPin,Search} from 'lucide-react';

const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
const RECENTS='gaonone_recent_locations_v1';
type Suggestion={place_id:string;text:string;structured_format?:Record<string,unknown>};
type Place={place_id?:string;formatted_address?:string;latitude?:number;longitude?:number};
type Coverage={serviceable:boolean;service_area_name?:string;distance_km?:number;radius_km?:number};
type Recent={label:string;latitude:number;longitude:number;serviceable?:boolean;serviceArea?:string};

function sessionId(){
  if(typeof crypto!=='undefined'&&'randomUUID'in crypto)return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
function readRecents():Recent[]{try{return JSON.parse(localStorage.getItem(RECENTS)||'[]').slice(0,5)}catch{return[]}}
function remember(location:Recent){
  const next=[location,...readRecents().filter(x=>Math.abs(x.latitude-location.latitude)>0.00001||Math.abs(x.longitude-location.longitude)>0.00001)].slice(0,5);
  localStorage.setItem(RECENTS,JSON.stringify(next));
  return next;
}

export function UniversalLocationSearch({compact=false}:{compact?:boolean}){
  const router=useRouter();
  const token=useRef(sessionId());
  const [q,setQ]=useState('');
  const [items,setItems]=useState<Suggestion[]>([]);
  const [recents,setRecents]=useState<Recent[]>([]);
  const [focused,setFocused]=useState(false);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  const normalized=q.trim();
  useEffect(()=>setRecents(readRecents()),[]);

  useEffect(()=>{
    if(normalized.length<2){setItems([]);return}
    const controller=new AbortController();
    const timer=setTimeout(async()=>{
      try{
        const params=new URLSearchParams({q:normalized,session_token:token.current});
        const response=await fetch(`${API}/location/autocomplete?${params}`,{signal:controller.signal,cache:'no-store'});
        if(!response.ok)throw new Error('Location search is temporarily unavailable.');
        setItems(await response.json());
        setMessage('');
      }catch(error){if((error as Error).name!=='AbortError'){setItems([]);setMessage((error as Error).message)}}
    },250);
    return()=>{clearTimeout(timer);controller.abort()};
  },[normalized]);

  const hint=useMemo(()=>compact?'Search area, colony, city, village or pincode':'Search any area, colony, neighbourhood, village, town, city, landmark or pincode',[compact]);

  async function coverage(latitude:number,longitude:number):Promise<Coverage>{
    try{
      const params=new URLSearchParams({latitude:String(latitude),longitude:String(longitude)});
      const response=await fetch(`${API}/location/serviceability?${params}`,{cache:'no-store'});
      if(!response.ok)return{serviceable:false};
      return response.json();
    }catch{return{serviceable:false}}
  }
  function go(location:Recent,c:Coverage){
    const saved={...location,serviceable:c.serviceable,serviceArea:c.service_area_name};
    setRecents(remember(saved));
    const next=new URLSearchParams({lat:String(location.latitude),lng:String(location.longitude),location:location.label,serviceable:c.serviceable?'1':'0'});
    if(c.service_area_name)next.set('service_area',c.service_area_name);
    if(c.distance_km!=null)next.set('service_distance',String(c.distance_km));
    if(c.radius_km!=null)next.set('service_radius',String(c.radius_km));
    router.push(`/market?${next}`);
  }
  async function useResolved(label:string,latitude:number,longitude:number){
    setBusy(true);setItems([]);setFocused(false);
    const c=await coverage(latitude,longitude);
    go({label,latitude,longitude},c);
  }
  async function select(placeId:string,label:string){
    setBusy(true);setItems([]);
    try{
      const params=new URLSearchParams({session_token:token.current});
      const response=await fetch(`${API}/location/place/${encodeURIComponent(placeId)}?${params}`,{cache:'no-store'});
      if(!response.ok)throw new Error('Could not resolve this location.');
      const place:Place=await response.json();
      if(place.latitude==null||place.longitude==null)throw new Error('This location has no usable coordinates.');
      await useResolved(place.formatted_address||label,place.latitude,place.longitude);
    }catch(error){setMessage((error as Error).message);setBusy(false)}
  }
  async function resolveCurrent(latitude:number,longitude:number){
    let label='Current location';
    try{
      const params=new URLSearchParams({latitude:String(latitude),longitude:String(longitude),session_token:token.current});
      const response=await fetch(`${API}/location/reverse?${params}`,{cache:'no-store'});
      if(response.ok){const value:Place|null=await response.json();if(value?.formatted_address)label=value.formatted_address}
    }catch{}
    await useResolved(label,latitude,longitude);
  }
  function useCurrentLocation(){
    if(!navigator.geolocation){setMessage('Location is not supported by this browser.');return}
    setBusy(true);setItems([]);
    navigator.geolocation.getCurrentPosition(
      pos=>void resolveCurrent(pos.coords.latitude,pos.coords.longitude),
      ()=>{setBusy(false);setMessage('Location permission was not granted. Search for your area instead.')},
      {enableHighAccuracy:false,timeout:10000},
    );
  }

  const showRecents=focused&&normalized.length<2&&recents.length>0;
  return <div style={{position:'relative',width:'100%'}}>
    <div className="search" style={{width:'100%'}}>
      <MapPin size={20}/>
      <input value={q} onFocus={()=>setFocused(true)} onBlur={()=>setTimeout(()=>setFocused(false),150)} onChange={e=>setQ(e.target.value)} placeholder={hint} aria-label="Search location" autoComplete="off"/>
      <button className="btn" type="button" onClick={useCurrentLocation} disabled={busy} aria-label="Use current location"><LocateFixed size={18}/></button>
    </div>
    {(items.length>0||showRecents)&&<div className="panel" style={{position:'absolute',zIndex:20,left:0,right:0,top:'calc(100% + 6px)',padding:6,maxHeight:320,overflowY:'auto'}}>
      {showRecents&&<div className="muted" style={{padding:'7px 10px',fontSize:12,fontWeight:700}}>RECENT LOCATIONS</div>}
      {showRecents&&recents.map(item=><button key={`${item.latitude}-${item.longitude}`} type="button" onMouseDown={e=>e.preventDefault()} onClick={()=>void useResolved(item.label,item.latitude,item.longitude)} style={{width:'100%',display:'flex',alignItems:'center',gap:10,textAlign:'left',padding:'12px 10px',border:0,background:'transparent',cursor:'pointer'}}><Clock3 size={16}/><span>{item.label}</span></button>)}
      {items.map(item=><button key={item.place_id} type="button" onMouseDown={e=>e.preventDefault()} onClick={()=>void select(item.place_id,item.text)} style={{width:'100%',display:'flex',alignItems:'center',gap:10,textAlign:'left',padding:'12px 10px',border:0,background:'transparent',cursor:'pointer'}}><Search size={16}/><span>{item.text}</span></button>)}
    </div>}
    {message&&<div className="muted" style={{marginTop:8,fontSize:13}}>{message}</div>}
  </div>;
}
