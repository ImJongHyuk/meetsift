export type CatalogModel={slug:string;displayName:string};
export type CatalogResult={models:CatalogModel[];fetchedAt:number;stale:boolean};
type Modality='transcription'|'text';
const TTL=5*60*1000;

// Public catalog: no credentials are needed or transmitted. Inference still uses
// the stage's saved key. Both audio stages share one catalog and in-flight fetch.
export class OpenRouterCatalog {
 private cache=new Map<Modality,CatalogResult>();
 private pending=new Map<Modality,Promise<CatalogResult>>();
 constructor(private request:typeof fetch=(...args)=>fetch(...args),private now=()=>Date.now()){}
 async list(stage:string,refresh=false):Promise<CatalogResult>{
  if(!['transcription','diarization','minutes'].includes(stage))throw Error('설정 단계를 확인하세요.');
  const modality:Modality=stage==='minutes'?'text':'transcription';
  const cached=this.cache.get(modality);
  const pending=this.pending.get(modality);
  if(pending)return pending;
  if(!refresh&&cached&&this.now()-cached.fetchedAt<TTL)return cached;
  const task=this.load(modality).catch(()=>{
   if(cached)return {...cached,stale:true};
   throw Error('OpenRouter 모델 목록을 불러오지 못했습니다. 네트워크를 확인한 뒤 새로고침하세요. 기존 모델 설정은 유지됩니다.');
  }).finally(()=>this.pending.delete(modality));
  this.pending.set(modality,task);
  return task;
 }
 private async load(modality:Modality):Promise<CatalogResult>{
  const response=await this.request(`https://openrouter.ai/api/v1/models?output_modalities=${modality}`,{redirect:'error',signal:AbortSignal.timeout(15000)});
  if(!response.ok)throw Error('Catalog request failed');
  const payload=await response.json() as {data?:unknown};
  if(!Array.isArray(payload.data))throw Error('Invalid model catalog');
  const models=new Map<string,CatalogModel>();
  for(const item of payload.data){
   if(!item||typeof item.id!=='string'||!item.id.trim())continue;
   const architecture=item.architecture;
   if(!Array.isArray(architecture?.output_modalities)||!architecture.output_modalities.includes(modality))continue;
   if(!Array.isArray(architecture?.input_modalities)||!architecture.input_modalities.includes(modality==='text'?'text':'audio'))continue;
   models.set(item.id,{slug:item.id,displayName:typeof item.name==='string'&&item.name.trim()?item.name:item.id});
  }
  if(!models.size)throw Error('No compatible models');
  const result={models:[...models.values()].sort((a,b)=>a.displayName.localeCompare(b.displayName)||a.slug.localeCompare(b.slug)),fetchedAt:this.now(),stale:false};
  this.cache.set(modality,result);
  return result;
 }
}
