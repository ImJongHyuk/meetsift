import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {loadChatExtension} from '../../dist-desktop/chatgpt-extension.js';
const host={appName:'Fixture',appId:'fixture',storageDir:tmpdir(),safeStorage:{},isReady:()=>true,openBrowser:async()=>{}};

test('core works without an extension and rejects relative paths',async()=>{
 const missing=await loadChatExtension(undefined,host);
 assert.equal(missing.available,false);
 assert.equal((await missing.session()).status,'unavailable');
 await assert.rejects(missing.models(),/별도 확장/);
 assert.equal((await loadChatExtension('./relative.js',host)).available,false);
});

test('loads an explicit compatible extension and forwards streams and events',async()=>{
 const directory=await mkdtemp(join(tmpdir(),'meetsift-extension-'));
 try{
  const path=join(directory,'fixture.mjs');
  await writeFile(path,`export function createMeetSiftChatGPT(host){
   const state={status:'connected',sharing:true,available:true};
   return {apiVersion:1,available:true,session:async()=>state,login:async()=>state,logout:async()=>state,cancelLogin(){},
    models:async()=>[{slug:host.appId,displayName:host.appName}],
    generate:async request=>{if(request.signal.aborted)throw Error('cancelled');request.onDelta('fixture');return {text:'fixture'};},
    onSession:listener=>{listener(state);return()=>{};}};
  }`);
  const extension=await loadChatExtension(path,host);
  assert.equal(extension.available,true);
  assert.equal((await extension.models())[0].slug,'fixture');
  let event;extension.onSession(value=>event=value);assert.equal(event.status,'connected');
  const controller=new AbortController();let delta='';
  assert.deepEqual(await extension.generate({model:'fixture',input:'',instructions:'',signal:controller.signal,onDelta:value=>delta+=value}),{text:'fixture'});
  assert.equal(delta,'fixture');controller.abort();
  await assert.rejects(extension.generate({signal:controller.signal}),/cancelled/);
 }finally{await rm(directory,{recursive:true,force:true});}
});

test('invalid versions and failures produce a safe unavailable state',async()=>{
 const directory=await mkdtemp(join(tmpdir(),'meetsift-extension-'));
 try{
  for(const [name,source] of [['old','export function createMeetSiftChatGPT(){return {apiVersion:0}}'],['failure',"throw Error('secret upstream content')"]]){
   const path=join(directory,name+'.mjs');await writeFile(path,source);
   const state=await(await loadChatExtension(path,host)).session();
   assert.equal(state.available,false);assert.ok(!state.error.message.includes('secret'));
  }
 }finally{await rm(directory,{recursive:true,force:true});}
});
