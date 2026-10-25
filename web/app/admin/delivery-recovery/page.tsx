'use client';

import {useEffect,useRef,useState} from 'react';
import {api,gaonApi} from '@/lib/api';
import {Nav} from '@/components/Nav';

type FailedDelivery={id:string;order_number?:string;status:string;store_name?:string;customer_landmark?:string;picked_up_at?:string|null;failed_at?:string|null;failure_reason?:string|null;failure_notes?:string|null};
type RecoveryResult={delivery_id:string;order_id:string;resolution:'reassign'|'return_to_store';order_status:string;delivery_status:string;refund_requested:boolean;settlement_voided:boolean};

const hasCapability=(capabilities:string[]|null,capability:string)=>capabilities?.includes(capability)===true;

export default function DeliveryRecovery(){
  const[tasks,setTasks]=useState<FailedDelivery[]>([]);
  const[capabilities,setCapabilities]=useState<string[]|null>(null);
  const[accessError,setAccessError]=useState('');
  const[queueError,setQueueError]=useState('');
  const[outcome,setOutcome]=useState('');
  const[busy,setBusy]=useState('');
  const[accessLoading,setAccessLoading]=useState(true);
  const[queueLoading,setQueueLoading]=useState(false);
  const[pendingReturn,setPendingReturn]=useState<FailedDelivery|null>(null);
  const accessSequence=useRef(0);
  const queueSequence=useRef(0);
  const resolutionLock=useRef(false);
  const canRecover=hasCapability(capabilities,'rider.operations');
  const canReturnToStore=canRecover&&hasCapability(capabilities,'refund.write')&&hasCapability(capabilities,'settlement.write');
  const operationBusy=Boolean(busy);

  useEffect(()=>{void verifyAccess();return()=>{accessSequence.current+=1;queueSequence.current+=1}},[]);

  async function loadQueue(granted:string[],accessId=accessSequence.current){
    if(!granted.includes('rider.operations'))return;
    const queueId=++queueSequence.current;
    setQueueLoading(true);setQueueError('');
    try{
      const next=await api<FailedDelivery[]>('/admin/deliveries/failed');
      if(accessId!==accessSequence.current||queueId!==queueSequence.current)return;
      setTasks(next);
    }catch(error:any){
      if(accessId!==accessSequence.current||queueId!==queueSequence.current)return;
      if(error?.status===403){
        setCapabilities([]);setTasks([]);setPendingReturn(null);setAccessError('Delivery recovery access is no longer available for this account.');
      }else setQueueError(error.message);
    }finally{
      if(accessId===accessSequence.current&&queueId===queueSequence.current)setQueueLoading(false);
    }
  }

  async function verifyAccess(){
    const accessId=++accessSequence.current;
    queueSequence.current+=1;
    setAccessLoading(true);setCapabilities(null);setAccessError('');setQueueError('');setTasks([]);setPendingReturn(null);
    try{
      const response=await gaonApi.capabilities();
      if(accessId!==accessSequence.current)return;
      setCapabilities(response.capabilities);
      if(!response.capabilities.includes('rider.operations')){
        setAccessError('Delivery recovery access is not available for this account.');
        return;
      }
      await loadQueue(response.capabilities,accessId);
    }catch{
      if(accessId!==accessSequence.current)return;
      setCapabilities([]);setTasks([]);setAccessError('Unable to verify delivery recovery access. Recovery actions are unavailable.');
    }finally{
      if(accessId===accessSequence.current)setAccessLoading(false);
    }
  }

  async function resolve(task:FailedDelivery,resolution:'reassign'|'return_to_store'){
    if(!canRecover||resolutionLock.current||(resolution==='return_to_store'&&!canReturnToStore))return;
    resolutionLock.current=true;
    setBusy(task.id);setQueueError('');setOutcome('');
    try{
      const result=await api<RecoveryResult>(`/admin/deliveries/${task.id}/resolve-failure`,{method:'POST',body:JSON.stringify({resolution})});
      const deliveryName=task.order_number||'Delivery';
      setPendingReturn(null);
      setOutcome(result.resolution==='reassign'?`${deliveryName} returned to the dispatch pool.`:`${deliveryName} returned to the store. ${result.settlement_voided?'Settlement was voided. ':''}${result.refund_requested?'A refund was requested.':'No refund request was needed.'}`);
      await loadQueue(capabilities||[]);
    }catch(error:any){
      if(error?.status===403){
        setCapabilities([]);setTasks([]);setPendingReturn(null);setAccessError('Delivery recovery access is no longer available for this account.');
      }else setQueueError(error.message);
    }finally{
      resolutionLock.current=false;
      setBusy('');
    }
  }

  function reviewReturn(task:FailedDelivery){
    if(!canReturnToStore||operationBusy)return;
    setOutcome('');setQueueError('');setPendingReturn(task);
  }

  return <><Nav/><main className="container section"><span className="eyebrow">Delivery recovery</span><h2>Failed deliveries requiring review</h2><p className="muted">Custody determines the permitted action. The backend alone reassigns pre-pickup failures or returns post-pickup orders and applies refund, stock and settlement rules.</p>
    {accessLoading&&<p className="muted" role="status">Checking delivery recovery access…</p>}
    {accessError&&<div className="notice" role="alert">{accessError}<button type="button" className="btn secondary" onClick={verifyAccess}>Retry access check</button></div>}
    {outcome&&<div className="notice" role="status">{outcome}</div>}
    {canRecover&&!accessLoading&&!accessError&&<><div className="row"><button type="button" className="btn secondary" disabled={queueLoading||operationBusy} onClick={()=>void loadQueue(capabilities||[])}>Refresh failed deliveries</button></div>{queueError&&<div className="notice" role="alert">{queueError}<button type="button" className="btn secondary" disabled={queueLoading||operationBusy} onClick={()=>void loadQueue(capabilities||[])}>Retry queue</button></div>}
      {queueLoading?<p className="muted" role="status">Loading failed deliveries…</p>:<div className="grid">{tasks.map(task=><article className="card" key={task.id}><div className="row space"><strong>{task.order_number||task.id}</strong><span className="badge status-failed">Failed</span></div><p>{task.store_name||'Store'} → {task.customer_landmark||'Customer location'}</p><p className="muted small">{task.failure_reason?.replaceAll('_',' ')||'Reason not recorded'}{task.failure_notes?` • ${task.failure_notes}`:''}</p>{task.picked_up_at?canReturnToStore?<>{pendingReturn?.id===task.id?<section className="notice" role="region" aria-label="Return-to-store confirmation" aria-describedby={`return-consequences-${task.id}`}><strong>Confirm return to store</strong><p id={`return-consequences-${task.id}`}>The backend will return this order, restore stock once, void settlement, and request a refund when appropriate. This recovery cannot be undone here.</p><div className="row"><button type="button" className="btn dangerBtn" disabled={operationBusy} onClick={()=>void resolve(task,'return_to_store')}>Confirm return to store</button><button type="button" className="btn secondary" disabled={operationBusy} onClick={()=>setPendingReturn(null)}>Cancel</button></div></section>:<button type="button" className="btn dangerBtn" disabled={operationBusy} onClick={()=>reviewReturn(task)}>Review return to store</button>}</>:<p className="muted small">Financial recovery requires elevated refund and settlement authority.</p>:<button type="button" className="btn" disabled={operationBusy} onClick={()=>void resolve(task,'reassign')}>{busy===task.id?'Resolving…':'Return to dispatch pool'}</button>}</article>)}</div>}
      {!queueLoading&&!queueError&&tasks.length===0&&<div className="notice">No failed deliveries require review.</div>}
    </>}
  </main></>;
}
