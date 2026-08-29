'use client';

import {useEffect,useRef,useState} from 'react';
import {LocateFixed,Radio,RadioTower} from 'lucide-react';
import {getToken} from '@/lib/api';

const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
const SEND_INTERVAL_MS=8000;
const STALE_POSITION_MS=30000;

export function RiderLocationSharing({deliveryId,active}:{deliveryId:string;active:boolean}){
  const[sharing,setSharing]=useState(false);
  const[message,setMessage]=useState(active?'Location sharing is off.':'Location sharing stopped.');
  const watchRef=useRef<number|null>(null);
  const lastSentRef=useRef(0);
  const latestRef=useRef<GeolocationPosition|null>(null);
  const sendingRef=useRef(false);
  const mountedRef=useRef(true);

  function clearWatch(){
    if(watchRef.current!==null&&typeof navigator!=='undefined'&&navigator.geolocation){navigator.geolocation.clearWatch(watchRef.current);watchRef.current=null}
  }

  function stop(){
    clearWatch();latestRef.current=null;
    if(mountedRef.current){setSharing(false);setMessage(active?'Location sharing is off.':'Location sharing stopped.')}
  }

  useEffect(()=>{
    mountedRef.current=true;
    if(!active)stop();
    const online=()=>{if(watchRef.current!==null&&latestRef.current){lastSentRef.current=0;void send(latestRef.current,true)}};
    window.addEventListener('online',online);
    return()=>{mountedRef.current=false;window.removeEventListener('online',online);clearWatch()};
  },[active,deliveryId]);

  async function send(position:GeolocationPosition,force=false){
    latestRef.current=position;
    const now=Date.now();
    if(now-position.timestamp>STALE_POSITION_MS){if(mountedRef.current)setMessage('Waiting for a fresh GPS fix…');return}
    if(!force&&now-lastSentRef.current<SEND_INTERVAL_MS)return;
    if(sendingRef.current)return;
    if(typeof navigator!=='undefined'&&!navigator.onLine){if(mountedRef.current)setMessage('Offline • GPS sharing will resume when the connection returns.');return}
    const token=getToken();if(!token)return;
    const c=position.coords;
    sendingRef.current=true;
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
      if(response.status===429){if(mountedRef.current)setMessage('Sharing live • update cadence protected');return}
      if(!response.ok){const body=await response.json().catch(()=>null);throw new Error(body?.detail||`Location update failed (${response.status})`)}
      lastSentRef.current=now;
      if(mountedRef.current)setMessage(`Sharing live • accuracy ≈ ${Math.round(c.accuracy)} m`);
    }catch(e:any){
      if(mountedRef.current)setMessage(typeof navigator!=='undefined'&&!navigator.onLine?'Offline • GPS sharing will resume automatically.':e.message||'Unable to share location. Retrying with the next GPS fix.');
    }finally{sendingRef.current=false}
  }

  function start(){
    if(!active){setMessage('Location sharing is available only during an active delivery.');return}
    if(!navigator.geolocation){setMessage('Location is not supported by this browser.');return}
    if(watchRef.current!==null)return;
    setMessage('Requesting location permission…');
    watchRef.current=navigator.geolocation.watchPosition(
      position=>{latestRef.current=position;setSharing(true);void send(position)},
      error=>{clearWatch();setSharing(false);setMessage(error.code===1?'Location permission denied. Enable it to share live delivery progress.':error.code===3?'GPS timed out. Try again where location signal is available.':error.message)},
      {enableHighAccuracy:true,maximumAge:5000,timeout:15000},
    );
  }

  return <div className="card stack">
    <div className="row space"><div className="row">{sharing?<RadioTower size={18}/>:<Radio size={18}/>}<strong>Live GPS</strong></div><span className={`badge ${sharing?'status-picked_up':''}`}>{sharing?'Sharing':'Off'}</span></div>
    <p className="muted small">{message}</p>
    {active&&(sharing?<button className="btn secondary" onClick={stop}>Stop sharing</button>:<button className="btn secondary" onClick={start}><LocateFixed size={16}/> Share live location</button>)}
  </div>;
}
