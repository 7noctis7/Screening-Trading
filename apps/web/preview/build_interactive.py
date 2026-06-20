"""Génère un dashboard HTML AUTONOME et INTERACTIF depuis les vraies données du snapshot.

Un seul fichier, aucune install, aucune API : à ouvrir directement au navigateur.
Interactivité (vanilla JS) : onglets, courbe d'equity avec crosshair + tooltip au survol,
heatmap de corrélation avec info au survol, screener cliquable, compteurs animés.

  python apps/web/preview/build_interactive.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from apps.api.snapshot import build_snapshot  # noqa: E402

_TEMPLATE = r"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Quant Terminal — interactif</title>
<meta name="theme-color" content="#08090c">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Quant Terminal">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%2308090c'/%3E%3Crect x='16' y='16' width='32' height='32' rx='9' fill='url(%23g)'/%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop stop-color='%233b82f6'/%3E%3Cstop offset='1' stop-color='%2322d3ee'/%3E%3C/linearGradient%3E%3C/defs%3E%3C/svg%3E">
<style>
:root{--bg:#08090c;--bg2:#0c0e12;--surface:#121419;--surface2:#171a20;--surface3:#1d212a;
--border:#23272f;--border2:#2d323c;--fg:#eef0f3;--muted:#9aa1ad;--muted2:#6b7280;
--accent:#3b82f6;--accent2:#60a5fa;--pos:#22c55e;--neg:#f43f5e;--warn:#f59e0b;
--shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.25);}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:radial-gradient(1200px 600px at 50% -10%,#10131a 0%,var(--bg) 55%) fixed;
color:var(--fg);-webkit-font-smoothing:antialiased;letter-spacing:-.01em;
font-family:'Inter',-apple-system,BlinkMacSystemFont,'SF Pro Text',system-ui,sans-serif}
::-webkit-scrollbar{width:9px;height:9px}::-webkit-scrollbar-thumb{background:var(--border2);border-radius:6px}
::-webkit-scrollbar-thumb:hover{background:#3a414d}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px 48px}
/* ---- top bar ---- */
.topbar{position:sticky;top:0;z-index:30;display:flex;justify-content:space-between;align-items:center;
gap:12px;padding:14px 20px;margin:0 -20px 4px;background:rgba(10,12,16,.72);
backdrop-filter:saturate(160%) blur(14px);border-bottom:1px solid var(--border)}
.brand{display:flex;align-items:center;gap:10px;font-size:16px;font-weight:650;letter-spacing:-.02em}
.brand .logo{width:22px;height:22px;border-radius:7px;background:linear-gradient(135deg,#3b82f6,#22d3ee);
display:inline-block;box-shadow:0 0 0 1px rgba(255,255,255,.08),0 4px 14px rgba(59,130,246,.45)}
.brand .tag{font-size:9.5px;font-weight:700;letter-spacing:.12em;color:var(--accent2);
border:1px solid var(--border2);border-radius:6px;padding:2px 6px;background:var(--surface)}
.status{display:flex;align-items:center;gap:10px;font-size:12px;color:var(--muted)}
.badge{display:inline-flex;align-items:center;gap:6px;padding:5px 10px;border-radius:999px;
background:var(--surface);border:1px solid var(--border);font-size:11px;font-weight:500}
.pulse{width:7px;height:7px;border-radius:50%;background:var(--pos);
box-shadow:0 0 0 0 rgba(34,197,94,.6);animation:pulse 2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(34,197,94,.5)}70%{box-shadow:0 0 0 7px rgba(34,197,94,0)}100%{box-shadow:0 0 0 0 rgba(34,197,94,0)}}
.clock{font-variant-numeric:tabular-nums;color:var(--fg);font-weight:550}
/* ---- tabs ---- */
.tabs{position:sticky;top:57px;z-index:20;display:flex;gap:4px;padding:10px 0;margin-bottom:14px;
flex-wrap:wrap;background:linear-gradient(var(--bg),rgba(8,9,12,.6))}
.tab{padding:8px 14px;border-radius:10px;background:transparent;border:1px solid transparent;
color:var(--muted);cursor:pointer;font-size:13px;font-weight:500;transition:all .18s ease}
.tab:hover{background:var(--surface2);color:var(--fg)}
.tab.active{background:var(--surface3);color:var(--fg);border-color:var(--border2);box-shadow:var(--shadow)}
.tab.active::before{content:'';display:inline-block;width:6px;height:6px;border-radius:50%;
background:var(--accent);margin-right:7px;vertical-align:middle;box-shadow:0 0 8px var(--accent)}
:focus-visible{outline:2px solid var(--accent2);outline-offset:2px;border-radius:8px}
.tab:focus-visible{outline-offset:0}
/* ---- pages ---- */
.page{display:none;flex-direction:column;gap:14px}
.page.active{display:flex;animation:fade .35s ease}
@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.asof{font-size:11px;color:var(--muted2);display:flex;align-items:center;gap:6px;
padding:2px 0 2px;letter-spacing:.01em}
.asof b{color:var(--muted);font-weight:550}
/* ---- cards ---- */
.card{background:linear-gradient(180deg,var(--surface),var(--bg2));border:1px solid var(--border);
border-radius:16px;padding:18px;transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease}
.card:hover{border-color:var(--border2);box-shadow:var(--shadow);transform:translateY(-1px)}
.label{color:var(--muted);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;font-weight:600}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:760px){.grid4{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}
.topbar .clock{display:none}.wrap{padding:0 12px 40px}
.tabs{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;top:56px}
.tabs::-webkit-scrollbar{display:none}.tab{white-space:nowrap;flex:0 0 auto}
h1{font-size:18px}.metric .val{font-size:22px}}
.metric .val{font-size:27px;margin-top:6px;font-variant-numeric:tabular-nums;font-weight:620;letter-spacing:-.02em}
.mono{font-variant-numeric:tabular-nums}
.pos{color:var(--pos)}.neg{color:var(--neg)}
.banner{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.dot{height:9px;width:9px;border-radius:50%;display:inline-block;margin-right:8px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{color:var(--muted);font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;text-align:left;
font-weight:600;padding-bottom:8px}
td{padding:8px 0;border-top:1px solid var(--border)}
tbody tr{transition:background .12s}
tbody tr:hover{background:var(--surface2)}
tr.srow,tr.srow td{cursor:pointer}
.facbar{height:7px;border-radius:4px;background:linear-gradient(90deg,var(--accent),var(--accent2));
display:inline-block;vertical-align:middle;transition:width .5s ease}
#chartWrap,.chartWrap{position:relative}
#tip,.tip{position:absolute;pointer-events:none;background:rgba(8,9,12,.95);border:1px solid var(--border2);
border-radius:10px;padding:8px 12px;font-size:12px;opacity:0;transition:opacity .1s;white-space:nowrap;
z-index:5;box-shadow:var(--shadow)}
/* ---- heatmap ---- */
.hm{display:grid;gap:6px}
.hcell{position:relative;border-radius:10px;padding:12px 10px;cursor:default;min-height:64px;
display:flex;flex-direction:column;justify-content:space-between;overflow:hidden;
border:1px solid rgba(255,255,255,.05);transition:transform .12s ease,box-shadow .12s ease}
.hcell:hover{transform:scale(1.04);box-shadow:var(--shadow);z-index:2}
.hcell .hn{font-size:11.5px;font-weight:600;line-height:1.15;color:#fff;text-shadow:0 1px 3px rgba(0,0,0,.5)}
.hcell .hv{font-size:16px;font-weight:700;font-variant-numeric:tabular-nums;color:#fff;text-shadow:0 1px 3px rgba(0,0,0,.5)}
.heat td{border:none;text-align:center;color:#fff;font-size:11px;padding:7px;border-radius:4px;cursor:default}
.heat th{text-align:center;padding:2px;font-size:11px}
.pill{display:inline-block;padding:3px 9px;border-radius:999px;font-size:11px;background:var(--surface3);
border:1px solid var(--border)}
.search{width:100%;background:var(--bg2);border:1px solid var(--border);border-radius:10px;
color:var(--fg);font-size:13px;padding:9px 12px;outline:none;transition:border-color .15s}
.search:focus{border-color:var(--accent)}
.chip{font-size:11px;padding:4px 10px;border-radius:999px;border:1px solid var(--border);
background:var(--surface);color:var(--muted);cursor:pointer;transition:all .15s}
.chip:hover{color:var(--fg);border-color:var(--border2)}
.chip.on{background:var(--accent);color:#fff;border-color:var(--accent)}
ul{margin:4px 0 0;padding-left:18px;font-size:13px}li{margin:3px 0}
.toggle{font-size:12px;color:var(--accent);cursor:pointer;user-select:none}
.tkr{color:var(--accent2);cursor:pointer;border-bottom:1px dotted var(--border2)}
.tkr:hover{color:#fff}
.modal{position:fixed;inset:0;z-index:60;background:rgba(4,5,7,.72);backdrop-filter:blur(6px);
display:flex;align-items:center;justify-content:center;padding:20px;animation:fade .2s ease}
.modalbox{width:min(900px,96vw);max-height:92vh;overflow:auto;box-shadow:var(--shadow)}
.close{cursor:pointer;color:var(--muted);font-size:16px;padding:2px 8px;border-radius:8px}
.close:hover{background:var(--surface3);color:var(--fg)}
</style></head><body>
<div class="topbar">
  <div class="brand"><span class="logo"></span>Quant Terminal<span class="tag">HEDGE-FUND</span></div>
  <div class="status">
    <span class="badge"><span class="pulse"></span><span id="freshBadge">flux différé</span></span>
    <span class="clock" id="clock">--:--:--</span>
  </div>
</div>
<div class="wrap">
<div class="tabs" role="tablist" aria-label="Sections du terminal">
<div class="tab active" data-p="dash" role="tab" tabindex="0" aria-selected="true">Dashboard</div>
<div class="tab" data-p="themes" role="tab" tabindex="0" aria-selected="false">Thèmes de marché</div>
<div class="tab" data-p="ml" role="tab" tabindex="0" aria-selected="false">Signaux ML</div>
<div class="tab" data-p="sent" role="tab" tabindex="0" aria-selected="false">Sentiment &amp; news</div>
<div class="tab" data-p="fund" role="tab" tabindex="0" aria-selected="false">Fondamentaux</div>
<div class="tab" data-p="uni" role="tab" tabindex="0" aria-selected="false">Univers</div>
<div class="tab" data-p="data" role="tab" tabindex="0" aria-selected="false">Données</div>
<div class="tab" data-p="pf" role="tab" tabindex="0" aria-selected="false">Portefeuille &amp; Analyse</div>
<div class="tab" data-p="pos" role="tab" tabindex="0" aria-selected="false">Positions</div>
<div class="tab" data-p="trades" role="tab" tabindex="0" aria-selected="false">Trades (fictif)</div>
<div class="tab" data-p="live" role="tab" tabindex="0" aria-selected="false">Portefeuille réel</div></div>

<div class="page active" id="dash"></div>
<div class="page" id="themes"></div>
<div class="page" id="ml"></div>
<div class="page" id="sent"></div>
<div class="page" id="fund"></div>
<div class="page" id="uni"></div>
<div class="page" id="data"></div>
<div class="page" id="pf"></div>
<div class="page" id="pos"></div>
<div class="page" id="trades"></div>
<div class="page" id="live"></div>
</div>
<script>const DATA = __DATA__;</script>
<script>
const $=(h)=>{const d=document.createElement('div');d.innerHTML=h.trim();return d.firstChild;};
const pct=(x)=>(x*100).toFixed(1)+'%';
const eur=(x)=>Math.round(x).toLocaleString('fr-FR');
const CYC={expansion:'#22c55e',recovery:'#3b82f6',slowdown:'#f59e0b',recession:'#ef4444'};
const fmtTS=(s)=>{if(!s)return '—';const d=new Date(s);return isNaN(d)?String(s).slice(0,16).replace('T',' '):
  d.toLocaleString('fr-FR',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'});};
const STANCE_C={bullish:'#22c55e',bearish:'#f43f5e',neutral:'#9aa1ad'};
const STANCE_I={bullish:'▲',bearish:'▼',neutral:'–'};
const stanceTag=(st,sec)=>`<span style="color:${STANCE_C[st]||'#9aa1ad'}">${STANCE_I[st]||'–'}</span> <span style="color:var(--muted)">${sec||'—'}</span>`;

// ---- tabs (clic + clavier, ARIA) ----
const TABS=[...document.querySelectorAll('.tab')];
function activate(t){
  TABS.forEach(x=>{x.classList.remove('active');x.setAttribute('aria-selected','false');});
  document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));
  t.classList.add('active');t.setAttribute('aria-selected','true');
  document.getElementById(t.dataset.p).classList.add('active');
  window.scrollTo({top:0,behavior:'smooth'});
}
TABS.forEach((t,i)=>{
  t.onclick=()=>activate(t);
  t.onkeydown=e=>{
    if(e.key==='Enter'||e.key===' '){e.preventDefault();activate(t);}
    else if(e.key==='ArrowRight'||e.key==='ArrowLeft'){
      e.preventDefault();const j=(i+(e.key==='ArrowRight'?1:TABS.length-1))%TABS.length;
      TABS[j].focus();activate(TABS[j]);}
  };
});

// ---- horloge live + badge de fraîcheur (flux différé) ----
(function(){
  const M=DATA.meta||{};
  const badge=document.getElementById('freshBadge');
  if(badge)badge.textContent='flux différé '+(M.delay_minutes||15)+' min';
  const clk=document.getElementById('clock');
  function tick(){if(clk)clk.textContent=new Date().toLocaleTimeString('fr-FR')+' UTC+'+(-new Date().getTimezoneOffset()/60);}
  tick();setInterval(tick,1000);
})();

// ---- bandeau "données au…" injecté en tête de CHAQUE onglet ----
const SECTION_ASOF={dash:(DATA.dashboard||{}).as_of,themes:(DATA.themes||{}).as_of,
  ml:(DATA.dashboard||{}).as_of,uni:(DATA.universe||{}).as_of,data:(DATA.data||{}).as_of,
  pf:(DATA.dashboard||{}).as_of,pos:(DATA.dashboard||{}).as_of,trades:(DATA.dashboard||{}).as_of,
  live:(DATA.dashboard||{}).as_of};
function freshnessChip(pageId){
  const M=DATA.meta||{},asof=SECTION_ASOF[pageId]||M.last_bar;
  return $(`<div class="asof">⟳ Données au <b>${fmtTS(asof)}</b> · différé ${M.delay_minutes||15} min · snapshot généré ${fmtTS(M.generated_at)} · mode <b>${M.mode||'synthetic'}</b></div>`);
}

// ---- compteur animé ----
function countUp(el,target,suffix,dur=700){
  const start=performance.now();const from=0;
  function step(now){const k=Math.min(1,(now-start)/dur);
    el.textContent=(from+(target-from)*k).toFixed(2).replace(/\.00$/,'')+(suffix||'');
    if(k<1)requestAnimationFrame(step);}
  requestAnimationFrame(step);
}

// ---- courbe interactive (axes prix+temps, dégradé, valeurs de fin, crosshair + tooltip) ----
const fmtDate=(s)=>{const v=String(s);return /^\d{4}-/.test(v)?v.slice(0,10):('Jour '+v);};
let _chartUID=0;
function lineChart(series,labels,title){
  const W=860,H=240,padL=46,padR=64,padT=10,padB=24,uid='c'+(++_chartUID);
  const all=[].concat(...series.map(s=>s.data));
  const lo=Math.min(...all),hi=Math.max(...all),rng=(hi-lo)||1;
  const n=series[0].data.length;
  const X=i=>padL+i*(W-padL-padR)/(n-1), Y=v=>(H-padB)-(v-lo)/rng*((H-padB)-padT);
  const poly=(d,c,w)=>`<polyline points="${d.map((v,i)=>X(i).toFixed(1)+','+Y(v).toFixed(1)).join(' ')}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linejoin="round"/>`;
  // dégradé sous la 1re série (portefeuille)
  const d0=series[0].data;
  const area=`<defs><linearGradient id="g${uid}" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="${series[0].color}" stop-opacity=".22"/>
    <stop offset="100%" stop-color="${series[0].color}" stop-opacity="0"/></linearGradient></defs>
    <polygon points="${X(0).toFixed(1)},${(H-padB)} ${d0.map((v,i)=>X(i).toFixed(1)+','+Y(v).toFixed(1)).join(' ')} ${X(n-1).toFixed(1)},${(H-padB)}" fill="url(#g${uid})"/>`;
  let yAxis='';
  for(let k=0;k<4;k++){const v=lo+k/3*(hi-lo),y=Y(v);
    yAxis+=`<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W-padR}" y2="${y.toFixed(1)}" stroke="var(--border)" stroke-width="1"/>`
      +`<text x="${padL-6}" y="${(y+3).toFixed(1)}" fill="var(--muted)" font-size="10" text-anchor="end">${v.toFixed(0)}</text>`;
  }
  let xAxis='';
  for(let k=0;k<5;k++){const i=Math.round(k/4*(n-1)),x=X(i);
    xAxis+=`<text x="${x.toFixed(1)}" y="${H-6}" fill="var(--muted)" font-size="10" text-anchor="${k===0?'start':k===4?'end':'middle'}">${fmtDate(labels?labels[i]:i)}</text>`;
  }
  // valeurs de FIN (dernier point) → toujours visibles, à droite de chaque courbe
  const endLabels=series.map(s=>{const v=s.data[n-1],y=Y(v);
    return `<text x="${W-padR+5}" y="${(y+3).toFixed(1)}" fill="${s.color}" font-size="11" font-weight="600">${v.toFixed(1)}</text>`
      +`<circle cx="${X(n-1).toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="${s.color}"/>`;}).join('');
  const wrap=$(`<div class="chartWrap card" style="position:relative">
    <div class="banner" style="margin-bottom:8px"><div class="label">${title||'Performance'}</div>
      <div style="display:flex;gap:14px;font-size:11px;color:var(--muted)">
      ${series.map(s=>`<span><span style="color:${s.color}">●</span> ${s.name}</span>`).join('')}</div></div>
    <svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" style="overflow:visible" preserveAspectRatio="none">
      ${area}${yAxis}${xAxis}
      ${series.map(s=>poly(s.data,s.color,s.w)).join('')}${endLabels}
      <line class="cx" x1="0" y1="${padT}" x2="0" y2="${H-padB}" stroke="#5b6675" stroke-width="1" opacity="0"/>
      ${series.map(s=>`<circle class="cd cd-${series.indexOf(s)}" r="3.5" fill="${s.color}" opacity="0"/>`).join('')}
      <rect class="ov" x="0" y="0" width="${W}" height="${H}" fill="transparent" style="cursor:crosshair"/>
    </svg><div class="tip" id="tip"></div></div>`);
  setTimeout(()=>{
    const svg=wrap.querySelector('svg'),ov=wrap.querySelector('.ov'),
      cx=wrap.querySelector('.cx'),cds=wrap.querySelectorAll('.cd'),tip=wrap.querySelector('.tip');
    function show(i){
      i=Math.max(0,Math.min(n-1,i));const x=X(i);
      cx.setAttribute('x1',x);cx.setAttribute('x2',x);cx.setAttribute('opacity','.55');
      cds.forEach((cd,k)=>{cd.setAttribute('cx',x);cd.setAttribute('cy',Y(series[k].data[i]));cd.setAttribute('opacity','1');});
      const r=svg.getBoundingClientRect(),px=x/W*r.width,flip=px>r.width*0.6;
      tip.style.opacity=1;tip.style.top='8px';
      tip.style.left=(flip?Math.max(6,px-tip.offsetWidth-14):px+14)+'px';
      tip.innerHTML=`<b>${fmtDate(labels?labels[i]:i)}</b><br>`+
        series.map(s=>`<span style="color:${s.color}">●</span> ${s.name}: <b>${s.data[i].toFixed(2)}</b>`).join('<br>');
    }
    ov.addEventListener('pointermove',e=>{const r=svg.getBoundingClientRect();
      show(Math.round(((e.clientX-r.left)/r.width*W-padL)/((W-padL-padR)/(n-1))));});
    ov.addEventListener('pointerleave',()=>{cx.setAttribute('opacity','0');cds.forEach(cd=>cd.setAttribute('opacity','0'));tip.style.opacity=0;});
    show(n-1);  // état initial = point le PLUS RÉCENT (toujours visible au chargement)
  },60);
  return wrap;
}

// ---- graphique TECHNIQUE en chandeliers + indicateurs (modale au clic sur un ticker) ----
// Autonome (vanilla SVG) — même esprit que TradingView lightweight-charts, sans dépendance.
function _sma(a,p){const o=Array(a.length).fill(null);let s=0;for(let i=0;i<a.length;i++){s+=a[i];if(i>=p)s-=a[i-p];if(i>=p-1)o[i]=s/p;}return o;}
function _ema(a,p){const o=Array(a.length).fill(null),k=2/(p+1);let e=a[0];for(let i=0;i<a.length;i++){e=i?a[i]*k+e*(1-k):a[i];if(i>=p-1)o[i]=e;}return o;}
function _rsi(a,p){const o=Array(a.length).fill(null);let g=0,l=0;for(let i=1;i<a.length;i++){const d=a[i]-a[i-1];const up=Math.max(d,0),dn=Math.max(-d,0);if(i<=p){g+=up;l+=dn;if(i===p){g/=p;l/=p;o[i]=100-100/(1+(l?g/l:99));}}else{g=(g*(p-1)+up)/p;l=(l*(p-1)+dn)/p;o[i]=100-100/(1+(l?g/l:99));}}return o;}
function _boll(a,p,k){const m=_sma(a,p),u=[],lo=[];for(let i=0;i<a.length;i++){if(m[i]==null){u.push(null);lo.push(null);continue;}let s=0;for(let j=i-p+1;j<=i;j++)s+=(a[j]-m[i])**2;const sd=Math.sqrt(s/p);u.push(m[i]+k*sd);lo.push(m[i]-k*sd);}return{m,u,lo};}

// agrège un historique daily en weekly/monthly (o=1er, h=max, l=min, c=dernier, v=somme)
function _agg(data,tf){
  if(tf==='D')return data;
  const wk=(s)=>{const d=new Date(s);d.setDate(d.getDate()-((d.getDay()+6)%7));return d.toISOString().slice(0,10);};
  const key=tf==='M'?(d=>d.t.slice(0,7)):(d=>wk(d.t));
  const out=[],m={};
  data.forEach(d=>{const k=key(d);if(!m[k]){m[k]={t:d.t,o:d.o,h:d.h,l:d.l,c:d.c,v:d.v||0};out.push(m[k]);}
    else{const b=m[k];b.h=Math.max(b.h,d.h);b.l=Math.min(b.l,d.l);b.c=d.c;b.t=d.t;b.v+=d.v||0;}});
  return out;
}
function candleChart(sym,state){
  let data=_agg((DATA.dashboard.position_series||{})[sym]||[], state.tf);
  if(!data.length)return $('<p style="color:var(--muted)">Pas de série disponible.</p>');
  const cap={D:200,W:200,M:160}[state.tf]||200; if(data.length>cap)data=data.slice(-cap);
  const closes=data.map(d=>d.c),n=data.length;
  const W=860,padL=52,padR=60,padT=10,hp=260,hv=state.vol?56:0,g1=hv?8:0,
    hr=state.rsi?80:0,g2=hr?8:0,xb=20,H=padT+hp+g1+hv+g2+hr+xb;
  const ov=[];
  if(state.ma20)ov.push(['MM20',_sma(closes,20),'#3b82f6']);
  if(state.ma50)ov.push(['MM50',_sma(closes,50),'#f59e0b']);
  if(state.ma100)ov.push(['MM100',_sma(closes,100),'#a78bfa']);
  if(state.ma200)ov.push(['MM200',_sma(closes,200),'#e879f9']);
  if(state.ema20)ov.push(['EMA20',_ema(closes,20),'#22d3ee']);
  if(state.boll){const bb=_boll(closes,20,2);ov.push(['BB+',bb.u,'#9aa1ad'],['BB-',bb.lo,'#9aa1ad']);}
  const hi=Math.max(...data.map(d=>d.h),...ov.flatMap(o=>o[1].filter(v=>v!=null)));
  const lo=Math.min(...data.map(d=>d.l),...ov.flatMap(o=>o[1].filter(v=>v!=null)));
  const rng=(hi-lo)||1,cw=(W-padL-padR)/n,pb=padT+hp;
  const X=i=>padL+i*cw+cw/2, Y=v=>pb-(v-lo)/rng*(hp-8);
  // axe Y prix (échelle de montant)
  let yA='';for(let k=0;k<5;k++){const v=lo+k/4*(hi-lo),y=Y(v);
    yA+=`<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W-padR}" y2="${y.toFixed(1)}" stroke="var(--border)" stroke-width="1"/><text x="${padL-6}" y="${(y+3).toFixed(1)}" fill="var(--muted)" font-size="10" text-anchor="end">${v.toFixed(2)}</text>`;}
  // chandeliers
  let candles='';data.forEach((d,i)=>{const up=d.c>=d.o,col=up?'#22c55e':'#f43f5e',x=X(i);
    candles+=`<line x1="${x.toFixed(1)}" y1="${Y(d.h).toFixed(1)}" x2="${x.toFixed(1)}" y2="${Y(d.l).toFixed(1)}" stroke="${col}" stroke-width="1"/>`
      +`<rect x="${(x-cw*0.32).toFixed(1)}" y="${Y(Math.max(d.o,d.c)).toFixed(1)}" width="${Math.max(1,cw*0.64).toFixed(1)}" height="${Math.max(1,Math.abs(Y(d.o)-Y(d.c))).toFixed(1)}" fill="${col}"/>`;});
  const ovl=ov.map(o=>`<polyline points="${o[1].map((v,i)=>v==null?'':X(i).toFixed(1)+','+Y(v).toFixed(1)).filter(Boolean).join(' ')}" fill="none" stroke="${o[2]}" stroke-width="1.3" opacity="0.9"/>`).join('');
  // MARQUEURS achat/vente (▲ vert sous le plus bas, ▼ rouge au-dessus du plus haut)
  const idxByDate=t=>{for(let i=0;i<n;i++)if(data[i].t>=t)return i;return n-1;};
  let marks='';
  ((DATA.dashboard.position_markers||{})[sym]||[]).forEach(mk=>{
    if(mk.t<data[0].t)return;const i=idxByDate(mk.t),x=X(i);
    if(mk.side==='buy'){const y=Y(data[i].l)+12;marks+=`<polygon points="${x},${(y-7).toFixed(1)} ${(x-4).toFixed(1)},${y.toFixed(1)} ${(x+4).toFixed(1)},${y.toFixed(1)}" fill="#22c55e"/>`;}
    else{const y=Y(data[i].h)-12;marks+=`<polygon points="${x},${(y+7).toFixed(1)} ${(x-4).toFixed(1)},${y.toFixed(1)} ${(x+4).toFixed(1)},${y.toFixed(1)}" fill="#f43f5e"/>`;}
  });
  // volumes
  let vol='';if(state.vol){const vbot=pb+g1+hv,maxv=Math.max(...data.map(d=>d.v||0),1);
    data.forEach((d,i)=>{const x=X(i),hh=(d.v||0)/maxv*(hv-4);
      vol+=`<rect x="${(x-cw*0.32).toFixed(1)}" y="${(vbot-hh).toFixed(1)}" width="${Math.max(1,cw*0.64).toFixed(1)}" height="${hh.toFixed(1)}" fill="${d.c>=d.o?'#22c55e':'#f43f5e'}" opacity="0.5"/>`;});
    vol+=`<text x="${padL}" y="${(pb+g1+10).toFixed(1)}" fill="var(--muted)" font-size="9">Volume</text>`;}
  // RSI
  let rsiSvg='';if(state.rsi){const r=_rsi(closes,14),rtop=pb+g1+hv+g2,rbot=rtop+hr,YR=v=>rbot-(v/100)*hr;
    rsiSvg=`<line x1="${padL}" y1="${YR(70).toFixed(1)}" x2="${W-padR}" y2="${YR(70).toFixed(1)}" stroke="#f43f5e" stroke-width="0.6" stroke-dasharray="3"/>`
      +`<line x1="${padL}" y1="${YR(30).toFixed(1)}" x2="${W-padR}" y2="${YR(30).toFixed(1)}" stroke="#22c55e" stroke-width="0.6" stroke-dasharray="3"/>`
      +`<polyline points="${r.map((v,i)=>v==null?'':X(i).toFixed(1)+','+YR(v).toFixed(1)).filter(Boolean).join(' ')}" fill="none" stroke="#a78bfa" stroke-width="1.2"/>`
      +`<text x="${padL}" y="${(rtop+10).toFixed(1)}" fill="var(--muted)" font-size="9">RSI 14</text>`;}
  // axe X (échelle de temps)
  let xA='';for(let k=0;k<6;k++){const i=Math.round(k/5*(n-1)),x=X(i);
    xA+=`<text x="${x.toFixed(1)}" y="${H-6}" fill="var(--muted)" font-size="9" text-anchor="${k===0?'start':k===5?'end':'middle'}">${data[i].t}</text>`;}
  const last=data[n-1],chg=(last.c/data[0].c-1)*100;
  return $(`<div>
    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px">
      <div><b style="font-size:15px">${sym}</b> <span class="mono">${last.c}</span>
        <span class="mono" style="color:${chg>=0?'#22c55e':'#f43f5e'}">${chg>=0?'+':''}${chg.toFixed(1)}%</span>
        <span style="color:var(--muted);font-size:11px">${data[0].t} → ${last.t}</span></div>
      <div style="font-size:11px;color:var(--muted)">▲ achat · ▼ vente · ${ov.map(o=>'<span style="color:'+o[2]+'">●</span> '+o[0]).join(' ')}</div></div>
    <svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" style="overflow:visible">${yA}${vol}${candles}${ovl}${marks}${rsiSvg}${xA}</svg></div>`);
}
function openChart(sym){
  const state={tf:'D',vol:true,ma20:true,ma50:true,ma100:false,ma200:false,ema20:false,boll:false,rsi:true};
  const ov=$('<div class="modal"></div>');
  const box=$('<div class="modalbox card"></div>');
  const head=$(`<div class="banner" style="margin-bottom:10px"><div class="label">Graphique technique — ${sym}</div>
    <span class="close" title="Fermer (Échap)">✕</span></div>`);
  const tfbar=$('<div style="display:flex;gap:6px;margin-bottom:8px"></div>');
  const toggles=$('<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px"></div>');
  const body=$('<div></div>');
  function draw(){body.innerHTML='';body.appendChild(candleChart(sym,state));}
  [['D','Daily'],['W','Weekly'],['M','Monthly']].forEach(([k,lab])=>{
    const ch=$(`<span class="chip${state.tf===k?' on':''}">${lab}</span>`);
    ch.onclick=()=>{state.tf=k;tfbar.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));ch.classList.add('on');draw();};
    tfbar.appendChild(ch);});
  [['vol','Volume'],['ma20','MM20'],['ma50','MM50'],['ma100','MM100'],['ma200','MM200'],['ema20','EMA20'],['boll','Bollinger'],['rsi','RSI']].forEach(([k,lab])=>{
    const ch=$(`<span class="chip${state[k]?' on':''}">${lab}</span>`);
    ch.onclick=()=>{state[k]=!state[k];ch.classList.toggle('on');draw();};toggles.appendChild(ch);});
  head.querySelector('.close').onclick=()=>ov.remove();
  ov.onclick=e=>{if(e.target===ov)ov.remove();};
  document.addEventListener('keydown',function esc(e){if(e.key==='Escape'){ov.remove();document.removeEventListener('keydown',esc);}});
  box.appendChild(head);box.appendChild(tfbar);box.appendChild(toggles);box.appendChild(body);ov.appendChild(box);
  document.body.appendChild(ov);draw();
}
// délégation : tout symbole .tkr (positions, trades en cours, portefeuille réel) ouvre son graphe
document.addEventListener('click',e=>{const t=e.target.closest('.tkr');if(t&&t.dataset.sym)openChart(t.dataset.sym);});
const tkr=(s)=>`<b class="tkr" data-sym="${s}" title="Voir le graphique technique">${s}</b>`;
// bandeau KPI de valeur de portefeuille (réutilisé Trades + Portefeuille réel)
function portfolioBar(k){
  const pos=(k.pnl_abs||0)>=0,col=pos?'#22c55e':'#f43f5e';
  const cell=(lab,val,c)=>`<div><div class="label">${lab}</div><div class="val" style="font-size:20px;${c?'color:'+c:''}">${val}</div></div>`;
  return $(`<div class="card"><div class="grid4" style="gap:14px">
    ${cell('Valeur du portefeuille','$'+eur(k.value||0))}
    ${cell('Gain / perte',(pos?'+':'')+'$'+eur(k.pnl_abs||0)+' ('+(pos?'+':'')+((k.pnl_pct||0)*100).toFixed(1)+'%)',col)}
    ${cell('Investi / Cash','$'+eur(k.invested||0)+' / $'+eur(k.cash||0))}
    ${cell('Exposition',((k.exposure_pct||0)*100).toFixed(0)+'% · '+(k.n_positions||0)+' lignes')}
    </div><div style="font-size:11px;color:var(--muted);margin-top:8px">Capital initial $${eur(k.initial||10000)} → objectif : surperformer le benchmark. Sans levier (exposition ≤ 100%, cash ≥ 0).</div></div>`);
}

// ---- DASHBOARD ----
(function(){
 try{
  const d=DATA.dashboard,m=d.metrics,p=document.getElementById('dash');
  const c=CYC[d.regime.cycle]||'#9aa1ab';
  const vp=d.vix_playbook||{regime:'',color:'#9aa1ad',exposure:1,action:''};
  p.appendChild($(`<div class="card banner">
    <div><span class="dot" style="background:${c}"></span>
    <b style="text-transform:capitalize">${d.regime.cycle}</b>
    <span style="color:var(--muted)">· ${d.regime.risk_mode}</span></div>
    <div class="mono" style="color:var(--muted);font-size:13px">
    courbe 2s10s ${d.regime.extras.curve_2s10s} · VIX ${(d.vix||0).toFixed(1)} · exposition ×${vp.exposure}</div></div>`));
  // Playbook volatilité (VIX) — règles d'exposition
  p.appendChild($(`<div class="card" style="border-color:${vp.color}40">
    <div class="banner" style="margin-bottom:6px">
      <div class="label">Playbook volatilité — VIX <b style="color:${vp.color};font-size:14px">${(d.vix||0).toFixed(1)}</b>
        <span class="pill" style="color:${vp.color};margin-left:6px">${vp.regime}</span></div>
      <div style="font-size:11px;color:var(--muted)">exposition pilotée <b style="color:var(--fg)">×${vp.exposure}</b></div></div>
    <div style="font-size:12.5px;color:var(--muted)">${vp.action}</div>
    <div style="display:flex;gap:4px;margin-top:8px;font-size:10px">
      <span class="pill" style="color:#22c55e">&lt;13 risk-on ×1.2</span>
      <span class="pill" style="color:#3b82f6">13–20 neutre</span>
      <span class="pill" style="color:#f59e0b">20–30 réduit</span>
      <span class="pill" style="color:#f43f5e">&gt;30 défensif ×0.3</span></div></div>`));
  const g=$('<div class="grid4"></div>');
  const cards=[['Rendement',m.total_return,'%',m.total_return>=0?'pos':'neg'],
    ['Sharpe',m.sharpe,'',''],['Sortino',m.sortino,'',''],['Max DD',m.max_drawdown,'%','neg']];
  cards.forEach(([lab,val,suf,tone])=>{
    const card=$(`<div class="card metric"><div class="label">${lab}</div><div class="val ${tone}"></div></div>`);
    g.appendChild(card);countUp(card.querySelector('.val'),suf==='%'?val*100:val,suf);
  });
  p.appendChild(g);
  // courbe equity vs benchmarks (axe temps = dates réelles, valeurs de fin visibles)
  const b=DATA.portfolio.benchmarks;
  const ser=[{name:'Portefeuille',data:b.portfolio,color:'#3b82f6',w:2.2}];
  if(b['Univers (équipondéré)'])ser.push({name:'Univers (équipondéré)',data:b['Univers (équipondéré)'],color:'#9aa1ad',w:1.4});
  if(b['S&P 500'])ser.push({name:'S&P 500',data:b['S&P 500'],color:'#5b6675',w:1.2});
  p.appendChild(lineChart(ser,d.dates,'Performance — Portefeuille vs benchmarks (rebasé 100)'));
  const MZ=DATA.meta||{};
  p.appendChild($(`<div style="font-size:11px;color:var(--muted);margin-top:-6px">
    ⓘ Capital initial <b style="color:var(--fg)">${(MZ.initial_capital||10000).toLocaleString('fr-FR')} \$</b> alloué aux
    <b style="color:var(--fg)">meilleurs setups</b> (tri par force relative, exposition pilotée par le VIX) sur
    <b style="color:var(--fg)">${MZ.traded_assets||0} actifs</b> de l'univers (${MZ.universe_size||0} suivis),
    du ${fmtTS(MZ.period_start).slice(0,10)} au ${fmtTS(MZ.last_bar).slice(0,10)} · ${(MZ.n_trades||0).toLocaleString('fr-FR')} trades.
    Profil <b style="color:var(--fg)">${MZ.profile||''}</b> — objectif : surperformer l'univers équipondéré.</div>`));
  // screener cliquable — table construite en UNE chaîne HTML complète (sinon les <tr> isolés sont supprimés par le navigateur)
  const sc=DATA.screener;
  let rowsHtml='';
  sc.rows.slice(0,8).forEach((r,idx)=>{
    let facHtml='';
    Object.entries(r.factors||{}).forEach(([f,v])=>{
      const w=Math.min(100,Math.abs(v)*120);
      facHtml+=`<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:12px">
        <span style="width:90px;color:var(--muted)">${f}</span>
        <span class="facbar" style="width:${w}px;background:${v>=0?'#22c55e':'#ef4444'}"></span>
        <span class="mono">${v.toFixed(3)}</span></div>`;
    });
    const ml=r.ml_score==null?'—':(r.ml_score*100).toFixed(0)+'%';
    const mlc=r.ml_score==null?'var(--muted)':(r.ml_score>=0.5?'#22c55e':'#f43f5e');
    rowsHtml+=`<tr class="srow" data-i="${idx}"><td style="color:var(--muted)">${r.rank}</td><td><b>${r.symbol}</b></td>
      <td style="color:var(--muted);font-size:11px">${r.sector||''}</td>
      <td class="mono" style="text-align:right">${r.score.toFixed(3)}</td>
      <td class="mono" style="text-align:right;color:${mlc}">${ml}</td>
      <td style="padding-left:14px;color:var(--muted)">${r.reason||''}</td></tr>
      <tr class="sdet" data-i="${idx}" style="display:none"><td colspan="6" style="border:none;padding-top:0">${facHtml}</td></tr>`;
  });
  const box=$(`<div class="card"><div class="label" style="margin-bottom:10px">Top screener — multi-actifs (score facteurs + edge ML · clique une ligne)</div>
    <table><thead><tr><th>#</th><th>Actif</th><th>Secteur</th><th style="text-align:right">Score</th><th style="text-align:right">ML</th><th style="padding-left:14px">Raison</th></tr></thead><tbody>${rowsHtml}</tbody></table></div>`);
  p.appendChild(box);
  makeSortable(box.querySelector('table'));   // screener triable (par paires ligne+détail)
  // câblage des clics APRÈS injection
  box.querySelectorAll('tr.srow').forEach(tr=>{
    tr.addEventListener('click',()=>{
      const det=box.querySelector('tr.sdet[data-i="'+tr.dataset.i+'"]');
      if(det)det.style.display=det.style.display==='none'?'':'none';
    });
  });
 }catch(e){console.error('rendu dashboard:',e);}
})();

// ---- PORTEFEUILLE ----
(function(){
 try{
  const a=DATA.portfolio.analysis,p=document.getElementById('pf');if(!a)return;
  const rel=a.relative,rm=a.risk;
  const relRows=Object.entries(rel).map(([k,v])=>`<tr><td style="color:var(--muted)">${k}</td><td class="mono" style="text-align:right">${v}</td></tr>`).join('');
  p.appendChild($(`<div class="grid2">
    <div class="card"><div class="label" style="margin-bottom:8px">Mesures relatives (vs univers équipondéré)</div>
      <table><tbody>${relRows}</tbody></table></div>
    <div class="card"><div class="label" style="margin-bottom:8px">Risque (FRM)</div>
      <div class="grid2" style="gap:10px">
      <div><div style="color:var(--muted);font-size:12px">VaR 95%</div><div style="font-size:18px">${pct(rm.var_95)}</div></div>
      <div><div style="color:var(--muted);font-size:12px">CVaR 95%</div><div style="font-size:18px">${pct(rm.cvar_95)}</div></div>
      <div><div style="color:var(--muted);font-size:12px">Vol</div><div style="font-size:18px">${pct(rm.vol)}</div></div>
      <div><div style="color:var(--muted);font-size:12px">Proba ruine (MC)</div><div style="font-size:18px">${pct(a.monte_carlo.p_ruin)}</div></div>
      </div></div></div>`));
  // modèles de risque avancés (GARCH, backtest VaR Kupiec, ACP, Sharpe déflaté)
  (function(){
    const g=rm.garch,vb=rm.var_backtest,fr=rm.factor_risk;
    if(!(g||vb||fr||rm.psr!=null))return;
    const cells=[];
    if(rm.var_cornish_fisher_95!=null)cells.push(['VaR Cornish-Fisher',pct(rm.var_cornish_fisher_95)]);
    if(g&&g.available)cells.push(['Vol prévue (GARCH)',pct(g.forecast_vol)]);
    if(vb)cells.push(['Backtest VaR (Kupiec)',vb.pass?'validé':'rejeté']);
    if(fr&&fr.available)cells.push(['Risque systématique',pct(fr.systematic_pct)]);
    if(rm.psr!=null)cells.push(['Sharpe probabiliste',pct(rm.psr)]);
    if(rm.dsr!=null)cells.push(['Sharpe déflaté',pct(rm.dsr)]);
    const inner=cells.map(([l,v])=>`<div><div style="color:var(--muted);font-size:12px">${l}</div><div style="font-size:18px">${v}</div></div>`).join('');
    p.appendChild($(`<div class="card"><div class="label" style="margin-bottom:8px">Modèles de risque</div><div class="grid4" style="gap:10px">${inner}</div></div>`));
  })();
  // projection Monte-Carlo INTERACTIVE (survol = percentiles à l'horizon pointé)
  const mp=a.mc_projection;
  if(mp&&mp.steps&&mp.steps.length){
    const W=860,H=210,padL=46,padR=70,padT=10,padB=22,m=mp.steps.length;
    const all=mp.p5.concat(mp.p95),lo=Math.min(...all,100),hi=Math.max(...all),rng=(hi-lo)||1;
    const X=i=>padL+i*(W-padL-padR)/(m-1),Y=v=>(H-padB)-(v-lo)/rng*((H-padB)-padT);
    const band=mp.p95.map((v,i)=>X(i).toFixed(1)+','+Y(v).toFixed(1)).join(' ')+' '+
      mp.p5.map((v,i)=>X(m-1-i).toFixed(1)+','+Y(mp.p5[m-1-i]).toFixed(1)).join(' ');
    const band2=mp.p75.map((v,i)=>X(i).toFixed(1)+','+Y(v).toFixed(1)).join(' ')+' '+
      mp.p25.map((v,i)=>X(m-1-i).toFixed(1)+','+Y(mp.p25[m-1-i]).toFixed(1)).join(' ');
    const line=(arr,c,w)=>`<polyline points="${arr.map((v,i)=>X(i).toFixed(1)+','+Y(v).toFixed(1)).join(' ')}" fill="none" stroke="${c}" stroke-width="${w}"/>`;
    let yA='';for(let k=0;k<4;k++){const v=lo+k/3*(hi-lo),y=Y(v);yA+=`<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W-padR}" y2="${y.toFixed(1)}" stroke="var(--border)" stroke-width="1"/><text x="${padL-6}" y="${(y+3).toFixed(1)}" fill="var(--muted)" font-size="10" text-anchor="end">${v.toFixed(0)}</text>`;}
    const endL=[['p95',mp.p95,'#22c55e'],['méd.',mp.p50,'#3b82f6'],['p5',mp.p5,'#f43f5e']]
      .map(([nm,arr,c])=>`<text x="${W-padR+5}" y="${(Y(arr[m-1])+3).toFixed(1)}" fill="${c}" font-size="11" font-weight="600">${arr[m-1].toFixed(0)}</text>`).join('');
    const card=$(`<div class="card chartWrap"><div class="banner" style="margin-bottom:8px">
      <div class="label">Projection Monte-Carlo — éventail à 1 an (base 100, ${mp.horizon} j ouvrés · survole)</div>
      <div style="font-size:11px;color:var(--muted)">médiane <b style="color:#3b82f6">${mp.final_p50}</b> · p5 <b style="color:#f43f5e">${mp.final_p5}</b> · p95 <b style="color:#22c55e">${mp.final_p95}</b></div></div>
      <svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" style="overflow:visible">
        ${yA}<polygon points="${band}" fill="#3b82f6" fill-opacity="0.10"/><polygon points="${band2}" fill="#3b82f6" fill-opacity="0.16"/>
        ${line(mp.p25,'#3b82f6',0.7)}${line(mp.p75,'#3b82f6',0.7)}${line(mp.p50,'#3b82f6',2)}${endL}
        <line class="mcx" x1="0" y1="${padT}" x2="0" y2="${H-padB}" stroke="#5b6675" stroke-width="1" opacity="0"/>
        <rect class="mov" x="0" y="0" width="${W}" height="${H}" fill="transparent" style="cursor:crosshair"/>
      </svg><div class="tip mctip"></div>
      <div style="font-size:11px;color:var(--muted);margin-top:8px;line-height:1.5">
        <b style="color:var(--fg)">Comment lire</b> : 1000 futurs simulés par rééchantillonnage des rendements passés (base 100 = aujourd'hui).
        La <b style="color:#3b82f6">médiane</b> est le scénario central ; la bande foncée = 50 % des cas (p25–p75), la claire = 90 % (p5–p95).
        Ex. à 1 an : la moitié des trajectoires finissent au-dessus de <b>${mp.final_p50}</b> ; il n'y a ~5 % de chance de faire pire que <b style="color:#f43f5e">${mp.final_p5}</b> ou mieux que <b style="color:#22c55e">${mp.final_p95}</b>. Plus le cône est large, plus l'incertitude est grande.</div></div>`);
    p.appendChild(card);
    setTimeout(()=>{const svg=card.querySelector('svg'),ov=card.querySelector('.mov'),cx=card.querySelector('.mcx'),tip=card.querySelector('.mctip');
      ov.addEventListener('pointermove',e=>{const r=svg.getBoundingClientRect();let i=Math.round(((e.clientX-r.left)/r.width*W-padL)/((W-padL-padR)/(m-1)));i=Math.max(0,Math.min(m-1,i));
        const x=X(i),px=x/W*r.width,flip=px>r.width*0.62;cx.setAttribute('x1',x);cx.setAttribute('x2',x);cx.setAttribute('opacity','.55');
        tip.style.opacity=1;tip.style.top='8px';tip.style.left=(flip?Math.max(6,px-tip.offsetWidth-14):px+14)+'px';
        tip.innerHTML=`<b>Horizon J+${mp.steps[i]}</b><br><span style="color:#22c55e">p95</span> ${mp.p95[i]}<br><span style="color:#3b82f6">médiane</span> ${mp.p50[i]}<br><span style="color:#f43f5e">p5</span> ${mp.p5[i]}`;});
      ov.addEventListener('pointerleave',()=>{cx.setAttribute('opacity','0');tip.style.opacity=0;});},60);
  }
  // heatmap interactive — table construite en UNE chaîne HTML complète
  const co=a.correlation;
  const headHtml='<tr><th></th>'+co.symbols.map(s=>`<th>${s}</th>`).join('')+'</tr>';
  let bodyHtml='';
  co.matrix.forEach((row,i)=>{
    bodyHtml+=`<tr><th style="text-align:right;color:var(--muted)">${co.symbols[i]}</th>`+
      row.map((v,j)=>{
        const r=Math.round(120+100*Math.max(0,v)),bl=Math.round(120+100*Math.max(0,-v));
        return `<td style="background:rgb(${r},100,${bl})" title="${co.symbols[i]} × ${co.symbols[j]} : ${v.toFixed(2)}">${v.toFixed(2)}</td>`;
      }).join('')+'</tr>';
  });
  const heat=$(`<div class="card" id="chartWrap"><div class="label" style="margin-bottom:6px">Corrélation (survole une case)</div>
    <div style="margin-bottom:8px">${co.clusters.map(c=>'<span class="pill" style="margin-right:6px">'+c.join(' · ')+'</span>').join('')}</div>
    <table class="heat"><thead>${headHtml}</thead><tbody>${bodyHtml}</tbody></table></div>`);
  p.appendChild(heat);
  // budget de risque + limites de concentration
  const rb=a.risk_budget,lim=a.limits;
  if(rb&&rb.symbols&&rb.symbols.length){
    const mx=Math.max(0.01,...rb.contrib_pct);
    const bars=rb.symbols.map((s,i)=>`<div style="display:flex;align-items:center;gap:8px;font-size:12px;margin-bottom:6px">
      <span class="mono" style="width:64px">${s}</span>
      <span style="height:8px;border-radius:4px;background:var(--accent);width:${Math.round(rb.contrib_pct[i]/mx*100)}%;max-width:360px"></span>
      <span class="mono" style="color:var(--muted)">${(rb.contrib_pct[i]*100).toFixed(1)}%</span></div>`).join('');
    const cd=rb.covariance_diagnostics||{};
    const kcol=(cd.cond_used<50)?'#22c55e':(cd.cond_used<500)?'#f59e0b':'#ef4444';
    const kappa=(cd.cond_used!=null)?`<div class="mono" style="font-size:11px;margin-top:2px" title="Nombre de condition de la covariance (avant → après shrinkage Ledoit-Wolf). Vert <50 (stable), ambre <500, rouge >500 (risque mal estimé)."><span style="color:var(--muted)">κ ${Math.round(cd.cond_raw)} → </span><span style="color:${kcol};font-weight:600">${Math.round(cd.cond_used)}</span>${cd.delta>0?`<span style="color:var(--muted)"> · shrinkage ${Math.round(cd.delta*100)}%</span>`:''}</div>`:'';
    p.appendChild($(`<div class="card"><div style="display:flex;justify-content:space-between;align-items:center">
      <div class="label">Budget de risque (contribution à la vol)</div>
      <div class="mono" style="font-size:12px;color:var(--muted)">vol ${pct(rb.portfolio_vol)} · diversif ×${rb.diversification_ratio}</div></div>
      ${kappa}
      <div style="margin-top:10px">${bars}</div></div>`));
  }
  if(lim){
    const br=lim.breaches.map(b=>`<div style="display:flex;justify-content:space-between;color:var(--warn);font-size:12px">
      <span>⚠️ ${b.type} — ${b.label}</span><span class="mono">${(b.weight*100).toFixed(1)}% &gt; ${(b.limit*100).toFixed(0)}%</span></div>`).join('');
    p.appendChild($(`<div class="card"><div style="display:flex;justify-content:space-between;align-items:center">
      <div class="label">Concentration &amp; limites</div>
      <div class="mono" style="font-size:12px">HHI ${lim.hhi} · N eff. ${lim.effective_n} ·
      <span style="color:${lim.ok?'#22c55e':'#f59e0b'}">${lim.ok?'conforme':lim.breaches.length+' dépassement(s)'}</span></div></div>
      ${br?'<div style="margin-top:8px">'+br+'</div>':''}</div>`));
  }
  // backtest multi-stratégie (indice équipondéré)
  const ms=a.multi_strategy;
  if(ms&&ms.available){
    const mrows=[...ms.strategies,ms.combined].map(s=>`<tr><td>${s.name}</td>
      <td class="mono" style="text-align:right;color:${s.total_return>=0?'#22c55e':'#f43f5e'}">${(s.total_return*100).toFixed(1)}%</td>
      <td class="mono" style="text-align:right">${s.sharpe}</td>
      <td class="mono" style="text-align:right;color:#f43f5e">${(s.max_drawdown*100).toFixed(1)}%</td>
      <td class="mono" style="text-align:right;color:var(--muted)">${(s.exposure*100).toFixed(0)}%</td></tr>`).join('');
    p.appendChild($(`<div class="card"><div style="display:flex;justify-content:space-between;align-items:center">
      <div class="label">Backtest multi-stratégie (indice équipondéré)</div>
      <div style="font-size:12px;color:var(--muted)">meilleure : <b style="color:var(--fg)">${ms.best}</b></div></div>
      <table style="width:100%;font-size:13px;margin-top:8px"><thead><tr><th style="text-align:left">Stratégie</th>
      <th style="text-align:right">Rendement</th><th style="text-align:right">Sharpe</th>
      <th style="text-align:right">Max DD</th><th style="text-align:right">Expo.</th></tr></thead><tbody>${mrows}</tbody></table></div>`));
  }
  // allocation optimale suggérée (HRP / min-variance / risk parity)
  const op=a.optimal_allocation;
  if(op&&op.symbols&&op.symbols.length){
    const orows=op.symbols.map((s,i)=>`<tr><td class="mono">${s}</td>
      <td class="mono" style="text-align:right;color:var(--muted)">${(op.current[i]*100).toFixed(1)}%</td>
      <td class="mono" style="text-align:right;color:#3b82f6">${(op.hrp[i]*100).toFixed(1)}%</td>
      <td class="mono" style="text-align:right;color:#60a5fa">${(op.min_variance[i]*100).toFixed(1)}%</td>
      <td class="mono" style="text-align:right;color:#a855f7">${((op.risk_parity?op.risk_parity[i]:0)*100).toFixed(1)}%</td></tr>`).join('');
    p.appendChild($(`<div class="card"><div class="label" style="margin-bottom:8px">Allocation optimale suggérée</div>
      <table style="width:100%;font-size:13px"><thead><tr><th style="text-align:left">Actif</th>
      <th style="text-align:right">Actuelle</th><th style="text-align:right">HRP</th>
      <th style="text-align:right">Min-var</th><th style="text-align:right">Risk parity</th></tr></thead>
      <tbody>${orows}</tbody></table>
      <div style="font-size:11px;color:var(--muted);margin-top:6px">HRP (López de Prado), min-variance &amp; risk parity (ERC) — robustes sans inversion instable de la covariance.</div></div>`));
  }
  // stress-tests macro + couverture
  const st=a.stress;
  if(st&&st.scenarios&&st.scenarios.length){
    const rows=st.scenarios.map(s=>`<tr><td>${s.name}</td>
      <td class="mono" style="text-align:right;color:${s.pnl_pct>=0?'#22c55e':'#f43f5e'}">${(s.pnl_pct*100).toFixed(1)}%</td>
      <td class="mono" style="text-align:right;color:var(--muted)">${((1+s.pnl_pct)*100).toFixed(0)}%</td></tr>`).join('');
    const h=st.hedge;
    const hedge=h?`<div style="margin-top:10px;font-size:12px;background:var(--surface3);border-radius:10px;padding:10px">
      <b>Couverture</b> — pire scénario : <span class="mono" style="color:#f43f5e">${(h.worst_pnl_pct*100).toFixed(1)}%</span> (${h.worst_scenario}). ${h.needed?('Suggestion : short indiciel ≈ <b class="mono">'+(h.hedge_pct*100).toFixed(1)+'%</b> pour viser ≤ '+(h.target_max_loss*100).toFixed(0)+'%.'):(h.rationale+'.')}</div>`:'';
    p.appendChild($(`<div class="card"><div class="label" style="margin-bottom:8px">Stress-tests macro</div>
      <table style="width:100%;font-size:13px"><thead><tr><th style="text-align:left">Scénario</th>
      <th style="text-align:right">Impact P&amp;L</th><th style="text-align:right">Valeur après choc</th></tr></thead>
      <tbody>${rows}</tbody></table>${hedge}</div>`));
  }
  // revue experte
  const rv=a.review,sc=rv.health_score,scc=sc>=65?'#22c55e':(sc<45?'#ef4444':'#f59e0b');
  const L=(t,arr,c)=>arr&&arr.length?`<div style="margin-bottom:8px"><div style="color:${c};font-size:12px;font-weight:600">${t}</div><ul>${arr.map(x=>'<li>'+x+'</li>').join('')}</ul></div>`:'';
  p.appendChild($(`<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <div class="label">Revue experte (CFA/FRM/CPA/CAIA)</div>
    <div class="mono" style="font-size:26px;color:${scc}">${sc}<span style="font-size:13px;color:var(--muted)">/100</span></div></div>
    ${L('Forces',rv.strengths,'#22c55e')}${L('Faiblesses',rv.weaknesses,'#f59e0b')}
    ${L('Risques',rv.risks,'#ef4444')}${L('Recommandations',rv.recommendations,'#3b82f6')}
    <div style="color:var(--muted);font-size:11px;font-style:italic;margin-top:6px">${rv.disclaimer}</div></div>`));
 }catch(e){console.error('rendu portefeuille:',e);}
})();

// ---- POSITIONS ----
(function(){
 try{
  const d=DATA.dashboard,p=document.getElementById('pos'),rows=d.positions||[],t=d.totals||{};
  const nb=rows.length, bull=rows.filter(r=>r.stance==='bullish').length;
  const box=$(`<div class="card"><div class="banner" style="margin-bottom:10px">
    <div class="label">Composition — ${nb} positions (clique un en-tête pour trier, un actif pour son graphique)</div>
    <div style="font-size:11px;color:var(--muted)">${bull}/${nb} dans des secteurs <span style="color:#22c55e">bullish</span> · le reste = meilleurs setups ailleurs</div></div>`);
  if(!rows.length){box.appendChild($('<p style="color:var(--muted);font-size:13px">Aucune position ouverte au dernier pas (stratégie à plat).</p>'));}
  else{
    const body=rows.map(r=>`<tr><td>${tkr(r.symbol)}</td><td>${stanceTag(r.stance,r.sector)}</td>
      <td class="mono" style="text-align:right">${r.ml_score==null?'—':(r.ml_score*100).toFixed(0)+'%'}</td>
      <td class="mono" style="text-align:right">${r.qty.toFixed(2)}</td><td class="mono" style="text-align:right">${r.avg_price}</td>
      <td class="mono" style="text-align:right">${eur(r.current_value)}</td>
      <td class="mono ${r.pnl_abs>=0?'pos':'neg'}" style="text-align:right">${eur(r.pnl_abs)} (${pct(r.pnl_pct)})</td></tr>`);
    box.appendChild(mkTable('<th>Actif</th><th>Secteur / tendance</th><th style="text-align:right">ML</th><th style="text-align:right">Qté</th><th style="text-align:right">PRU</th><th style="text-align:right">Valeur</th><th style="text-align:right">P&amp;L</th>',body));
  }
  p.appendChild(box);
  p.appendChild($(`<div class="card" style="display:flex;justify-content:space-between;font-size:13px">
    <span style="color:var(--muted)">Exposition brute ${eur(t.gross_exposure||0)} · nette ${eur(t.net_exposure||0)}</span>
    <span class="mono ${(t.pnl_abs||0)>=0?'pos':'neg'}">P&amp;L ${eur(t.pnl_abs||0)}</span></div>`));
 }catch(e){console.error('rendu positions:',e);}
})();

const dt=(s)=>s?String(s).slice(0,10):'—';
// table robuste : on assemble TOUTE la table en une chaîne (le parseur gère tr/td
// correctement à l'intérieur d'un <table>, contrairement à un <tr> isolé dans un div).
// tri générique : clic sur un en-tête trie le tableau (numérique ou texte, asc/desc)
function makeSortable(table){
  const ths=[...table.querySelectorAll('thead th')];
  ths.forEach((th,ci)=>{th.style.cursor='pointer';th.title='Trier cette colonne';let asc=false;
    const base=th.innerHTML;
    th.onclick=()=>{
      asc=!asc;const tb=table.querySelector('tbody');
      // groupe chaque ligne principale avec ses lignes de détail (det/sdet) → tri par PAIRES
      const groups=[];let cur=null;
      [...tb.children].forEach(tr=>{
        if((tr.classList.contains('det')||tr.classList.contains('sdet'))&&cur)cur.push(tr);
        else{cur=[tr];groups.push(cur);}
      });
      const num=s=>{const x=parseFloat(String(s).replace(/\s/g,'').replace(/[^0-9.\-]/g,''));return isNaN(x)?null:x;};
      groups.sort((A,B)=>{const x=(A[0].children[ci]?.textContent||'').trim(),y=(B[0].children[ci]?.textContent||'').trim();
        const nx=num(x),ny=num(y);const c=(nx!=null&&ny!=null)?nx-ny:x.localeCompare(y,'fr',{numeric:true});
        return asc?c:-c;});
      groups.forEach(g=>g.forEach(tr=>tb.appendChild(tr)));
      ths.forEach(h=>{h.innerHTML=h===th?base:h.innerHTML.replace(/ [▲▼]$/,'');});
      th.innerHTML=base+(asc?' ▲':' ▼');
    };
  });
}
function mkTable(head,bodyRows){
  const t=$(`<table><thead><tr>${head}</tr></thead><tbody>${bodyRows.join('')}</tbody></table>`);
  makeSortable(t);    // triable partout (gère aussi les tables à lignes dépliables)
  return t;
}

// ---- TRADES (historique + en cours) ----
(function(){
  const p=document.getElementById('trades'),st=DATA.trade_stats||{},
    closed=DATA.trades||[],open=DATA.open_trades||[];
  // bandeau de statistiques
  const wr=(st.win_rate||0)*100;
  const cards=[['Trades clôturés',st.count||0,''],['Taux de réussite',wr.toFixed(0),'%'],
    ['P&L réalisé (clôturés)','$'+eur(st.pnl_total||0),'','pnl'],['Profit factor',st.profit_factor??'—',''],
    ['Meilleur','$'+eur(st.best||0),'','best'],['Pire','$'+eur(st.worst||0),'','worst']];
  const g=$('<div class="grid4"></div>');
  cards.forEach(([lab,val,suf,kind])=>{
    const tone=kind==='worst'?'neg':kind==='best'?'pos':kind==='pnl'?((st.pnl_total||0)>=0?'pos':'neg'):'';
    g.appendChild($(`<div class="card metric"><div class="label">${lab}</div>
      <div class="val ${tone}" style="font-size:22px">${val}${suf}</div></div>`));
  });
  p.appendChild(g);
  // bandeau VALEUR DE PORTEFEUILLE (capital, gain/perte, exposition)
  const k=DATA.dashboard.portfolio||{};
  p.appendChild(portfolioBar(k));
  const latent=Math.round((k.pnl_abs||0)-(st.pnl_total||0));
  p.appendChild($(`<div style="font-size:11px;color:var(--muted);margin-top:-6px">
    ⓘ <b style="color:var(--fg)">P&L réalisé</b> (trades clôturés) $${eur(st.pnl_total||0)}
    + <b style="color:var(--fg)">P&L latent</b> (positions ouvertes) $${eur(latent)}
    = <b style="color:var(--fg)">gain total</b> $${eur(k.pnl_abs||0)}. Démo synthétique (« fictif »).</div>`));
  // trades en cours
  const oc=$(`<div class="card"><div class="label" style="margin-bottom:10px">Trades en cours (clique un actif pour son graphique)</div></div>`);
  if(!open.length){oc.appendChild($('<p style="color:var(--muted);font-size:13px">Aucun trade ouvert au dernier pas (stratégie à plat).</p>'));}
  else{
    const head='<th>Actif</th><th>Sens</th><th style="text-align:right">Qté</th><th style="text-align:right">PRU</th><th style="text-align:right">Valeur</th><th style="text-align:right">P&amp;L latent</th>';
    const rows=open.map(r=>`<tr><td>${tkr(r.symbol)}</td><td>${r.side}</td>
      <td class="mono" style="text-align:right">${r.qty}</td><td class="mono" style="text-align:right">${r.avg_price}</td>
      <td class="mono" style="text-align:right">${eur(r.current_value)}</td>
      <td class="mono ${r.pnl_abs>=0?'pos':'neg'}" style="text-align:right">${eur(r.pnl_abs)} (${pct(r.pnl_pct)})</td></tr>`);
    oc.appendChild(mkTable(head,rows));
  }
  p.appendChild(oc);
  // historique
  const hc=$(`<div class="card"><div class="label" style="margin-bottom:10px">Historique des trades passés (clique une ligne pour le détail)</div></div>`);
  if(!closed.length){hc.appendChild($('<p style="color:var(--muted);font-size:13px">Aucun trade dans le journal.</p>'));}
  else{
    const head='<th>Actif</th><th>Sens</th><th>Entrée</th><th>Sortie</th><th style="text-align:right">P&amp;L</th><th style="text-align:right">%</th><th>Motif sortie</th>';
    const rows=closed.map(t=>{
      const win=(t.pnl_net||0)>=0,f=t.features_snapshot||{};
      const feat=Object.entries(f).map(([k,v])=>k+'='+(typeof v==='number'?v.toFixed(2):v)).join(' · ')||'—';
      return `<tr class="srow"><td><b>${t.instrument}</b></td><td>${t.side}</td>
        <td class="mono" style="color:var(--muted)">${dt(t.entry_ts)}</td>
        <td class="mono" style="color:var(--muted)">${dt(t.exit_ts)}</td>
        <td class="mono ${win?'pos':'neg'}" style="text-align:right">${eur(t.pnl_net||0)}</td>
        <td class="mono ${win?'pos':'neg'}" style="text-align:right">${pct(t.pnl_pct||0)}</td>
        <td style="color:var(--muted)">${t.exit_reason||''}</td></tr>
        <tr class="det" style="display:none"><td colspan="7" style="border:none;padding-top:0">
        <div style="font-size:12px;color:var(--muted)">stratégie <b style="color:var(--fg)">${t.strategy||'—'}</b> · entrée ${(t.entry_price||0).toFixed(2)} → sortie ${(t.exit_price||0).toFixed(2)} · qté ${t.qty} · motif entrée « ${t.entry_reason||'—'} »<br>features : ${feat}</div></td></tr>`;
    });
    const table=mkTable(head,rows);
    table.querySelectorAll('tr.srow').forEach(row=>{
      row.onclick=()=>{const det=row.nextElementSibling;
        if(det)det.style.display=det.style.display==='none'?'':'none';};
    });
    hc.appendChild(table);
  }
  p.appendChild(hc);
})();

// ---- UNIVERS (complet, recherchable + filtres) ----
(function(){
 try{
  const u=DATA.universe,p=document.getElementById('uni');if(!u)return;
  const all=u.instruments||[];
  const g=$('<div class="grid4"></div>');
  [['Instruments (univers complet)',eur(u.instruments_total||all.length)],
   ['Classes d\'actifs',Object.keys(u.by_asset_class||{}).length],
   ['Sources actives',u.sources_enabled+' / '+u.sources_total],
   ['Rebuild',u.rebuild_cadence_days+' j']]
   .forEach(([lab,val])=>g.appendChild($(`<div class="card metric"><div class="label">${lab}</div><div class="val" style="font-size:22px">${val}</div></div>`)));
  p.appendChild(g);
  // répartition par classe
  const bc=$(`<div class="card"><div class="label" style="margin-bottom:10px">Répartition par classe d'actifs</div></div>`);
  const max=Math.max(1,...Object.values(u.by_asset_class||{}));
  Object.entries(u.by_asset_class||{}).forEach(([k,v])=>{
    bc.appendChild($(`<div style="display:flex;align-items:center;gap:8px;margin:5px 0;font-size:12px">
      <span style="width:90px;color:var(--muted)">${k}</span>
      <span class="facbar" style="width:${Math.round(v/max*100)}%;max-width:420px"></span>
      <span class="mono">${v}</span></div>`));
  });
  p.appendChild(bc);
  // EXPLORATEUR univers complet : recherche + filtres de classe
  const ex=$(`<div class="card"><div class="banner" style="margin-bottom:12px">
    <div class="label">Univers complet — explorateur</div>
    <div id="uCount" style="font-size:11px;color:var(--muted)"></div></div></div>`);
  const search=$('<input class="search" placeholder="Rechercher un symbole, un nom, une place…" style="margin-bottom:10px">');
  const classes=['tous',...Object.keys(u.by_asset_class||{})];
  const chips=$('<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px"></div>');
  let curClass='tous',curQ='';
  classes.forEach((c,idx)=>{const ch=$(`<span class="chip${idx===0?' on':''}">${c}</span>`);
    ch.onclick=()=>{curClass=c;chips.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));ch.classList.add('on');render();};
    chips.appendChild(ch);});
  const tableWrap=$('<div style="max-height:520px;overflow:auto"></div>');
  ex.appendChild(search);ex.appendChild(chips);ex.appendChild(tableWrap);p.appendChild(ex);
  function render(){
    const q=curQ.toLowerCase();
    const rows=all.filter(r=>(curClass==='tous'||r.asset_class===curClass)&&(!q||
      (r.symbol+' '+r.name+' '+r.venue+' '+(r.sector||'')).toLowerCase().includes(q))).slice(0,500);
    const body=rows.map(r=>`<tr><td class="mono"><b>${r.symbol}</b></td><td style="color:var(--muted)">${r.name||''}</td>
      <td>${r.asset_class||''}</td><td style="color:var(--muted)">${r.venue||''}</td>
      <td style="color:var(--muted)">${r.sector||r.currency||''}</td></tr>`);
    tableWrap.innerHTML='';
    tableWrap.appendChild(mkTable('<th>Symbole</th><th>Nom</th><th>Classe</th><th>Place</th><th>Secteur / Devise</th>',body));
    ex.querySelector('#uCount').textContent=rows.length+' / '+all.length+' instruments'+(rows.length>=500?' (500 affichés)':'');
  }
  search.addEventListener('input',e=>{curQ=e.target.value;render();});
  render();
  // sources
  const sc=$(`<div class="card"><div class="label" style="margin-bottom:10px">Sources déclaratives (offline + réseau)</div></div>`);
  const srcRows=u.sources.map(s=>`<tr><td><b>${s.id}</b></td><td style="color:var(--muted)">${s.kind}</td>
    <td><span class="pill" style="color:${s.network?'#f59e0b':'#22c55e'}">${s.network?'réseau':'offline'}</span></td>
    <td><span class="pill" style="color:${s.enabled?'#22c55e':'#9aa1ad'}">${s.enabled?'activée':'désactivée'}</span></td></tr>`);
  sc.appendChild(mkTable('<th>Source</th><th>Type</th><th>Accès</th><th>Statut</th>',srcRows));
  p.appendChild(sc);
 }catch(e){console.error('rendu univers:',e);}
})();

// ---- DONNÉES (collecte + base de données) ----
(function(){
  const d=DATA.data,p=document.getElementById('data');if(!d)return;
  // collecte
  const g=$('<div class="grid4"></div>');
  [['Provider',d.provider],['Barres collectées',eur(d.total_bars)],
   ['Symboles collectés',eur(d.symbols_total||(d.collection||[]).length)],['Fondamentaux',d.fundamentals_provider||'—']]
   .forEach(([lab,val])=>g.appendChild($(`<div class="card metric"><div class="label">${lab}</div><div class="val" style="font-size:20px">${val}</div></div>`)));
  p.appendChild(g);
  const cc=$(`<div class="card"><div class="banner" style="margin-bottom:6px">
    <div class="label">Collecte OHLCV — univers complet (${eur((d.collection||[]).length)} symboles)</div></div>
    <div style="color:var(--muted);font-size:12px;margin-bottom:10px">Ordre de fallback : ${(d.fallback_order||[]).join(' → ')||'—'} · cache ${d.cache?'activé':'désactivé'}</div></div>`);
  const colRows=(d.collection||[]).map(r=>`<tr><td class="mono"><b>${r.symbol}</b></td>
    <td style="color:var(--muted)">${r.asset_class||''}</td>
    <td class="mono" style="text-align:right">${r.bars}</td><td class="mono" style="color:var(--muted)">${dt(r.start)}</td>
    <td class="mono" style="color:var(--muted)">${dt(r.end)}</td><td class="mono" style="text-align:right">${r.last_close}</td></tr>`);
  const colWrap=$('<div style="max-height:460px;overflow:auto"></div>');
  colWrap.appendChild(mkTable('<th>Symbole</th><th>Classe</th><th style="text-align:right">Barres</th><th>Début</th><th>Fin</th><th style="text-align:right">Dernier cours</th>',colRows));
  cc.appendChild(colWrap);
  p.appendChild(cc);
  // qualité
  const q=d.quality||{},ok=q.ok;
  const qc=$(`<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <div class="label">Contrôle qualité (${q.symbol||''})</div>
    <span class="pill" style="color:${ok?'#22c55e':'#ef4444'}">${ok?'✓ conforme':'✗ erreurs'}</span></div>
    <div style="font-size:12px;color:var(--muted)">${q.n_rows||0} lignes validées · prix>0 · cohérence OHLC · timestamps croissants · trous temporels${(q.warnings||[]).length?(' — '+q.warnings.join('; ')):' : aucun'}${(q.errors||[]).length?(' — ERREURS: '+q.errors.join('; ')):''}</div></div>`);
  p.appendChild(qc);
  // base de données (couches)
  const lc=$(`<div class="card"><div class="label" style="margin-bottom:10px">Base de données — couches médaillon</div></div>`);
  (d.layers||[]).forEach(l=>lc.appendChild($(`<div style="padding:8px 0;border-top:1px solid var(--border)">
    <div style="font-size:13px"><b>${l.name}</b> <span class="pill" style="margin-left:6px">${l.store}</span></div>
    <div style="font-size:12px;color:var(--muted);margin-top:3px">${l.desc}</div></div>`)));
  p.appendChild(lc);
  // cadence de mise à jour
  p.appendChild($(`<div class="card" style="border-color:var(--border2)">
    <div class="label" style="margin-bottom:6px">Mise à jour des données</div>
    <div style="font-size:12px;color:var(--muted)">Batch <b style="color:var(--fg)">EOD quotidien</b> : chaque jour de bourse, la barre du jour
    est ajoutée à l'historique de <b style="color:var(--fg)">chaque actif</b> (append incrémental, jamais d'écrasement) ;
    contrôles qualité rejoués avant intégration. Intraday différé ${(DATA.meta||{}).delay_minutes||15} min.
    Univers rebâti tous les ${(DATA.universe||{}).rebuild_cadence_days||30} j (snapshot daté point-in-time).
    <i>Démo : série synthétique reproductible regénérée jusqu'à la date du jour ; en production, ordonnanceur
    (scripts/scheduler.py) + stores DuckDB/Parquet persistants.</i></div></div>`));
})();

// ---- THÈMES DE MARCHÉ (heatmap YTD interactive + meilleurs setups) ----
const heatColor=(v,m)=>{const t=Math.max(-1,Math.min(1,v/m));
  return `hsl(${t>=0?150:356} 68% ${(20+Math.abs(t)*24).toFixed(0)}%)`;};
(function(){
 try{
  const th=DATA.themes,p=document.getElementById('themes');if(!th)return;
  const STANCE={bullish:['#22c55e','▲ bullish'],bearish:['#f43f5e','▼ bearish'],neutral:['#9aa1ad','– neutre']};
  const maxAbs=Math.max(0.01,...th.sectors.map(s=>Math.abs(s.ytd)));
  // KPI
  const g=$('<div class="grid4"></div>');
  [['Thèmes suivis',th.sectors.length,''],['Bullish ▲',th.bullish.length,'',  'pos'],
   ['Bearish ▼',th.bearish.length,'','neg'],['Meilleur thème YTD',pct(th.sectors[0].ytd),'','pos']]
   .forEach(([lab,val,suf,tone])=>g.appendChild($(`<div class="card metric"><div class="label">${lab}</div>
     <div class="val ${tone||''}" style="font-size:22px">${val}${suf}</div></div>`)));
  p.appendChild(g);
  // HEATMAP interactive (survol = détail)
  const hc=$(`<div class="card" id="hmWrap" style="position:relative">
    <div class="banner" style="margin-bottom:12px"><div class="label">Heatmap — performance YTD par thème (survole une case)</div>
    <div style="font-size:11px;color:var(--muted)">vert = haussier · rouge = baissier · 4ᵉ révolution industrielle + secteurs GICS</div></div></div>`);
  const hm=$('<div class="hm" style="grid-template-columns:repeat(auto-fill,minmax(150px,1fr))"></div>');
  const htip=$('<div id="tip"></div>');
  th.sectors.forEach(s=>{
    const cell=$(`<div class="hcell" style="background:${heatColor(s.ytd,maxAbs)}">
      <div class="hn">${s.sector}</div><div class="hv">${pct(s.ytd)}</div></div>`);
    cell.addEventListener('pointermove',e=>{
      const r=hc.getBoundingClientRect();
      htip.style.opacity=1;
      htip.style.left=Math.min(r.width-230,e.clientX-r.left+14)+'px';
      htip.style.top=(e.clientY-r.top+14)+'px';
      htip.innerHTML=`<b>${s.sector}</b> <span style="color:${STANCE[s.stance][0]}">${STANCE[s.stance][1]}</span><br>`
        +`YTD <b class="mono">${pct(s.ytd)}</b> · momentum <span class="mono">${pct(s.momentum)}</span><br>`
        +`Top setups : ${s.top_assets.map(a=>'<b>'+a.symbol+'</b> '+pct(a.ytd)).join(' · ')}`;
    });
    cell.addEventListener('pointerleave',()=>{htip.style.opacity=0;});
    hm.appendChild(cell);
  });
  hc.appendChild(hm);hc.appendChild(htip);p.appendChild(hc);
  // bullish / bearish résumé
  p.appendChild($(`<div class="card banner">
    <div style="font-size:13px"><span style="color:#22c55e">▲ Bullish :</span> <span style="color:var(--muted)">${th.bullish.join(' · ')||'—'}</span></div>
    <div style="font-size:13px"><span style="color:#f43f5e">▼ Bearish :</span> <span style="color:var(--muted)">${th.bearish.join(' · ')||'—'}</span></div></div>`));
  // meilleurs setups par secteur
  const sc=$(`<div class="card"><div class="label" style="margin-bottom:10px">Meilleurs setups par thème (momentum + tendance vs MM50)</div></div>`);
  const rows=th.sectors.map(s=>{
    const tops=s.top_assets.map(a=>`<span class="pill" style="margin:0 6px 4px 0;display:inline-block"><b>${a.symbol}</b> ${pct(a.ytd)} · ${a.setup}</span>`).join('');
    return `<tr><td style="white-space:nowrap"><span style="color:${STANCE[s.stance][0]};font-size:11px">${STANCE[s.stance][1]}</span><br><b>${s.sector}</b></td>
      <td class="mono" style="text-align:right;vertical-align:top;color:${STANCE[s.stance][0]}">${pct(s.ytd)}</td>
      <td style="padding-left:12px">${tops}</td></tr>`;
  });
  sc.appendChild(mkTable('<th>Thème</th><th style="text-align:right">YTD</th><th style="padding-left:12px">Top actifs / setup</th>',rows));
  p.appendChild(sc);
  p.appendChild($(`<div style="font-size:11px;color:var(--muted)">Données synthétiques reproductibles. Lecture : privilégier les setups haussiers dans les thèmes bullish ; éviter les contre-tendances dans les thèmes bearish.</div>`));
 }catch(e){console.error('rendu thèmes:',e);}
})();

// ---- SIGNAUX ML (edge cross-section sur tout l'univers) ----
(function(){
 try{
  const ml=DATA.ml,p=document.getElementById('ml');if(!ml)return;
  if(!ml.available){p.appendChild($('<div class="card"><p style="color:var(--muted);font-size:13px">Modèle ML indisponible (échantillon insuffisant).</p></div>'));return;}
  const g=$('<div class="grid4"></div>');
  [['Modèle',ml.model],['AUC (CV purgée)',ml.auc!=null?ml.auc:'—'],
   ['Échantillon (train)',eur(ml.n_train)],['Horizon',ml.horizon_days+' j']]
   .forEach(([lab,val])=>g.appendChild($(`<div class="card metric"><div class="label">${lab}</div><div class="val" style="font-size:20px">${val}</div></div>`)));
  p.appendChild(g);
  p.appendChild($(`<div style="font-size:11px;color:var(--muted);margin-top:-4px"><b style="color:var(--fg)">${ml.model}</b> entraîné en cross-section sur TOUT l'univers (features : momentum 1m/3m, tendance vs MM50, RSI, volatilité). Score = probabilité de hausse à ~${ml.horizon_days} j. Validation : <b style="color:var(--fg)">${ml.validation||'CV purgée + embargo'}</b> (López de Prado, anti-fuite des labels chevauchants).</div>`));
  // top conviction
  const tc=$(`<div class="card"><div class="label" style="margin-bottom:10px">Top convictions ML (proba de hausse la plus élevée)</div></div>`);
  const rows=ml.top_conviction.map(a=>`<tr><td class="mono"><b>${a.symbol}</b></td><td style="color:var(--muted)">${a.name||''}</td>
    <td style="color:var(--muted);font-size:11px">${a.sector||''}</td>
    <td class="mono" style="text-align:right;color:${a.ml_score>=0.5?'#22c55e':'#f43f5e'}">${(a.ml_score*100).toFixed(1)}%</td></tr>`);
  tc.appendChild(mkTable('<th>Actif</th><th>Nom</th><th>Secteur</th><th style="text-align:right">Proba hausse</th>',rows));
  p.appendChild(tc);
  // importance des features
  const fi=$(`<div class="card"><div class="label" style="margin-bottom:10px">Importance des variables (|poids| standardisés)</div></div>`);
  const maxw=Math.max(...ml.feature_importance.map(f=>f.weight),0.01);
  ml.feature_importance.forEach(f=>fi.appendChild($(`<div style="display:flex;align-items:center;gap:8px;margin:6px 0;font-size:12px">
    <span style="width:140px;color:var(--muted)">${f.feature}</span>
    <span class="facbar" style="width:${Math.round(f.weight/maxw*100)}%;max-width:360px"></span>
    <span class="mono">${f.weight.toFixed(3)}</span></div>`)));
  p.appendChild(fi);
  // validation & robustesse (calibration, conformal, walk-forward, drift)
  const cal=ml.calibration,cf=ml.conformal,wf=ml.walk_forward,dr=ml.drift;
  if((cal&&cal.available)||(cf&&cf.available)||(wf&&wf.available)||(dr&&dr.available)){
    const vc=$(`<div class="card"><div class="label" style="margin-bottom:10px">Validation & robustesse</div></div>`);
    const grid=$('<div class="grid4"></div>');
    if(wf&&wf.available)grid.appendChild($(`<div class="card metric"><div class="label">AUC walk-forward</div><div class="val" style="font-size:18px">${wf.auc_mean} ± ${wf.auc_std}</div></div>`));
    if(cal&&cal.available)grid.appendChild($(`<div class="card metric"><div class="label">Brier (calibré)</div><div class="val" style="font-size:18px;color:${cal.brier_calibrated<=cal.brier_raw?'#22c55e':'#f59e0b'}">${cal.brier_calibrated}</div></div>`));
    if(cf&&cf.available)grid.appendChild($(`<div class="card metric"><div class="label">Couverture conformal</div><div class="val" style="font-size:18px">${(cf.empirical_coverage*100).toFixed(0)}%<span style="font-size:11px;color:var(--muted)"> /${(cf.target_coverage*100).toFixed(0)}%</span></div></div>`));
    if(dr&&dr.available)grid.appendChild($(`<div class="card metric"><div class="label">Drift features (PSI)</div><div class="val" style="font-size:18px;color:${dr.drift_detected?'#f59e0b':'#22c55e'}">${dr.drift_detected?dr.flagged.length+' forte(s)':'stable'}</div></div>`));
    vc.appendChild(grid);
    p.appendChild(vc);
  }
  p.appendChild($('<div style="font-size:11px;color:var(--muted)">Démonstration sur données synthétiques : l\'edge prédictif est volontairement modeste (marché en grande partie aléatoire). Le score ML enrichit le screener et confirme les setups.</div>'));
 }catch(e){console.error('rendu ml:',e);}
})();

// ---- PORTEFEUILLE RÉEL (connexion brokers Alpaca / Bitmart) ----
(function(){
 try{
  const L=DATA.live,p=document.getElementById('live');if(!L)return;
  const dot=L.connected?'#22c55e':'#f59e0b';
  p.appendChild($(`<div class="card banner">
    <div><span class="dot" style="background:${dot}"></span>
      <b>${L.connected?'Compte connecté':'Aucun compte connecté'}</b>
      <span style="color:var(--muted)">· mode <b style="color:var(--fg)">${L.mode}</b> (paper par défaut, jamais d'ordre réel non confirmé)</span></div></div>`));
  // KPI RÉELS uniquement si un compte est connecté (sinon portefeuille réel = vide)
  if(L.connected&&L.portfolio&&L.portfolio.value){p.appendChild(portfolioBar(L.portfolio));}
  else{p.appendChild($(`<div class="card"><div class="grid4">
    <div><div class="label">Valeur du compte</div><div class="val" style="font-size:20px">—</div></div>
    <div><div class="label">Gain / perte</div><div class="val" style="font-size:20px">—</div></div>
    <div><div class="label">Positions réelles</div><div class="val" style="font-size:20px">0</div></div>
    <div><div class="label">Statut</div><div class="val" style="font-size:14px;color:#f59e0b">à connecter</div></div>
    </div><div style="font-size:11px;color:var(--muted);margin-top:8px">Connectez Alpaca / Bitmart pour voir ici votre VRAI portefeuille (valeur, P&L, positions). Aucun montant fictif n'est affiché.</div></div>`));}
  // brokers
  const bc=$(`<div class="grid2"></div>`);
  L.brokers.forEach(b=>bc.appendChild($(`<div class="card">
    <div class="banner" style="margin-bottom:6px"><div class="label">${b.name}</div>
      <span class="pill" style="color:${b.connected?'#22c55e':'#f59e0b'}">${b.connected?'connecté':'à connecter'}</span></div>
    <div style="font-size:12px;color:var(--muted)">${b.scope} · ${b.paper?'paper':'live'}</div>
    <div style="font-size:11px;color:var(--muted);margin-top:8px">Clés requises : ${b.env.map(e=>'<span class="pill" style="margin-right:4px">'+e+'</span>').join('')}</div></div>`)));
  p.appendChild(bc);
  // OÙ METTRE VOS CLÉS API
  p.appendChild($(`<div class="card" style="border-color:var(--accent)">
    <div class="label" style="margin-bottom:8px">🔑 Où indiquer vos clés API</div>
    <div style="font-size:12px;color:var(--muted);line-height:1.7">
    Créez un fichier <b style="color:var(--fg)">.env</b> à la racine du projet (jamais committé) :
    <pre style="background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:10px;margin:8px 0;font-size:11px;color:var(--fg);overflow:auto">ALPACA_API_KEY=xxxxxxxx
ALPACA_API_SECRET=xxxxxxxx
BITMART_API_KEY=xxxxxxxx
BITMART_API_SECRET=xxxxxxxx
BITMART_API_MEMO=xxxxxxxx</pre>
    ou via le terminal : <span class="pill">export ALPACA_API_KEY="..."</span> dans <b style="color:var(--fg)">~/.zshrc</b>.<br>
    Puis : aperçu sûr <span class="pill">python3 scripts/run_live.py</span> (dry-run) ·
    exécution paper <span class="pill">python3 scripts/run_live.py --live --yes</span>.
    Permissions API minimales (jamais de retrait).</div></div>`));
  // allocation cible (POIDS %, pas de montant fictif) — à dimensionner sur votre capital réel
  const oc=$(`<div class="card"><div class="label" style="margin-bottom:10px">Allocation cible du modèle — ${L.target_orders.length} lignes (% du portefeuille, à appliquer à votre capital réel)</div></div>`);
  if(!L.target_orders.length){oc.appendChild($('<p style="color:var(--muted);font-size:13px">Aucune position cible.</p>'));}
  else{
    const rows=L.target_orders.map(o=>`<tr><td>${tkr(o.symbol)}</td><td>${o.side}</td>
      <td style="color:var(--muted)">${o.asset_class}</td>
      <td><span class="pill">${o.broker}</span></td>
      <td class="mono" style="text-align:right">${pct(o.weight_pct||0)}</td></tr>`);
    oc.appendChild(mkTable('<th>Actif</th><th>Sens</th><th>Classe</th><th>Broker</th><th style="text-align:right">Poids cible</th>',rows));
  }
  p.appendChild(oc);
 }catch(e){console.error('rendu live:',e);}
})();

// ---- PWA : service worker (mode hors-ligne, « ajouter à l'écran d'accueil ») ----
if('serviceWorker' in navigator){window.addEventListener('load',()=>{
  navigator.serviceWorker.register('sw.js').catch(()=>{});});}

// ---- Sentiment & news ----
(function(){
  const p=document.getElementById('sent');if(!p)return;
  const S=DATA.sentiment||{};
  if(!S.available){p.appendChild($(`<div class="card"><div class="label">Sentiment</div>
    <p style="color:var(--muted)">Aucune donnée de sentiment.</p></div>`));return;}
  const moodPct=Math.round(((S.market_mood||0)+1)/2*100);
  const head=$(`<div class="card">
    <div class="label">Humeur de marché (positions)</div>
    <div style="display:flex;align-items:center;gap:14px;margin-top:8px">
      <div style="font-size:26px;font-weight:700">${stanceTag(S.market_label,'')}</div>
      <div style="flex:1">
        <div style="height:10px;border-radius:6px;background:var(--surface3);overflow:hidden">
          <div style="height:100%;width:${moodPct}%;background:linear-gradient(90deg,#f43f5e,#9aa1ad,#22c55e)"></div></div>
        <div class="asof" style="margin-top:6px">score moyen <b>${(S.market_mood||0).toFixed(2)}</b> ·
          moteur <b>${S.engine||'—'}</b> · source <b>${S.source||'—'}</b></div>
      </div>
    </div></div>`);
  p.appendChild(head);
  const rows=(S.rows||[]).map(r=>{
    const hl=(r.headlines||[]).map(h=>h.link?`<a href="${h.link}" target="_blank" rel="noopener" style="color:var(--accent2)">${h.title}</a>`:h.title).join(' · ')||'<span style="color:var(--muted2)">—</span>';
    return `<tr><td>${r.symbol}</td><td style="color:var(--muted)">${stanceTag(r.label,r.sector)}</td>
      <td class="mono" data-sort="${r.score}" style="text-align:right;color:${r.score>0?'var(--pos)':r.score<0?'var(--neg)':'var(--muted)'}">${(r.score||0).toFixed(2)}</td>
      <td class="mono" style="text-align:right">${r.n_news||0}</td>
      <td style="font-size:11.5px">${hl}</td></tr>`;
  });
  const c=$(`<div class="card"><div class="label">Sentiment par position</div></div>`);
  c.appendChild(mkTable('<th>Actif</th><th>Sentiment</th><th style="text-align:right">Score</th><th style="text-align:right">News</th><th>Titres</th>',rows));
  p.appendChild(c);
})();

// ---- Fondamentaux ----
(function(){
  const p=document.getElementById('fund');if(!p)return;
  const F=DATA.fundamentals||{};
  if(!F.available){p.appendChild($(`<div class="card"><div class="label">Fondamentaux</div>
    <p style="color:var(--muted)">Aucun fondamental disponible.</p></div>`));return;}
  const RC={BUY:'#22c55e',HOLD:'#9aa1ad',SELL:'#f43f5e'};
  const pp=(x)=>x==null?'—':(x*100).toFixed(0)+'%';
  p.appendChild($(`<div class="card"><div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;align-items:center">
    <div class="label">Analyse fondamentale — source ${F.source}</div>
    <div class="mono" style="font-size:12px;color:var(--muted)">${F.n} titres · <span style="color:#22c55e">${F.buys} BUY</span></div></div>
    <p style="color:var(--muted);font-size:11.5px;margin-top:6px">${F.method}</p></div>`));
  const rows=(F.rows||[]).map(r=>`<tr><td>${r.symbol}</td>
    <td style="color:var(--muted);font-size:11px">${r.sector||'—'}</td>
    <td class="mono" data-sort="${r.per}" style="text-align:right">${r.per}</td>
    <td class="mono" data-sort="${r.pb}" style="text-align:right">${r.pb}</td>
    <td class="mono" data-sort="${r.roe}" style="text-align:right">${pp(r.roe)}</td>
    <td class="mono" data-sort="${r.fcf_yield}" style="text-align:right">${pp(r.fcf_yield)}</td>
    <td class="mono" data-sort="${r.margin_of_safety==null?-999:r.margin_of_safety}" style="text-align:right;color:${r.margin_of_safety==null?'var(--muted)':r.margin_of_safety>0?'#22c55e':'#f43f5e'}">${r.margin_of_safety==null?'—':(r.margin_of_safety*100).toFixed(0)+'%'}</td>
    <td class="mono" data-sort="${r.f_score}" style="text-align:right;color:${r.f_score>=7?'#22c55e':r.f_score>=4?'#f59e0b':'#f43f5e'}">${r.f_score}/9</td>
    <td class="mono" data-sort="${r.tech_score}" style="text-align:right;color:${r.tech_label==='haussier'?'#22c55e':r.tech_label==='baissier'?'#f43f5e':'#9aa1ad'}">${r.tech_score}</td>
    <td class="mono" data-sort="${r.combined_score}" style="text-align:right">${r.combined_score}</td>
    <td style="text-align:right;font-weight:600;color:${RC[r.rating]}">${r.rating}</td></tr>`);
  const c=$(`<div class="card"><div class="label" style="margin-bottom:8px">Score value + quality · DCF</div></div>`);
  c.appendChild(mkTable('<th>Actif</th><th>Secteur</th><th style="text-align:right">PER</th><th style="text-align:right">P/B</th><th style="text-align:right">ROE</th><th style="text-align:right">FCF yld</th><th style="text-align:right">Marge sécu.</th><th style="text-align:right">F-score</th><th style="text-align:right">Tech</th><th style="text-align:right">Fond+Tech</th><th style="text-align:right">Reco</th>',rows));
  p.appendChild(c);
})();

// ---- bandeau "données au…" en tête de chaque onglet + ouverture sur le 1er ----
['dash','themes','ml','sent','fund','uni','data','pf','pos','trades','live'].forEach(id=>{
  const pg=document.getElementById(id);if(pg)pg.insertBefore(freshnessChip(id),pg.firstChild);
});
</script></body></html>"""


# --- PWA : manifest + service worker (générés à côté de interactive.html) ---
_ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'%3E"
         "%3Crect width='512' height='512' rx='112' fill='%2308090c'/%3E%3Crect x='128' y='128' "
         "width='256' height='256' rx='72' fill='url(%23g)'/%3E%3Cdefs%3E%3ClinearGradient id='g' "
         "x1='0' y1='0' x2='1' y2='1'%3E%3Cstop stop-color='%233b82f6'/%3E%3Cstop offset='1' "
         "stop-color='%2322d3ee'/%3E%3C/linearGradient%3E%3C/defs%3E%3C/svg%3E")
_MANIFEST = {
    "name": "Quant Terminal", "short_name": "Quant", "start_url": "interactive.html",
    "scope": ".", "display": "standalone", "orientation": "any",
    "background_color": "#08090c", "theme_color": "#08090c",
    "description": "Terminal quant : screening & trading systématique multi-actifs.",
    "icons": [{"src": _ICON, "sizes": "512x512", "type": "image/svg+xml", "purpose": "any maskable"}],
}
# Cache-first sur la coquille → ouverture instantanée + usage hors-ligne sur téléphone.
_SW = """const C='quant-terminal-v1';const A=['interactive.html','manifest.webmanifest'];
self.addEventListener('install',e=>{self.skipWaiting();
  e.waitUntil(caches.open(C).then(c=>c.addAll(A).catch(()=>{})));});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>
  Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;
  e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(resp=>{
    const cp=resp.clone();caches.open(C).then(c=>c.put(e.request,cp).catch(()=>{}));return resp;
  }).catch(()=>caches.match('interactive.html'))));});
"""


def build() -> tuple[str, dict]:
    snap = build_snapshot()
    return _TEMPLATE.replace("__DATA__", json.dumps(snap)), snap["meta"]


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    out = here / "interactive.html"
    html, meta = build()
    out.write_text(html, encoding="utf-8")
    (here / "manifest.webmanifest").write_text(json.dumps(_MANIFEST, ensure_ascii=False), encoding="utf-8")
    (here / "sw.js").write_text(_SW, encoding="utf-8")
    print(f"écrit : {out}  (+ manifest.webmanifest, sw.js — PWA installable)")
    print(f"  → MODE DES DONNÉES : {meta.get('mode')}   "
          f"(univers {meta.get('universe_size')} · tradés {meta.get('traded_assets')})")
    if meta.get("mode") == "synthetic":
        print("  ⚠️  Toujours synthétique : vérifiez  echo $QUANT_PRICE_DB  (doit pointer YAHOO.db)")
    else:
        print("  ✅ Données RÉELLES utilisées (YAHOO.db).")
