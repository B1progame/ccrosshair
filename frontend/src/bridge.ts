export type Style = {id:string; name:string; family:string; source:string; tags:string[]; favorite:boolean; color:string; opacity:number; shape:string; dot:boolean; active:boolean; armLength:number; gap:number; thickness:number; circleRadius:number; tStyle:boolean};
export type Snapshot = {version:1; revision:number; theme:string; resolvedTheme?:'dark'|'light'; accent:string; overlay:boolean; activeId:string; selectedId:string; styles:Style[]};
type ChannelSignal<T> = { connect:(handler:(value:T)=>void)=>void };
declare global { interface Window { qt?: { webChannelTransport: unknown }; QWebChannel?: new (transport:unknown, callback:(channel:{objects:Record<string,{request:(json:string)=>void; response:ChannelSignal<string>; stateEvent:ChannelSignal<string>}>})=>void)=>void; } }
type Reply = {id:string;ok:boolean;result?:unknown;error?:{code:string;message:string}};
const allowed = new Set(['ready','selectStyle','activateStyle','toggleFavorite','setOverlay','navigate','toggleNative','openDetail','setTheme']);
export class Bridge {
  private native?: {request:(json:string)=>void;response:ChannelSignal<string>;stateEvent:ChannelSignal<string>};
  private pending = new Map<string,(r:Reply)=>void>();
  private listeners = new Set<(s:Snapshot)=>void>();
  private statusListeners = new Set<(s:'connecting'|'connected'|'failed')=>void>();
  status:'connecting'|'connected'|'failed'='connecting';
  snapshot?:Snapshot;
  constructor(){const deadline=Date.now()+5000;const attempt=()=>{if(this.native)return;if(window.qt?.webChannelTransport&&window.QWebChannel){new window.QWebChannel(window.qt.webChannelTransport,ch=>{this.native=ch.objects.control;this.native!.response.connect(raw=>{const r=JSON.parse(raw) as Reply;if(r.ok&&r.result&&typeof r.result==='object'&&'version' in r.result){this.snapshot=r.result as Snapshot;this.listeners.forEach(f=>f(this.snapshot!))}this.pending.get(r.id)?.(r);this.pending.delete(r.id)});this.native!.stateEvent.connect(raw=>{const e=JSON.parse(raw);if(e.type==='state'){this.snapshot=e.snapshot;this.listeners.forEach(f=>f(e.snapshot))}});this.setStatus('connected');void this.send('ready',{});});return}if(Date.now()>=deadline){this.setStatus('failed');return}window.setTimeout(attempt,40)};attempt();}
  private setStatus(s:'connecting'|'connected'|'failed'){this.status=s;this.statusListeners.forEach(f=>f(s))}
  async send(command:string,payload:Record<string,unknown>){if(!allowed.has(command)) throw Error('Unsupported command'); if(!this.native) throw Error('Native bridge unavailable'); const id=globalThis.crypto?.randomUUID?.()??`req-${Date.now()}-${Math.random().toString(36).slice(2)}`;return await new Promise<Reply>((resolve,reject)=>{const t=window.setTimeout(()=>{this.pending.delete(id);reject(Error('Control app did not respond'))},8000);this.pending.set(id,r=>{clearTimeout(t);resolve(r)});this.native!.request(JSON.stringify({version:1,id,command,payload}));});}
  subscribe(f:(s:Snapshot)=>void){this.listeners.add(f);if(this.snapshot)f(this.snapshot);return()=>{this.listeners.delete(f)}}
  subscribeStatus(f:(s:'connecting'|'connected'|'failed')=>void){this.statusListeners.add(f);f(this.status);return()=>{this.statusListeners.delete(f)}}
}
export const bridge = new Bridge();
