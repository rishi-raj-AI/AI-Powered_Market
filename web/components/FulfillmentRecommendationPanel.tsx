'use client';

import {useState} from 'react';
import {MapPin,RefreshCw,Truck} from 'lucide-react';
import {FulfillmentRecommendation,fulfillmentDetail,fulfillmentLabel,fulfillmentRecommendation} from '@/lib/commerceIntelligence';

export function FulfillmentRecommendationPanel({storeId}:{storeId:string}){
  const[result,setResult]=useState<FulfillmentRecommendation|null>(null);
  const[busy,setBusy]=useState(false);
  const[error,setError]=useState('');
  const[selected,setSelected]=useState('');

  async function check(){
    setBusy(true);setError('');
    if(!navigator.geolocation){setError('Location is unavailable on this device. You can still choose at checkout.');setBusy(false);return}
    navigator.geolocation.getCurrentPosition(async position=>{
      try{
        const next=await fulfillmentRecommendation(storeId,position.coords.latitude,position.coords.longitude);
        setResult(next);setSelected(next.recommended_mode);
      }catch(e:any){setError(e.message||'Could not check fulfilment right now.')}
      finally{setBusy(false)}
    },()=>{setError('Location permission was not granted. You can still choose at checkout.');setBusy(false)},{enableHighAccuracy:false,timeout:8000,maximumAge:120000});
  }

  return <div className="notice"><div className="row space"><div className="row"><Truck size={18}/><strong>Delivery or pickup?</strong></div><button type="button" className="btn secondary" disabled={busy} onClick={check}>{busy?<RefreshCw size={16}/>:<MapPin size={16}/>} {busy?'Checking…':result?'Recheck location':'Use my location'}</button></div>
    {!result&&!error&&<div className="muted small">Check your current location for the best available fulfilment option.</div>}
    {error&&<div className="muted small">{error}</div>}
    {result&&<><div style={{marginTop:10}}><strong>Recommended: {fulfillmentLabel(result.recommended_mode)}</strong><div className="muted small">{fulfillmentDetail(result)} Store-hours logic uses Asia/Kolkata.</div></div><div className="field" style={{marginTop:10}}><label htmlFor={`fulfillment-${storeId}`}>Fulfilment choice</label><select id={`fulfillment-${storeId}`} value={selected} onChange={e=>setSelected(e.target.value)}><option value={result.recommended_mode}>{fulfillmentLabel(result.recommended_mode)} — recommended</option>{result.recommended_mode!=='delivery_now'&&result.delivery_serviceable&&result.store_open&&<option value="delivery_now">Delivery now</option>}{result.recommended_mode!=='pickup_now'&&result.store_open&&<option value="pickup_now">Pickup now</option>}{result.delivery_serviceable&&<option value="scheduled_delivery">Schedule delivery</option>}<option value="scheduled_pickup">Schedule pickup</option></select><span className="muted small">This selector previews availability; the final checkout contract revalidates the order and location.</span></div></>}
  </div>;
}
