'use client';

import {useEffect,useRef,useState} from 'react';
import {LocateFixed,Radio,RadioTower} from 'lucide-react';
import {getToken} from '@/lib/api';

const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';

export function RiderLocationSharing({deliveryId,active}:{deliveryId:string;active:boolean}){
  const[sharing,setSharing]=useState(false);
  const[message,setMessage]=useState(active?'Location sharing is off.':'Location sharing stopped.');
  const watchRef=useRef<number|null>(null);
  const lastSentRef=useRef(0);

  function stop(){
    if(watchRef.current!==null&&navigator.geolocation){navigator.geolocation.clearWatch(watchRef.current);watchRef.current=null}
    setSharing(false);
  }

  useEffect(()=>{if(!active)stop();return()=>stop()},[active]);

  async function send(position:GeolocationPosition){
    const now=Date.now();
    if(now-lastSentRef.current<8000)return;
    lastSentRef.current=now;
    const token=getToken();if(!token)return;
    const c=position.coords;
    try{
      const response=await fetch(`${API}/delivery/${deliveryId}/location`,{
        method:'POST',
        headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},
        body:JSON.stringify({
          latitude:c.latitude,
          longitude:c.longitude,
          accuracy_m:c.accuracy,
          heading_deg:c.heading!=null&&Number.isFinite(c.heading)?c.heading:null,
          speed_mps:c.speed!=null&&Number.isFinite(c.speed)?c.speed:null,
          recorded_at:new Date(position.timestamp).toISOString(),
        }),
      });
      if(!response.ok){const body=await response.json().catch(()=>null);throw new Error(body?.detail||`Location update failed (${response.status})`)}
      setMessage(`Sharing live • accuracy ≈ ${Math.round(c.accuracy)} m`);
    }catch(e:any){setMessage(e.message||'Unable to share location.')}
  }

  function start(){
    if(!active){setMessage('Location sharing is available only during an active delivery.');return}
    if(!navigator.geolocation){setMessage('Location is not supported by this browser.');return}
    if(watchRef.current!==null)return;
    setMessage('Requesting location permission…');
    watchRef.current=navigator.geolocation.watchPosition(
      position=>{setSharing(true);void send(position)},
      error=>{stop();setMessage(error.code===1?'Location permission denied. Enable it to share live delivery progress.':error.message)},
      {enableHighAccuracy:true,maximumAge:5000,timeout:15000},
    );
  }

  return <div className="card stack">
    <div className="row space"><div className="row">{sharing?<RadioTower size={18}/>:<Radio size={18}/>}<strong>Live GPS</strong></div><span className={`badge ${sharing?'status-picked_up':''}`}>{sharing?'Sharing':'Off'}</span></div>
    <p className="muted small">{message}</p>
    {active&&(sharing?<button className="btn secondary" onClick={stop}>Stop sharing</button>:<button className="btn secondary" onClick={start}><LocateFixed size={16}/> Share live location</button>)}
  </div>;
}
