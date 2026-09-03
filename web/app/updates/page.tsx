'use client';
import {useEffect,useState} from 'react';
import {Bell,PackageCheck,Truck} from 'lucide-react';
import Link from 'next/link';
import {gaonApi,NotificationEvent} from '@/lib/api';
import {Nav} from '@/components/Nav';

export default function Updates(){
  const [items,setItems]=useState<NotificationEvent[]>([]);
  const [error,setError]=useState('');
  async function load(){try{setItems(await gaonApi.notifications());setError('')}catch(e:any){setError(e.status===401?'Please login to view updates':e.message)}}
  useEffect(()=>{load()},[]);
  const icon=(type:string)=>type.startsWith('delivery.')?<Truck size={20}/>:type.includes('delivered')?<PackageCheck size={20}/>:<Bell size={20}/>;
  const orderId=(item:NotificationEvent)=>typeof item.data?.order_id==='string'?item.data.order_id:null;
  return <><Nav/><main className="container section"><div className="sectionHead"><div><span className="eyebrow">Live order activity</span><h2>Updates</h2><p className="muted">Stored operational events link back to the affected order when the backend includes an order reference.</p></div><button className="btn ghost" onClick={load}>Refresh</button></div>{error&&<div className="notice">{error}</div>}<div className="stack">{items.map(item=>{const oid=orderId(item);return <div className="card row" key={item.id} style={{gap:14,alignItems:'flex-start'}}><div className="iconBox">{icon(item.event_type)}</div><div style={{flex:1}}><strong>{item.title}</strong><p>{item.body}</p><div className="row space"><span className="muted">{new Date(item.created_at).toLocaleString('en-IN')}</span>{oid&&<Link className="btn ghost" href={`/orders?focus=${encodeURIComponent(oid)}`}>View order</Link>}</div></div></div>})}{!items.length&&!error&&<div className="panel muted">No updates yet. Your order activity will appear here.</div>}</div></main></>}
