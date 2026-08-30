'use client';

import {useEffect,useState} from 'react';
import Link from 'next/link';
import {History,RefreshCw,ShoppingCart} from 'lucide-react';
import {gaonApi} from '@/lib/api';
import {cadenceCopy,RepeatCadenceItem,repeatPurchaseCadence} from '@/lib/commerceIntelligence';

export function DueAgainPanel(){
  const[items,setItems]=useState<RepeatCadenceItem[]>([]);
  const[loading,setLoading]=useState(true);
  const[error,setError]=useState('');
  const[busy,setBusy]=useState('');
  const[msg,setMsg]=useState('');

  async function load(){
    setLoading(true);setError('');
    try{const data=await repeatPurchaseCadence();setItems(data.items.filter(item=>item.due||item.urgency_score>=0.65).slice(0,6))}
    catch(e:any){if(e.status!==401)setError(e.message||'Could not load repeat suggestions.')}
    finally{setLoading(false)}
  }
  useEffect(()=>{load()},[]);

  async function buyAgain(item:RepeatCadenceItem){
    if(!item.listing_id)return;
    setBusy(item.product_id);setMsg('');
    try{await gaonApi.addCart(item.listing_id,1);setMsg(`${item.product_name} added to your cart after a live stock check.`)}
    catch(e:any){setMsg(e.message||'Could not add this item. Open the store to choose a current alternative.')}
    finally{setBusy('')}
  }

  if(loading)return <div className="panel"><div className="row"><RefreshCw size={17}/><span className="muted">Checking what may be due again…</span></div></div>;
  if(error)return <div className="panel"><div className="row space"><span className="muted">{error}</span><button className="btn secondary" onClick={load}>Retry</button></div></div>;
  if(!items.length)return null;
  return <section className="panel"><div className="sectionHead"><div><span className="eyebrow">Repeat essentials</span><h3>Due again</h3><p className="muted">Suggestions come only from your delivered-order history. Stock is checked again before anything enters the cart.</p></div><History size={22}/></div>{msg&&<div className="notice">{msg}</div>}<div className="stack">{items.map(item=><div className="card row space" key={item.product_id}><div><strong>{item.product_name}</strong><div className="muted small">{cadenceCopy(item)} • bought {item.purchase_count} times</div></div><div className="row">{item.available_now&&item.listing_id?<button className="btn" disabled={busy===item.product_id} onClick={()=>buyAgain(item)}><ShoppingCart size={16}/> {busy===item.product_id?'Adding…':'Buy again'}</button>:<Link className="btn secondary" href={`/market/${item.last_store_id}`}>View store</Link>}</div></div>)}</div></section>;
}
