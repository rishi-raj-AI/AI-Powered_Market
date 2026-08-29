'use client';

import {useEffect,useState} from 'react';
import {AlertTriangle,Clock3,MapPin,Navigation,Radio,RefreshCw} from 'lucide-react';
import {getToken} from '@/lib/api';
import {LocationMap,MapPoint} from '@/components/LocationMap';

type Point={latitude?:number|null;longitude?:number|null;label?:string|null};
type RiderLocation={latitude:number;longitude:number;accuracy_m?:number|null;heading_deg?:number|null;speed_mps?:number|null;recorded_at:string};
type Tracking={order_id:string;order_number:string;order_status:string;delivery_id?:string|null;delivery_status?:string|null;tracking_active:boolean;store:Point;customer:Point;rider?:RiderLocation|null;rider_location_age_seconds?:number|null};
type RouteData={available:boolean;provider:string;origin:Point;destination:Point;distance_meters?:number|null;duration_seconds?:number|null;encoded_polyline?:string|null};

const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
const STALE_LOCATION_SECONDS=30;
const label=(value:string)=>value.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
const duration=(seconds?:number|null)=>seconds==null?'—':seconds<60?'< 1 min':`${Math.max(1,Math.round(seconds/60))} min`;
const distance=(meters?:number|null)=>meters==null?'—':meters<1000?`${meters} m`:`${(meters/1000).toFixed(1)} km`;

export function LiveTracking({orderId}:{orderId:string}){
  const[data,setData]=useState<Tracking|null>(null);
  const[route,setRoute]=useState<RouteData|null>(null);
  const[error,setError]=useState('');
  const[loading,setLoading]=useState(true);

  async function load(){
    const token=getToken();if(!token)return;
    try{const response=await fetch(`${API}/orders/${orderId}/tracking`,{headers:{Authorization:`Bearer ${token}`},cache:'no-store'});if(!response.ok)throw new Error(`Tracking unavailable (${response.status})`);setData(await response.json());setError('')}catch(e:any){setError(e.message||'Tracking unavailable.')}finally{setLoading(false)}
  }
  async function loadRoute(){
    const token=getToken();if(!token)return;
    try{const response=await fetch(`${API}/orders/${orderId}/route`,{headers:{Authorization:`Bearer ${token}`},cache:'no-store'});if(response.ok)setRoute(await response.json())}catch{}
  }

  useEffect(()=>{load();loadRoute();const gpsTimer=window.setInterval(load,5000);const routeTimer=window.setInterval(loadRoute,30000);return()=>{window.clearInterval(gpsTimer);window.clearInterval(routeTimer)}},[orderId]);

  if(loading)return <div className="card"><p className="muted"><RefreshCw size={15}/> Loading delivery tracking…</p></div>;
  if(error)return <div className="card"><p className="muted">{error}</p></div>;
  if(!data)return null;

  const rider=data.rider;
  const age=data.rider_location_age_seconds??0;
  const stale=Boolean(rider&&age>STALE_LOCATION_SECONDS);
  const riderMap=rider?`https://www.google.com/maps/search/?api=1&query=${rider.latitude},${rider.longitude}`:null;
  const points:MapPoint[]=[];
  if(data.store.latitude!=null&&data.store.longitude!=null)points.push({lat:data.store.latitude,lng:data.store.longitude,label:data.store.label||'Store',kind:'store'});
  if(data.customer.latitude!=null&&data.customer.longitude!=null)points.push({lat:data.customer.latitude,lng:data.customer.longitude,label:data.customer.label||'Delivery address',kind:'customer'});
  if(rider&&data.tracking_active)points.push({lat:rider.latitude,lng:rider.longitude,label:stale?'Delivery partner • delayed location':'Delivery partner',kind:'rider'});
  const center=rider&&data.tracking_active?{lat:rider.latitude,lng:rider.longitude}:points[0];

  return <div className="card stack" aria-live="polite">
    <div className="row space"><div className="row"><Radio size={18}/><strong>Live delivery</strong></div><span className={`badge status-${data.delivery_status||'unassigned'}`}>{label(data.delivery_status||'unassigned')}</span></div>
    {route?.available&&!stale&&<div className="row space"><div className="row"><Clock3 size={17}/><strong>ETA {duration(route.duration_seconds)}</strong></div><span className="muted">{distance(route.distance_meters)} remaining</span></div>}
    {route?.available&&stale&&<div className="notice"><AlertTriangle size={17}/> ETA paused until a fresh rider location arrives.</div>}
    {points.length>0&&<LocationMap latitude={center?.lat} longitude={center?.lng} markers={points} encodedPolyline={!stale?route?.encoded_polyline||'':''} height={320} zoom={15}/>} 
    {data.tracking_active?<>
      {rider?<>
        <div className="row"><MapPin size={17}/><span>Rider location received {age}s ago</span></div>
        {stale&&<div className="notice"><AlertTriangle size={17}/> Rider location may be delayed. The app will update automatically when a fresh GPS signal arrives.</div>}
        <p className="muted small">GPS accuracy {rider.accuracy_m!=null?`≈ ${Math.round(rider.accuracy_m)} m`:'not reported'}.</p>
        {riderMap&&<a className="btn secondary" href={riderMap} target="_blank" rel="noreferrer"><Navigation size={16}/> Open rider location</a>}
      </>:<p className="muted">Rider assigned. Waiting for the first live GPS update.</p>}
    </>:<p className="muted">{data.order_status==='delivered'?'Delivery completed. Live rider sharing has stopped for privacy.':'Live tracking starts after a rider accepts the delivery.'}</p>}
  </div>;
}
