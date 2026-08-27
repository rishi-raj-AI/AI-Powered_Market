'use client';
import {useEffect,useMemo,useState} from 'react';
import {AlertTriangle,Boxes,IndianRupee,MapPinned,PackageCheck,RefreshCw,Store,Truck,Users} from 'lucide-react';
import {AdminOverview,gaonApi,Merchant,MerchantStatus} from '@/lib/api';
import {Nav} from '@/components/Nav';

const money=(value:string|number)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(Number(value||0));
const label=(value:string)=>value.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());

export default function Admin(){
  const [merchants,setMerchants]=useState<Merchant[]>([]);
  const [overview,setOverview]=useState<AdminOverview|null>(null);
  const [msg,setMsg]=useState('');
  const [busy,setBusy]=useState('');
  async function load(){try{const [m,o]=await Promise.all([gaonApi.merchants(),gaonApi.adminOverview()]);setMerchants(m);setOverview(o);setMsg('')}catch(e:any){setMsg(e.message)}}
  useEffect(()=>{load()},[]);
  async function changeStatus(id:string,status:MerchantStatus){setBusy(id);try{await gaonApi.updateMerchantStatus(id,status);setMsg(status==='approved'?'Merchant activated.':'Merchant suspended and storefronts hidden.');await load()}catch(e:any){setMsg(e.message)}finally{setBusy('')}}
  const pipeline=useMemo(()=>overview?Object.entries(overview.orders.by_status):[],[overview]);
  return <><Nav/><main className="container section">
    <div className="sectionHead"><div><span className="eyebrow">Operations control</span><h2>Admin dashboard</h2><p className="muted">Live marketplace health, fulfilment pressure and merchant controls.</p></div><button className="btn secondary" onClick={load}><RefreshCw size={16}/> Refresh</button></div>
    {msg&&<div className="notice">{msg}</div>}
    <div className="statsGrid">
      <div className="card statCard"><Users/><span className="statValue">{overview?.users??'—'}</span><strong>Users</strong><span className="muted">Verified marketplace accounts</span></div>
      <div className="card statCard"><MapPinned/><span className="statValue">{overview?.villages??'—'}</span><strong>Villages</strong><span className="muted">Active service coverage</span></div>
      <div className="card statCard"><Store/><span className="statValue">{overview?.active_stores??'—'}</span><strong>Live stores</strong><span className="muted">Visible customer storefronts</span></div>
      <div className="card statCard"><IndianRupee/><span className="statValue">{overview?money(overview.gross_order_value):'—'}</span><strong>Order value</strong><span className="muted">Non-cancelled GMV</span></div>
      <div className="card statCard"><PackageCheck/><span className="statValue">{overview?.orders.total??'—'}</span><strong>Orders</strong><span className="muted">All-time order volume</span></div>
      <div className="card statCard"><Truck/><span className="statValue">{overview?.operations.ready_unassigned_deliveries??'—'}</span><strong>Awaiting rider</strong><span className="muted">Ready and unassigned</span></div>
      <div className="card statCard"><AlertTriangle/><span className="statValue">{overview?.operations.low_stock_listings??'—'}</span><strong>Low stock</strong><span className="muted">Available listings at 5 or less</span></div>
      <div className="card statCard"><Boxes/><span className="statValue">{overview?money(overview.paid_gmv):'—'}</span><strong>Collected GMV</strong><span className="muted">Paid orders</span></div>
    </div>

    <section className="section splitGrid">
      <div className="panel"><div className="sectionHead"><div><h2 className="subhead">Order pipeline</h2><span className="muted">Current operational distribution.</span></div></div><div className="stack">{pipeline.map(([status,count])=><div className="metricRow" key={status}><span>{label(status)}</span><strong>{count}</strong></div>)}</div></div>
      <div className="panel"><div className="sectionHead"><div><h2 className="subhead">Merchant health</h2><span className="muted">Approval and risk state.</span></div></div><div className="stack"><div className="metricRow"><span>Pending review</span><strong>{overview?.merchants.pending??0}</strong></div><div className="metricRow"><span>Approved</span><strong>{overview?.merchants.approved??0}</strong></div><div className="metricRow"><span>Suspended</span><strong>{overview?.merchants.suspended??0}</strong></div></div></div>
    </section>

    <section className="section"><div className="panel"><div className="sectionHead"><div><h2 className="subhead">Merchant control</h2><span className="muted">Approve applicants, suspend risky sellers, or restore access immediately.</span></div></div><div className="tableWrap"><table className="table"><thead><tr><th>Business</th><th>Status</th><th>GSTIN</th><th>Action</th></tr></thead><tbody>{merchants.map(m=><tr key={m.id}><td><strong>{m.business_name}</strong></td><td><span className={`badge status-${m.status}`}>{label(m.status)}</span></td><td>{m.gstin||'—'}</td><td><div className="row">{m.status!=='approved'&&<button disabled={busy===m.id} className="btn" onClick={()=>changeStatus(m.id,'approved')}>{m.status==='pending'?'Approve':'Reactivate'}</button>}{m.status==='approved'&&<button disabled={busy===m.id} className="btn dangerBtn" onClick={()=>changeStatus(m.id,'suspended')}>Suspend</button>}</div></td></tr>)}{merchants.length===0&&<tr><td colSpan={4} className="muted">No merchant applications yet.</td></tr>}</tbody></table></div></div></section>
  </main></>;
}
