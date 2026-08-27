'use client';

import {FormEvent,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import {gaonApi,setToken} from '@/lib/api';
import {Nav} from '@/components/Nav';

declare global {
  interface Window {
    initSendOTP?: (configuration: Record<string, unknown>) => void;
  }
}

// MSG91 OTP Widget browser token. The private account Authkey remains server-side only.
const MSG91_WIDGET_ID='366841725756303030313539';
const MSG91_WIDGET_TOKEN='565081TwccrS3r6a90922dP1';
const MSG91_SCRIPT_ID='msg91-otp-provider';
const MSG91_SCRIPT_SRC='https://verify.msg91.com/otp-provider.js';

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

function looksLikeJwt(value:unknown):value is string{
  return typeof value==='string'&&value.split('.').length===3&&value.length>20;
}

function accessToken(data:unknown):string|null{
  if(looksLikeJwt(data))return data;
  if(!data||typeof data!=='object')return null;
  const value=data as Record<string,unknown>;

  // MSG91 Web/Mobile Widget responses may expose the verified JWT in
  // access-token/access_token/token/jwt or in `message` on success.
  for(const key of ['access-token','access_token','token','jwt','message']){
    if(looksLikeJwt(value[key]))return value[key] as string;
  }

  for(const key of ['data','result','response']){
    const nested=value[key];
    if(nested&&typeof nested==='object'){
      const token=accessToken(nested);
      if(token)return token;
    }
  }
  return null;
}

function loadMsg91Sdk():Promise<void>{
  if(window.initSendOTP)return Promise.resolve();

  return new Promise((resolve,reject)=>{
    const existing=document.getElementById(MSG91_SCRIPT_ID) as HTMLScriptElement|null;

    const waitForInitializer=(attempt=0)=>{
      if(window.initSendOTP){resolve();return;}
      if(attempt>=100){reject(new Error('MSG91 OTP SDK loaded but its initializer is unavailable.'));return;}
      window.setTimeout(()=>waitForInitializer(attempt+1),100);
    };

    if(existing){
      waitForInitializer();
      return;
    }

    const script=document.createElement('script');
    script.id=MSG91_SCRIPT_ID;
    script.src=MSG91_SCRIPT_SRC;
    script.async=true;
    script.onload=()=>waitForInitializer();
    script.onerror=()=>reject(new Error('MSG91 OTP SDK failed to load. Check your connection and try again.'));
    document.body.appendChild(script);
  });
}

export default function Login(){
  const [name,setName]=useState('');
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const loginStarted=useRef(false);
  const router=useRouter();

  async function finishLogin(token:string){
    if(loginStarted.current)return;
    loginStarted.current=true;
    try{
      const result=await gaonApi.exchangeWidgetToken(token,name.trim()||undefined);
      setToken(result.access_token);
      const me=await gaonApi.me();
      const route={merchant:'/merchant',admin:'/admin',delivery:'/delivery',customer:'/market'}[me.role]||'/market';
      router.replace(route);
    }catch(error){
      loginStarted.current=false;
      throw error;
    }
  }

  async function openOtp(e:FormEvent){
    e.preventDefault();
    setMessage('');
    setBusy(true);
    loginStarted.current=false;

    try{
      await loadMsg91Sdk();
      if(!window.initSendOTP)throw new Error('MSG91 OTP SDK is unavailable.');

      window.initSendOTP({
        widgetId:MSG91_WIDGET_ID,
        tokenAuth:MSG91_WIDGET_TOKEN,
        success:async(data:unknown)=>{
          try{
            const token=accessToken(data);
            if(!token)throw new Error('MSG91 verified the OTP but the access token response was not recognized.');
            setMessage('Phone verified. Signing you in…');
            await finishLogin(token);
          }catch(error){
            console.error('GaonOne login exchange failure',error);
            setMessage(providerMessage(error));
            setBusy(false);
          }
        },
        failure:(error:unknown)=>{
          console.error('MSG91 OTP failure',error);
          setMessage(providerMessage(error));
          setBusy(false);
        },
      });

      // The MSG91 default widget owns the phone, CAPTCHA, send/resend and verify UI.
      setBusy(false);
    }catch(error){
      console.error('MSG91 initialization failure',error);
      setMessage(providerMessage(error));
      setBusy(false);
    }
  }

  return <>
    <Nav/>
    <div className="authWrap"><div className="panel authCard">
      <span className="eyebrow">Secure passwordless login</span>
      <h1>Sign in with your mobile</h1>
      <p className="muted">MSG91 will securely handle your mobile number, CAPTCHA and OTP verification.</p>
      <form className="form" onSubmit={openOtp}>
        <div className="field">
          <label>Name (first login)</label>
          <input value={name} onChange={e=>setName(e.target.value)} placeholder="Your name" autoComplete="name"/>
        </div>
        <button className="btn" disabled={busy}>{busy?'Opening OTP…':'Continue with OTP'}</button>
      </form>
      {message&&<p className="notice">{message}</p>}
    </div></div>
  </>;
}
