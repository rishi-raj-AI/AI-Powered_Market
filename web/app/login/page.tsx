'use client';

import Script from 'next/script';
import {FormEvent,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import {gaonApi,setToken} from '@/lib/api';
import {Nav} from '@/components/Nav';

declare global {
  interface Window {
    initSendOTP?: (configuration: Record<string, unknown>) => void;
    sendOtp?: (identifier: string, success?: (data: unknown) => void, failure?: (error: unknown) => void) => void;
    verifyOtp?: (otp: string | number, success?: (data: unknown) => void, failure?: (error: unknown) => void) => void;
    isCaptchaVerified?: () => boolean;
  }
}

// MSG91 explicitly designs the Widget token for browser-side OTP Widget use.
// The private account Authkey is NEVER placed here; it remains server-side only.
const MSG91_WIDGET_ID='366841725756303030313539';
const MSG91_WIDGET_TOKEN='565081TwccrS3r6a90922dP1';
const MSG91_CAPTCHA_RENDER_ID='msg91-captcha';

function providerMessage(error:unknown):string{
  if(error instanceof Error)return error.message;
  if(typeof error==='string'&&error.trim())return error;
  if(error&&typeof error==='object'){
    const value=error as Record<string,unknown>;
    for(const key of ['message','error','detail','msg','description']){
      const candidate=value[key];
      if(typeof candidate==='string'&&candidate.trim())return candidate;
      if(candidate&&typeof candidate==='object'){
        const nested=providerMessage(candidate);
        if(nested!=='MSG91 authentication failed.')return nested;
      }
    }
    try{
      const serialized=JSON.stringify(error);
      if(serialized&&serialized!=='{}')return `MSG91: ${serialized.slice(0,500)}`;
    }catch{}
  }
  return 'MSG91 authentication failed.';
}

function accessToken(data:unknown):string|null{
  if(typeof data==='string')return data.split('.').length===3?data:null;
  if(!data||typeof data!=='object')return null;
  const value=data as Record<string,unknown>;
  for(const key of ['access-token','access_token','token','jwt']){
    if(typeof value[key]==='string'&&(value[key] as string).length>20)return value[key] as string;
  }
  const nested=value.data;
  return nested&&typeof nested==='object'?accessToken(nested):null;
}

function normalizeIdentifier(phone:string){
  const digits=phone.replace(/\D/g,'');
  return digits.length===10?`91${digits}`:digits;
}

export default function Login(){
  const [phone,setPhone]=useState('+91');
  const [otp,setOtp]=useState('');
  const [name,setName]=useState('');
  const [step,setStep]=useState(1);
  const [message,setMessage]=useState('');
  const [sdkReady,setSdkReady]=useState(false);
  const [busy,setBusy]=useState(false);
  const loginStarted=useRef(false);
  const router=useRouter();

  async function finishLogin(token:string){
    if(loginStarted.current)return;
    loginStarted.current=true;
    try{
      const result=await gaonApi.exchangeWidgetToken(token,name||undefined);
      setToken(result.access_token);
      const me=await gaonApi.me();
      const route={merchant:'/merchant',admin:'/admin',delivery:'/delivery',customer:'/market'}[me.role]||'/market';
      router.replace(route);
    }catch(error){
      loginStarted.current=false;
      throw error;
    }
  }

  function fail(error:unknown){
    console.error('MSG91 OTP failure',error);
    setMessage(providerMessage(error));
  }

  function initializeWidget(){
    if(!window.initSendOTP){
      setMessage('MSG91 OTP SDK failed to load. Please reload the page.');
      return;
    }
    // With exposed custom UI methods, MSG91 recommends listening to the
    // sendOtp/verifyOtp callbacks only. Registering both configuration-level
    // success/failure callbacks and verifyOtp callbacks causes duplicate events.
    window.initSendOTP({
      widgetId:MSG91_WIDGET_ID,
      tokenAuth:MSG91_WIDGET_TOKEN,
      exposeMethods:true,
      captchaRenderId:MSG91_CAPTCHA_RENDER_ID,
    });
    setSdkReady(true);
  }

  async function request(e:FormEvent){
    e.preventDefault();setMessage('');setBusy(true);loginStarted.current=false;
    try{
      if(!sdkReady||!window.sendOtp)throw new Error('OTP service is still loading. Please retry in a moment.');
      const identifier=normalizeIdentifier(phone);
      if(!/^91\d{10}$/.test(identifier))throw new Error('Enter a valid 10-digit Indian mobile number.');
      if(window.isCaptchaVerified&&window.isCaptchaVerified()===false){
        throw new Error('Complete the CAPTCHA verification, then press Send OTP.');
      }
      await new Promise<void>((resolve,reject)=>window.sendOtp!(identifier,()=>resolve(),reject));
      setMessage('OTP sent to your mobile number.');
      setStep(2);
    }catch(error){fail(error)}finally{setBusy(false)}
  }

  async function verify(e:FormEvent){
    e.preventDefault();setMessage('');setBusy(true);
    try{
      if(!window.verifyOtp)throw new Error('OTP service is not ready. Please reload and try again.');
      await new Promise<void>((resolve,reject)=>window.verifyOtp!(otp,async(data:unknown)=>{
        try{
          const token=accessToken(data);
          if(!token)throw new Error('OTP verified but no MSG91 access token was returned.');
          await finishLogin(token);
          resolve();
        }catch(error){reject(error)}
      },reject));
    }catch(error){fail(error)}finally{setBusy(false)}
  }

  return <>
    <Script src="https://verify.msg91.com/otp-provider.js" strategy="afterInteractive" onLoad={initializeWidget}/>
    <Nav/>
    <div className="authWrap"><div className="panel authCard">
      <span className="eyebrow">Secure passwordless login</span>
      <h1>{step===1?'Enter your mobile number':'Verify OTP'}</h1>
      <p className="muted">OTP verification secured by MSG91.</p>
      {step===1&&<div id={MSG91_CAPTCHA_RENDER_ID}/>} 
      {step===1?<form className="form" onSubmit={request}>
        <div className="field"><label>Mobile number</label><input value={phone} onChange={e=>setPhone(e.target.value)} required inputMode="tel"/></div>
        <div className="field"><label>Name (first login)</label><input value={name} onChange={e=>setName(e.target.value)} placeholder="Your name"/></div>
        <button className="btn" disabled={busy||!sdkReady}>{busy?'Sending…':sdkReady?'Send OTP':'Loading OTP…'}</button>
      </form>:<form className="form" onSubmit={verify}>
        <div className="field"><label>OTP</label><input value={otp} onChange={e=>setOtp(e.target.value.replace(/\D/g,''))} inputMode="numeric" autoComplete="one-time-code" minLength={4} maxLength={8} required/></div>
        <button className="btn" disabled={busy}>{busy?'Verifying…':'Verify & continue'}</button>
        <button type="button" className="btn ghost" disabled={busy} onClick={()=>{setOtp('');setMessage('');setStep(1);loginStarted.current=false}}>Change number</button>
      </form>}
      {message&&<p className="notice">{message}</p>}
    </div></div>
  </>;
}
