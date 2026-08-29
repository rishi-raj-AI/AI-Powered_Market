'use client';

import {useEffect,useMemo,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import {LocateFixed,MapPin,Search} from 'lucide-react';

const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
type Suggestion={place_id:string;text:string;structured_format?:Record<string,unknown>};
type Place={place_id:string;formatted_address?:string;latitude?:number;longitude?:number};

function sessionId(){
  if(typeof crypto!=='undefined'&&'randomUUID'in crypto)return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function UniversalLocationSearch({compact=false}:{compact?:boolean}){
  const router=useRouter();
  const token=useRef(sessionId());
  const [q,setQ]=useState('');
  const [items,setItems]=useState<Suggestion[]>([]);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  const normalized=q.trim();

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
      }catch(error){
        if((error as Error).name!=='AbortError'){setItems([]);setMessage((error as Error).message)}
      }
    },250);
    return()=>{clearTimeout(timer);controller.abort()};
  },[normalized]);

  const hint=useMemo(()=>compact?'Search area, colony, city, village or pincode':'Search any area, colony, neighbourhood, village, town, city, landmark or pincode',[compact]);

  async function select(placeId:string,label:string){
    setBusy(true);setItems([]);
    try{
      const params=new URLSearchParams({session_token:token.current});
      const response=await fetch(`${API}/location/place/${encodeURIComponent(placeId)}?${params}`,{cache:'no-store'});
      if(!response.ok)throw new Error('Could not resolve this location.');
      const place:Place=await response.json();
      if(place.latitude==null||place.longitude==null)throw new Error('This location has no usable coordinates.');
      const next=new URLSearchParams({lat:String(place.latitude),lng:String(place.longitude),location:place.formatted_address||label});
      router.push(`/market?${next}`);
    }catch(error){setMessage((error as Error).message);setBusy(false)}
  }

  function useCurrentLocation(){
    if(!navigator.geolocation){setMessage('Location is not supported by this browser.');return}
    setBusy(true);setItems([]);
    navigator.geolocation.getCurrentPosition(
      pos=>{const next=new URLSearchParams({lat:String(pos.coords.latitude),lng:String(pos.coords.longitude),location:'Current location'});router.push(`/market?${next}`)},
      ()=>{setBusy(false);setMessage('Location permission was not granted. Search for your area instead.')},
      {enableHighAccuracy:false,timeout:10000},
    );
  }

  return <div style={{position:'relative',width:'100%'}}>
    <div className="search" style={{width:'100%'}}>
      <MapPin size={20}/>
      <input value={q} onChange={e=>setQ(e.target.value)} placeholder={hint} aria-label="Search location" autoComplete="off"/>
      <button className="btn" type="button" onClick={useCurrentLocation} disabled={busy} aria-label="Use current location"><LocateFixed size={18}/></button>
    </div>
    {items.length>0&&<div className="panel" style={{position:'absolute',zIndex:20,left:0,right:0,top:'calc(100% + 6px)',padding:6,maxHeight:320,overflowY:'auto'}}>
      {items.map(item=><button key={item.place_id} type="button" onClick={()=>select(item.place_id,item.text)} style={{width:'100%',display:'flex',alignItems:'center',gap:10,textAlign:'left',padding:'12px 10px',border:0,background:'transparent',cursor:'pointer'}}><Search size={16}/><span>{item.text}</span></button>)}
    </div>}
    {message&&<div className="muted" style={{marginTop:8,fontSize:13}}>{message}</div>}
  </div>;
}
