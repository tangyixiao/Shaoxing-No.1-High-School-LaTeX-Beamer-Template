import { build, checkSpec } from './vendor/product-render/build.js';
import { config } from './vendor/_print-core/print3d.js';

// Original concept models over the unmodified taste raymarch renderer. No WebGL animation loop:
// only a requested camera/material change produces a new frame, including under reduced motion.
config.maxLive = 2;
config.maxCanvasPx = 620000;
config.fineTexels = 360000;
const BASE = new URL('./', import.meta.url);
const MODELS = {
  command: { title: '命令工作台', accent: '#62c7a5', detail: '键帽、金属底座与终端灯线，表达命令入口。' },
  bridge: { title: '协议接插台', accent: '#ec8264', detail: '接口、弧形连接线与信号灯，表达工具之间的连接。' },
  training: { title: '训练计时台', accent: '#c4ba68', detail: '三层进阶台与机械计时器，表达练习、复测与进阶。' },
  library: { title: '知识讲台', accent: '#bd6b55', detail: '纸页、装订书册与阅读灯，表达学习资料和演示。' },
  atlas: { title: '十国印章台', accent: '#d6a459', detail: '十枚铜印与抽象地图表达多国路线；形状不对应精确疆界。' }
};
const PRESETS = {
  reset: { angle: -28, elev: 26 }, front: { angle: 0, elev: 20 },
  side: { angle: -82, elev: 22 }, top: { angle: -8, elev: 72 }
};
export const viewers = new Map();
const specs = new Map();
let serial = 0;
let drawing = Promise.resolve();
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const enqueue = task => { const result = drawing.catch(() => {}).then(task); drawing = result.catch(() => {}); return result; };
const el = (tag, cls, text) => { const node = document.createElement(tag); if (cls) node.className = cls; if (text) node.textContent = text; return node; };
const clamp = (n, low, high) => Math.max(low, Math.min(high, n));
const angle = n => ((n + 180) % 360 + 360) % 360 - 180;

function cssColor(value, fallback) {
  value = value.trim();
  if (/^#[\da-f]{6}$/i.test(value)) return value;
  if (/^#[\da-f]{3}$/i.test(value)) return '#' + [...value.slice(1)].map(c => c + c).join('');
  const channels = value.match(/^rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/i);
  return channels ? '#' + channels.slice(1).map(c => clamp(+c,0,255).toString(16).padStart(2,'0')).join('') : fallback;
}
function palette(host, id) {
  const styles = getComputedStyle(host);
  const tone = document.documentElement.dataset.theme || document.documentElement.dataset.tone;
  const dark = tone ? tone === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  return {
    bg: cssColor(styles.getPropertyValue('--bg'), dark ? '#151719' : '#f1eee7'),
    surface: cssColor(styles.getPropertyValue('--surface'), dark ? '#282c2e' : '#e6e0d5'),
    ink: cssColor(styles.getPropertyValue('--ink'), dark ? '#f0ede5' : '#252a29'),
    accent: cssColor(styles.getPropertyValue('--model-accent'), MODELS[id].accent)
  };
}
async function loadSpec(id) {
  if (!specs.has(id)) specs.set(id, fetch(new URL(`specs/${id}.json`, BASE)).then(async response => {
    if (!response.ok) throw new Error(`model HTTP ${response.status}`);
    const spec = await response.json();
    const errors = checkSpec(spec);
    if (errors.length) throw new Error(errors.join('; '));
    return spec;
  }));
  return specs.get(id);
}

export async function mount(host) {
  if (viewers.has(host)) return viewers.get(host);
  const id = host.dataset.model;
  if (!MODELS[id]) { host.textContent = '未找到此项目交互示意。'; host.dataset.threeState = 'fallback'; return null; }
  const meta = {...MODELS[id]};
  const english = host.dataset.modelLang === 'en' || document.documentElement.lang === 'en';
  if(english)meta.title={command:'COMMAND WORKBENCH',bridge:'CONNECTION PATCHBAY',training:'TRAINING CHRONOMETER',library:'READING DESK',atlas:'HISTORICAL SEAL TABLE'}[id];
  const words = english
    ? { concept: 'Interactive project study', model: '3D model', loading: 'Preparing 3D', fallback: '2D structural study', rotate: 'Rotation', reset: 'Reset', front: 'Front', side: 'Side', top: 'Top', hint: 'Drag or use ← → to rotate. Home resets the view.', note: 'Conceptual visualization, not manufactured hardware or a game screenshot.' }
    : { concept: '项目交互示意', model: '3D 模型', loading: '准备 3D', fallback: '二维结构示意', rotate: '旋转', reset: '重置', front: '正面', side: '侧面', top: '顶视', hint: '拖动或按 ← → 旋转，Home 重置视角。', note: '概念视觉，不代表实际硬件或游戏截图。' };
  host.classList.add('project-3d');
  host.dataset.threeState = 'loading';
  host.dataset.threeModel = id;
  host.dataset.threeMotion = reduced.matches ? 'reduced' : 'on-demand';
  host.replaceChildren();
  const uid = `project-3d-${++serial}`;
  const header = el('div','project-3d__header');
  const heading = el('span','project-3d__title', `${words.concept} / ${host.dataset.modelTitle || meta.title}`);
  const status = el('span','project-3d__state',words.loading);
  status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  header.append(heading,status);
  const stage = el('div','project-3d__stage');stage.tabIndex=0;
  stage.setAttribute('role','group');stage.setAttribute('aria-label', `${meta.title}。${words.hint} ${words.note}`);
  stage.setAttribute('aria-describedby',`${uid}-hint`);
  const fallback = el('img','project-3d__fallback');
  fallback.src = new URL(`fallbacks/${id}.svg`,BASE).href;
  fallback.alt = `${meta.title}，${words.fallback}。${meta.detail}`;
  const canvasHost = el('div','project-3d__render');
  canvasHost.setAttribute('aria-label',`${meta.title}，${words.concept}`);
  canvasHost.setAttribute('aria-hidden','true');
  stage.append(fallback,canvasHost);
  const controls = el('div','project-3d__controls');controls.setAttribute('aria-label',words.model);
  const buttons = el('div','project-3d__presets');
  const presetButtons = {};
  for (const key of ['reset','front','side','top']) {
    const button=el('button','project-3d__button',words[key]);button.type='button';
    button.dataset.threeView=key;button.setAttribute('aria-pressed',String(key==='reset'));
    presetButtons[key]=button;buttons.append(button);
  }
  const sliderLabel=el('label','project-3d__slider-label',words.rotate);sliderLabel.htmlFor=`${uid}-rotation`;
  const slider=el('input','project-3d__slider');slider.type='range';slider.min='-180';slider.max='180';slider.step='1';slider.value='-28';slider.id=`${uid}-rotation`;
  const output=el('output','project-3d__angle','−28°');output.setAttribute('for',slider.id);
  const range=el('div','project-3d__range');range.append(sliderLabel,slider,output);
  controls.append(buttons,range);
  const hint=el('p','project-3d__hint',words.hint);hint.id=`${uid}-hint`;
  const note=el('span','project-3d__concept-note',words.note);hint.append(' ',note);
  host.append(header,stage,controls,hint);
  let spec,controller=null,pose={...PRESETS.reset},token=0,destroyed=false,frame=0,drag=null,redrawQueued=false;
  let activeView='reset';
  function state(value,reason='') {
    host.dataset.threeState=value;
    status.textContent=value==='ready'?words.model:value==='loading'?words.loading:words.fallback;
    if(reason)host.dataset.threeReason=reason;
    const disabled=value==='fallback';
    slider.disabled=disabled;
    Object.values(presetButtons).forEach(b=>b.disabled=disabled);
    if(disabled)stage.setAttribute('aria-label',`${meta.title}。${words.fallback}。${meta.detail}`);
  }
  function syncControls() {
    slider.value=String(Math.round(pose.angle));output.value=`${Math.round(pose.angle)}°`;output.textContent=output.value;
    slider.setAttribute('aria-valuetext',output.value);
    Object.entries(presetButtons).forEach(([key,b])=>b.setAttribute('aria-pressed',String(key===activeView)));
    host.dataset.threeAngle=String(Math.round(pose.angle));
    host.dataset.threeElevation=String(pose.elev);
  }
  async function draw(current=controller,my=token) {
    if(!current||destroyed||my!==token)return;
    await current.ready();
    if(destroyed||my!==token){current.release();return;}
    if(current.info.fallback){current.release();state('fallback',current.info.fallback);return;}
    current.set({angle:pose.angle,turn:0,interactive:0});
    current.pose({t:0,hover:0});
    current.release();
    // release() may synchronously reclaim WebGL (reduced motion / offscreen) after
    // keepFrame(). `shown` then describes the removed live canvas, while `still=frame`
    // remains the actual rendered model. Both are valid pictures, not SVG fallbacks.
    const info=current.info;
    if(info.fallback)state('fallback',info.fallback);
    else if(info.shown||info.still==='frame'){state('ready');delete host.dataset.threeReason;}
  }
  async function rebuild() {
    const my=++token;
    if(controller){controller.destroy();controller=null;}
    canvasHost.replaceChildren();delete canvasHost.dataset.printFallback;
    state('loading');
    if(host.dataset.modelFallback==='true'){state('fallback','requested static structural study');return;}
    try {
      spec=spec||await loadSpec(id);
      if(destroyed||my!==token)return;
      const object=build(spec,{base:new URL(`specs/${id}.json`,BASE).href,view:{name:activeView,angle:pose.angle,elev:pose.elev}});
      if(object.problems().length)throw new Error(object.problems().join('; '));
      controller=object.mount0(canvasHost,{palette:palette(host,id),params:{size:.83,transparent:1,turn:0,interactive:0,angle:pose.angle,shadow:1}});
      const current=controller;
      await enqueue(()=>draw(current,my));
    }catch(error){if(!destroyed&&my===token)state('fallback',String(error.message||error));}
  }
  function rotate(value) {
    pose.angle=angle(value);activeView='custom';syncControls();
    if(!controller||frame)return;
    frame=requestAnimationFrame(()=>{frame=0;requestDraw();});
  }
  function requestDraw(){
    if(redrawQueued||destroyed)return;
    redrawQueued=true;
    enqueue(async()=>{redrawQueued=false;await draw();}).catch(error=>state('fallback',String(error.message||error)));
  }
  function chooseView(key) { activeView=key;pose={...PRESETS[key]};syncControls();return rebuild(); }
  Object.entries(presetButtons).forEach(([key,b])=>b.addEventListener('click',()=>chooseView(key)));
  slider.addEventListener('input',()=>rotate(+slider.value));
  stage.addEventListener('pointerdown',event=>{
    if(event.button!==0||host.dataset.threeState==='fallback')return;
    drag={x:event.clientX,angle:pose.angle,id:event.pointerId};stage.setPointerCapture(event.pointerId);stage.classList.add('is-dragging');stage.focus({preventScroll:true});
  });
  stage.addEventListener('pointermove',event=>{if(drag&&event.pointerId===drag.id)rotate(drag.angle+(event.clientX-drag.x)*.5);});
  function drop(){drag=null;stage.classList.remove('is-dragging');}
  stage.addEventListener('pointerup',drop);stage.addEventListener('pointercancel',drop);stage.addEventListener('lostpointercapture',drop);
  stage.addEventListener('keydown',event=>{
    if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();rotate(pose.angle+(event.key==='ArrowRight'?1:-1)*(event.shiftKey?20:5));}
    else if(event.key==='Home'){event.preventDefault();chooseView('reset');}
    else if(event.key==='ArrowUp'){event.preventDefault();chooseView('top');}
    else if(event.key==='ArrowDown'){event.preventDefault();chooseView('front');}
  });
  const lossWatcher=new MutationObserver(()=>{
    // The renderer deliberately calls loseContext() during idle disposal and owns
    // retries for genuine GPU loss. Only its terminal failure signal selects SVG.
    const failure=canvasHost.dataset.printFallback||controller?.info.fallback;
    if(failure)state('fallback',failure);
  });
  lossWatcher.observe(canvasHost,{attributes:true,attributeFilter:['data-print-fallback']});
  const themeWatcher=new MutationObserver(()=>{
    if(controller){controller.setPalette(palette(host,id));requestDraw();}
  });
  themeWatcher.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme','data-tone','class','style']});
  const onReduced=()=>{host.dataset.threeMotion=reduced.matches?'reduced':'on-demand';};
  reduced.addEventListener('change',onReduced);
  const api={
    get controller(){return controller;},get pose(){return {...pose};},
    rotate,view:chooseView,
    setPalette(){controller?.setPalette(palette(host,id));return enqueue(()=>draw());},
    destroy(){destroyed=true;token++;if(frame)cancelAnimationFrame(frame);controller?.destroy();lossWatcher.disconnect();themeWatcher.disconnect();reduced.removeEventListener('change',onReduced);viewers.delete(host);}
  };
  viewers.set(host,api);syncControls();
  await rebuild();return api;
}
export async function mountAll(root=document){return Promise.all([...root.querySelectorAll('[data-model]')].map(mount));}
export const ready=document.readyState==='loading'
  ? new Promise(resolve=>document.addEventListener('DOMContentLoaded',()=>resolve(mountAll()),{once:true}))
  : mountAll();
window.project3D={viewers,mount,mountAll,ready};
