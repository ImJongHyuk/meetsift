import {createChatGPT} from '@siwc/local';
import {createElectronCredentialEncryption} from './credential-encryption.js';
import type {SafeStorage} from 'electron';

type Host={appName:string;appId:string;storageDir:string;safeStorage:SafeStorage;isReady:()=>boolean;openBrowser:(url:string)=>Promise<void>};
export function createMeetSiftChatGPT(host:Host){
 const client=createChatGPT({appName:host.appName,appId:host.appId,redirectPort:0,storageDir:host.storageDir,
  credentialEncryption:createElectronCredentialEncryption(host.safeStorage,host.isReady),openBrowser:host.openBrowser});
 const session=async()=>({...await client.getSession(),available:true});
 return {
  apiVersion:1 as const,available:true,session,
  login:async()=>({...await client.signIn(),available:true}),
  logout:async()=>{await client.disconnect();return session();},
  cancelLogin:()=>client.cancelSignIn(),
  models:()=>client.listModels(),
  generate:(request:{model:string;input:string;instructions:string;signal:AbortSignal;onDelta:(text:string)=>void})=>client.streamResponse(request),
  onSession:(listener:(value:Awaited<ReturnType<typeof session>>)=>void)=>client.subscribe(value=>listener({...value,available:true})),
 };
}
