import {execFileSync} from 'node:child_process';
import {readFileSync,existsSync} from 'node:fs';
import {resolve,relative,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const files=[...new Set(execFileSync('git',['ls-files','--cached','--others','--exclude-standard','-z'],{cwd:root}).toString().split('\0').filter(Boolean))];
const forbiddenPath=/(^|\/)(?:plans?|reports?|work|outputs?|\.codex|\.claude|\.idea|\.vscode|node_modules|release|models|recordings|meetings|user-data|\.local-data|\.venv[^/]*|__pycache__)(\/|$)|(^|\/)(?:CLAUDE\.md|api-token|provider-settings\.json|credentials\.json|auth\.json|\.env(?:\..*)?|evaluation\.md|validation\.md)$|\.(?:log|wav|m4a|mp3|aac|flac|ogg|opus|mp4|webm|pem|key|p12|pfx|sqlite|db)$/i;
const rules=[
 ['personal absolute path',/(?:\/home\/|\/Users\/|\/mnt\/[a-z]\/Users\/|\b[a-z]:[\\/]Users[\\/])[^\s"'<>]+/i],
 ['private network address',/https?:\/\/(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?=[:/\s"']|$)/i],
 ['credential',/\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-(?:or-v1-)?[A-Za-z0-9_-]{30,}|AKIA[A-Z0-9]{16})\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/],
];
const findings=[];
function inspect(file,buffer,revision){
 const location=revision?{revision,file}:{file};
 if(forbiddenPath.test(file))findings.push({...location,issue:'local state or work record'});
 if(buffer.includes(0)){findings.push({...location,issue:'binary file requires explicit review'});return;}
 const lines=buffer.toString('utf8').split(/\r?\n/);
 for(let i=0;i<lines.length;i++)for(const [issue,pattern] of rules)if(pattern.test(lines[i]))findings.push({...location,line:i+1,issue});
}
for(const file of files){
 const path=resolve(root,file);
 if(!existsSync(path))continue;
 if(relative(root,path).startsWith('..'))throw Error('File outside repository');
 inspect(file,readFileSync(path));
}
if(process.argv.includes('--history')){
 const revisions=execFileSync('git',['rev-list','--all'],{cwd:root}).toString().trim().split(/\r?\n/).filter(Boolean);
 const seen=new Set();
 for(const revision of revisions){
  const entries=execFileSync('git',['ls-tree','-r','-z',revision],{cwd:root}).toString().split('\0').filter(Boolean);
  for(const entry of entries){
   const [,type,hash,file]=entry.match(/^\d+ (\w+) ([a-f0-9]+)\t(.+)$/s)??[];
   if(type!=='blob'||seen.has(`${file}:${hash}`))continue;
   seen.add(`${file}:${hash}`);
   inspect(file,execFileSync('git',['cat-file','blob',hash],{cwd:root}),revision.slice(0,12));
  }
 }
}
// Print locations and rule names only, never matching credentials or private data.
if(findings.length){console.error(JSON.stringify({findings},null,2));process.exitCode=1;}
else console.log(`Public source surface checked: ${files.filter(file=>existsSync(resolve(root,file))).length} files; no flagged paths, work records or credential patterns.`);
