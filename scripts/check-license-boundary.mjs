import {readFileSync,existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const read=path=>readFileSync(resolve(root,path),'utf8').replaceAll('\r\n','\n');
const pkg=JSON.parse(read('package.json')),lock=JSON.parse(read('package-lock.json'));
if(pkg.license!=='SEE LICENSE IN LICENSES.md'||lock.packages[''].license!==pkg.license)throw Error('Combined package must declare its mixed license scope');
if(!read('LICENSES/MIT.txt').startsWith('MIT License'))throw Error('Own code MIT license missing');
if(!read('LICENSE').includes('not MIT-only')||!read('LICENSES.md').includes('noncommercial'))throw Error('Combined scope notice missing');
const sdk='extensions/chatgpt/vendor/siwc-local';
if(pkg.dependencies['@siwc/local']!=='file:'+sdk)throw Error('Unexpected SDK source');
const expected=JSON.parse(read('scripts/siwc-integrity.json'));
for(const [path,hash]of Object.entries(expected)){
 if(createHash('sha256').update(read(path)).digest('hex')!==hash)throw Error('Vendored source or notice changed: '+path);
}
if(!read('extensions/chatgpt/src/credential-encryption.ts').includes('LicenseRef-OpenAI-SIWC-Noncommercial-1.0'))throw Error('Copied adapter license notice missing');
for(const path of ['LICENSE','PROVENANCE.md','THIRD_PARTY_NOTICES.md']){
 if(!existsSync(resolve(root,sdk,path)))throw Error('Missing upstream notice');
}
console.log('License scope checked: own code MIT; bundled SDK and copied adapter noncommercial; upstream source/notices preserved.');
