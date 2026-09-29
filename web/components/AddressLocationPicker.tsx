'use client';

import {useEffect,useRef,useState} from 'react';
import {CheckCircle2,LocateFixed,MapPin,Search,XCircle} from 'lucide-react';
import {gaonApi,PlaceSuggestion,Serviceability} from '@/lib/api';
import {LocationMap} from '@/components/LocationMap';

const newSession=()=>typeof crypto!=='undefined'&&'randomUUID' in crypto?crypto.randomUUID():`${Date.now()}-${Math.random()}`;

type Props={latitude?:number;longitude?:number;onChange:(lat:number,lng:number)=>void;onAddress:(address:string)=>void;onServiceability?:(service:Serviceability|null)=>void;mode?:'delivery'|'store';requireServiceable?:boolean};

export function AddressLocationPicker({latitude,longitude,onChange,onAddress,onServiceability,mode='delivery',requireServiceable=true}:Props){
 const[q,setQ]=useState('');
 const[suggestions,setSuggestions]=useState<PlaceSuggestion[]>([]);
 const[service,setService]=useState<Serviceability|null>(null);
 const[msg,setMsg]=useState('');
 const[busy,setBusy]=useState(false);
 const session=useRef(newSession());
 const autocompleteRequest=useRef(0);
 const locationRequest=useRef(0);
 const suppressAutocompleteFor=useRef<string|null>(null);
 const noun=mode==='store'?'storefront':'delivery location';
 const searchId=mode==='store'?'store-location-search':'delivery-location-search';

 function publishService(next:Serviceability|null){setService(next);onServiceability?.(next)}
 function clearSuggestions(){autocompleteRequest.current+=1;setSuggestions([])}
 function isCurrent(requestId:number){return requestId===locationRequest.current}
 function beginLocationRequest(){const requestId=++locationRequest.current;clearSuggestions();setBusy(true);return requestId}
 function applyAddress(address:string){suppressAutocompleteFor.current=address.trim();onAddress(address);setQ(address)}
 function changeQuery(next:string){
  suppressAutocompleteFor.current=null;
  if(busy){
   locationRequest.current+=1;
   setBusy(false);
  }
  setQ(next);
 }

 useEffect(()=>{
  const requestId=++autocompleteRequest.current;
  const query=q.trim();
  if(suppressAutocompleteFor.current===query){
   suppressAutocompleteFor.current=null;
   setSuggestions([]);
   return;
  }
  if(query.length<3){setSuggestions([]);return}
  const timer=window.setTimeout(async()=>{
   try{
    const next=await gaonApi.placeAutocomplete(query,session.current);
    if(requestId!==autocompleteRequest.current)return;
    setSuggestions(next);
    setMsg('');
   }catch(e:any){
    if(requestId!==autocompleteRequest.current)return;
    setSuggestions([]);
    setMsg(e.message||'Location search unavailable. You can still place the pin manually.');
   }
  },350);
  return()=>window.clearTimeout(timer);
 },[q]);

 async function resolve(lat:number,lng:number,requestId=beginLocationRequest()){
  onChange(lat,lng);
  try{
   const[r,next]=await Promise.all([gaonApi.reverseGeocode(lat,lng),requireServiceable?gaonApi.serviceability(lat,lng):Promise.resolve(null)]);
   if(!isCurrent(requestId))return;
   publishService(next);
   if(r.formatted_address)applyAddress(r.formatted_address);
   setMsg('');
  }catch(e:any){
   if(!isCurrent(requestId))return;
   publishService(null);
   setMsg(e.message||'Could not verify this location.');
  }finally{
   if(isCurrent(requestId))setBusy(false);
  }
 }
 async function choose(item:PlaceSuggestion){
  const requestId=beginLocationRequest();
  try{
   const place=await gaonApi.placeDetails(item.place_id,session.current);
   if(!isCurrent(requestId))return;
   onChange(place.latitude,place.longitude);
   applyAddress(place.formatted_address);
   const next=requireServiceable?await gaonApi.serviceability(place.latitude,place.longitude):null;
   if(!isCurrent(requestId))return;
   publishService(next);
   session.current=newSession();
   setMsg('');
  }catch(e:any){
   if(!isCurrent(requestId))return;
   publishService(null);
   setMsg(e.message||'Could not select this location.');
  }finally{
   if(isCurrent(requestId))setBusy(false);
  }
 }
 function current(){
  if(!navigator.geolocation){setMsg('Location is not supported by this browser.');return}
  const requestId=beginLocationRequest();
  navigator.geolocation.getCurrentPosition(async p=>{await resolve(p.coords.latitude,p.coords.longitude,requestId)},e=>{
   if(!isCurrent(requestId))return;
   setMsg(e.message||'Location permission was denied.');
   setBusy(false);
  },{enableHighAccuracy:true,timeout:10000});
 }
 return <div className="stack"><div className="field"><label htmlFor={searchId}><Search size={15}/> Search {noun}</label><div className="row"><input id={searchId} value={q} onChange={e=>changeQuery(e.target.value)} placeholder="Search area, road, landmark or address" autoComplete="off"/><button type="button" className="btn secondary" onClick={current} disabled={busy}><LocateFixed size={16}/> Current location</button></div>{suggestions.length>0&&<div className="card stack" aria-label="Location suggestions">{suggestions.map(s=><button type="button" className="btn secondary" style={{justifyContent:'flex-start',textAlign:'left'}} key={s.place_id} disabled={busy} onClick={()=>void choose(s)}><MapPin size={16}/><span><strong>{s.main_text||s.text}</strong>{s.secondary_text&&<span className="muted small"> — {s.secondary_text}</span>}</span></button>)}</div>}</div><LocationMap latitude={latitude} longitude={longitude} editable onChange={resolve} height={300}/>{latitude!==undefined&&longitude!==undefined&&<span className="muted small">Pinned coordinates: {latitude.toFixed(5)}, {longitude.toFixed(5)}</span>}{service&&(service.serviceable?<div className="notice"><CheckCircle2 size={17}/> {mode==='store'?'Store is inside':'Delivery available in'} {service.service_area_name}. {service.distance_km!=null&&`About ${service.distance_km.toFixed(1)} km from the local hub.`}</div>:<div className="notice"><XCircle size={17}/> This pin is outside the currently active GaonOne service area. Adjust the pin before continuing.</div>)}{msg&&<div className="muted small">{msg}</div>}</div>;
}
