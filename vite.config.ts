import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({root:'web', base:'./', plugins:[react(),{name:'dev-csp',transformIndexHtml(html,ctx){return ctx.server?html.replace("script-src 'self';","script-src 'self' 'unsafe-inline';").replace('ws://127.0.0.1:5173','ws://127.0.0.1:*'):html;}}], build:{outDir:'../dist',emptyOutDir:true}, server:{strictPort:true, proxy:{'^/api/':{target:'http://127.0.0.1:8765',headers:process.env.MEETING_API_TOKEN?{Authorization:`Bearer ${process.env.MEETING_API_TOKEN}`}:{}}}}});
