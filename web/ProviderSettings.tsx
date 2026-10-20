import {useEffect,useRef,useState} from 'react';
import type {Provider,ProviderSettings as Settings,Stage,StageSettings} from './types';
import {OpenRouterModelPicker} from './OpenRouterModelPicker';

export const DEFAULT_SETTINGS:Settings={transcription:{provider:'local',baseUrl:'',model:''},diarization:{provider:'local',baseUrl:'',model:''},minutes:{provider:'local',baseUrl:'http://127.0.0.1:11434/v1',model:''}};
export const providerLabel={local:'로컬 GPU',server:'외부 서버',openrouter:'OpenRouter',chatgpt:'ChatGPT 연결'};
const stages:[Stage,string][]=[['transcription','전사'],['diarization','화자 분리'],['minutes','회의록']];

function selectProvider(stage:Stage,provider:Provider):StageSettings{
 if(provider==='openrouter')return {provider,baseUrl:'https://openrouter.ai/api/v1',model:'',endpoint:'/audio/transcriptions',responseFormat:'verbose_json',options:''};
 if(provider==='local')return {provider,baseUrl:stage==='minutes'?'http://127.0.0.1:11434/v1':'',model:''};
 if(provider==='server')return {provider,baseUrl:'',model:'',endpoint:'/audio/transcriptions',responseFormat:'verbose_json',options:''};
 return {provider,baseUrl:'',model:''};
}

export function ProviderSettings({value,onClose,onSave,chatGPTAvailable}:{chatGPTAvailable:boolean;value:Settings;onClose:()=>void;onSave:(settings:Settings)=>void}){
 const [draft,setDraft]=useState<Settings>(()=>structuredClone(value)),[saving,setSaving]=useState(false),[testing,setTesting]=useState<Stage>(),[error,setError]=useState(''),[messages,setMessages]=useState<Partial<Record<Stage,string>>>({});
 const dialog=useRef<HTMLDialogElement>(null);
 useEffect(()=>{dialog.current?.showModal();},[]);
 const update=(stage:Stage,patch:Partial<StageSettings>)=>{setDraft(current=>({...current,[stage]:{...current[stage],...patch}}));setMessages(current=>({...current,[stage]:undefined}));};
 async function save(){setSaving(true);setError('');try{if(!window.meetingDesktop)throw Error('공급자 설정은 데스크톱 앱에서 저장할 수 있습니다.');onSave(await window.meetingDesktop.saveSettings(draft));onClose();}catch(e){setError(String(e).replace(/^Error: /,''));}finally{setSaving(false);}}
 async function test(stage:Stage){setTesting(stage);setError('');try{const result=await window.meetingDesktop!.testProvider(stage,draft[stage]);setMessages(current=>({...current,[stage]:result.message}));}catch(e){setMessages(current=>({...current,[stage]:String(e).replace(/^Error: /,'')}));}finally{setTesting(undefined);}}
 return <dialog ref={dialog} className="provider-dialog" aria-labelledby="settings-title" onCancel={event=>{if(saving)event.preventDefault();else onClose();}}>
  <div className="settings-heading"><div><h2 id="settings-title">모델·공급자 설정</h2><p>각 단계의 실행 위치와 모델을 선택하세요. 변경 사항은 다음 요청부터 적용됩니다.</p></div><button aria-label="설정 닫기" disabled={saving} onClick={onClose}>×</button></div>
  <p className="settings-notice">외부 전사·화자 분리에는 녹음이, 외부 회의록 작성에는 전사문·규칙이 전송됩니다. API 키는 이 PC에서 암호화해 저장합니다.</p>
  <div className="settings-body">
  {stages.map(([stage,label])=>{
   const config=draft[stage],localAudio=config.provider==='local'&&stage!=='minutes',remote=config.provider!=='chatgpt'&&!localAudio;
   return <fieldset key={stage} disabled={saving} className="provider-stage"><legend>{label}</legend>
    <label>{label} 공급자<select aria-label={`${label} 공급자`} value={config.provider} onChange={e=>{setDraft(current=>({...current,[stage]:selectProvider(stage,e.target.value as Provider)}));setMessages(current=>({...current,[stage]:undefined}));}}>
     <option value="local">로컬 GPU{stage==='minutes'?' · 로컬 모델 서버':''}</option><option value="server">외부 서버</option><option value="openrouter">OpenRouter</option>{stage==='minutes'&&(chatGPTAvailable||config.provider==='chatgpt')?<option value="chatgpt" disabled={!chatGPTAvailable}>{chatGPTAvailable?'ChatGPT 확장':'ChatGPT · 확장 설치 필요'}</option>:null}
    </select></label>
    {config.provider==='chatgpt'?<p className="settings-help">{chatGPTAvailable?'별도 ChatGPT 확장을 사용합니다. 확장에는 비상업 조건이 적용되며 API 키는 필요하지 않습니다.':'ChatGPT 확장을 별도로 설치하거나 다른 회의록 공급자를 선택하세요. 기존 로그인 정보는 보존됩니다.'}</p>:<>
     {remote?<label>서버 주소<input aria-label={`${label} 서버 주소`} value={config.baseUrl} placeholder={stage==='minutes'?'http://127.0.0.1:11434/v1':'https://server.example/v1'} onChange={e=>update(stage,{baseUrl:e.target.value})}/></label>:null}
     {config.provider==='openrouter'?<OpenRouterModelPicker stage={stage} label={label} value={config.model} onChange={model=>update(stage,{model})}/>:<label>{localAudio?'모델 폴더 경로 (선택)':'모델 ID'}<input aria-label={`${label} 모델`} value={config.model} placeholder={localAudio?'비워두면 기존 백엔드 환경변수 사용':stage==='minutes'?'예: 서버에서 제공하는 모델 ID':'모델 ID'} onChange={e=>update(stage,{model:e.target.value})}/></label>}
     {localAudio?<p className="settings-help">{stage==='transcription'?'MOSS·Whisper 선택은 전사문의 모델 메뉴에서 합니다.':'기존 Nemotron GPU 환경을 사용합니다.'} 모델 경로는 백엔드가 실행되는 기기 기준입니다.</p>:<label>API 키<input type="password" autoComplete="off" aria-label={`${label} API 키`} value={config.apiKey??''} placeholder={config.hasApiKey?'저장된 키 유지 · 새 키를 입력하면 교체':config.provider==='openrouter'?'OpenRouter API 키를 입력하세요':'인증이 없는 서버는 비워두세요'} onChange={e=>update(stage,{apiKey:e.target.value})}/>{config.hasApiKey?<button className="clear-key" onClick={()=>update(stage,{apiKey:'',hasApiKey:false})}>저장된 키 지우기</button>:null}</label>}
     {stage==='minutes'&&config.provider==='local'?<p className="settings-help">Ollama·vLLM 등으로 로컬 모델을 먼저 서빙하세요. 앱이 LLM을 직접 설치하거나 실행하지 않습니다.</p>:null}
     {remote&&stage!=='minutes'?<details><summary>음성 API 세부 설정</summary><label>API 경로<input aria-label={`${label} API 경로`} value={config.endpoint||'/audio/transcriptions'} onChange={e=>update(stage,{endpoint:e.target.value})}/></label>
      <label>응답 형식<select aria-label={`${label} 응답 형식`} value={config.responseFormat||'verbose_json'} onChange={e=>update(stage,{responseFormat:e.target.value})}><option value="verbose_json">verbose_json · 시간 정보</option>{config.provider!=='openrouter'?<option value="diarized_json">diarized_json · 화자 포함</option>:null}</select></label>
      {stage==='diarization'?<label>공급자 옵션 JSON<input aria-label="화자 분리 공급자 옵션" value={config.options||''} placeholder={config.provider==='openrouter'?'비우면 MAI-Transcribe 2·Scribe v2·Deepgram 옵션 자동 적용':'예: 공급자가 요구하는 화자 분리 옵션'} onChange={e=>update(stage,{options:e.target.value})}/></label>:null}
     </details>:null}
     {config.provider==='openrouter'?<p className="settings-help">{stage==='minutes'?'텍스트 입력·출력을 지원하는 모델 목록입니다.':'음성 전사 모델 목록입니다. 시간 정보(verbose_json) 지원 여부는 공급자·모델별로 확인하세요.'} 공개 목록 조회에는 API 키가 필요하지 않으며, 실제 사용 가능 여부는 키의 권한·잔액에 따라 달라집니다.</p>:null}
     {stage==='diarization'&&remote?<p className="settings-help">시간과 화자 ID를 반환하는 모델이 필요합니다. 목록은 화자 분리 지원을 보장하지 않으므로 모델의 지원 여부와 공급자 옵션을 확인하세요. 긴 녹음의 청크 간 화자 동일성은 자동 확정하지 않습니다.</p>:null}
    </>}
    <button className="test-provider" disabled={!!testing||saving||!window.meetingDesktop} onClick={()=>test(stage)}>{testing===stage?'확인 중…':`${label} 연결 확인`}</button>{messages[stage]?<p className="provider-message" role="status">{messages[stage]}</p>:null}
   </fieldset>;
  })}
  </div>
  {error?<p className="error settings-error" role="alert">{error}</p>:null}
  <div className="settings-actions"><button disabled={saving} onClick={onClose}>취소</button><button className="primary" disabled={saving||!!testing} onClick={save}>{saving?'저장 중…':'설정 저장'}</button></div>
 </dialog>;
}
