'use client';

import {useEffect,useRef,useState} from 'react';
import {LocateFixed,MapPin} from 'lucide-react';
import styles from './LocationMap.module.css';

export type MapPoint={lat:number;lng:number;label?:string;kind?:'store'|'customer'|'rider'};

type Props={
  latitude?:number;
  longitude?:number;
  onChange?:(lat:number,lng:number)=>void;
  editable?:boolean;
  height?:number;
  zoom?:number;
  markers?:MapPoint[];
  encodedPolyline?:string;
  className?:string;
};

const key=process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY||'';
const mapId=process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID||'';
let loader:Promise<any>|null=null;

function decodePolyline(encoded:string):Array<{lat:number;lng:number}>{
  const path:Array<{lat:number;lng:number}>=[];let index=0,lat=0,lng=0;
  while(index<encoded.length){
    let shift=0,result=0,byte=0;do{byte=encoded.charCodeAt(index++)-63;result|=(byte&0x1f)<<shift;shift+=5}while(byte>=0x20);lat+=(result&1)?~(result>>1):(result>>1);
    shift=0;result=0;do{byte=encoded.charCodeAt(index++)-63;result|=(byte&0x1f)<<shift;shift+=5}while(byte>=0x20);lng+=(result&1)?~(result>>1):(result>>1);
    path.push({lat:lat/1e5,lng:lng/1e5});
  }
  return path;
}

function loadGoogleMaps():Promise<any>{
  if(typeof window==='undefined')return Promise.reject(new Error('Maps require a browser.'));
  const w=window as any;
  if(w.google?.maps)return Promise.resolve(w.google.maps);
  if(!key)return Promise.reject(new Error('Google Maps is not configured.'));
  if(loader)return loader;
  loader=new Promise((resolve,reject)=>{
    const existing=document.getElementById('gaonone-google-maps') as HTMLScriptElement|null;
    const ready=()=>{const maps=(window as any).google?.maps;maps?resolve(maps):reject(new Error('Google Maps did not initialize.'))};
    if(existing){existing.addEventListener('load',ready,{once:true});existing.addEventListener('error',()=>reject(new Error('Google Maps failed to load.')),{once:true});return}
    const script=document.createElement('script');
    script.id='gaonone-google-maps';
    script.src=`https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&loading=async&v=weekly`;
    script.async=true;
    script.defer=true;
    script.onload=ready;
    script.onerror=()=>reject(new Error('Google Maps failed to load.'));
    document.head.appendChild(script);
  });
  return loader;
}

export function mapsConfigured(){return Boolean(key)}

export function LocationMap({latitude,longitude,onChange,editable=false,height=280,zoom=16,markers=[],encodedPolyline='',className=''}:Props){
  const root=useRef<HTMLDivElement|null>(null);
  const mapRef=useRef<any>(null);
  const overlays=useRef<any[]>([]);
  const routeLine=useRef<any>(null);
  const [available,setAvailable]=useState(Boolean(key));
  const [message,setMessage]=useState(key?'Loading map…':'Embedded map will activate after Google Maps setup.');
  const fallbackLat=latitude??20.0778;
  const fallbackLng=longitude??73.7898;

  useEffect(()=>{
    let alive=true;
    loadGoogleMaps().then(async maps=>{
      if(!alive||!root.current)return;
      const options:any={center:{lat:fallbackLat,lng:fallbackLng},zoom,mapTypeControl:false,streetViewControl:false,fullscreenControl:false,clickableIcons:false};
      if(mapId)options.mapId=mapId;
      const map=new maps.Map(root.current,options);mapRef.current=map;setAvailable(true);setMessage('');
      if(editable&&onChange){map.addListener('idle',()=>{const center=map.getCenter();if(center)onChange(center.lat(),center.lng())})}
    }).catch(()=>{if(alive){setAvailable(false);setMessage('Embedded map is not configured yet. Coordinates still work.')}});
    return()=>{alive=false;overlays.current.forEach(x=>{try{x.map=null}catch{}});overlays.current=[];routeLine.current?.setMap?.(null);routeLine.current=null;mapRef.current=null};
  },[]);

  useEffect(()=>{const map=mapRef.current;if(!map||latitude===undefined||longitude===undefined)return;map.panTo({lat:latitude,lng:longitude})},[latitude,longitude]);

  useEffect(()=>{
    const map=mapRef.current;const g=(window as any).google;if(!map||!g?.maps||!mapId)return;
    overlays.current.forEach(x=>{try{x.map=null}catch{}});overlays.current=[];
    if(!markers.length)return;
    g.maps.importLibrary('marker').then(({AdvancedMarkerElement}:any)=>{
      overlays.current=markers.map(point=>new AdvancedMarkerElement({map,position:{lat:point.lat,lng:point.lng},title:point.label||point.kind||'Location'}));
      if(markers.length>1&&!encodedPolyline){const bounds=new g.maps.LatLngBounds();markers.forEach(p=>bounds.extend({lat:p.lat,lng:p.lng}));map.fitBounds(bounds,56)}
    }).catch(()=>{});
  },[markers.map(m=>`${m.lat},${m.lng},${m.label||''}`).join('|'),encodedPolyline]);

  useEffect(()=>{
    const map=mapRef.current;const g=(window as any).google;if(!map||!g?.maps)return;
    routeLine.current?.setMap?.(null);routeLine.current=null;
    if(!encodedPolyline)return;
    const path=decodePolyline(encodedPolyline);if(!path.length)return;
    routeLine.current=new g.maps.Polyline({map,path,strokeOpacity:.85,strokeWeight:5,geodesic:true});
    const bounds=new g.maps.LatLngBounds();path.forEach(p=>bounds.extend(p));map.fitBounds(bounds,56);
  },[encodedPolyline]);

  function locate(){
    if(!navigator.geolocation){setMessage('Location is unavailable in this browser.');return}
    navigator.geolocation.getCurrentPosition(p=>{const lat=p.coords.latitude,lng=p.coords.longitude;mapRef.current?.panTo({lat,lng});mapRef.current?.setZoom(17);onChange?.(lat,lng);setMessage('Current location selected.');},()=>setMessage('Location permission was not granted.'),{enableHighAccuracy:true,timeout:10000,maximumAge:15000});
  }

  return <div className={`${styles.shell} ${className}`}>
    <div className={styles.map} ref={root} style={{height}} aria-label={editable?'Choose exact location on map':'Location map'}>
      {!available&&<div className={styles.fallback}><MapPin size={28}/><strong>Location ready</strong><span>{latitude!==undefined&&longitude!==undefined?`${latitude.toFixed(5)}, ${longitude.toFixed(5)}`:'Choose current location or enter the landmark.'}</span></div>}
    </div>
    {editable&&available&&<div className={styles.pin} aria-hidden="true"><MapPin size={34}/></div>}
    {editable&&<div className={styles.toolbar}><button type="button" className="btn secondary" onClick={locate}><LocateFixed size={15}/> Use current location</button><span className="muted small">Move the map until the pin is at the exact entrance.</span></div>}
    {message&&<div className={`muted small ${styles.message}`}>{message}</div>}
  </div>;
}
