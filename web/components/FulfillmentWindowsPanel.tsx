'use client';
import {useEffect,useState} from 'react';
import {CalendarClock} from 'lucide-react';
import {api} from '@/lib/api';

type Window={start_at:string;end_at:string;mode:'delivery'|'pickup'};
const format=(value:string)=>new Intl.DateTimeFormat('en-IN',{weekday:'short',hour:'numeric',minute:'2-digit',timeZone:'Asia/Kolkata'}).format(new Date(value));
export function FulfillmentWindowsPanel({storeId,deliveryEnabled,pickupEnabled}:{storeId:string;deliveryEnabled:boolean;pickupEnabled:boolean}){
 const initial=deliveryEnabled?'delivery':'pickup';const[mode,setMode]=useState<'delivery'|'pickup'>(initial);const[items,setItems]=useState<Window[]>([]);const[loading,setLoading]=useState(false);const[error,setError]=useState('');
 async function load(next=mode){setLoading(true);setError('');try{setItems(await api<Window[]>(`/stores/${storeId}/fulfillment-windows?mode=${next}&days=3`))}catch(e:any){setError(e.message)}finally{setLoading(false)}}
 useEffect(()=>{if(deliveryEnabled||pickupEnabled)load(initial)},[storeId]);
 function choose(next:'delivery'|'pickup'){setMode(next);load(next)}
 if(!deliveryEnabled&&!pickupEnabled)return null;
 return <div className="notice"><div className="row space"><div className="row"><CalendarClock size={18}/><strong>Upcoming fulfilment windows</strong></div><div className="row">{deliveryEnabled&&<button className={`btn ${mode==='delivery'?'':'ghost'}`} onClick={()=>choose('delivery')}>Delivery</button>}{pickupEnabled&&<button className={`btn ${mode==='pickup'?'':'ghost'}`} onClick={()=>choose('pickup')}>Pickup</button>}</div></div><div className="muted small">India-local availability preview. A window is not reserved here; final checkout revalidates fulfilment.</div>{loading&&<div className="muted small">Checking windows…</div>}{error&&<div className="dangerText small">{error}</div>}{!loading&&!error&&!items.length&&<div className="muted small">No window is currently available for this mode.</div>}{items.length>0&&<div className="row" style={{overflowX:'auto',marginTop:8}}>{items.slice(0,6).map(w=><span className="pill" key={w.start_at}>{format(w.start_at)}–{new Intl.DateTimeFormat('en-IN',{hour:'numeric',minute:'2-digit',timeZone:'Asia/Kolkata'}).format(new Date(w.end_at))}</span>)}</div>}</div>;
}
