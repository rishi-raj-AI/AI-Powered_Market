'use client';

import {useEffect,useState} from 'react';
import {ShieldCheck} from 'lucide-react';
import {MerchantReliability,merchantReliability,trustDetail,trustLabel} from '@/lib/commerceIntelligence';

export function StoreTrustSignal({storeId}:{storeId:string}){
  const[result,setResult]=useState<MerchantReliability|null>(null);
  const[error,setError]=useState('');
  useEffect(()=>{merchantReliability(storeId).then(setResult).catch(e=>setError(e.message||'Trust signal unavailable.'))},[storeId]);
  if(error)return <div className="notice muted"><div className="row"><ShieldCheck size={18}/><span>Store fulfilment history is temporarily unavailable. This does not block ordering.</span></div></div>;
  if(!result)return <div className="notice muted"><div className="row"><ShieldCheck size={18}/><span>Loading store fulfilment history…</span></div></div>;
  const percent=Math.round(result.score*100);
  return <div className="notice"><div className="row space"><div className="row"><ShieldCheck size={18}/><strong>{trustLabel(result)}</strong></div>{result.confidence!=='low'&&<span className="badge">{percent}% operational signal</span>}</div><div className="muted small">{trustDetail(result)}</div></div>;
}
