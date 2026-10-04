export type Style = {
  id: string; name: string; family: string; source: string; description: string; tags: string[];
  favorite: boolean; color: string; opacity: number;
  shape: 'classic_cross'|'dot'|'circle_cross'|'custom_grid'|'bracket'|'diamond'|'ring'|'square';
  dot: boolean; active: boolean; armLength: number; gap: number; thickness: number;
  circleRadius: number; circleThickness: number; centerDotSize: number; tStyle: boolean;
  rotationDegrees: number; outlineEnabled: boolean; outlineThickness: number;
  outlineColor: string; outlineOpacity: number; customGridSize: number; customCellSize: number;
  customFilledCells: Array<[number, number]>; canvasSize: number;
  editableSettings: Array<{key:string; label:string; kind:string; minimum:number|null; maximum:number|null; step:number|null; value:number|string|boolean|null}>;
};
export type ZoomSettings = {
  sidebarEnabled:boolean; liveEnabled:boolean; zoomEnabled:boolean; hotkeySequence:string;
  displayMode:'monitor'|'crosshair'; targetMonitorId:string; positionXPercent:number; positionYPercent:number;
  zoomPercent:number; animationEnabled:boolean; animationDurationMs:number;
};
export type CreatorModel = {
  format:'crosshair-overlay-creator-v2'; version:number; name:string; grid_size:number; creation_mode:'draw'|'pixel';
  color_hex:string; filled_cells:Array<[number,number]>; style_id:string; created_at:string; updated_at:string;
};
export type Game = {id:string; title:string; source:string; executablePath:string; iconPath:string; styleId:string; enabled:boolean};
export type SettingsSnapshot = {
  selectedSize:number; globalSize:number; theme:string; accent:string; autoUpdate:boolean; startupTray:boolean;
  fullscreenAuto:boolean; gameAutoSwitch:boolean; storagePath:string; betaVisible:boolean; sidebarCollapsed:boolean; zoom:ZoomSettings;
  monitors:Array<{id:string; name:string}>;
};
export type Snapshot = {
  version:1; revision:number; theme:string; resolvedTheme:'dark'|'light'; accent:string; appVersion:string; runtime:string;
  overlay:boolean; activeId:string; selectedId:string; page:string; styleCount:number; catalogRevision:number; styles:Style[];
  settings:SettingsSnapshot; games:Game[]; gamesStatus:string; creator:CreatorModel|null;
};
export type CommandPayloads = {
  ready: Record<string, never>; navigate:{page:string}; queryCatalog:{query:string;filter:string;page:number;pageSize:number};
  toggleNative:Record<string,never>; quit:Record<string,never>; selectStyle:{styleId:string}; activateStyle:{styleId:string};
  toggleFavorite:{styleId:string}; openDetail:{styleId:string}; updateStyle:{styleId:string;updates:Record<string,number|string|boolean>};
  saveVariant:{styleId:string}; sendToCreator:{styleId:string}; setOverlay:{enabled:boolean}; setTheme:{theme:string};
  setAccent:{color:string}; setSelectedSize:{value:number}; setGlobalSize:{value:number};
  setSidebarCollapsed:{collapsed:boolean};
  setStartup:{preference:'updates'|'tray';enabled:boolean}; setFullscreenAuto:{enabled:boolean};
  setGameAutoSwitch:{enabled:boolean}; setBetaVisible:{enabled:boolean}; importPack:Record<string,never>; exportStyle:{styleId:string};
  exportCurrent:Record<string,never>; exportSelection:{styleIds:string[]}; creatorSave:{model:CreatorModel;activate:boolean};
  creatorExport:{model:CreatorModel}; setGameProfile:{gameId:string;styleId:string;enabled:boolean};
  importGame:Record<string,never>; rescanGames:Record<string,never>; setZoom:{settings:ZoomSettings};
  chooseStorage:Record<string,never>; checkUpdates:Record<string,never>; resetSettings:Record<string,never>;
};
export type CommandName = keyof CommandPayloads;
type Reply<T=unknown> = {id:string;ok:boolean;result?:T;error?:{code:string;message:string}};
type ChannelSignal<T> = {connect:(handler:(value:T)=>void)=>void};
type Control = {request:(json:string)=>void;response:ChannelSignal<string>;stateEvent:ChannelSignal<string>};
declare global {
  interface Window {
    qt?:{webChannelTransport:unknown};
    QWebChannel?:new (transport:unknown,callback:(channel:{objects:Record<string,Control>})=>void)=>void;
  }
}

export class Bridge {
  private native?:Control;
  private pending=new Map<string,{resolve:(reply:Reply)=>void;timer:number}>();
  private listeners=new Set<(snapshot:Snapshot)=>void>();
  private statusListeners=new Set<(status:'connecting'|'connected'|'failed')=>void>();
  private connectTimer=0;
  private deadline=0;
  status:'connecting'|'connected'|'failed'='connecting';
  snapshot?:Snapshot;

  constructor(){this.connect()}

  connect(){
    if(this.native)return;
    this.setStatus('connecting');
    this.deadline=Date.now()+8000;
    const attempt=()=>{
      if(this.native)return;
      if(window.qt?.webChannelTransport&&window.QWebChannel){
        try {
          new window.QWebChannel(window.qt.webChannelTransport,channel=>{
            const control=channel.objects.control;
            if(!control){this.retryConnection();return}
            this.native=control;
            control.response.connect(raw=>this.onResponse(raw));
            control.stateEvent.connect(raw=>this.onState(raw));
            this.setStatus('connected');
            void this.send('ready',{}).catch(()=>this.retryConnection());
          });
          return;
        } catch { /* WebEngine transport can be installed slightly after the page script. */ }
      }
      if(Date.now()>=this.deadline){this.setStatus('failed');return}
      this.connectTimer=window.setTimeout(attempt,40);
    };
    attempt();
  }

  retryConnection(){
    this.native=undefined;
    window.clearTimeout(this.connectTimer);
    this.connect();
  }

  private setStatus(status:'connecting'|'connected'|'failed'){
    this.status=status;
    this.statusListeners.forEach(listener=>listener(status));
  }

  private acceptSnapshot(snapshot:Snapshot){
    if(!snapshot||snapshot.version!==1||!Number.isSafeInteger(snapshot.revision))return;
    if(this.snapshot&&snapshot.revision<this.snapshot.revision)return;
    this.snapshot=snapshot;
    this.listeners.forEach(listener=>listener(snapshot));
  }

  private onResponse(raw:string){
    let reply:Reply;
    try{reply=JSON.parse(raw) as Reply}catch{return}
    if(reply.ok&&reply.result&&typeof reply.result==='object'&&'version' in reply.result)this.acceptSnapshot(reply.result as Snapshot);
    const pending=this.pending.get(reply.id);
    if(pending){window.clearTimeout(pending.timer);this.pending.delete(reply.id);pending.resolve(reply)}
  }

  private onState(raw:string){
    try{
      const event=JSON.parse(raw) as {type?:string;snapshot?:Snapshot};
      if(event.type==='state'&&event.snapshot)this.acceptSnapshot(event.snapshot);
    }catch{/* Ignore malformed events without breaking future updates. */}
  }

  send<C extends CommandName>(command:C,payload:CommandPayloads[C]):Promise<Reply>{
    if(!this.native)return Promise.reject(Error('Native bridge unavailable'));
    const id=globalThis.crypto?.randomUUID?.()??`req-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    return new Promise((resolve,reject)=>{
      const timer=window.setTimeout(()=>{
        this.pending.delete(id);reject(Error('Control app did not respond'));
      },8000);
      this.pending.set(id,{resolve,timer});
      try{this.native!.request(JSON.stringify({version:1,id,command,payload}))}
      catch(error){window.clearTimeout(timer);this.pending.delete(id);reject(error)}
    });
  }

  subscribe(listener:(snapshot:Snapshot)=>void){
    this.listeners.add(listener);if(this.snapshot)listener(this.snapshot);
    return()=>{this.listeners.delete(listener)};
  }

  subscribeStatus(listener:(status:'connecting'|'connected'|'failed')=>void){
    this.statusListeners.add(listener);listener(this.status);
    return()=>{this.statusListeners.delete(listener)};
  }
}
export const bridge=new Bridge();
