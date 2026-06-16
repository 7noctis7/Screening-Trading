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
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quant Terminal — interactif</title>
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
<div class="tab" data-p="uni" role="tab" tabindex="0" aria-selected="false">Univers</div>
<div class="tab" data-p="data" role="tab" tabindex="0" aria-selected="false">Données</div>
<div class="tab" data-p="pf" role="tab" tabindex="0" aria-selected="false">Portefeuille &amp; Analyse</div>
<div class="tab" data-p="pos" role="tab" tabindex="0" aria-selected="false">Positions</div>
<div class="tab" data-p="trades" role="tab" tabindex="0" aria-selected="false">Trades</div></div>

<div class="page active" id="dash"></div>
<div class="page" id="themes"></div>
<div class="page" id="ml"></div>
<div class="page" id="uni"></div>
<div class="page" id="data"></div>
<div class="page" id="pf"></div>
<div class="page" id="pos"></div>
<div class="page" id="trades"></div>
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
  pf:(DATA.dashboard||{}).as_of,pos:(DATA.dashboard||{}).as_of,trades:(DATA.dashboard||{}).as_of};
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

// ---- DASHBOARD ----
(function(){
 try{
  const d=DATA.dashboard,m=d.metrics,p=document.getElementById('dash');
  const c=CYC[d.regime.cycle]||'#9aa1ab';
  p.appendChild($(`<div class="card banner">
    <div><span class="dot" style="background:${c}"></span>
    <b style="text-transform:capitalize">${d.regime.cycle}</b>
    <span style="color:var(--muted)">· ${d.regime.risk_mode}</span></div>
    <div class="mono" style="color:var(--muted);font-size:13px">
    courbe 2s10s ${d.regime.extras.curve_2s10s} · VIX ${(d.regime.vix||0).toFixed(0)} · exposition ×${d.regime.exposure_multiplier}</div></div>`));
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
    ⓘ Backtest <b style="color:var(--fg)">swing</b> sur <b style="color:var(--fg)">${MZ.traded_assets||MZ.universe_size||0} actifs</b>
    de l'univers (${MZ.universe_size||0} suivis), du ${fmtTS(MZ.period_start).slice(0,10)} au ${fmtTS(MZ.last_bar).slice(0,10)} ·
    ${(MZ.n_trades||0).toLocaleString('fr-FR')} trades · régime <b style="text-transform:capitalize;color:var(--fg)">${d.regime.cycle}</b>
    → exposition pilotée ×${d.regime.exposure_multiplier}.</div>`));
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
  // projection Monte Carlo (éventail des trajectoires futures, base 100)
  const mp=a.mc_projection;
  if(mp&&mp.steps&&mp.steps.length){
    const W=860,H=200,padL=44,padR=64,padT=10,padB=22,m=mp.steps.length;
    const all=mp.p5.concat(mp.p95),lo=Math.min(...all,100),hi=Math.max(...all),rng=(hi-lo)||1;
    const X=i=>padL+i*(W-padL-padR)/(m-1),Y=v=>(H-padB)-(v-lo)/rng*((H-padB)-padT);
    const band=mp.p95.map((v,i)=>X(i).toFixed(1)+','+Y(v).toFixed(1)).join(' ')+' '+
      mp.p5.map((v,i)=>X(m-1-i).toFixed(1)+','+Y(mp.p5[m-1-i]).toFixed(1)).join(' ');
    const line=(arr,c,w)=>`<polyline points="${arr.map((v,i)=>X(i).toFixed(1)+','+Y(v).toFixed(1)).join(' ')}" fill="none" stroke="${c}" stroke-width="${w}"/>`;
    let yA='';for(let k=0;k<4;k++){const v=lo+k/3*(hi-lo),y=Y(v);yA+=`<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W-padR}" y2="${y.toFixed(1)}" stroke="var(--border)" stroke-width="1"/><text x="${padL-6}" y="${(y+3).toFixed(1)}" fill="var(--muted)" font-size="10" text-anchor="end">${v.toFixed(0)}</text>`;}
    const endL=[['p95',mp.p95,'#22c55e'],['médiane',mp.p50,'#3b82f6'],['p5',mp.p5,'#f43f5e']]
      .map(([n,arr,c])=>`<text x="${W-padR+5}" y="${(Y(arr[m-1])+3).toFixed(1)}" fill="${c}" font-size="11" font-weight="600">${arr[m-1].toFixed(0)}</text>`).join('');
    p.appendChild($(`<div class="card"><div class="banner" style="margin-bottom:8px">
      <div class="label">Projection Monte-Carlo — éventail à 1 an (base 100, ${mp.horizon} j ouvrés)</div>
      <div style="font-size:11px;color:var(--muted)">médiane <b style="color:var(--fg)">${mp.final_p50}</b> · p5 <b style="color:#f43f5e">${mp.final_p5}</b> · p95 <b style="color:#22c55e">${mp.final_p95}</b></div></div>
      <svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" style="overflow:visible">
        ${yA}<polygon points="${band}" fill="#3b82f6" fill-opacity="0.14"/>
        ${line(mp.p25,'#3b82f6',0.8)}${line(mp.p75,'#3b82f6',0.8)}${line(mp.p50,'#3b82f6',2)}${endL}
      </svg>
      <div style="font-size:11px;color:var(--muted);margin-top:6px">Rééchantillonnage bootstrap des rendements réalisés (1000 trajectoires) → cône d'incertitude de la valeur future du portefeuille.</div></div>`));
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
  let inner;
  if(!rows.length){
    inner='<p style="color:var(--muted);font-size:13px">Aucune position ouverte au dernier pas (stratégie à plat).</p>';
  }else{
    let rowsHtml='';
    rows.forEach(r=>{
      const ml=r.ml_score==null?'—':(r.ml_score*100).toFixed(0)+'%';
      rowsHtml+=`<tr class="srow"><td><b>${r.symbol}</b></td><td>${stanceTag(r.stance,r.sector)}</td>
        <td class="mono" style="text-align:right">${ml}</td>
        <td class="mono" style="text-align:right">${r.qty.toFixed(2)}</td><td class="mono" style="text-align:right">${r.avg_price}</td>
        <td class="mono" style="text-align:right">${eur(r.current_value)}</td>
        <td class="mono ${r.pnl_abs>=0?'pos':'neg'}" style="text-align:right">${eur(r.pnl_abs)} (${pct(r.pnl_pct)})</td></tr>`;
    });
    inner=`<table><thead><tr><th>Actif</th><th>Secteur / tendance</th><th style="text-align:right">ML</th><th style="text-align:right">Qté</th><th style="text-align:right">PRU</th><th style="text-align:right">Valeur</th><th style="text-align:right">P&amp;L</th></tr></thead><tbody>${rowsHtml}</tbody></table>`;
  }
  const nb=rows.length, bull=rows.filter(r=>r.stance==='bullish').length;
  const box=$(`<div class="card"><div class="banner" style="margin-bottom:10px">
    <div class="label">Composition — ${nb} positions</div>
    <div style="font-size:11px;color:var(--muted)">${bull}/${nb} dans des secteurs <span style="color:#22c55e">bullish</span> · le reste = meilleurs setups ailleurs</div></div>${inner}</div>`);
  p.appendChild(box);
  p.appendChild($(`<div class="card" style="display:flex;justify-content:space-between;font-size:13px">
    <span style="color:var(--muted)">Exposition brute ${eur(t.gross_exposure||0)} · nette ${eur(t.net_exposure||0)}</span>
    <span class="mono ${(t.pnl_abs||0)>=0?'pos':'neg'}">P&amp;L ${eur(t.pnl_abs||0)}</span></div>`));
 }catch(e){console.error('rendu positions:',e);}
})();

const dt=(s)=>s?String(s).slice(0,10):'—';
// table robuste : on assemble TOUTE la table en une chaîne (le parseur gère tr/td
// correctement à l'intérieur d'un <table>, contrairement à un <tr> isolé dans un div).
const mkTable=(head,bodyRows)=>$(`<table><thead><tr>${head}</tr></thead><tbody>${bodyRows.join('')}</tbody></table>`);

// ---- TRADES (historique + en cours) ----
(function(){
  const p=document.getElementById('trades'),st=DATA.trade_stats||{},
    closed=DATA.trades||[],open=DATA.open_trades||[];
  // bandeau de statistiques
  const wr=(st.win_rate||0)*100;
  const cards=[['Trades clôturés',st.count||0,''],['Taux de réussite',wr.toFixed(0),'%'],
    ['P&L cumulé',eur(st.pnl_total||0),' €','pnl'],['Profit factor',st.profit_factor??'—',''],
    ['Meilleur',eur(st.best||0),' €','best'],['Pire',eur(st.worst||0),' €','worst']];
  const g=$('<div class="grid4"></div>');
  cards.forEach(([lab,val,suf,kind])=>{
    const tone=kind==='worst'?'neg':kind==='best'?'pos':kind==='pnl'?((st.pnl_total||0)>=0?'pos':'neg'):'';
    g.appendChild($(`<div class="card metric"><div class="label">${lab}</div>
      <div class="val ${tone}" style="font-size:22px">${val}${suf}</div></div>`));
  });
  p.appendChild(g);
  // trades en cours
  const oc=$(`<div class="card"><div class="label" style="margin-bottom:10px">Trades en cours</div></div>`);
  if(!open.length){oc.appendChild($('<p style="color:var(--muted);font-size:13px">Aucun trade ouvert au dernier pas (stratégie à plat).</p>'));}
  else{
    const head='<th>Actif</th><th>Sens</th><th style="text-align:right">Qté</th><th style="text-align:right">PRU</th><th style="text-align:right">Valeur</th><th style="text-align:right">P&amp;L latent</th>';
    const rows=open.map(r=>`<tr><td><b>${r.symbol}</b></td><td>${r.side}</td>
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
  [['Modèle',ml.model],['AUC (out-of-time)',ml.auc!=null?ml.auc:'—'],
   ['Échantillon (train)',eur(ml.n_train)],['Horizon',ml.horizon_days+' j']]
   .forEach(([lab,val])=>g.appendChild($(`<div class="card metric"><div class="label">${lab}</div><div class="val" style="font-size:20px">${val}</div></div>`)));
  p.appendChild(g);
  p.appendChild($(`<div style="font-size:11px;color:var(--muted);margin-top:-4px">Régression logistique entraînée en cross-section sur TOUT l'univers (features : momentum 1m/3m, tendance vs MM50, RSI, volatilité). Score = probabilité de hausse à ~${ml.horizon_days} j. Validation hors-échantillon temporelle (AUC).</div>`));
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
  p.appendChild($('<div style="font-size:11px;color:var(--muted)">Démonstration sur données synthétiques : l\'edge prédictif est volontairement modeste (marché en grande partie aléatoire). Le score ML enrichit le screener et confirme les setups.</div>'));
 }catch(e){console.error('rendu ml:',e);}
})();

// ---- bandeau "données au…" en tête de chaque onglet + ouverture sur le 1er ----
['dash','themes','ml','uni','data','pf','pos','trades'].forEach(id=>{
  const pg=document.getElementById(id);if(pg)pg.insertBefore(freshnessChip(id),pg.firstChild);
});
</script></body></html>"""


def build() -> str:
    snap = build_snapshot()
    return _TEMPLATE.replace("__DATA__", json.dumps(snap))


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "interactive.html"
    out.write_text(build(), encoding="utf-8")
    print(f"écrit : {out}")
