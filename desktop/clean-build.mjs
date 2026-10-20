import {rm} from 'node:fs/promises';
import {resolve,dirname,relative} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
for(const name of ['dist','dist-desktop']){
 const target=resolve(root,name);
 if(relative(root,target)!==name)throw Error('Unexpected build output path');
 await rm(target,{recursive:true,force:true});
}
