import {isAbsolute} from 'node:path';
import {pathToFileURL} from 'node:url';
import type {SafeStorage} from 'electron';

export type ExtensionSession={status:string;sharing:boolean;available:boolean;identity?:{name?:string;email?:string};error?:{message:string}};
export type ExtensionHost={appName:string;appId:string;storageDir:string;safeStorage:SafeStorage;isReady:()=>boolean;openBrowser:(url:string)=>Promise<void>};
export type ExtensionRequest={model:string;input:string;instructions:string;signal:AbortSignal;onDelta:(text:string)=>void};
export type ChatExtension={
 apiVersion:1;
 available:boolean;
 session:()=>Promise<ExtensionSession>;
 login:()=>Promise<ExtensionSession>;
 logout:()=>Promise<ExtensionSession>;
 cancelLogin:()=>void;
 models:()=>Promise<{slug:string;displayName:string}[]>;
 generate:(request:ExtensionRequest)=>Promise<{text:string}>;
 onSession:(listener:(session:ExtensionSession)=>void)=>()=>void;
};
const unavailableMessage='ChatGPT 연동을 사용할 수 없습니다. 설치 상태를 확인하거나 다른 회의록 공급자를 선택하세요.';
function unavailable(message=unavailableMessage):ChatExtension{
 const reject=async():Promise<never>=>{throw Error(message);};
 return {apiVersion:1,available:false,session:async()=>({status:'unavailable',sharing:false,available:false,error:{message}}),login:reject,logout:reject,cancelLogin:()=>{},models:reject,generate:reject,onSession:()=>()=>{}};
}
// The bundled adapter has its own license scope. An explicit path may load
// trusted local integration code; the MIT grant does not relicense the SDK.
export async function loadChatExtension(path:string|undefined,host:ExtensionHost):Promise<ChatExtension>{
 if(!path)return unavailable();
 if(!isAbsolute(path))return unavailable('ChatGPT 확장 파일은 절대 경로로 지정하세요.');
 try{
  const module=await import(pathToFileURL(path).href);
  if(typeof module.createMeetSiftChatGPT!=='function')throw Error('Invalid extension');
  const extension=await module.createMeetSiftChatGPT(host);
  if(extension?.apiVersion!==1||extension.available!==true||!['session','login','logout','cancelLogin','models','generate','onSession'].every(key=>typeof extension[key]==='function'))throw Error('Unsupported extension');
  return extension;
 }catch{return unavailable('ChatGPT 확장을 불러오지 못했습니다. 설치·빌드 상태와 확장 API 버전을 확인하세요.');}
}
