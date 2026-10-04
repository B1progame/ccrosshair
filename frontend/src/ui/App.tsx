import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import gsap from 'gsap';
import {
  Activity, ArrowLeft, ArrowRight, Check, Crosshair, Download, FilePlus2, Gamepad2, Heart,
  Home, Info, LayoutGrid, Moon, Monitor, PanelLeftClose, PanelLeftOpen, RotateCcw, Save, Search, Settings2, Sun, Undo2,
  Redo2, Zap, ZoomIn, Star, Pencil,
} from 'lucide-react';
import { bridge, type CreatorModel, type Game, type Snapshot, type Style, type ZoomSettings } from '../bridge';
import { CrosshairPreview } from './CrosshairPreview';

const emptyZoom:ZoomSettings={sidebarEnabled:false,liveEnabled:false,zoomEnabled:false,hotkeySequence:'CTRL+ALT+Z',displayMode:'monitor',targetMonitorId:'same_as_game',positionXPercent:50,positionYPercent:50,zoomPercent:200,animationEnabled:false,animationDurationMs:180};
const demo:Snapshot={version:1,revision:0,theme:'dark',resolvedTheme:'dark',accent:'#67D4AE',appVersion:'',runtime:'native',overlay:false,activeId:'',selectedId:'',page:'library',styleCount:0,catalogRevision:0,styles:[],settings:{selectedSize:100,globalSize:100,theme:'system',accent:'#67D4AE',autoUpdate:false,startupTray:false,fullscreenAuto:false,gameAutoSwitch:true,storagePath:'',betaVisible:false,sidebarCollapsed:false,zoom:emptyZoom,monitors:[]},games:[],gamesStatus:'',creator:null};
type Page='Home'|'Library'|'My Crosshairs'|'Detail'|'Creator'|'Games'|'Zoom'|'Export'|'Settings'|'About';
const nav:[Page,typeof Home][]=[['Home',Home],['Library',LayoutGrid],['My Crosshairs',Star],['Creator',Pencil],['Games',Gamepad2],['Zoom',ZoomIn],['Export',Download],['Settings',Settings2],['About',Info]];
const pageFilter=(page:Page,filter:string)=>page==='My Crosshairs'&&filter==='all'?'my':filter;

function contrastText(hex:string){const value=hex.replace('#','');if(!/^[\da-f]{6}$/i.test(value))return '#10201a';const channels=[0,2,4].map(i=>parseInt(value.slice(i,i+2),16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return .2126*channels[0]+.7152*channels[1]+.0722*channels[2]>.42?'#111615':'#fff'}
function SettingRow({title,help,children}:{title:string;help?:string;children:React.ReactNode}){return <label className="setting-row"><span><b>{title}</b>{help&&<small>{help}</small>}</span>{children}</label>}
function Toggle({checked,onChange,label}:{checked:boolean;onChange:(value:boolean)=>void;label:string}){return <button className={'switch '+(checked?'checked':'')} role="switch" aria-checked={checked} aria-label={label} onClick={()=>onChange(!checked)}><i/></button>}
function PersistRange({value,min,max,step=1,onCommit,label}:{value:number;min:number;max:number;step?:number;onCommit:(value:number)=>void;label:string}){
  const [draft,setDraft]=useState(value);const dirty=useRef(false);
  useEffect(()=>{if(!dirty.current)setDraft(value)},[value]);
  const commit=()=>{if(dirty.current){dirty.current=false;onCommit(draft)}};
  return <span className="range-field"><input type="range" aria-label={label} min={min} max={max} step={step} value={draft} onChange={event=>{dirty.current=true;setDraft(Number(event.target.value))}} onPointerUp={commit} onKeyUp={commit} onBlur={commit}/><output>{draft}</output></span>;
}

export function App(){
  const [state,setState]=useState<Snapshot>(bridge.snapshot??demo);
  const [page,setPage]=useState<Page>('Library');
  const [filter,setFilter]=useState('all');
  const [query,setQuery]=useState('');
  const [catalogItems,setCatalogItems]=useState<Style[]>(bridge.snapshot?.styles??[]);
  const [catalogTotal,setCatalogTotal]=useState(bridge.snapshot?.styleCount??0);
  const [catalogPage,setCatalogPage]=useState(0);
  const [selectedId,setSelectedId]=useState(bridge.snapshot?.selectedId??'');
  const [detailId,setDetailId]=useState('');
  const [bridgeStatus,setBridgeStatus]=useState(bridge.status);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [exportIds,setExportIds]=useState<string[]>([]);
  const searchRef=useRef<HTMLInputElement>(null);
  const mainRef=useRef<HTMLElement>(null);

  useEffect(()=>bridge.subscribe(next=>{
    setState(next);
    setCatalogItems(current=>current.map(item=>next.styles.find(updated=>updated.id===item.id)??item));
    setSelectedId(current=>next.selectedId&&next.selectedId!==current?next.selectedId:current);
    if(next.creator) setCreatorModel(next.creator);
  }),[]);
  useEffect(()=>bridge.subscribeStatus(setBridgeStatus),[]);
  useEffect(()=>{
    const onKey=(event:KeyboardEvent)=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();searchRef.current?.focus()}}
    window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);
  },[]);
  useEffect(()=>{
    if(bridgeStatus!=='connected'||(page!=='Library'&&page!=='My Crosshairs'&&page!=='Export'))return;
    let cancelled=false;
    const timer=window.setTimeout(async()=>{
      try{
        const reply=await bridge.send('queryCatalog',{query,filter:pageFilter(page,filter),page:catalogPage,pageSize:36});
        if(!reply.ok)throw Error(reply.error?.message??'Could not search the crosshair library');
        const result=reply.result as {styles:Style[];total:number};
        if(!cancelled){setCatalogItems(result.styles);setCatalogTotal(result.total)}
      }catch(cause){if(!cancelled)setError(String(cause))}
    },100);
    return()=>{cancelled=true;window.clearTimeout(timer)};
  },[bridgeStatus,page,query,filter,catalogPage,state.catalogRevision]);
  useEffect(()=>{
    if(window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
    const scope=gsap.context(()=>gsap.fromTo('.page-head',{y:4,opacity:.72},{y:0,opacity:1,duration:.16,ease:'power2.out'}),mainRef);
    return()=>scope.revert();
  },[page]);

  const [creatorModel,setCreatorModel]=useState<CreatorModel>(()=>bridge.snapshot?.creator??{
    format:'crosshair-overlay-creator-v2',version:2,name:'New Crosshair',grid_size:32,creation_mode:'draw',color_hex:'#67D4AE',filled_cells:[],style_id:'',created_at:'',updated_at:'',
  });
  const [history,setHistory]=useState<Array<Array<[number,number]>>>([]);
  const [future,setFuture]=useState<Array<Array<[number,number]>>>([]);
  const [painting,setPainting]=useState(false);

  const command=useCallback(async<C extends keyof import('../bridge').CommandPayloads>(name:C,payload:import('../bridge').CommandPayloads[C])=>{
    try{
      setBusy(true);const result=await bridge.send(name,payload);
      if(!result.ok)throw Error(result.error?.message??'The action failed');
      setError('');return result.result;
    }catch(cause){setError(cause instanceof Error?cause.message:String(cause));return undefined}
    finally{setBusy(false)}
  },[]);

  const go=(target:Page)=>{
    setPage(target);setCatalogPage(0);setError('');
    const route:Record<Page,string>={Home:'home',Library:'library','My Crosshairs':'my_crosshairs',Detail:'detail',Creator:'creator',Games:'games',Zoom:'zoom',Export:'export',Settings:'settings',About:'about'};
    void command('navigate',{page:route[target]});
  };
  const active=state.styles.find(style=>style.id===state.activeId)??catalogItems.find(style=>style.id===state.activeId);
  const selected=state.styles.find(style=>style.id===selectedId)??catalogItems.find(style=>style.id===selectedId);
  const detail=state.styles.find(style=>style.id===detailId)??catalogItems.find(style=>style.id===detailId)??selected;
  const visibleItems=useMemo(()=>catalogItems,[catalogItems]);
  const setZoom=(key:keyof ZoomSettings,value:ZoomSettings[keyof ZoomSettings])=>void command('setZoom',{settings:{...state.settings.zoom,[key]:value}});
  const exportToggle=(id:string)=>setExportIds(ids=>ids.includes(id)?ids.filter(item=>item!==id):[...ids,id]);
  const paintCell=(x:number,y:number,erase=false)=>{
    const key=`${x}:${y}`;const prior=creatorModel.filled_cells;const exists=prior.some(cell=>`${cell[0]}:${cell[1]}`===key);
    if((erase&&exists)||(!erase&&!exists)){
      setHistory(entries=>[...entries.slice(-79),prior]);setFuture([]);
      const filled=erase?prior.filter(cell=>`${cell[0]}:${cell[1]}`!==key):[...prior,[x,y] as [number,number]];
      setCreatorModel(model=>({...model,filled_cells:filled}));
    }
  };
  const creatorUndo=()=>{if(!history.length)return;setFuture(items=>[...items,creatorModel.filled_cells]);setCreatorModel(model=>({...model,filled_cells:history.at(-1)!}));setHistory(items=>items.slice(0,-1))};
  const creatorRedo=()=>{if(!future.length)return;setHistory(items=>[...items,creatorModel.filled_cells]);setCreatorModel(model=>({...model,filled_cells:future.at(-1)!}));setFuture(items=>items.slice(0,-1))};
  const freshCreator=()=>{setHistory(items=>[...items.slice(-79),creatorModel.filled_cells]);setCreatorModel(model=>({...model,filled_cells:[],name:'New Crosshair'}))};
  const appTheme=state.resolvedTheme==='light'?'light':'dark';

  const renderLibrary=()=> <section className="library-layout"><div className="catalog">
    <div className="toolbar"><label className="search"><Search size={16}/><input ref={searchRef} value={query} onChange={event=>{setQuery(event.target.value);setCatalogPage(0)}} placeholder="Search crosshairs" aria-label="Search crosshairs"/><kbd>Ctrl K</kbd></label>
      <select className="filter" aria-label="Filter crosshairs" value={filter} onChange={event=>{setFilter(event.target.value);setCatalogPage(0)}}><option value="all">{page==='My Crosshairs'?'My styles':'All styles'}</option><option value="favorites">Favorites</option><option value="creator">Creator</option><option value="imports">Imports</option><option value="custom">Custom</option></select>
      <button className="icon-button" aria-label="Show favorites" onClick={()=>{setFilter('favorites');go('My Crosshairs')}}><Heart size={16}/></button>
    </div>
    <div className="result-line"><span>{catalogTotal} crosshairs</span><span>{page==='My Crosshairs'?'Your collection':'Library'}</span></div>
    <div className="grid">{visibleItems.map(style=><article key={style.id} className={'card '+(selectedId===style.id?'selected':'')}>
      <div className="card-top"><span className="tag">{style.source.replaceAll('_',' ')}</span><button className={'favorite '+(style.favorite?'saved':'')} aria-label={style.favorite?'Remove favorite':'Add favorite'} aria-pressed={style.favorite} onClick={()=>void command('toggleFavorite',{styleId:style.id})}><Heart size={15} fill={style.favorite?'currentColor':'none'}/></button>
        {page==='Export'&&<input type="checkbox" aria-label={`Select ${style.name} for export`} checked={exportIds.includes(style.id)} onChange={()=>exportToggle(style.id)}/>}</div>
      <button className="card-select" onClick={()=>{setSelectedId(style.id);void command('selectStyle',{styleId:style.id})}} onDoubleClick={()=>{setDetailId(style.id);go('Detail')}} aria-pressed={selectedId===style.id} aria-label={`${style.name}, ${style.family}${style.active?', active':''}`} title={style.name}>
        <CrosshairPreview item={style}/><span className="card-meta"><span><b>{style.name}</b><small>{style.family}</small></span>{style.active&&<span className="live">ACTIVE</span>}</span>
      </button>
    </article>)}</div>
    {!visibleItems.length&&<div className="empty"><Crosshair size={24}/><b>No matching crosshairs</b><span>Try another name or tag.</span></div>}
    <div className="catalog-pager"><button className="secondary" disabled={!catalogPage} onClick={()=>setCatalogPage(p=>p-1)}><ArrowLeft size={14}/> Previous</button><span>{catalogTotal?catalogPage+1:0} / {Math.max(1,Math.ceil(catalogTotal/36))}</span><button className="secondary" disabled={(catalogPage+1)*36>=catalogTotal} onClick={()=>setCatalogPage(p=>p+1)}>Next <ArrowRight size={14}/></button></div>
  </div>
  <aside className="inspector"><div className="inspect-title"><div><span className="eyebrow">PREVIEW</span><h2>{selected?.name??'Select a crosshair'}</h2></div><button className="icon-button" aria-label={selected?.favorite?'Remove favorite':'Add favorite'} disabled={!selected} onClick={()=>selected&&void command('toggleFavorite',{styleId:selected.id})}><Heart size={16} fill={selected?.favorite?'currentColor':'none'}/></button></div>
    <div className="large-preview">{selected?<CrosshairPreview item={selected}/>:<Crosshair size={36} strokeWidth={1.2}/>}<span>Preview only</span></div>
    <p className="inspector-description">{selected?.description??'Choose a style to inspect its details and preview.'}</p>
    <div className="inspect-details"><div><small>FAMILY</small><b>{selected?.family??'—'}</b></div><div><small>SOURCE</small><b>{selected?.source??'—'}</b></div></div>
    <div className="inspect-actions"><button className="primary wide" disabled={!selected||busy} onClick={()=>selected&&void command('activateStyle',{styleId:selected.id})}><Check size={16}/> Use this crosshair</button><button className="secondary wide" disabled={!selected} onClick={()=>{if(selected){setDetailId(selected.id);go('Detail')}}}>Edit details</button>
    {page==='Export'&&<button className="secondary wide" disabled={!exportIds.length} onClick={()=>void command('exportSelection',{styleIds:exportIds})}>Export selected ({exportIds.length})</button>}</div>
    <div className="active-note"><span className="pulse"/><div><b>{state.overlay?'Overlay running':'Overlay paused'}</b><small>{active?.name??'No active style'}</small></div><button className="text-button" onClick={()=>void command('setOverlay',{enabled:!state.overlay})}>{state.overlay?'Pause':'Resume'}</button></div>
  </aside></section>;

  const renderHome=()=> <section className="home-layout">
    <div className="home-primary"><div className="eyebrow">OVERLAY STATUS</div><h2>{state.overlay?'Ready when you are':'Overlay is paused'}</h2><p>Choose a reticle, make a quick adjustment, then activate it over your game.</p><div className="home-actions"><button className="primary" onClick={()=>void command('setOverlay',{enabled:!state.overlay})}><Activity size={16}/>{state.overlay?'Pause overlay':'Start overlay'}</button><button className="secondary" onClick={()=>go('Library')}>Browse crosshairs</button></div><div className="home-active"><span>ACTIVE CROSSHAIR</span><b>{active?.name??'None selected'}</b><div>{active&&<CrosshairPreview item={active}/>}</div></div></div>
    <div className="home-side"><div className="panel-card"><div className="panel-heading"><h3>Quick select</h3><button className="text-button" onClick={()=>go('Library')}>Full library <ArrowRight size={14}/></button></div><div className="quick-list">{state.styles.slice(0,5).map(style=><button key={style.id} className="quick-style" onClick={()=>void command('activateStyle',{styleId:style.id})}><CrosshairPreview item={style}/><span><b>{style.name}</b><small>{style.family}</small></span><Check size={15}/></button>)}</div></div><div className="panel-card"><div className="panel-heading"><h3>Quick controls</h3></div><SettingRow title="Selected size"><PersistRange label="Selected size" min={50} max={200} value={state.settings.selectedSize} onCommit={value=>void command('setSelectedSize',{value})}/></SettingRow><SettingRow title="Overlay scale"><PersistRange label="Overlay scale" min={50} max={200} value={state.settings.globalSize} onCommit={value=>void command('setGlobalSize',{value})}/></SettingRow></div></div>
  </section>;

  const renderDetail=()=>detail?<section className="detail-layout"><div className="detail-preview-panel"><div className="panel-heading"><div><span className="eyebrow">LIVE PREVIEW</span><h2>{detail.name}</h2></div><button className="secondary" onClick={()=>void command('activateStyle',{styleId:detail.id})}>Use crosshair</button></div><div className="detail-stage"><CrosshairPreview item={detail}/></div><p>{detail.description}</p><div className="detail-tags">{detail.tags.map(tag=><span className="tag" key={tag}>{tag}</span>)}</div></div><div className="detail-controls panel-card"><div className="panel-heading"><div><span className="eyebrow">STYLE TUNING</span><h3>Editable settings</h3></div><button className="icon-button" title="Save as a custom variant" onClick={()=>void command('saveVariant',{styleId:detail.id})}><Save size={16}/></button></div>
      {!detail.editableSettings.length&&<p className="muted">This style has no direct controls. Send it to the creator to edit its design.</p>}
      {detail.editableSettings.map(spec=>{
        const key=spec.key==='color_rgba'?'color':spec.key==='arm_length'?'armLength':spec.key==='center_dot'?'dot':spec.key==='center_dot_size'?'centerDotSize':spec.key==='circle_radius'?'circleRadius':spec.key==='circle_thickness'?'circleThickness':spec.key==='outline_enabled'?'outlineEnabled':spec.key==='outline_thickness'?'outlineThickness':spec.key==='rotation_degrees'?'rotationDegrees':spec.key==='t_style'?'tStyle':spec.key;
        if(spec.kind==='bool')return <SettingRow key={key} title={spec.label}><Toggle checked={Boolean(spec.value)} label={spec.label} onChange={value=>void command('updateStyle',{styleId:detail.id,updates:{[key]:value}})}/></SettingRow>;
        if(spec.kind==='color')return <SettingRow key={key} title={spec.label}><input type="color" aria-label={spec.label} value={String(spec.value??detail.color)} onChange={event=>void command('updateStyle',{styleId:detail.id,updates:{color:event.target.value}})}/></SettingRow>;
        const field=key==='opacity'?'opacity':key;
        return <SettingRow key={key} title={spec.label}><PersistRange label={spec.label} min={spec.minimum??0} max={spec.maximum??100} step={spec.step??1} value={Number(spec.value??0)} onCommit={value=>void command('updateStyle',{styleId:detail.id,updates:{[field]:value}})}/></SettingRow>;
      })}
      <div className="detail-actions"><button className="secondary" onClick={async()=>{await command('sendToCreator',{styleId:detail.id});go('Creator')}}><Pencil size={15}/> Send to creator</button><button className="secondary" onClick={()=>void command('exportStyle',{styleId:detail.id})}><Download size={15}/> Export style</button></div>
    </div></section>:<div className="empty">Choose a crosshair in the library to view its detail controls.</div>;

  const renderCreator=()=> <section className="creator-layout"><div className="creator-board panel-card"><div className="panel-heading"><div><span className="eyebrow">RETICLE CANVAS</span><h2>{creatorModel.name||'Untitled crosshair'}</h2></div><div className="creator-tools"><button className="icon-button" aria-label="Undo" disabled={!history.length} onClick={creatorUndo}><Undo2 size={16}/></button><button className="icon-button" aria-label="Redo" disabled={!future.length} onClick={creatorRedo}><Redo2 size={16}/></button><button className="icon-button" aria-label="Clear canvas" onClick={freshCreator}><RotateCcw size={16}/></button></div></div><div className="canvas-wrap" onPointerUp={()=>setPainting(false)} onPointerLeave={()=>setPainting(false)}><div className="creator-canvas" style={{gridTemplateColumns:`repeat(${creatorModel.grid_size},1fr)`}}>{Array.from({length:creatorModel.grid_size*creatorModel.grid_size},(_,index)=>{const x=index%creatorModel.grid_size,y=Math.floor(index/creatorModel.grid_size);const filled=creatorModel.filled_cells.some(cell=>cell[0]===x&&cell[1]===y);return <button key={index} className={filled?'cell filled':'cell'} style={{'--cell-color':creatorModel.color_hex} as React.CSSProperties} aria-label={`Grid cell ${x+1}, ${y+1}${filled?', filled':''}`} onPointerDown={event=>{event.preventDefault();setPainting(true);paintCell(x,y,event.button===2)}} onPointerEnter={event=>{if(painting)paintCell(x,y,event.buttons===2)}} onContextMenu={event=>event.preventDefault()}/>})}</div></div><div className="canvas-help">Click or drag to draw · Right-click or erase tool to remove</div></div>
    <aside className="creator-controls panel-card"><div className="panel-heading"><div><span className="eyebrow">DESIGN</span><h3>Crosshair creator</h3></div></div><SettingRow title="Name"><input value={creatorModel.name} maxLength={64} onChange={event=>setCreatorModel(model=>({...model,name:event.target.value}))}/></SettingRow><SettingRow title="Grid size"><select value={creatorModel.grid_size} onChange={event=>setCreatorModel(model=>({...model,grid_size:Number(event.target.value),filled_cells:model.filled_cells.filter(([x,y])=>x<Number(event.target.value)&&y<Number(event.target.value))}))}>{[16,24,32,40,48,64].map(size=><option key={size}>{size}</option>)}</select></SettingRow><SettingRow title="Creation mode"><select value={creatorModel.creation_mode} onChange={event=>setCreatorModel(model=>({...model,creation_mode:event.target.value as CreatorModel['creation_mode']}))}><option value="draw">Draw</option><option value="pixel">Pixel art</option></select></SettingRow><SettingRow title="Color"><input type="color" value={creatorModel.color_hex} onChange={event=>setCreatorModel(model=>({...model,color_hex:event.target.value.toUpperCase()}))}/></SettingRow><div className="creator-actions"><button className="primary wide" disabled={busy} onClick={()=>void command('creatorSave',{model:creatorModel,activate:true})}><Save size={15}/> Save and activate</button><button className="secondary wide" onClick={()=>void command('creatorSave',{model:creatorModel,activate:false})}>Save to My Crosshairs</button><button className="secondary wide" onClick={()=>void command('creatorExport',{model:creatorModel})}><Download size={15}/> Export design</button></div><p className="muted">{creatorModel.filled_cells.length} cells · {history.length?`${history.length} undo steps`:'No changes yet'}</p></aside></section>;

  const renderGames=()=> <section className="settings-page"><div className="panel-card"><div className="panel-heading"><div><span className="eyebrow">GAME PROFILES</span><h2>Automatic profile switching</h2></div><button className="secondary" onClick={()=>void command('rescanGames',{})}><RotateCcw size={15}/> Rescan</button></div><p className="muted">{state.gamesStatus||'Detected games and custom executables.'}</p><SettingRow title="Enable while a game is fullscreen"><Toggle checked={state.settings.fullscreenAuto} label="Enable overlay in fullscreen games" onChange={enabled=>void command('setFullscreenAuto',{enabled})}/></SettingRow><SettingRow title="Switch style with the active game"><Toggle checked={state.settings.gameAutoSwitch} label="Switch crosshair profile automatically" onChange={enabled=>void command('setGameAutoSwitch',{enabled})}/></SettingRow><div className="game-list">{state.games.map(game=><GameRow key={game.id} game={game} styles={state.styles} onChange={(styleId,enabled)=>void command('setGameProfile',{gameId:game.id,styleId,enabled})}/>)}</div><button className="secondary" onClick={()=>void command('importGame',{})}><FilePlus2 size={15}/> Add executable</button></div></section>;

  const renderZoom=()=>state.settings.betaVisible?<section className="settings-page"><div className="panel-card"><div className="panel-heading"><div><span className="eyebrow">BETA FEATURES</span><h2>Zoom and live preview</h2></div><ZoomIn size={20}/></div><p className="muted">Native capture stays in the Windows runtime; these controls only configure the overlay.</p><SettingRow title="Enable Zoom"><Toggle checked={state.settings.zoom.zoomEnabled} label="Enable zoom overlay" onChange={value=>setZoom('zoomEnabled',value)}/></SettingRow><SettingRow title="Live zoom"><Toggle checked={state.settings.zoom.liveEnabled} label="Enable live zoom" onChange={value=>setZoom('liveEnabled',value)}/></SettingRow><SettingRow title="Show Zoom in the sidebar"><Toggle checked={state.settings.zoom.sidebarEnabled} label="Show Zoom beta page" onChange={value=>void command('setBetaVisible',{enabled:value})}/></SettingRow><SettingRow title="Hotkey"><input key={state.settings.zoom.hotkeySequence} defaultValue={state.settings.zoom.hotkeySequence} onBlur={event=>setZoom('hotkeySequence',event.target.value)}/></SettingRow><SettingRow title="Display"><select value={state.settings.zoom.displayMode} onChange={event=>setZoom('displayMode',event.target.value as ZoomSettings['displayMode'])}><option value="monitor">Monitor</option><option value="crosshair">Crosshair focus</option></select></SettingRow><SettingRow title="Monitor"><select value={state.settings.zoom.targetMonitorId} onChange={event=>setZoom('targetMonitorId',event.target.value)}>{state.settings.monitors.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></SettingRow><SettingRow title={`Zoom level · ${state.settings.zoom.zoomPercent}%`}><PersistRange label="Zoom level" min={200} max={1000} step={25} value={state.settings.zoom.zoomPercent} onCommit={value=>setZoom('zoomPercent',value)}/></SettingRow><SettingRow title={`Horizontal position · ${state.settings.zoom.positionXPercent}%`}><PersistRange label="Horizontal position" min={0} max={100} value={state.settings.zoom.positionXPercent} onCommit={value=>setZoom('positionXPercent',value)}/></SettingRow><SettingRow title={`Vertical position · ${state.settings.zoom.positionYPercent}%`}><PersistRange label="Vertical position" min={0} max={100} value={state.settings.zoom.positionYPercent} onCommit={value=>setZoom('positionYPercent',value)}/></SettingRow><SettingRow title="Animated transitions"><Toggle checked={state.settings.zoom.animationEnabled} label="Animate zoom transitions" onChange={value=>setZoom('animationEnabled',value)}/></SettingRow><SettingRow title="Animation duration"><PersistRange label="Animation duration" min={0} max={1000} step={10} value={state.settings.zoom.animationDurationMs} onCommit={value=>setZoom('animationDurationMs',value)}/></SettingRow></div></section>:<section className="empty"><ZoomIn size={24}/><b>Zoom is disabled</b><span>Enable the Zoom sidebar switch in Settings → Beta features.</span><button className="secondary" onClick={()=>go('Settings')}>Open settings</button></section>;

  const renderSettings=()=> <section className="settings-page settings-groups"><div className="panel-card"><div className="panel-heading"><div><span className="eyebrow">APPEARANCE</span><h2>Interface and crosshair</h2></div></div><SettingRow title="Color theme"><select value={state.settings.theme} onChange={event=>void command('setTheme',{theme:event.target.value})}><option value="system">System</option><option value="dark">Dark</option><option value="light">Light</option></select></SettingRow><SettingRow title="Accent color"><input type="color" value={state.settings.accent} onChange={event=>void command('setAccent',{color:event.target.value})}/></SettingRow><SettingRow title={`Selected crosshair size · ${state.settings.selectedSize}%`}><PersistRange label="Selected crosshair size" min={50} max={200} value={state.settings.selectedSize} onCommit={value=>void command('setSelectedSize',{value})}/></SettingRow><SettingRow title={`Global scale · ${state.settings.globalSize}%`}><PersistRange label="Global scale" min={50} max={200} value={state.settings.globalSize} onCommit={value=>void command('setGlobalSize',{value})}/></SettingRow></div>
    <div className="panel-card"><div className="panel-heading"><div><span className="eyebrow">APP BEHAVIOR</span><h2>Startup and updates</h2></div></div><SettingRow title="Check for updates at startup"><Toggle checked={state.settings.autoUpdate} label="Check for updates at startup" onChange={enabled=>void command('setStartup',{preference:'updates',enabled})}/></SettingRow><SettingRow title="Start minimized to tray"><Toggle checked={state.settings.startupTray} label="Start minimized to tray" onChange={enabled=>void command('setStartup',{preference:'tray',enabled})}/></SettingRow><SettingRow title="Show Zoom beta controls"><Toggle checked={state.settings.betaVisible} label="Show Zoom beta controls" onChange={enabled=>void command('setBetaVisible',{enabled})}/></SettingRow><SettingRow title="Storage folder" help={state.settings.storagePath}><button className="secondary" onClick={()=>void command('chooseStorage',{})}>Choose folder</button></SettingRow><div className="settings-actions"><button className="secondary" onClick={()=>void command('checkUpdates',{})}>Check for updates</button><button className="danger-button" onClick={()=>void command('resetSettings',{})}>Reset settings</button><button className="text-button" onClick={()=>void command('quit',{})}>Quit application</button></div></div></section>;

  const renderExport=()=> <section className="export-page"><div className="panel-card"><div className="panel-heading"><div><span className="eyebrow">IMPORT / EXPORT</span><h2>Move your crosshair styles</h2></div></div><p className="muted">Export one style from the inspector, or select styles in the catalog to create a shareable pack.</p><div className="export-actions"><button className="primary" onClick={()=>void command('importPack',{})}><FilePlus2 size={15}/> Import crosshair pack</button><button className="secondary" onClick={()=>void command('exportCurrent',{})} disabled={!state.activeId}><Download size={15}/> Export active crosshair</button></div><div className="export-current"><span>Active style</span><b>{active?.name??'None selected'}</b></div></div>{renderLibrary()}</section>;

  const renderAbout=()=> <section className="about-page"><div className="panel-card"><div className="brand-icon"><Crosshair size={24}/></div><span className="eyebrow">CROSSHAIR OVERLAY</span><h2>Precision when every pixel counts.</h2><p>Configure a lightweight crosshair overlay, organize style collections, and create your own reticles.</p><dl><div><dt>Version</dt><dd>{state.appVersion||'Unknown'}</dd></div><div><dt>Runtime</dt><dd>{state.runtime==='native'?'Windows native services connected':state.runtime}</dd></div><div><dt>Styles in library</dt><dd>{state.styleCount}</dd></div></dl><button className="secondary" onClick={()=>void command('checkUpdates',{})}>Check for updates</button></div></section>;

  let content:React.ReactNode;
  if(page==='Library'||page==='My Crosshairs')content=renderLibrary();
  else if(page==='Home')content=renderHome();
  else if(page==='Detail')content=renderDetail();
  else if(page==='Creator')content=renderCreator();
  else if(page==='Games')content=renderGames();
  else if(page==='Zoom')content=renderZoom();
  else if(page==='Settings')content=renderSettings();
  else if(page==='Export')content=renderExport();
  else content=renderAbout();

  const headingText:Record<Page,string>={Home:'Home',Library:'Library','My Crosshairs':'My Crosshairs',Detail:'Crosshair details',Creator:'Creator',Games:'Games',Zoom:'Zoom beta',Export:'Export',Settings:'Settings',About:'About'};
  const subtitle:Record<Page,string>={Home:'A quick view of your active overlay and favorite controls.',Library:'Find, inspect, tune, and activate a crosshair.', 'My Crosshairs':'Your favorites, imports, and custom crosshair collection.',Detail:'Tune the selected style and save your changes.',Creator:'Draw, undo, and save a crosshair design.',Games:'Map a crosshair to a game profile.',Zoom:'Configure the native zoom and live preview.',Export:'Import styles and share selected crosshairs.',Settings:'Set how Crosshair Overlay looks and behaves.',About:'Application information and runtime status.'};

  return <div className={'shell '+(state.settings.sidebarCollapsed?'sidebar-collapsed':'')} data-theme={appTheme} style={{'--accent':state.accent,'--accent-ink':contrastText(state.accent)} as React.CSSProperties}>
    <aside className="rail"><div className="brand"><div className="brand-icon"><Crosshair size={20}/></div><div><b>Crosshair</b><small>OVERLAY CONTROL</small></div><button className="collapse-nav" aria-label={state.settings.sidebarCollapsed?'Expand navigation':'Collapse navigation'} title={state.settings.sidebarCollapsed?'Expand navigation':'Collapse navigation'} onClick={()=>void command('setSidebarCollapsed',{collapsed:!state.settings.sidebarCollapsed})}>{state.settings.sidebarCollapsed?<PanelLeftOpen size={16}/>:<PanelLeftClose size={16}/>}</button></div><div className="rail-label">WORKSPACE</div>{nav.map(([name,Icon])=><button key={name} className={'nav '+(page===name?'on':'')} aria-label={name} title={state.settings.sidebarCollapsed?name:undefined} aria-current={page===name?'page':undefined} onClick={()=>go(name)}><Icon size={17}/><span>{name}</span>{name==='Zoom'&&!state.settings.betaVisible&&<i className="nav-locked" aria-label="Beta disabled"/>}</button>)}<div className="rail-bottom"><div className={'runtime '+(state.overlay?'running':'')}><i/><div><b>{state.overlay?'Overlay running':'Overlay paused'}</b><small>{active?.name??'No active style'}</small></div><button aria-label="Toggle overlay" onClick={()=>void command('setOverlay',{enabled:!state.overlay})}><Activity size={16}/></button></div><button className="native" onClick={()=>void command('toggleNative',{})}>Switch to classic controls</button><small className="shortcut-hint">Switch back with Ctrl + Shift + N</small></div></aside>
    <main className="main" ref={mainRef}><header><div className="crumb">Workspace <span>/</span> {headingText[page]}</div><div className="head-actions"><span className="status"><i className={bridgeStatus==='connected'?'':bridgeStatus==='failed'?'offline':'connecting'}/> {bridgeStatus==='connected'?'Native runtime connected':bridgeStatus==='failed'?'Native bridge unavailable':'Connecting to runtime…'}</span><button className="icon-button" aria-label="Cycle color theme" disabled={bridgeStatus!=='connected'} onClick={()=>void command('setTheme',{theme:state.settings.theme==='system'?'dark':state.settings.theme==='dark'?'light':'system'})}>{state.settings.theme==='light'?<Sun size={17}/>:<Moon size={17}/>}</button></div></header>
      <section className="page-head"><div><h1>{headingText[page]}</h1><p>{subtitle[page]}</p></div>{(page==='Library'||page==='My Crosshairs')&&<button className="primary" onClick={()=>void command('setOverlay',{enabled:!state.overlay})}><Activity size={16}/>{state.overlay?'Pause overlay':'Start overlay'}</button>}{page==='Creator'&&<button className="primary" onClick={()=>void command('creatorSave',{model:creatorModel,activate:true})}><Save size={15}/> Save design</button>}</section>
      {(error||bridgeStatus==='failed')&&<div className="error" role="alert">{error||'The native control bridge is unavailable. Retry the connection or switch to classic controls.'}<button onClick={()=>{setError('');bridge.retryConnection()}}>Retry</button></div>}
      {content}
      <footer><span>Crosshair Overlay <b>•</b> v{state.appVersion||'—'}</span><span><span className={'connected '+(bridgeStatus==='connected'?'':'disconnected')}/>{bridgeStatus==='connected'?`Connected to ${state.runtime} runtime`:bridgeStatus==='failed'?'Runtime disconnected':'Connecting to runtime'}</span></footer>
    </main>
  </div>;
}

function GameRow({game,styles,onChange}:{game:Game;styles:Style[];onChange:(styleId:string,enabled:boolean)=>void}){
  const [styleId,setStyleId]=useState(game.styleId);
  const [styleQuery,setStyleQuery]=useState('');
  const [styleChoices,setStyleChoices]=useState(styles);
  const [styleError,setStyleError]=useState('');
  useEffect(()=>setStyleId(game.styleId),[game.styleId]);
  useEffect(()=>{if(!styleQuery.trim())setStyleChoices(styles)},[styles,styleQuery]);
  useEffect(()=>{
    if(!styleQuery.trim())return;
    let cancelled=false;
    const timer=window.setTimeout(async()=>{
      try{
        const reply=await bridge.send('queryCatalog',{query:styleQuery,filter:'all',page:0,pageSize:36});
        if(!reply.ok)throw Error(reply.error?.message??'Could not search styles');
        if(!cancelled){setStyleChoices((reply.result as {styles:Style[]}).styles);setStyleError('')}
      }catch(cause){if(!cancelled)setStyleError(cause instanceof Error?cause.message:String(cause))}
    },120);
    return()=>{cancelled=true;window.clearTimeout(timer)};
  },[styleQuery]);
  const selectedStyle=styles.find(style=>style.id===styleId)??styleChoices.find(style=>style.id===styleId);
  return <div className="game-row"><div className="game-identity"><span className="game-icon"><Monitor size={17}/></span><span><b>{game.title}</b><small title={game.executablePath}>{game.source} · {game.executablePath||'Detected game'}</small></span></div><div className="game-style-picker"><input aria-label={`Search styles for ${game.title}`} placeholder="Find style" value={styleQuery} onChange={event=>setStyleQuery(event.target.value)}/><select aria-label={`Crosshair for ${game.title}`} value={styleId} onChange={event=>{setStyleId(event.target.value);onChange(event.target.value,game.enabled)}}><option value="">Select style</option>{styleId&&!styleChoices.some(style=>style.id===styleId)&&<option value={styleId}>{selectedStyle?.name??styleId} (current)</option>}{styleChoices.map(style=><option key={style.id} value={style.id}>{style.name}</option>)}</select>{styleError&&<small className="game-style-error" role="status">{styleError}</small>}</div><Toggle checked={game.enabled} label={`Enable profile for ${game.title}`} onChange={enabled=>onChange(styleId,enabled)}/></div>;
}
