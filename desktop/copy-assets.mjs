import {copyFile} from 'node:fs/promises';
await copyFile(new URL('./preload.cjs',import.meta.url), new URL('../dist-desktop/preload.cjs',import.meta.url));
await copyFile(new URL('../docs/assets/meetsift-icon.png',import.meta.url), new URL('../dist-desktop/icon.png',import.meta.url));
