'use client';
import {useEffect,useState} from 'react';
import {Bell,PackageCheck,Truck} from 'lucide-react';
import {gaonApi,NotificationEvent} from '@/lib/api';
import {Nav} from '@/components/Nav';

export default function Updates(){
  const [items,setItems]=useState<NotificationEvent[]>([]);
  const [error,setError]=useState('');
  async function load(){try{setItems(await gaonApi.notifications());setError('')}catch(e:any){setError(e.status===401?'Please login to view updates':e.message)}}
  useEffect(()=>{load()},[]);
  const icon=(type:string)=>type.startsWith('delivery.')?<Truck size={20}/>:type.includes('delivered')?<PackageCheck size={20}/>:<Bell size={20}/>;
  return <><Nav/><main className="container section"><div className="sectionHead"><div><span className="eyebrow">Live order activity</span><h2>Updates</h2><p className="muted">Order and delivery events are stored here even before push notifications are connected.</p></div><button className="btn ghost" onClick={load}>Refresh</button></div>{error&&<div className="notice">{error}</div>}<div className="stack">{items.map(item=><div className="card row" key={item.id} style={{gap:14,alignItems:'flex-start'}}><div className="iconBox">{icon(item.event_type)}</div><div><strong>{item.title}</strong><p>{item.body}</p><span className="muted">{new Date(item.created_at).toLocaleString()}</span></div></div>)}{!items.length&&!error&&<div className="panel muted">No updates yet. Your order activity will appear here.</div>}</div></main></>}
