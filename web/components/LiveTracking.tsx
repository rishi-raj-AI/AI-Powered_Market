'use client';

import {useEffect,useState} from 'react';
import {MapPin,Navigation,Radio,RefreshCw} from 'lucide-react';
import {getToken} from '@/lib/api';

type Point={latitude?:number|null;longitude?:number|null;label?:string|null};
type RiderLocation={latitude:number;longitude:number;accuracy_m?:number|null;heading_deg?:number|null;speed_mps?:number|null;recorded_at:string};
type Tracking={order_id:string;order_number:string;order_status:string;delivery_id?:string|null;delivery_status?:string|null;tracking_active:boolean;store:Point;customer:Point;rider?:RiderLocation|null;rider_location_age_seconds?:number|null};

const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
const label=(value:string)=>value.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());

export function LiveTracking({orderId}:{orderId:string}){
  const[data,setData]=useState<Tracking|null>(null);
  const[error,setError]=useState('');
  const[loading,setLoading]=useState(true);

  async function load(){
    const token=getToken();
    if(!token)return;
    try{
      const response=await fetch(`${API}/orders/${orderId}/tracking`,{headers:{Authorization:`Bearer ${token}`},cache:'no-store'});
      if(!response.ok)throw new Error(`Tracking unavailable (${response.status})`);
      setData(await response.json());setError('');
    }catch(e:any){setError(e.message||'Tracking unavailable.')}finally{setLoading(false)}
  }

  useEffect(()=>{
    load();
    const timer=window.setInterval(()=>{if(data?.tracking_active!==false)load()},5000);
    return()=>window.clearInterval(timer);
  },[orderId,data?.tracking_active]);

  if(loading)return <div className="card"><p className="muted"><RefreshCw size={15}/> Loading delivery tracking…</p></div>;
  if(error)return <div className="card"><p className="muted">{error}</p></div>;
  if(!data)return null;

  const rider=data.rider;
  const riderMap=rider?`https://www.google.com/maps/search/?api=1&query=${rider.latitude},${rider.longitude}`:null;
  return <div className="card stack" aria-live="polite">
    <div className="row space"><div className="row"><Radio size={18}/><strong>Live delivery</strong></div><span className={`badge status-${data.delivery_status||'unassigned'}`}>{label(data.delivery_status||'unassigned')}</span></div>
    {data.tracking_active?<>
      {rider?<>
        <div className="row"><MapPin size={17}/><span>Rider location received {data.rider_location_age_seconds??0}s ago</span></div>
        <p className="muted small">GPS accuracy {rider.accuracy_m!=null?`≈ ${Math.round(rider.accuracy_m)} m`:'not reported'}.</p>
        {riderMap&&<a className="btn secondary" href={riderMap} target="_blank" rel="noreferrer"><Navigation size={16}/> Open rider location</a>}
      </>:<p className="muted">Rider assigned. Waiting for the first live GPS update.</p>}
    </>:<p className="muted">{data.order_status==='delivered'?'Delivery completed. Live rider sharing has stopped for privacy.':'Live tracking starts after a rider accepts the delivery.'}</p>}
  </div>;
}
