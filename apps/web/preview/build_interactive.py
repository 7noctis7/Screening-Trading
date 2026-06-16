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
:root{--bg:#0a0b0d;--surface:#141619;--surface2:#1b1e23;--border:#262a31;--fg:#e6e8eb;
--muted:#9aa1ab;--accent:#3b82f6;--pos:#22c55e;--neg:#ef4444;--warn:#f59e0b;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Inter,system-ui,sans-serif}
.wrap{max-width:880px;margin:0 auto;padding:20px}
h1{font-size:20px;font-weight:600;letter-spacing:-.02em;margin:0 0 2px}
.sub{color:var(--muted);font-size:12px;margin-bottom:16px}
.tabs{display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap}
.tab{padding:8px 14px;border-radius:10px;background:var(--surface);border:1px solid var(--border);
color:var(--muted);cursor:pointer;font-size:13px;transition:all .15s}
.tab:hover{background:var(--surface2);color:var(--fg)}
.tab.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.page{display:none;flex-direction:column;gap:14px}
.page.active{display:flex}
.card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:18px;
transition:border-color .2s}
.card:hover{border-color:#374151}
.label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:640px){.grid4{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}
.metric .val{font-size:26px;margin-top:6px;font-variant-numeric:tabular-nums}
.mono{font-variant-numeric:tabular-nums}
.pos{color:var(--pos)}.neg{color:var(--neg)}
.banner{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.dot{height:10px;width:10px;border-radius:50%;display:inline-block;margin-right:8px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{color:var(--muted);font-size:11px;text-align:left;font-weight:400;padding-bottom:6px}
td{padding:7px 0;border-top:1px solid var(--border)}
tr.srow{cursor:pointer;transition:background .12s}
tr.srow:hover{background:var(--surface2)}
.facbar{height:6px;border-radius:3px;background:var(--accent);display:inline-block;vertical-align:middle}
#chartWrap{position:relative}
#tip{position:absolute;pointer-events:none;background:#000;border:1px solid var(--border);
border-radius:8px;padding:6px 10px;font-size:12px;opacity:0;transition:opacity .1s;white-space:nowrap;z-index:5}
.heat td{border:none;text-align:center;color:#fff;font-size:11px;padding:7px;border-radius:4px;
cursor:default;transition:transform .1s}
.heat td:hover{transform:scale(1.12)}
.heat th{text-align:center;padding:2px;font-size:11px}
.pill{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;background:var(--surface2)}
ul{margin:4px 0 0;padding-left:18px;font-size:13px}li{margin:3px 0}
.toggle{font-size:12px;color:var(--accent);cursor:pointer;user-select:none}
</style></head><body><div class="wrap">
<h1>Quant Terminal</h1><div class="sub">données synthétiques · interactif · passe la souris sur les graphiques</div>
<div class="tabs">
<div class="tab active" data-p="dash">Dashboard</div>
<div class="tab" data-p="pf">Portefeuille &amp; Analyse</div>
<div class="tab" data-p="pos">Positions</div>
<div class="tab" data-p="trades">Trades</div>
<div class="tab" data-p="uni">Univers</div>
<div class="tab" data-p="data">Données</div></div>

<div class="page active" id="dash"></div>
<div class="page" id="pf"></div>
<div class="page" id="pos"></div>
<div class="page" id="trades"></div>
<div class="page" id="uni"></div>
<div class="page" id="data"></div>
</div>
<script>const DATA = __DATA__;</script>
<script>
const $=(h)=>{const d=document.createElement('div');d.innerHTML=h.trim();return d.firstChild;};
const pct=(x)=>(x*100).toFixed(1)+'%';
const eur=(x)=>Math.round(x).toLocaleString('fr-FR');
const CYC={expansion:'#22c55e',recovery:'#3b82f6',slowdown:'#f59e0b',recession:'#ef4444'};

// ---- tabs ----
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.page').forEach(x=>x.classList.remove('active'));
  t.classList.add('active');document.getElementById(t.dataset.p).classList.add('active');
});

// ---- compteur animé ----
function countUp(el,target,suffix,dur=700){
  const start=performance.now();const from=0;
  function step(now){const k=Math.min(1,(now-start)/dur);
    el.textContent=(from+(target-from)*k).toFixed(2).replace(/\.00$/,'')+(suffix||'');
    if(k<1)requestAnimationFrame(step);}
  requestAnimationFrame(step);
}

// ---- courbe interactive (crosshair + tooltip) ----
function lineChart(series,labels){
  const W=820,H=210,pad=8;
  const all=[].concat(...series.map(s=>s.data));
  const lo=Math.min(...all),hi=Math.max(...all),rng=(hi-lo)||1;
  const n=series[0].data.length;
  const X=i=>pad+i*(W-2*pad)/(n-1), Y=v=>H-pad-(v-lo)/rng*(H-2*pad);
  const poly=(d,c,w)=>`<polyline points="${d.map((v,i)=>X(i).toFixed(1)+','+Y(v).toFixed(1)).join(' ')}" fill="none" stroke="${c}" stroke-width="${w}"/>`;
  const wrap=$(`<div id="chartWrap" class="card">
    <div class="label" style="margin-bottom:8px">Equity ${series.length>1?'vs S&amp;P 500 (rebasé 100)':''}</div>
    <svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" style="overflow:visible">
      ${series.map(s=>poly(s.data,s.color,s.w)).join('')}
      <line id="cx" x1="0" y1="${pad}" x2="0" y2="${H-pad}" stroke="#4b5563" stroke-width="1" opacity="0"/>
      <circle id="cd" r="4" fill="${series[0].color}" opacity="0"/>
      <rect id="ov" x="0" y="0" width="${W}" height="${H}" fill="transparent"/>
    </svg><div id="tip"></div></div>`);
  setTimeout(()=>{
    const svg=wrap.querySelector('svg'),ov=wrap.querySelector('#ov'),
      cx=wrap.querySelector('#cx'),cd=wrap.querySelector('#cd'),tip=wrap.querySelector('#tip');
    ov.addEventListener('pointermove',e=>{
      const r=svg.getBoundingClientRect();
      const px=(e.clientX-r.left)/r.width*W;
      let i=Math.round((px-pad)/((W-2*pad)/(n-1)));i=Math.max(0,Math.min(n-1,i));
      const x=X(i),y=Y(series[0].data[i]);
      cx.setAttribute('x1',x);cx.setAttribute('x2',x);cx.setAttribute('opacity','.6');
      cd.setAttribute('cx',x);cd.setAttribute('cy',y);cd.setAttribute('opacity','1');
      tip.style.opacity=1;
      tip.style.left=Math.min(r.width-150,(x/W*r.width)+12)+'px';tip.style.top='6px';
      tip.innerHTML=`<b>${labels?labels[i]:('Jour '+i)}</b><br>`+
        series.map(s=>`<span style="color:${s.color}">●</span> ${s.name}: <b>${s.data[i].toFixed(2)}</b>`).join('<br>');
    });
    ov.addEventListener('pointerleave',()=>{cx.setAttribute('opacity','0');cd.setAttribute('opacity','0');tip.style.opacity=0;});
  },50);
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
  // courbe equity vs benchmark
  const b=DATA.portfolio.benchmarks;
  p.appendChild(lineChart([
    {name:'Portefeuille',data:b.portfolio,color:'#3b82f6',w:2},
    {name:'S&P 500',data:b['S&P 500'],color:'#9aa1ab',w:1.3}]));
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
    rowsHtml+=`<tr class="srow" data-i="${idx}"><td style="color:var(--muted)">${r.rank}</td><td><b>${r.symbol}</b></td>
      <td class="mono" style="text-align:right">${r.score.toFixed(3)}</td>
      <td style="padding-left:14px;color:var(--muted)">${r.reason||''}</td></tr>
      <tr class="sdet" data-i="${idx}" style="display:none"><td colspan="4" style="border:none;padding-top:0">${facHtml}</td></tr>`;
  });
  const box=$(`<div class="card"><div class="label" style="margin-bottom:10px">Top screener (clique une ligne)</div>
    <table><thead><tr><th>#</th><th>Actif</th><th style="text-align:right">Score</th><th style="padding-left:14px">Raison</th></tr></thead><tbody>${rowsHtml}</tbody></table></div>`);
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
    <div class="card"><div class="label" style="margin-bottom:8px">Mesures relatives (vs S&amp;P 500)</div>
      <table><tbody>${relRows}</tbody></table></div>
    <div class="card"><div class="label" style="margin-bottom:8px">Risque (FRM)</div>
      <div class="grid2" style="gap:10px">
      <div><div style="color:var(--muted);font-size:12px">VaR 95%</div><div style="font-size:18px">${pct(rm.var_95)}</div></div>
      <div><div style="color:var(--muted);font-size:12px">CVaR 95%</div><div style="font-size:18px">${pct(rm.cvar_95)}</div></div>
      <div><div style="color:var(--muted);font-size:12px">Vol</div><div style="font-size:18px">${pct(rm.vol)}</div></div>
      <div><div style="color:var(--muted);font-size:12px">Proba ruine (MC)</div><div style="font-size:18px">${pct(a.monte_carlo.p_ruin)}</div></div>
      </div></div></div>`));
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
      rowsHtml+=`<tr class="srow"><td><b>${r.symbol}</b></td><td>${r.side}</td>
        <td class="mono" style="text-align:right">${r.qty}</td><td class="mono" style="text-align:right">${r.avg_price}</td>
        <td class="mono" style="text-align:right">${eur(r.current_value)}</td>
        <td class="mono ${r.pnl_abs>=0?'pos':'neg'}" style="text-align:right">${eur(r.pnl_abs)} (${pct(r.pnl_pct)})</td></tr>`;
    });
    inner=`<table><thead><tr><th>Actif</th><th>Sens</th><th style="text-align:right">Qté</th><th style="text-align:right">PRU</th><th style="text-align:right">Valeur</th><th style="text-align:right">P&amp;L</th></tr></thead><tbody>${rowsHtml}</tbody></table>`;
  }
  const box=$(`<div class="card"><div class="label" style="margin-bottom:10px">Composition</div>${inner}</div>`);
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

// ---- UNIVERS ----
(function(){
  const u=DATA.universe,p=document.getElementById('uni');if(!u)return;
  const g=$('<div class="grid4"></div>');
  [['Sources actives',u.sources_enabled+' / '+u.sources_total],['Instruments seed',eur(u.seed_total)],
   ['Classes d\'actifs',Object.keys(u.by_asset_class||{}).length],['Rebuild',u.rebuild_cadence_days+' j']]
   .forEach(([lab,val])=>g.appendChild($(`<div class="card metric"><div class="label">${lab}</div><div class="val" style="font-size:22px">${val}</div></div>`)));
  p.appendChild(g);
  // répartition par classe
  const bc=$(`<div class="card"><div class="label" style="margin-bottom:10px">Répartition par classe d'actifs (seed offline)</div></div>`);
  const max=Math.max(1,...Object.values(u.by_asset_class||{}));
  Object.entries(u.by_asset_class||{}).forEach(([k,v])=>{
    bc.appendChild($(`<div style="display:flex;align-items:center;gap:8px;margin:5px 0;font-size:12px">
      <span style="width:90px;color:var(--muted)">${k}</span>
      <span class="facbar" style="width:${Math.round(v/max*100)}%;max-width:420px"></span>
      <span class="mono">${v}</span></div>`));
  });
  p.appendChild(bc);
  // sources
  const sc=$(`<div class="card"><div class="label" style="margin-bottom:10px">Sources déclaratives (offline + réseau)</div></div>`);
  const srcRows=u.sources.map(s=>`<tr><td><b>${s.id}</b></td><td style="color:var(--muted)">${s.kind}</td>
    <td><span class="pill" style="color:${s.network?'#f59e0b':'#22c55e'}">${s.network?'réseau':'offline'}</span></td>
    <td><span class="pill" style="color:${s.enabled?'#22c55e':'#9aa1ab'}">${s.enabled?'activée':'désactivée'}</span></td></tr>`);
  sc.appendChild(mkTable('<th>Source</th><th>Type</th><th>Accès</th><th>Statut</th>',srcRows));
  p.appendChild(sc);
  // échantillon
  if(u.sample&&u.sample.length){
    const ec=$(`<div class="card"><div class="label" style="margin-bottom:10px">Échantillon d'instruments</div></div>`);
    const smp=u.sample.map(r=>`<tr><td class="mono"><b>${r.symbol}</b></td>
      <td style="color:var(--muted)">${r.name||''}</td><td>${r.asset_class||''}</td><td style="color:var(--muted)">${r.venue||''}</td></tr>`);
    ec.appendChild(mkTable('<th>Symbole</th><th>Nom</th><th>Classe</th><th>Place</th>',smp));
    p.appendChild(ec);
  }
})();

// ---- DONNÉES (collecte + base de données) ----
(function(){
  const d=DATA.data,p=document.getElementById('data');if(!d)return;
  // collecte
  const g=$('<div class="grid4"></div>');
  [['Provider',d.provider],['Barres collectées',eur(d.total_bars)],
   ['Symboles',(d.collection||[]).length],['Fondamentaux',d.fundamentals_provider||'—']]
   .forEach(([lab,val])=>g.appendChild($(`<div class="card metric"><div class="label">${lab}</div><div class="val" style="font-size:20px">${val}</div></div>`)));
  p.appendChild(g);
  const cc=$(`<div class="card"><div class="label" style="margin-bottom:6px">Collecte OHLCV</div>
    <div style="color:var(--muted);font-size:12px;margin-bottom:10px">Ordre de fallback : ${(d.fallback_order||[]).join(' → ')||'—'} · cache ${d.cache?'activé':'désactivé'}</div></div>`);
  const colRows=(d.collection||[]).map(r=>`<tr><td class="mono"><b>${r.symbol}</b></td>
    <td class="mono" style="text-align:right">${r.bars}</td><td class="mono" style="color:var(--muted)">${dt(r.start)}</td>
    <td class="mono" style="color:var(--muted)">${dt(r.end)}</td><td class="mono" style="text-align:right">${r.last_close}</td></tr>`);
  cc.appendChild(mkTable('<th>Symbole</th><th style="text-align:right">Barres</th><th>Début</th><th>Fin</th><th style="text-align:right">Dernier cours</th>',colRows));
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
})();
</script></body></html>"""


def build() -> str:
    snap = build_snapshot()
    return _TEMPLATE.replace("__DATA__", json.dumps(snap))


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "interactive.html"
    out.write_text(build(), encoding="utf-8")
    print(f"écrit : {out}")
