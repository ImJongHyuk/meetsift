import {useEffect,useState,useRef} from 'react';
import type {Job,Model,Session,StageSettings} from './types';
import {clock,download,request} from './api';
export const DEFAULT_RULES='결정사항과 할 일에 근거 시간을 남겨주세요. 할 일에는 담당자와 기한을 포함하고, 확인되지 않은 내용은 확인 필요로 표시해주세요.';
// An explicit empty edit is distinct from a new job's initially empty rules.
export function resolveRules(current:string,stored:string|undefined,edited:string|undefined){
 return edited ?? (stored && stored.length > 0 ? stored : current);
}
export function meetingTranscript(job:Job){
 const timedJob=job as Job & {timing_quality?:string};
 return JSON.stringify({
  timing_quality:timedJob.timing_quality ?? 'unknown',
  segments:job.segments.map(segment=>({
   segment_id:segment.id,
   start_seconds:segment.start,
   end_seconds:segment.end,
   time:`${clock(segment.start)}–${clock(segment.end)}`,
   speaker_id:segment.speaker_id,
   speaker:job.speakers[segment.speaker_id]||segment.speaker_name||segment.speaker_id,
   overlap:segment.overlap,
   review_flags:segment.review_flags ?? [],
   timing_quality:(segment as typeof segment & {timing_quality?:string}).timing_quality ?? timedJob.timing_quality ?? 'unknown',
   text:segment.text,
  })),
 },null,2);
}
export function Minutes({job,provider,session,edit,onError,flush,onGenerating}:{job?:Job;provider:StageSettings;session:Session;edit:(patch:Partial<Job>)=>void;onError:(message:string)=>void;flush:()=>Promise<void>;onGenerating:(value:boolean)=>void}){
 const rulesFile=useRef<HTMLInputElement>(null);
 const editedRules=useRef(new Map<string,string>());
 const [models,setModels]=useState<Model[]>([]),[model,setModel]=useState(''),[generating,setGenerating]=useState(false),[draft,setDraft]=useState(''),[rules,setRules]=useState(DEFAULT_RULES);
 useEffect(()=>{setDraft(job?.minutes||'');setRules(current=>resolveRules(current,job?.rules,job?editedRules.current.get(job.id):undefined));},[job?.id]);
 useEffect(()=>{let current=true;if((provider.provider!=='chatgpt'||session.status==='connected')&&window.meetingDesktop)window.meetingDesktop.models().then(value=>{if(current){setModels(value);setModel(value[0]?.slug||'');}}).catch(error=>onError(String(error)));else{setModels([]);setModel('');}return()=>{current=false;};},[session.status,provider]);
 function updateRules(text:string){setRules(text);if(job){editedRules.current.set(job.id,text);edit({rules:text});}}
 async function generate(){const desktop=window.meetingDesktop;if(!desktop||!job)return;setGenerating(true);onGenerating(true);setDraft('');let text='';const unsubscribe=desktop.onDelta(delta=>{text+=delta;setDraft(text);});try{edit({rules});await flush();const result=await desktop.generate({model,rules,transcript:meetingTranscript(job)});setDraft(result.text);edit({minutes:result.text,rules});}catch(error){onError(String(error));if(text)edit({minutes:text,rules});}finally{unsubscribe();setGenerating(false);onGenerating(false);}}
 async function exportTranscript(format:'json'|'markdown'){if(!job)return;try{edit({rules});await flush();const result=await request<any>(`/api/jobs/${job.id}/export?format=${format}`);download(`${job.title||'전사문'}.${format==='json'?'json':'md'}`,typeof result==='string'?result:JSON.stringify(result,null,2),format==='json'?'application/json':'text/markdown');}catch(error){onError(String(error));}}
 return <section className="minutes panel"><h2>회의록</h2><div className="rules-label"><label className="field-label" htmlFor="rules">회의록 작성 규칙</label><button disabled={generating} className="load-rules" onClick={()=>rulesFile.current?.click()}>규칙 불러오기</button><input ref={rulesFile} type="file" className="sr-only" accept=".md,.txt,text/plain,text/markdown" onChange={async e=>{const file=e.target.files?.[0];if(!file)return;try{if(file.size>80000)throw Error('규칙 파일은 80 KB 이하여야 합니다.');const text=await file.text();if(text.length>20000)throw Error('규칙은 20,000자 이하여야 합니다.');updateRules(text);}catch(error){onError(String(error));}e.target.value='';}}/></div><textarea id="rules" className="rules" value={rules} maxLength={20000} disabled={generating} onChange={e=>{updateRules(e.target.value);}}/>
 {provider.provider!=='chatgpt'||session.status==='connected'?<><label className="sr-only" htmlFor="chat-model">회의록 모델</label><select id="chat-model" value={model} disabled={generating} onChange={e=>setModel(e.target.value)}>{models.length?models.map(m=><option key={m.slug} value={m.slug}>{m.displayName}</option>):<option value="">{provider.provider==='chatgpt'?'사용 가능한 모델 불러오는 중':'모델·공급자 설정에서 회의록 모델을 선택하세요'}</option>}</select></>:null}
 <div className="minutes-actions"><button className="primary" disabled={!job?.segments?.length||(provider.provider==='chatgpt'&&session.status!=='connected')||!model||generating} onClick={generate}>{provider.provider==='chatgpt'?'ChatGPT로 회의록 작성':'회의록 작성'}</button><button disabled={!job||generating} onClick={()=>exportTranscript('markdown')}>전사문 내보내기</button></div>
 {generating?<button className="subtle" onClick={()=>window.meetingDesktop?.cancel()}>작성 중단</button>:null}
 <div className="minutes-body">{draft||generating?<><label className="sr-only" htmlFor="minutes-output">회의록 내용</label><textarea id="minutes-output" className="minutes-output" value={draft} disabled={generating} placeholder="회의록 작성 중…" onChange={e=>{setDraft(e.target.value);edit({minutes:e.target.value});}}/><div className="export-row"><button disabled={generating} onClick={()=>download(`${job?.title||'회의록'}-회의록.md`,draft,'text/markdown')}>회의록 저장</button><button disabled={generating} onClick={()=>exportTranscript('json')}>JSON 내보내기</button></div></>:<div className="minutes-empty">회의록이 여기에 표시됩니다.{!window.meetingDesktop?<small>ChatGPT 연결은 데스크톱 앱에서 사용할 수 있습니다.</small>:provider.provider==='chatgpt'&&session.status!=='connected'?<small>ChatGPT에 연결한 후 회의록을 작성하세요.</small>:null}</div>}</div>
 </section>;
}
