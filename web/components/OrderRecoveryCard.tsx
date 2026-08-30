'use client';
import Link from 'next/link';
import {useEffect,useState} from 'react';
import {LifeBuoy} from 'lucide-react';
import {api} from '@/lib/api';

type Action={code:string;label:string;priority:number};type Recovery={order_status:string;payment_status:string;delivery_status?:string|null;actions:Action[];has_recovery_action:boolean};
export function OrderRecoveryCard({orderId}:{orderId:string}){const[data,setData]=useState<Recovery|null>(null);useEffect(()=>{api<Recovery>(`/orders/${orderId}/recovery`).then(setData).catch(()=>{})},[orderId]);if(!data?.has_recovery_action)return null;const support=data.actions.some(a=>a.code==='contact_support');return <div className="card" style={{marginTop:10}}><div className="row"><LifeBuoy size={17}/><strong>What can I do now?</strong></div><div className="muted small" style={{marginTop:6}}>{data.actions.map(a=>a.label).join(' • ')}</div>{support&&<Link className="btn secondary" style={{marginTop:8}} href={`/support?order_id=${encodeURIComponent(orderId)}`}>Get order help</Link>}</div>}
