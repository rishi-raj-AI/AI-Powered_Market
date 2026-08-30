'use client';

import {useState} from 'react';
import {MapPin,RefreshCw,Truck} from 'lucide-react';
import {FulfillmentMode,FulfillmentRecommendation,fulfillmentDetail,fulfillmentLabel,fulfillmentRecommendation} from '@/lib/commerceIntelligence';

export function FulfillmentRecommendationPanel({storeId}:{storeId:string}){
  const[result,setResult]=useState<FulfillmentRecommendation|null>(null);
  const[busy,setBusy]=useState(false);
  const[error,setError]=useState('');
  const[selected,setSelected]=useState<FulfillmentMode|''>('');
  async function check(){setBusy(true);setError('');if(!navigator.geolocation){setError('Location is unavailable on this device. You can still choose at checkout.');setBusy(false);return}navigator.geolocation.getCurrentPosition(async position=>{try{const next=await fulfillmentRecommendation(storeId,position.coords.latitude,position.coords.longitude);setResult(next);setSelected(next.recommended_mode)}catch(e:any){setError(e.message||'Could not check fulfilment right now.')}finally{setBusy(false)}},()=>{setError('Location permission was not granted. You can still choose at checkout.');setBusy(false)},{enableHighAccuracy:false,timeout:8000,maximumAge:120000})}
  const options:FulfillmentMode[]=[];if(result){if(result.delivery_enabled&&result.delivery_serviceable&&result.store_open)options.push('delivery_now');if(result.pickup_enabled&&result.store_open)options.push('pickup_now');if(result.delivery_enabled&&result.delivery_serviceable&&!result.store_open)options.push('scheduled_delivery');if(result.pickup_enabled&&!result.store_open)options.push('scheduled_pickup');if(!options.length)options.push('unavailable')}
  return <div className="notice"><div className="row space"><div className="row"><Truck size={18}/><strong>Delivery or pickup?</strong></div><button type="button" className="btn secondary" disabled={busy} onClick={check}>{busy?<RefreshCw size={16}/>:<MapPin size={16}/>} {busy?'Checking…':result?'Recheck location':'Use my location'}</button></div>{!result&&!error&&<div className="muted small">Check your current location for the best available fulfilment option.</div>}{error&&<div className="muted small">{error}</div>}{result&&<><div style={{marginTop:10}}><strong>Recommended: {fulfillmentLabel(result.recommended_mode)}</strong><div className="muted small">{fulfillmentDetail(result)} Store-hours logic uses Asia/Kolkata.</div></div><div className="field" style={{marginTop:10}}><label htmlFor={`fulfillment-${storeId}`}>Fulfilment choice</label><select id={`fulfillment-${storeId}`} value={selected} disabled={options.length===1&&options[0]==='unavailable'} onChange={e=>setSelected(e.target.value as FulfillmentMode)}>{options.map(mode=><option key={mode} value={mode}>{fulfillmentLabel(mode)}{mode===result.recommended_mode?' — recommended':''}</option>)}</select><span className="muted small">Only modes supported by this store and location are shown. Checkout revalidates the final order.</span></div></>}</div>;
}
