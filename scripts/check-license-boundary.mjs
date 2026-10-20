import {execFileSync} from 'node:child_process';
import {existsSync,readFileSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const pkg=JSON.parse(readFileSync(resolve(root,'package.json'),'utf8'));
const lock=JSON.parse(readFileSync(resolve(root,'package-lock.json'),'utf8'));
if(pkg.license!=='MIT'||lock.packages[''].license!=='MIT')throw Error('The core package must declare MIT');
if(Object.keys(lock.packages).some(path=>path.includes('@siwc/')||path.startsWith('vendor/')))throw Error('SDK dependency remains in the core lockfile');
const files=execFileSync('git',['ls-files','--cached','--others','--exclude-standard','-z'],{cwd:root}).toString().split('\0').filter(Boolean);
const blocked=[];
for(const file of files){
 if(!existsSync(resolve(root,file)))continue;
 if(/^vendor\//.test(file)||file==='desktop/credential-encryption.ts')blocked.push(file);
 if(/\.(?:ts|tsx|js|cjs|mjs)$/.test(file)&&readFileSync(resolve(root,file),'utf8').includes(['electron','safe','storage','v1'].join('-')))blocked.push(file);
}
if(blocked.length)throw Error('SDK or copied adapter remains: '+blocked.join(', '));
if(!readFileSync(resolve(root,'LICENSE'),'utf8').startsWith('MIT License'))throw Error('Missing core MIT license');
console.log('MIT core boundary checked: no vendored SDK, copied adapter or SDK dependency.');
