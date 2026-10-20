import {useEffect,useId,useState} from 'react';
import type {CatalogResult,Stage} from './types';

export function OpenRouterModelPicker({stage,label,value,onChange}:{stage:Stage;label:string;value:string;onChange:(model:string)=>void}){
 const [catalog,setCatalog]=useState<CatalogResult>(),[query,setQuery]=useState(''),[reload,setReload]=useState(0),[loading,setLoading]=useState(true),[error,setError]=useState('');
 const statusId=useId();
 useEffect(()=>{
  let active=true;
  setLoading(true);setError('');
  const desktop=window.meetingDesktop;
  if(!desktop){setLoading(false);setError('모델 목록은 데스크톱 앱에서 불러올 수 있습니다.');return;}
  desktop.openRouterModels(stage,reload>0).then(result=>{
   if(!active)return;
   setCatalog(result);
   if(result.stale)setError('목록 갱신에 실패해 이전 목록을 표시합니다. 네트워크를 확인하고 다시 새로고침하세요.');
  }).catch(()=>{if(active)setError('모델 목록을 불러오지 못했습니다. 네트워크를 확인하고 새로고침하세요. 기존 모델 설정은 유지됩니다.');}).finally(()=>{if(active)setLoading(false);});
  return()=>{active=false;};
 },[stage,reload]);
 const models=catalog?.models??[],needle=query.trim().toLocaleLowerCase();
 const filtered=models.filter(model=>`${model.displayName} ${model.slug}`.toLocaleLowerCase().includes(needle));
 const selected=models.find(model=>model.slug===value);
 const hiddenSelection=value&&!filtered.some(model=>model.slug===value);
 return <div className="model-catalog" aria-busy={loading}>
  <div className="catalog-tools"><label>모델 검색<input type="search" aria-label={`${label} 모델 검색`} value={query} placeholder="모델 이름 또는 ID 검색" onChange={event=>setQuery(event.target.value)}/></label><button type="button" aria-label={`${label} 모델 목록 새로고침`} disabled={loading} onClick={()=>setReload(current=>current+1)}>새로고침</button></div>
  <label>모델 선택<select aria-label={`${label} 모델`} aria-describedby={statusId} value={value} onChange={event=>onChange(event.target.value)}>
   <option value="" disabled>{loading?'모델 목록 불러오는 중…':'사용할 모델을 선택하세요'}</option>
   {hiddenSelection?<option value={value}>{selected?`${selected.displayName} · ${value} (현재 선택)`:`${value} (현재 설정 · 목록에서 확인되지 않음)`}</option>:null}
   {filtered.map(model=><option key={model.slug} value={model.slug}>{model.displayName} · {model.slug}</option>)}
  </select></label>
  <p id={statusId} className="settings-help" role="status">{loading?'OpenRouter에서 모델 목록을 불러오는 중…':catalog?`${filtered.length}개 검색됨 / ${models.length}개 모델 · 조회 ${new Date(catalog.fetchedAt).toLocaleTimeString('ko-KR')} · 5분 캐시`:''}{!loading&&catalog&&!filtered.length?' · 검색 결과가 없습니다.':''}</p>
  {error?<p className="error catalog-error" role="alert">{error}</p>:null}
 </div>;
}
