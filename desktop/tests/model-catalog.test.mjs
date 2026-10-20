import {test} from 'node:test';
import assert from 'node:assert/strict';
import {OpenRouterCatalog} from '../../dist-desktop/model-catalog.js';

const audio=(id,name=id)=>({id,name,architecture:{input_modalities:['audio'],output_modalities:['transcription']}});
const text=(id)=>({id,name:id,architecture:{input_modalities:['text','image'],output_modalities:['text']}});
const response=(data)=>new Response(JSON.stringify({data}));

test('discovers new IDs, names and compatible modalities without a model whitelist',async()=>{
 const requests=[];
 const catalog=new OpenRouterCatalog(async(url,options)=>{
  requests.push([url,options]);
  return response([audio('new/audio','New Audio'),audio('new/audio','New Audio'),text('new/chat'),null,{id:'invalid'},audio('')]);
 });
 assert.deepEqual((await catalog.list('transcription')).models,[{slug:'new/audio',displayName:'New Audio'}]);
 assert.deepEqual((await catalog.list('minutes')).models,[{slug:'new/chat',displayName:'new/chat'}]);
 assert.match(requests[0][0],/output_modalities=transcription$/);
 assert.match(requests[1][0],/output_modalities=text$/);
 assert.equal(requests[0][1].headers,undefined,'public catalog never sends credentials');
 assert.equal(requests[0][1].redirect,'error');
 await assert.rejects(catalog.list('unknown'),/설정 단계/);
});

test('shares audio requests and cache; refresh, TTL and recovery replace cached results',async()=>{
 let calls=0,now=1000,fail=false;
 const catalog=new OpenRouterCatalog(async()=>{
  calls++;
  if(fail)throw Error('private upstream error');
  return response([audio(`model/${calls}`)]);
 },()=>now);
 const [first,second]=await Promise.all([catalog.list('transcription'),catalog.list('diarization')]);
 assert.equal(calls,1);assert.deepEqual(first,second);
 assert.deepEqual(await catalog.list('transcription'),first);assert.equal(calls,1);
 assert.equal((await catalog.list('diarization',true)).models[0].slug,'model/2');
 now+=300001;
 assert.equal((await catalog.list('transcription')).models[0].slug,'model/3');
 fail=true;
 const stale=await catalog.list('diarization',true);
 assert.equal(stale.stale,true);assert.equal(stale.models[0].slug,'model/3');assert.equal(stale.fetchedAt,now);
 fail=false;
 assert.equal((await catalog.list('transcription',true)).stale,false);
});

test('rejects bad/empty catalogs and network failures without exposing upstream content',async()=>{
 for(const request of [async()=>{throw Error('secret');},async()=>new Response('secret',{status:401}),async()=>new Response('invalid'),async()=>response([]),async()=>response([text('wrong-modality')]),async()=>new Response('{}')]){
  const catalog=new OpenRouterCatalog(request);
  await assert.rejects(catalog.list('transcription'),error=>!error.message.includes('secret')&&error.message.includes('기존 모델 설정은 유지'));
 }
});
