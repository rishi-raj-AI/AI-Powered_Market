import type {PaymentIntent,PaymentVerify} from '@/lib/api';

declare global{
  interface Window{
    Razorpay?:new(options:RazorpayOptions)=>{open:()=>void;on:(event:string,handler:(response:any)=>void)=>void};
  }
}

type RazorpayOptions={
  key:string;
  amount:number;
  currency:string;
  name:string;
  description:string;
  order_id:string;
  handler:(response:RazorpaySuccess)=>void|Promise<void>;
  prefill?:{name?:string;contact?:string};
  theme?:Record<string,string>;
  modal?:{ondismiss?:()=>void};
};

type RazorpaySuccess={razorpay_payment_id:string;razorpay_order_id:string;razorpay_signature:string};

let sdkPromise:Promise<void>|null=null;

export function loadRazorpay():Promise<void>{
  if(typeof window==='undefined')return Promise.reject(new Error('Payment checkout is only available in the browser.'));
  if(window.Razorpay)return Promise.resolve();
  if(sdkPromise)return sdkPromise;
  sdkPromise=new Promise((resolve,reject)=>{
    const existing=document.querySelector<HTMLScriptElement>('script[data-gaonone-razorpay="1"]');
    if(existing){existing.addEventListener('load',()=>resolve(),{once:true});existing.addEventListener('error',()=>reject(new Error('Unable to load Razorpay Checkout.')),{once:true});return}
    const script=document.createElement('script');
    script.src='https://checkout.razorpay.com/v1/checkout.js';
    script.async=true;
    script.dataset.gaononeRazorpay='1';
    script.onload=()=>resolve();
    script.onerror=()=>reject(new Error('Unable to load Razorpay Checkout.'));
    document.head.appendChild(script);
  });
  return sdkPromise;
}

export async function openRazorpayCheckout(args:{intent:PaymentIntent;orderNumber:string;customerName?:string;customerPhone?:string;onSuccess:(payload:PaymentVerify)=>Promise<void>;onDismiss?:()=>void}){
  await loadRazorpay();
  if(!window.Razorpay)throw new Error('Razorpay Checkout did not initialize.');
  const checkout=new window.Razorpay({
    key:args.intent.key_id,
    amount:args.intent.amount_subunits,
    currency:args.intent.currency,
    name:'GaonOne',
    description:`Order ${args.orderNumber}`,
    order_id:args.intent.provider_order_id,
    prefill:{name:args.customerName,contact:args.customerPhone},
    modal:{ondismiss:args.onDismiss},
    handler:async(response:RazorpaySuccess)=>{
      await args.onSuccess({
        payment_attempt_id:args.intent.payment_attempt_id,
        razorpay_payment_id:response.razorpay_payment_id,
        razorpay_signature:response.razorpay_signature,
      });
    },
  });
  checkout.open();
}
