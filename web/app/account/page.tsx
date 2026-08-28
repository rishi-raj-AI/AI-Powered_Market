'use client';

import {FormEvent,useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
import {BriefcaseBusiness,CheckCircle2,ShieldCheck,UserRound} from 'lucide-react';
import {ApiError,gaonApi,Merchant,User} from '@/lib/api';
import {Nav} from '@/components/Nav';

export default function AccountPage(){
  const router=useRouter();
  const [me,setMe]=useState<User|null>(null);
  const [merchant,setMerchant]=useState<Merchant|null>(null);
  const [businessName,setBusinessName]=useState('');
  const [gstin,setGstin]=useState('');
  const [loading,setLoading]=useState(true);
  const [submitting,setSubmitting]=useState(false);
  const [message,setMessage]=useState('');

  useEffect(()=>{
    (async()=>{
      try{
        const user=await gaonApi.me();setMe(user);
        if(user.role==='merchant'){
          try{setMerchant(await gaonApi.merchant())}catch(e){if(!(e instanceof ApiError&&e.status===404))throw e}
        }
      }catch(e:any){
        if(e instanceof ApiError&&e.status===401){router.replace('/login');return}
        setMessage(e.message||'Unable to load account.');
      }finally{setLoading(false)}
    })();
  },[router]);

  async function apply(e:FormEvent){
    e.preventDefault();
    if(!businessName.trim()){setMessage('Enter your business or shop name.');return}
    setSubmitting(true);setMessage('');
    try{
      const result=await gaonApi.applyMerchant(businessName.trim(),gstin.trim()||undefined);
      setMerchant(result);
      const user=await gaonApi.me();setMe(user);
      setMessage('Merchant application submitted. Your account is now waiting for admin approval.');
    }catch(e:any){setMessage(e.message||'Unable to submit merchant application.')}finally{setSubmitting(false)}
  }

  if(loading)return <><Nav/><main className="container section"><div className="panel"><p>Loading account…</p></div></main></>;

  return <><Nav/><main className="container section">
    <div className="sectionHead"><div><span className="eyebrow">Your account</span><h2>Profile & business</h2><p className="muted">Manage your GaonOne identity and start selling locally.</p></div></div>
    {message&&<div className="notice">{message}</div>}
    <div className="grid" style={{gridTemplateColumns:'repeat(auto-fit,minmax(300px,1fr))',gap:18}}>
      <section className="panel stack">
        <div className="row"><span className="storeIcon"><UserRound size={22}/></span><div><h3 style={{margin:0}}>Account</h3><p className="muted" style={{margin:'4px 0 0'}}>Verified GaonOne user</p></div></div>
        <div><strong>Phone</strong><p className="muted">{me?.phone||'—'}</p></div>
        <div><strong>Role</strong><p className="muted" style={{textTransform:'capitalize'}}>{me?.role||'customer'}</p></div>
        <div className="row"><ShieldCheck size={17}/><span>{me?.is_verified?'Phone verified':'Verification pending'}</span></div>
      </section>

      {merchant?<section className="panel stack">
        <div className="row"><span className="storeIcon"><BriefcaseBusiness size={22}/></span><div><h3 style={{margin:0}}>{merchant.business_name}</h3><p className="muted" style={{margin:'4px 0 0'}}>Merchant application</p></div></div>
        <div className="row"><CheckCircle2 size={17}/><strong style={{textTransform:'capitalize'}}>Status: {merchant.status}</strong></div>
        {merchant.status==='pending'&&<p className="muted">Your application is waiting for GaonOne admin approval. Once approved, sign in again and the Merchant workspace will open automatically.</p>}
        {merchant.status==='approved'&&<button className="btn" onClick={()=>router.push('/merchant')}>Open Merchant workspace</button>}
        {merchant.status==='suspended'&&<p className="muted">This merchant account is suspended. Contact the GaonOne pilot administrator.</p>}
      </section>:
      me?.role==='customer'?<section className="panel stack">
        <div><span className="eyebrow">Sell on GaonOne</span><h3>Become a local merchant</h3><p className="muted">Apply with your shop or business name. The pilot admin reviews the application before your storefront goes live.</p></div>
        <form className="stack" onSubmit={apply}>
          <label><strong>Business / shop name</strong><input value={businessName} onChange={e=>setBusinessName(e.target.value)} placeholder="e.g. Nimbu Kirana & General Store" maxLength={160}/></label>
          <label><strong>GSTIN <span className="muted">(optional)</span></strong><input value={gstin} onChange={e=>setGstin(e.target.value.toUpperCase())} placeholder="GSTIN if applicable" maxLength={20}/></label>
          <button className="btn" disabled={submitting}>{submitting?'Submitting…':'Apply as merchant'}</button>
        </form>
      </section>:<section className="panel stack"><h3>Role workspace</h3><p className="muted">Your current role is <strong>{me?.role}</strong>. Use the navigation above to open its workspace.</p></section>}
    </div>
  </main></>;
}
