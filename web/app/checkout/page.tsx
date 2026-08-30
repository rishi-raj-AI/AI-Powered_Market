'use client';

import {FormEvent,useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
import {AlertTriangle,MapPin,RefreshCw,ShieldCheck} from 'lucide-react';
import {Address,Cart,CheckoutDecision,gaonApi,PaymentConfig,Village} from '@/lib/api';
import {openRazorpayCheckout} from '@/lib/razorpay';
import {AddressLocationPicker} from '@/components/AddressLocationPicker';
import {Nav} from '@/components/Nav';

const money=(v:string|number)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR'}).format(Number(v));
const humanize=(value:string)=>value.replaceAll('_',' ');

export default function Checkout(){
 const[addresses,setAddresses]=useState<Address[]>([]);
 const[villages,setVillages]=useState<Village[]>([]);
 const[cart,setCart]=useState<Cart|null>(null);
 const[decision,setDecision]=useState<CheckoutDecision|null>(null);
 const[decisionBusy,setDecisionBusy]=useState(false);
 const[decisionError,setDecisionError]=useState('');
 const[payConfig,setPayConfig]=useState<PaymentConfig|null>(null);
 const[selected,setSelected]=useState('');
 const[showForm,setShowForm]=useState(false);
 const[village,setVillage]=useState('');
 const[landmark,setLandmark]=useState('');
 const[house,setHouse]=useState('');
 const[directions,setDirections]=useState('');
 const[recipient,setRecipient]=useState('');
 const[phone,setPhone]=useState('');
 const[lat,setLat]=useState<number|undefined>();
 const[lng,setLng]=useState<number|undefined>();
 const[payment,setPayment]=useState<'cod'|'upi'>('cod');
 const[msg,setMsg]=useState('');
 const[busy,setBusy]=useState(false);
 const router=useRouter();

 async function refreshDecision(addressId:string){
   setDecisionBusy(true);setDecisionError('');
   try{setDecision(await gaonApi.checkoutDecision(addressId))}
   catch(e:any){setDecision(null);setDecisionError(e.message||'Checkout verification failed.')}
   finally{setDecisionBusy(false)}
 }

 async function load(){
   try{
     const[a,v,c,p]=await Promise.all([gaonApi.addresses(),gaonApi.villages(),gaonApi.cart(),gaonApi.paymentConfig()]);
     setAddresses(a);setVillages(v);setCart(c);setPayConfig(p);
     const next=selected&&a.some(x=>x.id===selected)?selected:(a.find(x=>x.is_default)?.id||a[0]?.id||'');
     setSelected(next);
     if(next)await refreshDecision(next);else{setDecision(null);setDecisionError('')}
   }catch(e:any){setMsg(e.message)}
 }

 useEffect(()=>{load()},[]);

 async function saveAddress(e:FormEvent){
   e.preventDefault();
   try{
     if(lat===undefined||lng===undefined){setMsg('Pin the exact delivery location before saving.');return}
     const service=await gaonApi.serviceability(lat,lng);
     if(!service.serviceable){setMsg('This address is outside the current GaonOne delivery area. Move the pin inside an active service area.');return}
     const a=await gaonApi.createAddress({village_id:village,label:'Home',recipient_name:recipient||undefined,phone:phone||undefined,house_details:house||undefined,landmark,directions:directions||undefined,latitude:lat,longitude:lng,is_default:addresses.length===0});
     setSelected(a.id);setShowForm(false);setLat(undefined);setLng(undefined);await load();
   }catch(e:any){setMsg(e.message)}
 }

 async function chooseAddress(id:string){setSelected(id);await refreshDecision(id)}

 async function place(){
   if(!selected){setMsg('Add or select an address first.');return}
   if(!cart?.items.length){setMsg('Your cart is empty.');return}
   if(decisionBusy||decision?.ready!==true){setMsg('GaonOne must verify this cart and delivery location before the order can be placed.');return}
   if(payment==='upi'&&!payConfig?.enabled){setMsg('UPI is not enabled yet. Choose cash on delivery.');return}
   setBusy(true);setMsg('');
   try{
     const o=await gaonApi.checkout(selected,payment);
     if(payment==='cod'){router.push('/orders?placed='+o.order_number);return}
     const intent=await gaonApi.paymentIntent(o.id);const address=addresses.find(a=>a.id===selected);
     await openRazorpayCheckout({intent,orderNumber:o.order_number,customerName:address?.recipient_name,customerPhone:address?.phone,onDismiss:()=>{setBusy(false);setMsg(`Order ${o.order_number} was created, but payment is still pending. You can retry from Orders.`);router.push('/orders?payment=pending&order='+o.id)},onSuccess:async payload=>{try{await gaonApi.verifyPayment(payload);router.push('/orders?placed='+o.order_number+'&paid=1')}catch(e:any){setBusy(false);setMsg(e.message||'Payment verification failed. Check Orders before retrying.')}}});
   }catch(e:any){setBusy(false);setMsg(e.message)}finally{if(payment==='cod')setBusy(false)}
 }

 const ready=decision?.ready===true;
 return <><Nav/><main className="container section"><div className="sectionHead"><div><span className="eyebrow">Final step</span><h2>Checkout</h2><p className="muted">GaonOne verifies live stock, serviceability and checkout rules for your selected location.</p></div></div>
 {msg&&<div className="notice">{msg}</div>}
 {selected&&<div className={`notice ${!decisionBusy&&!ready?'dangerText':''}`}><div className="row">{decisionBusy?<RefreshCw size={18}/>:ready?<ShieldCheck size={18}/>:<AlertTriangle size={18}/>}<strong>{decisionBusy?'Rechecking checkout…':ready?'Ready to place order':'Checkout needs attention'}</strong></div>{decisionError&&<div className="muted small">{decisionError} <button className="btn secondary" type="button" onClick={()=>refreshDecision(selected)}>Retry</button></div>}{!decisionError&&decision?.blockers.length? <div className="muted small">{decision.blockers.map(humanize).join(' • ')}</div>:null}{!decisionError&&decision?.warnings.length? <div className="muted small">Warnings: {decision.warnings.map(humanize).join(' • ')}</div>:null}</div>}
 <div className="splitGrid checkoutLayout"><div className="stack"><div className="panel"><div className="row space"><div><h3>Delivery address</h3><span className="muted">Search or use your current location, then pin the exact entrance for delivery.</span></div><button className="btn secondary" onClick={()=>setShowForm(!showForm)}>+ Add address</button></div>{showForm&&<form className="form formInset" onSubmit={saveAddress}>
 <div className="field"><label htmlFor="checkout-village">Service-area fallback *</label><select id="checkout-village" required value={village} onChange={e=>{setVillage(e.target.value);const v=villages.find(x=>x.id===e.target.value);if(v?.latitude!==undefined&&v?.longitude!==undefined&&lat===undefined&&lng===undefined){setLat(v.latitude);setLng(v.longitude)}}}><option value="">Select area fallback</option>{villages.map(v=><option key={v.id} value={v.id}>{v.name}, {v.district}</option>)}</select><span className="muted small">The exact landmark/GPS point below is the primary delivery location.</span></div>
 <div className="row"><div className="field" style={{flex:1}}><label htmlFor="checkout-recipient">Recipient</label><input id="checkout-recipient" value={recipient} onChange={e=>setRecipient(e.target.value)}/></div><div className="field" style={{flex:1}}><label htmlFor="checkout-phone">Phone</label><input id="checkout-phone" value={phone} onChange={e=>setPhone(e.target.value)}/></div></div>
 <div className="field"><label htmlFor="checkout-house">House / area / locality</label><input id="checkout-house" value={house} onChange={e=>setHouse(e.target.value)} placeholder="House name, gali, colony, locality"/></div>
 <div className="field"><label htmlFor="checkout-landmark">Landmark *</label><input id="checkout-landmark" required value={landmark} onChange={e=>setLandmark(e.target.value)} placeholder="Near temple, school, main chowk..."/></div>
 <div className="field"><div className="fieldLabel">Exact delivery point *</div><AddressLocationPicker latitude={lat} longitude={lng} onChange={(nextLat,nextLng)=>{setLat(nextLat);setLng(nextLng)}} onAddress={address=>{if(!landmark)setLandmark(address)}}/></div>
 <div className="field"><label htmlFor="checkout-directions">Directions for rider</label><textarea id="checkout-directions" value={directions} onChange={e=>setDirections(e.target.value)} placeholder="Gate colour, road turn, whom to ask for..."/></div><button className="btn">Save address</button></form>}
 <div className="stack" style={{marginTop:14}}>{addresses.map(a=><label className={`card addressCard ${selected===a.id?'selectedCard':''}`} key={a.id}><div className="row"><input type="radio" name="address" checked={selected===a.id} onChange={()=>chooseAddress(a.id)}/><MapPin size={18}/><div><strong>{a.label}{a.is_default?' • Default':''}</strong><div className="muted">{a.house_details?`${a.house_details}, `:''}{a.landmark}</div>{a.latitude!==undefined&&a.longitude!==undefined&&<div className="muted small">Exact location saved</div>}{a.directions&&<div className="muted small">{a.directions}</div>}</div></div></label>)}{addresses.length===0&&!showForm&&<div className="notice">Add a delivery address to continue.</div>}</div></div>
 <div className="panel"><h3>Payment</h3><label className={`card row ${payment==='cod'?'selectedCard':''}`}><input type="radio" name="payment" checked={payment==='cod'} onChange={()=>setPayment('cod')}/><div><strong>Cash on delivery</strong><div className="muted">Pay the rider when your order arrives.</div></div></label><label className={`card row ${payment==='upi'?'selectedCard':''}`} style={{marginTop:10,opacity:payConfig?.enabled?1:.55}}><input type="radio" name="payment" disabled={!payConfig?.enabled} checked={payment==='upi'} onChange={()=>setPayment('upi')}/><div><strong>UPI / online payment</strong><div className="muted">{payConfig?.enabled?'Secure Razorpay checkout. Payment is verified by GaonOne before being marked paid.':'Coming soon — Razorpay credentials not enabled.'}</div></div></label></div></div>
 <aside className="panel summaryCard"><h3>Order summary</h3><div className="metricRow"><span>{cart?.items.length||0} cart lines</span><strong>{money(decision?.subtotal??cart?.subtotal??0)}</strong></div>{decision?.delivery_fee!==undefined&&<div className="metricRow"><span>Local delivery</span><strong>{money(decision.delivery_fee)}</strong></div>}{decision?.total!==undefined&&<div className="metricRow totalRow"><span>Total</span><strong>{money(decision.total)}</strong></div>}{decision?.merchant_reliability!==undefined&&<p className="muted small">Store fulfilment signal {Math.round(decision.merchant_reliability*100)}% from {decision.merchant_reliability_samples??0} sampled orders. This is an operational signal, not a customer rating.</p>}<div className="row muted small"><ShieldCheck size={16}/> Stock and delivery eligibility are rechecked before confirmation.</div><button className="btn fullBtn" disabled={busy||decisionBusy||!cart?.items.length||!ready} onClick={place}>{decisionBusy?'Rechecking checkout…':!ready?'Resolve checkout blockers':busy?(payment==='upi'?'Opening secure payment…':'Placing order…'):(payment==='upi'?'Place order & pay':'Place order')}</button></aside></div></main></>;
}
