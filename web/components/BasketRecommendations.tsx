'use client';
import {useEffect,useState} from 'react';
import {Plus,Sparkles} from 'lucide-react';
import {api,gaonApi} from '@/lib/api';

type Suggestion={listing_id:string;name:string;unit:string;price:string;stock_quantity:number;reason:string};
export function BasketRecommendations({onAdded}:{onAdded?:()=>void}){
 const[items,setItems]=useState<Suggestion[]>([]);const[loading,setLoading]=useState(true);const[error,setError]=useState('');const[busy,setBusy]=useState('');
 async function load(){setLoading(true);try{const data=await api<{items:Suggestion[]}>('/cart/recommendations');setItems(data.items||[]);setError('')}catch(e:any){setError(e.message)}finally{setLoading(false)}}
 useEffect(()=>{load()},[]);
 async function add(item:Suggestion){setBusy(item.listing_id);try{await gaonApi.addCart(item.listing_id,1);await load();onAdded?.()}catch(e:any){setError(e.message)}finally{setBusy('')}}
 if(loading)return <div className="notice">Checking useful add-ons from this store…</div>;
 if(!items.length&&!error)return null;
 return <section className="panel"><div className="sectionHead"><div><span className="eyebrow">Same store</span><h3><Sparkles size={18}/> Useful add-ons</h3><p className="muted small">Suggestions use your current basket and live store inventory.</p></div></div>{error&&<div className="notice">{error} <button className="btn ghost" onClick={load}>Retry</button></div>}<div className="stack">{items.slice(0,4).map(item=><div className="cartItem" key={item.listing_id}><div><strong>{item.name}</strong><div className="muted small">{item.unit} • ₹{item.price} • {item.reason.replaceAll('_',' ')}</div></div><button className="btn secondary" disabled={busy===item.listing_id||item.stock_quantity<1} onClick={()=>add(item)}><Plus size={15}/> {busy===item.listing_id?'Adding…':'Add'}</button></div>)}</div></section>;
}
