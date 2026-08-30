'use client';
import {useState} from 'react';
import {RefreshCw} from 'lucide-react';
import {api,gaonApi} from '@/lib/api';

type Alternative={listing_id:string;name:string;brand?:string;unit:string;price:string;price_delta:string};
export function SubstitutionChoices({listingId,onAdded}:{listingId:string;onAdded?:()=>void}){
 const[open,setOpen]=useState(false);const[items,setItems]=useState<Alternative[]>([]);const[loading,setLoading]=useState(false);const[error,setError]=useState('');const[busy,setBusy]=useState('');
 async function toggle(){if(open){setOpen(false);return}setOpen(true);if(items.length)return;setLoading(true);try{const data=await api<{items:Alternative[]}>(`/store-products/${listingId}/substitutions`);setItems(data.items||[]);setError('')}catch(e:any){setError(e.message)}finally{setLoading(false)}}
 async function add(item:Alternative){setBusy(item.listing_id);try{await gaonApi.addCart(item.listing_id,1);onAdded?.()}catch(e:any){setError(e.message)}finally{setBusy('')}}
 return <div><button className="btn ghost" onClick={toggle}><RefreshCw size={14}/>{open?'Hide alternatives':'Alternatives'}</button>{open&&<div className="notice" style={{marginTop:8}}><strong>Choose a replacement manually</strong><div className="muted small">Nothing is substituted automatically; checkout revalidates your chosen item.</div>{loading&&<div className="muted small">Checking same-store alternatives…</div>}{error&&<div className="dangerText small">{error}</div>}{!loading&&!items.length&&!error&&<div className="muted small">No close same-store alternative is available right now.</div>}{items.slice(0,3).map(item=><div className="row space" key={item.listing_id} style={{marginTop:8}}><span><strong>{item.name}</strong><span className="muted small"> • {item.unit} • ₹{item.price}</span></span><button className="btn secondary" disabled={busy===item.listing_id} onClick={()=>add(item)}>{busy===item.listing_id?'Adding…':'Choose'}</button></div>)}</div>}</div>;
}
