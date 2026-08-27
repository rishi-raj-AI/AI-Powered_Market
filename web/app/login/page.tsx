'use client';

import Script from 'next/script';
import {FormEvent,useState} from 'react';
import {useRouter} from 'next/navigation';
import {gaonApi,setToken} from '@/lib/api';
import {Nav} from '@/components/Nav';

declare global {
  interface Window {
    initSendOTP?: (configuration: Record<string, unknown>) => void;
    sendOtp?: (identifier: string, success?: (data: unknown) => void, failure?: (error: unknown) => void) => void;
    verifyOtp?: (otp: string | number, success?: (data: unknown) => void, failure?: (error: unknown) => void) => void;
  }
}

const widgetId=process.env.NEXT_PUBLIC_MSG91_WIDGET_ID||'';
const widgetToken=process.env.NEXT_PUBLIC_MSG91_WIDGET_TOKEN||'';
const widgetEnabled=Boolean(widgetId&&widgetToken);

function msg(error:unknown){
  if(error instanceof Error)return error.message;
  if(typeof error==='string')return error;
  if(error&&typeof error==='object'){
    const value=error as Record<string,unknown>;
    for(const key of ['message','error','detail'])if(typeof value[key]==='string')return value[key] as string;
  }
  return 'Authentication failed. Please try again.';
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
  const [sdkReady,setSdkReady]=useState(!widgetEnabled);
  const [busy,setBusy]=useState(false);
  const router=useRouter();

  async function finishLogin(token:string){
    const result=await gaonApi.exchangeWidgetToken(token,name||undefined);
    setToken(result.access_token);
    const me=await gaonApi.me();
    const route={merchant:'/merchant',admin:'/admin',delivery:'/delivery',customer:'/market'}[me.role]||'/market';
    router.push(route);
  }

  function initializeWidget(){
    if(!widgetEnabled||!window.initSendOTP)return;
    window.initSendOTP({
      widgetId,
      tokenAuth:widgetToken,
      exposeMethods:true,
      captchaRenderId:'msg91-captcha',
      success:async(data:unknown)=>{
        const token=accessToken(data);
        if(!token){setMessage('MSG91 verified the OTP but did not return an access token.');return;}
        try{setBusy(true);await finishLogin(token)}catch(error){setMessage(msg(error))}finally{setBusy(false)}
      },
      failure:(error:unknown)=>setMessage(msg(error)),
    });
    setSdkReady(true);
  }

  async function request(e:FormEvent){
    e.preventDefault();setMessage('');setBusy(true);
    try{
      if(widgetEnabled){
        if(!sdkReady||!window.sendOtp)throw new Error('OTP service is still loading. Please retry in a moment.');
        const identifier=normalizeIdentifier(phone);
        if(!/^91\d{10}$/.test(identifier))throw new Error('Enter a valid 10-digit Indian mobile number.');
        await new Promise<void>((resolve,reject)=>window.sendOtp!(identifier,()=>resolve(),reject));
        setMessage('OTP sent to your mobile number.');setStep(2);
      }else{
        const result=await gaonApi.requestOtp(phone);
        setMessage(result.dev_otp?`Development OTP: ${result.dev_otp}`:result.message);setStep(2);
      }
    }catch(error){setMessage(msg(error))}finally{setBusy(false)}
  }

  async function verify(e:FormEvent){
    e.preventDefault();setMessage('');setBusy(true);
    try{
      if(widgetEnabled){
        if(!window.verifyOtp)throw new Error('OTP service is not ready. Please reload and try again.');
        await new Promise<void>((resolve,reject)=>window.verifyOtp!(otp,async(data:unknown)=>{
          try{
            const token=accessToken(data);
            if(!token)throw new Error('OTP verified but no MSG91 access token was returned.');
            await finishLogin(token);resolve();
          }catch(error){reject(error)}
        },reject));
      }else{
        const result=await gaonApi.verifyOtp(phone,otp,name||undefined);
        setToken(result.access_token);
        const me=await gaonApi.me();
        const route={merchant:'/merchant',admin:'/admin',delivery:'/delivery',customer:'/market'}[me.role]||'/market';
        router.push(route);
      }
    }catch(error){setMessage(msg(error))}finally{setBusy(false)}
  }

  return <>
    {widgetEnabled&&<Script src="https://verify.msg91.com/otp-provider.js" strategy="afterInteractive" onLoad={initializeWidget}/>} 
    <Nav/>
    <div className="authWrap"><div className="panel authCard">
      <span className="eyebrow">Secure passwordless login</span>
      <h1>{step===1?'Enter your mobile number':'Verify OTP'}</h1>
      <p className="muted">{widgetEnabled?'OTP verification secured by MSG91.':'Development OTP login.'}</p>
      <div id="msg91-captcha"/>
      {step===1?<form className="form" onSubmit={request}>
        <div className="field"><label>Mobile number</label><input value={phone} onChange={e=>setPhone(e.target.value)} required inputMode="tel"/></div>
        <div className="field"><label>Name (first login)</label><input value={name} onChange={e=>setName(e.target.value)} placeholder="Your name"/></div>
        <button className="btn" disabled={busy||!sdkReady}>{busy?'Sending…':'Send OTP'}</button>
      </form>:<form className="form" onSubmit={verify}>
        <div className="field"><label>OTP</label><input value={otp} onChange={e=>setOtp(e.target.value.replace(/\D/g,''))} inputMode="numeric" autoComplete="one-time-code" required/></div>
        <button className="btn" disabled={busy}>{busy?'Verifying…':'Verify & continue'}</button>
        <button type="button" className="btn ghost" disabled={busy} onClick={()=>{setOtp('');setMessage('');setStep(1)}}>Change number</button>
      </form>}
      {message&&<p className="notice">{message}</p>}
    </div></div>
  </>;
}
