const {contextBridge,ipcRenderer}=require('electron');
const listen=(channel,callback)=>{const handler=(_event,value)=>callback(value);ipcRenderer.on(channel,handler);return()=>ipcRenderer.removeListener(channel,handler);};
contextBridge.exposeInMainWorld('meetingDesktop',{
 chooseRecording:()=>ipcRenderer.invoke('recording:choose'),
 openRouterModels:(stage,refresh=false)=>ipcRenderer.invoke('settings:openrouter-models',stage,refresh),
 getSettings:()=>ipcRenderer.invoke('settings:get'),saveSettings:settings=>ipcRenderer.invoke('settings:save',settings),testProvider:(stage,config)=>ipcRenderer.invoke('settings:test',stage,config),
 request:(path,method,body)=>ipcRenderer.invoke('backend:request',path,method,body),
 upload:payload=>ipcRenderer.invoke('backend:upload',payload),
 session:()=>ipcRenderer.invoke('chatgpt:session'),login:()=>ipcRenderer.invoke('chatgpt:login'),logout:()=>ipcRenderer.invoke('chatgpt:logout'),cancelLogin:()=>ipcRenderer.invoke('chatgpt:cancel-login'),
 models:()=>ipcRenderer.invoke('chatgpt:models'),generate:payload=>ipcRenderer.invoke('chatgpt:generate',payload),cancel:()=>ipcRenderer.invoke('chatgpt:cancel'),
 onDelta:callback=>listen('chatgpt:delta',callback),onSession:callback=>listen('chatgpt:session-changed',callback)
});
