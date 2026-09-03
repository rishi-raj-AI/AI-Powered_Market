'use client';
import {useEffect,useState} from 'react';
import {Nav} from '@/components/Nav';
import {api} from '@/lib/api';

type FailedDelivery={id:string;order_number?:string;status:string;store_name?:string;customer_landmark?:string;picked_up_at?:string|null;failed_at?:string|null;failure_reason?:string|null;failure_notes?:string|null};

export default function DeliveryRecovery(){
  const[tasks,setTasks]=useState<FailedDelivery[]>([]);const[error,setError]=useState('');const[busy,setBusy]=useState('');
  async function load(){try{setTasks(await api<FailedDelivery[]>('/admin/deliveries/failed'));setError('')}catch(e:any){setError(e.message)}}
  useEffect(()=>{load()},[]);
  async function resolve(task:FailedDelivery,resolution:'reassign'|'return_to_store'){setBusy(task.id);try{await api(`/admin/deliveries/${task.id}/resolve-failure`,{method:'POST',body:JSON.stringify({resolution})});await load()}catch(e:any){setError(e.message)}finally{setBusy('')}}
  return <><Nav/><main className="container section"><span className="eyebrow">Delivery recovery</span><h2>Failed deliveries requiring review</h2><p className="muted">Custody determines the permitted action. The backend alone reassigns pre-pickup failures or returns post-pickup orders and applies refund, stock and settlement rules.</p>{error&&<div className="notice">{error}</div>}<div className="grid">{tasks.map(task=><article className="card" key={task.id}><div className="row space"><strong>{task.order_number||task.id}</strong><span className="badge status-failed">Failed</span></div><p>{task.store_name||'Store'} → {task.customer_landmark||'Customer location'}</p><p className="muted small">{task.failure_reason?.replaceAll('_',' ')||'Reason not recorded'}{task.failure_notes?` • ${task.failure_notes}`:''}</p><button className="btn" disabled={busy===task.id} onClick={()=>resolve(task,task.picked_up_at?'return_to_store':'reassign')}>{busy===task.id?'Resolving…':task.picked_up_at?'Confirm return to store':'Return to dispatch pool'}</button></article>)}</div>{!error&&tasks.length===0&&<div className="notice">No failed deliveries require review.</div>}</main></>;
}
