'use client';

import {useEffect,useState} from 'react';
import {Nav} from '@/components/Nav';
import {gaonApi,getToken,type Store,type StoreProduct} from '@/lib/api';

const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
type MediaAsset={id:string;state:string;alt_text:string|null;position:number;is_primary:boolean;created_at:string};
type ApprovedAsset={id:string;url:string;alt_text:string|null;position:number;is_primary:boolean};

export default function MerchantMedia(){
  const[listingId,setListingId]=useState('');
  const[stores,setStores]=useState<Store[]>([]);
  const[storeId,setStoreId]=useState('');
  const[inventory,setInventory]=useState<StoreProduct[]>([]);
  const[file,setFile]=useState<File|null>(null);
  const[preview,setPreview]=useState('');
  const[assets,setAssets]=useState<MediaAsset[]>([]);
  const[approved,setApproved]=useState<ApprovedAsset[]>([]);
  const[busy,setBusy]=useState(false);
  const[loading,setLoading]=useState(false);
  const[error,setError]=useState('');
  const[notice,setNotice]=useState('');
  useEffect(()=>()=>{if(preview)URL.revokeObjectURL(preview)},[preview]);
  useEffect(()=>{
    let active=true;
    gaonApi.myStores().then(items=>{
      if(!active)return;
      setStores(items);
      if(items.length===1)setStoreId(items[0].id);
    }).catch(e=>{if(active)setError(e instanceof Error?e.message:'Unable to load stores')});
    return()=>{active=false};
  },[]);
  useEffect(()=>{
    let active=true;
    setInventory([]);
    if(!storeId)return;
    gaonApi.storeInventory(storeId).then(items=>{if(active)setInventory(items)})
      .catch(e=>{if(active)setError(e instanceof Error?e.message:'Unable to load product listings')});
    return()=>{active=false};
  },[storeId]);

  async function request(path:string,init:RequestInit={},expectedStatus?:number){
    const token=getToken();
    if(!token)throw new Error('Sign in as a merchant or administrator first.');
    const res=await fetch(`${API}${path}`,{...init,headers:{...(init.headers||{}),Authorization:`Bearer ${token}`},cache:'no-store'});
    let body:any;try{body=await res.json()}catch{body=null}
    if(!res.ok)throw new Error(typeof body?.detail==='string'?body.detail:`Request failed (${res.status})`);
    if(expectedStatus!==undefined&&res.status!==expectedStatus)throw new Error('Secure image upload returned an unexpected response.');
    return body;
  }
  async function refresh(id=listingId){
    if(!/^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(id)){setError('Enter a valid store-product ID.');return}
    setLoading(true);setError('');
    try{
      const privateAssets=await request(`/media/store-products/${encodeURIComponent(id)}/images`);
      setAssets(privateAssets);
      const publicRes=await fetch(`${API}/media/store-products/${encodeURIComponent(id)}/approved-images`,{cache:'no-store'});
      setApproved(publicRes.ok?await publicRes.json():[]);
    }catch(e:any){setError(e.message);setAssets([]);setApproved([])}
    finally{setLoading(false)}
  }
  async function updateAltText(asset:MediaAsset,value:string){
    setBusy(true);setError('');setNotice('');
    try{
      await request(`/media/store-products/${encodeURIComponent(listingId)}/images/${asset.id}`,{
        method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({alt_text:value})
      });
      setNotice('Image description saved.');await refresh();
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }
  async function upload(){
    if(!file||!listingId)return;
    if(!['image/jpeg','image/png','image/webp'].includes(file.type)){setError('Choose a JPEG, PNG or WebP image.');return}
    setBusy(true);setError('');setNotice('');
    try{
      const form=new FormData();form.append('file',file);
      const result=await request(`/media/store-products/${encodeURIComponent(listingId)}/images`,{method:'POST',body:form},202);
      if(result?.state!=='quarantined'||typeof result?.id!=='string'||!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(result.id))throw new Error('The image upload was not confirmed as quarantined.');
      setNotice(`Image ${result.id} securely queued for scanning. It will not appear publicly until approved.`);
      setFile(null);setPreview('');
      await refresh();
    }catch(e:any){setError(e.message)}
    finally{setBusy(false)}
  }
  return <><Nav/><main className="container section">
    <span className="eyebrow">Merchant media</span><h2>Product photo management</h2>
    <p className="muted">Photos are attached to a specific store product, quarantined and scanned before an approved derivative can appear in the marketplace. Original uploads remain private.</p>
    <div className="card">
      {stores.length>0&&<><label htmlFor="media-store">Store</label><select id="media-store" value={storeId} onChange={e=>{setStoreId(e.target.value);setListingId('');setAssets([]);setApproved([]);setFile(null)}}><option value="">Choose a store</option>{stores.map(store=><option key={store.id} value={store.id}>{store.name}</option>)}</select>
      <label htmlFor="media-listing">Product listing</label><select id="media-listing" value={inventory.some(item=>item.id===listingId)?listingId:''} onChange={e=>{setListingId(e.target.value);setAssets([]);setApproved([]);setFile(null)}}><option value="">Choose a product</option>{inventory.map(item=><option key={item.id} value={item.id}>{item.product.name} · {item.product.unit}</option>)}</select></>}
      <label htmlFor="listing-id">Store-product ID (advanced)</label>
      <input id="listing-id" aria-label="Store-product ID" placeholder="Store-product UUID" value={listingId} onChange={e=>{setListingId(e.target.value.trim());setAssets([]);setApproved([]);setError('')}}/>
      <button className="btn" disabled={!listingId||loading} onClick={()=>refresh()}>{loading?'Loading…':'View photo status'}</button>
    </div>
    <div className="card" style={{marginTop:14}}>
      <label htmlFor="product-photo">Upload a photo for this product</label>
      <input id="product-photo" type="file" accept="image/jpeg,image/png,image/webp" onChange={e=>{const next=e.target.files?.[0]||null;setFile(next);setError('');setPreview(next?URL.createObjectURL(next):'')}}/>
      <button className="btn" disabled={!file||!listingId||busy} onClick={upload}>{busy?'Uploading…':'Securely upload & queue scan'}</button>
      {preview&&<div style={{marginTop:14}}><img src={preview} alt="Local preview of selected product photo" style={{maxWidth:'100%',maxHeight:260,objectFit:'contain'}}/></div>}
    </div>
    {error&&<div className="notice" role="alert">{error}</div>}
    {notice&&<div className="notice" role="status">{notice}</div>}
    <section className="card" style={{marginTop:14}}><h3>Processing status</h3>
      {assets.length===0?<p className="muted">No photos loaded for this product.</p>:<ul>{assets.map(asset=><li key={asset.id}><strong>{asset.state}</strong> · Photo {asset.id.slice(0,8)} · Position {asset.position}{asset.is_primary?' · Primary':''}<div><label htmlFor={`alt-${asset.id}`}>Accessible image description</label><input id={`alt-${asset.id}`} aria-label={`Image description ${asset.id.slice(0,8)}`} maxLength={240} defaultValue={asset.alt_text||''} onBlur={event=>{if(event.target.value.trim()!==(asset.alt_text||''))void updateAltText(asset,event.target.value)}} disabled={busy}/></div></li>)}</ul>}
      <button className="btn" disabled={!listingId||loading} onClick={()=>refresh()}>{loading?'Refreshing…':'Refresh status'}</button>
    </section>
    <section className="card" style={{marginTop:14}}><h3>Public approved photos</h3>
      {approved.length===0?<p className="muted">No approved public photos are available.</p>:<div style={{display:'flex',gap:12,flexWrap:'wrap'}}>{approved.map(asset=><img key={asset.id} src={asset.url} alt={asset.alt_text||'Approved product photo'} loading="lazy" style={{width:160,height:160,objectFit:'cover'}}/>)}</div>}
    </section>
  </main></>;
}
