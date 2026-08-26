const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
export class ApiError extends Error{constructor(public status:number,message:string){super(message)}}
export function getToken(){if(typeof window==='undefined')return null;return localStorage.getItem('gaonone_token')}
export function setToken(token:string){localStorage.setItem('gaonone_token',token)}
export function clearToken(){localStorage.removeItem('gaonone_token')}
export async function api<T>(path:string,init:RequestInit={}):Promise<T>{const token=getToken();const headers=new Headers(init.headers);if(!headers.has('Content-Type'))headers.set('Content-Type','application/json');if(token)headers.set('Authorization',`Bearer ${token}`);const res=await fetch(`${API}${path}`,{...init,headers,cache:'no-store'});if(!res.ok){let message=`Request failed (${res.status})`;try{const j=await res.json();message=j.detail||message}catch{}throw new ApiError(res.status,message)}if(res.status===204)return undefined as T;return res.json()}
export const gaonApi={requestOtp:(phone:string)=>api<{message:string;dev_otp?:string}>('/auth/request-otp',{method:'POST',body:JSON.stringify({phone})}),verifyOtp:(phone:string,otp:string,full_name?:string)=>api<{access_token:string;token_type:string}>('/auth/verify-otp',{method:'POST',body:JSON.stringify({phone,otp,full_name})}),me:()=>api<User>('/users/me'),villages:()=>api<Village[]>('/villages'),categories:()=>api<Category[]>('/categories'),stores:(villageId?:string)=>api<Store[]>(`/stores${villageId?`?village_id=${villageId}`:''}`),store:(id:string)=>api<Store>(`/stores/${id}`),storeProducts:(id:string)=>api<StoreProduct[]>(`/stores/${id}/products`),cart:()=>api<Cart>('/cart'),addCart:(store_product_id:string,quantity:number)=>api<Cart>('/cart/items',{method:'POST',body:JSON.stringify({store_product_id,quantity})}),removeCart:(id:string)=>api<Cart>(`/cart/items/${id}`,{method:'DELETE'}),orders:()=>api<Order[]>('/orders'),merchant:()=>api<Merchant>('/merchants/me')};
export type User={id:string;phone:string;full_name?:string;role:'customer'|'merchant'|'delivery'|'admin';is_active:boolean;is_verified:boolean};
export type Village={id:string;name:string;taluka?:string;district:string;state:string;pincode?:string;latitude?:number;longitude?:number;is_active:boolean};
export type Category={id:string;name:string;slug:string;is_active:boolean};
export type Store={id:string;merchant_id:string;village_id:string;service_area_id?:string;name:string;slug:string;description?:string;phone?:string;landmark?:string;delivery_enabled:boolean;pickup_enabled:boolean;is_active:boolean};
export type Product={id:string;category_id:string;name:string;description?:string;brand?:string;unit:string;image_url?:string};
export type StoreProduct={id:string;store_id:string;product_id:string;price:string;mrp?:string;stock_quantity:number;is_available:boolean;product:Product};
export type CartItem={id:string;store_product_id:string;quantity:number;unit_price:string;store_product?:StoreProduct};
export type Cart={id?:string;store_id?:string;items:CartItem[];subtotal?:string};
export type Order={id:string;status:string;payment_status:string;total_amount:string;delivery_fee:string;created_at:string};
export type Merchant={id:string;business_name:string;gstin?:string;status:string};
