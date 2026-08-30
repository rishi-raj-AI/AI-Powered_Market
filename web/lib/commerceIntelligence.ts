import {api} from './api';

export type PreparationEstimate={
  store_id:string;
  estimated_preparation_minutes:number;
  confidence:'low'|'medium'|'high';
  sample_count:number;
  basis:'historical_store_median'|'limited_store_history'|'platform_fallback'|string;
};

export type FulfillmentMode='delivery_now'|'pickup_now'|'scheduled_delivery'|'scheduled_pickup'|'unavailable';
export type FulfillmentRecommendation={
  store_id:string;
  recommended_mode:FulfillmentMode;
  delivery_serviceable:boolean;
  store_open:boolean;
  timezone?:string;
  reasons:string[];
};

export async function preparationEstimate(storeId:string){
  return api<PreparationEstimate>(`/stores/${storeId}/preparation-estimate`);
}

export async function fulfillmentRecommendation(storeId:string,latitude:number,longitude:number){
  const query=new URLSearchParams({latitude:String(latitude),longitude:String(longitude)});
  return api<FulfillmentRecommendation>(`/stores/${storeId}/fulfillment-recommendation?${query}`);
}

export function preparationCopy(estimate:PreparationEstimate){
  const minutes=estimate.estimated_preparation_minutes;
  if(estimate.basis==='platform_fallback')return `Usually ready in about ${minutes} min`;
  if(estimate.confidence==='low')return `Estimated around ${minutes} min`;
  return `Typically ready in about ${minutes} min`;
}

export function preparationDetail(estimate:PreparationEstimate){
  if(estimate.sample_count<=0)return 'Early estimate while this store builds order history.';
  return `Based on ${estimate.sample_count} recent fulfilled orders • ${estimate.confidence} confidence`;
}

export function fulfillmentLabel(mode:FulfillmentMode){
  return ({
    delivery_now:'Delivery now',
    pickup_now:'Pickup now',
    scheduled_delivery:'Schedule delivery',
    scheduled_pickup:'Schedule pickup',
    unavailable:'Unavailable right now',
  } as const)[mode];
}

export function fulfillmentDetail(result:FulfillmentRecommendation){
  if(result.recommended_mode==='delivery_now')return 'Recommended: the store is open and this delivery location is serviceable.';
  if(result.recommended_mode==='pickup_now')return 'Recommended: pickup is available now; delivery is not serviceable to this location.';
  if(result.recommended_mode==='scheduled_delivery')return 'Delivery is serviceable, but the store is currently closed. Schedule for an open window.';
  if(result.recommended_mode==='scheduled_pickup')return 'Pickup is supported after the store reopens.';
  return 'This store cannot fulfil this location/mode right now.';
}
