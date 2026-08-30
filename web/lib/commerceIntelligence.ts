import {api} from './api';

export type PreparationEstimate={
  store_id:string;
  estimated_preparation_minutes:number;
  confidence:'low'|'medium'|'high';
  sample_count:number;
  basis:'historical_store_median'|'limited_store_history'|'platform_fallback'|string;
};

export async function preparationEstimate(storeId:string){
  return api<PreparationEstimate>(`/stores/${storeId}/preparation-estimate`);
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
