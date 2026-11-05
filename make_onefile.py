#!/usr/bin/env python3
"""make_onefile.py — build ONE self-contained HTML file that browses the site.

The deployed site is 5,930 separate pages; this packs the whole experience into
a single file with a client-side router: home, screener, sectors -> industries,
lists, compare, and stock pages. Full detail (charts/statements/quarters) is
inlined for the largest N companies; every other company still gets a page
built from index-level data.
"""
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
FULL_N = int(sys.argv[1]) if len(sys.argv) > 1 else 400

idx = json.loads((DATA / "index.json").read_text())
prices = json.loads((DATA / "prices.json").read_text())
css = (ROOT / "static/css/style.css").read_text()

# slim index rows
KEEP = ["ticker","name","sector","industry","fy","revenue","net_income","net_margin",
        "gross_margin","operating_margin","roe","roa","rev_cagr_5y","debt_to_equity",
        "current_ratio","fcf","fcf_margin","eps","dcf","ttm_revenue","ttm_net_income",
        "ttm_net_margin","ttm_eps","ttm_as_of","pays_dividend","dividend_per_share",
        "payout_ratio","dividend_cagr_5y","rev_spark"]
def rnd(v):
    return round(v, 4) if isinstance(v, float) else v
slim = [{k: rnd(r.get(k)) for k in KEEP if r.get(k) is not None} for r in idx]

# full records for the biggest companies
top = sorted(idx, key=lambda r: (r.get("revenue") or 0), reverse=True)[:FULL_N]
full = {}
for r in top:
    p = DATA / "companies" / f"{r['ticker'].replace('/','-')}.json"
    if not p.exists():
        continue
    rec = json.loads(p.read_text())
    full[rec["ticker"]] = {
        "years": rec["years"], "series": rec["series"], "latest": rec["latest"],
        "metrics": rec["metrics"], "dcf": rec.get("dcf"),
        "quarter_labels": rec.get("quarter_labels", []), "q_series": rec.get("q_series", {}),
        "ttm": rec.get("ttm", {}), "exchange": rec.get("exchange",""),
        "cik": rec.get("cik"), "data_through": rec.get("data_through",""),
    }

payload = json.dumps({"index": slim, "prices": prices, "full": full}, separators=(",", ":"))

html = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>StocksReviewer — full site preview</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap" rel="stylesheet">
<style>__CSS__
.hidden{display:none}
.nav-active{background:rgba(255,255,255,.12);color:#fff!important}
.pgnav{display:flex;gap:8px;align-items:center;margin:16px 0}
.pgnav button{font-family:var(--mono);font-size:.8rem;padding:6px 12px;border:1px solid var(--line);background:var(--card);border-radius:6px;cursor:pointer}
.pgnav button:disabled{opacity:.4;cursor:default}
.banner{background:var(--amber-wash,#fdf6e3);border:1px solid var(--line);border-left:3px solid var(--green-br);border-radius:8px;padding:10px 14px;font-size:.82rem;color:var(--ink-soft);margin:14px 0}
</style></head><body>
<header class="topbar"><div class="wrap">
<a href="#/" class="brand">Stocks<b>Reviewer</b></a>
<div class="searchbox"><input id="q" placeholder="Search ticker or company…" autocomplete="off"><div class="results" id="res"></div></div>
<nav class="tnav">
<a href="#/screener" data-nav="screener">Screener</a>
<a href="#/compare" data-nav="compare">Compare</a>
<a href="#/lists" data-nav="lists">Lists</a>
<a href="#/sectors" data-nav="sectors">Sectors</a>
</nav></div></header>
<div id="app"></div>
<footer class="foot"><div class="wrap"><div class="foot-legal">
Single-file preview of stocksreviewer.com — <span id="ftcount"></span> US companies, fundamentals from SEC EDGAR (public domain). Full detail pages inlined for the largest __FULLN__ by revenue; all others show summary data. Live price charts are omitted in this offline file. Not investment advice.
</div></div></footer>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const D=JSON.parse(document.getElementById('payload').textContent);
const IDX=D.index, PRICES=D.prices, FULL=D.full;
const BY={}; IDX.forEach(r=>BY[r.ticker]=r);
document.getElementById('ftcount').textContent=IDX.length.toLocaleString();
const app=document.getElementById('app');

const money=(v,dp=1)=>{if(v==null)return'—';const a=Math.abs(v),s=v<0?'-':'';
 if(a>=1e12)return s+'$'+(a/1e12).toFixed(dp)+'T';if(a>=1e9)return s+'$'+(a/1e9).toFixed(dp)+'B';
 if(a>=1e6)return s+'$'+(a/1e6).toFixed(dp)+'M';if(a>=1e3)return s+'$'+(a/1e3).toFixed(dp)+'K';return s+'$'+a.toFixed(0);};
const pct=(v,dp=1)=>v==null?'—':(v*100).toFixed(dp)+'%';
const usd=v=>v==null?'—':'$'+v.toFixed(2);
const rat=v=>v==null?'—':v.toFixed(2);
const cls=v=>v==null?'':(v<0?'neg':(v>0?'pos':''));
const slug=s=>(s||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function spark(vals,w=104,h=26){const pts=[];vals=vals||[];
 vals.forEach((v,i)=>{if(v!=null)pts.push([i,v]);});if(pts.length<2)return'';
 const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
 const dx=(x1-x0)||1,dy=(y1-y0)||1;
 const d=pts.map(([x,y],i)=>(i?'L':'M')+((x-x0)/dx*(w-2)+1).toFixed(1)+','+(h-1-(y-y0)/dy*(h-2)).toFixed(1)).join(' ');
 const col=ys[ys.length-1]>=ys[0]?'var(--green)':'var(--red)';
 return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path d="${d}" fill="none" stroke="${col}" stroke-width="1.5"/></svg>`;}

// axis chart identical in spirit to the built site
function chart(pairs,fmt){const present=pairs.filter(p=>p[1]!=null).map(p=>p[1]);
 if(!present.length)return'<p class="muted">No data.</p>';
 const mx=Math.max(...present),mn=Math.min(...present);
 const hi=Math.max(mx,0),lo=Math.min(mn,0),rng=(hi-lo)||1,zero=hi/rng*100;
 const F=v=>fmt==='usd'?usd(v):money(v);
 const bars=pairs.map(([x,v])=>{if(v==null)return`<div class="bcol"></div>`;
  const h=Math.abs(v)/rng*100, top=v>=0?zero-h:zero;
  return `<div class="bcol"><div class="bb${v<0?' down':''}" style="top:${top.toFixed(2)}%;height:${h.toFixed(2)}%" title="${x}: ${F(v)}"><span class="vl">${F(v)}</span></div></div>`;}).join('');
 return `<div class="chartbox"><div class="yaxis" style="height:160px"><span class="ymax">${F(mx)}</span>${mn<0?`<span class="yzero" style="top:${zero.toFixed(2)}%">0</span><span class="ymin">${F(mn)}</span>`:'<span class="ymin">$0</span>'}</div>
 <div class="plot"><div class="bars-area" style="height:160px"><div class="gl" style="top:0"></div><div class="gl gl-zero" style="top:${zero.toFixed(2)}%"></div>${bars}</div>
 <div class="xrow">${pairs.map(p=>`<div class="xcol">${p[0]}</div>`).join('')}</div></div></div>`;}

/* ---------------- HOME ---------------- */
function home(){
 const top=IDX.slice().sort((a,b)=>(b.revenue||0)-(a.revenue||0)).slice(0,15);
 app.innerHTML=`<section class="hero"><div class="wrap">
 <span class="kick">Sourced from SEC EDGAR · ${IDX.length.toLocaleString()} companies</span>
 <h1>The numbers companies <em>actually filed</em> — not the ones they advertised.</h1>
 <p>Revenue, earnings, cash flow, margins, returns, dividends and a transparent valuation model for US public companies. Pulled straight from XBRL filings.</p>
 <div class="hero-stats"><div><div class="n">${IDX.length.toLocaleString()}</div><div class="l">Companies</div></div>
 <div><div class="n">12yr</div><div class="l">Annual history</div></div>
 <div><div class="n">$0</div><div class="l">Public-domain data</div></div></div></div></section>
 <section class="section"><div class="wrap">
 <div class="banner">This is a single-file offline preview of the whole site. Everything works except the live TradingView price chart. Use the search box, or the Screener / Compare / Lists / Sectors links above.</div>
 <div class="panel-head"><h2 style="margin:0">Largest companies by revenue</h2><a class="kick" href="#/screener">Open screener →</a></div>
 <div class="tbl-wrap" style="margin-top:14px"><table><thead><tr><th class="l">Company</th><th>Revenue</th><th>Net income</th><th>Net margin</th><th>ROE</th><th>5y CAGR</th><th>EPS</th><th class="l">Trend</th></tr></thead><tbody>
 ${top.map(r=>`<tr onclick="location.hash='#/stock/${r.ticker}'" style="cursor:pointer">
 <td class="l"><span class="t-ticker">${r.ticker}</span> <span class="t-name">${esc(r.name)}</span></td>
 <td class="num">${money(r.revenue)}</td><td class="num ${cls(r.net_income)}">${money(r.net_income)}</td>
 <td class="num">${pct(r.net_margin)}</td><td class="num">${pct(r.roe)}</td>
 <td class="num ${cls(r.rev_cagr_5y)}">${pct(r.rev_cagr_5y)}</td><td class="num">${usd(r.eps)}</td>
 <td class="l">${spark(r.rev_spark)}</td></tr>`).join('')}
 </tbody></table></div></div></section>`;}

/* ---------------- SCREENER ---------------- */
let scrState={basis:'annual',sector:'',rev:0,margin:-99,cagr:-99,div:'',key:'revenue',dir:-1,page:0};
function screener(){
 const sectors=[...new Set(IDX.map(r=>r.sector).filter(Boolean))].sort();
 app.innerHTML=`<section class="section"><div class="wrap">
 <span class="kick">Fundamental screener</span><h1 style="margin:8px 0 4px">Screen by the filed numbers</h1>
 <p class="muted">All ${IDX.length.toLocaleString()} companies. Click a header to sort; click a row to open the company.</p>
 <div class="filters">
 <div><label>Basis</label><select id="f-basis"><option value="annual">Annual (last FY)</option><option value="ttm">TTM (last 4 qtrs)</option></select></div>
 <div><label>Sector</label><select id="f-sector"><option value="">All sectors</option>${sectors.map(s=>`<option>${esc(s)}</option>`).join('')}</select></div>
 <div><label>Min revenue</label><select id="f-rev"><option value="0">Any</option><option value="100000000">$100M+</option><option value="1000000000">$1B+</option><option value="10000000000">$10B+</option><option value="100000000000">$100B+</option></select></div>
 <div><label>Min net margin</label><select id="f-margin"><option value="-99">Any</option><option value="0">Profitable</option><option value="0.1">10%+</option><option value="0.2">20%+</option></select></div>
 <div><label>Min 5y rev CAGR</label><select id="f-cagr"><option value="-99">Any</option><option value="0">Growing</option><option value="0.1">10%+</option><option value="0.2">20%+</option></select></div>
 <div><label>Dividend</label><select id="f-div"><option value="">Any</option><option value="1">Pays dividend</option></select></div>
 <div class="count" id="count"></div></div>
 <div class="tbl-wrap"><table><thead><tr>
 <th class="l s" data-k="ticker">Ticker</th><th class="l s" data-k="name">Company</th>
 <th class="s" data-k="revenue" id="h-rev">Revenue</th><th class="s" data-k="net_income" id="h-ni">Net income</th>
 <th class="s" data-k="net_margin" id="h-nm">Net margin</th><th class="s" data-k="roe">ROE</th>
 <th class="s" data-k="rev_cagr_5y">5y CAGR</th><th class="s" data-k="dividend_per_share">Div/sh</th>
 <th class="s" data-k="debt_to_equity">D/E</th></tr></thead><tbody id="sb"></tbody></table></div>
 <div class="pgnav"><button id="prev">← Prev</button><span class="muted mono" id="pg"></span><button id="next">Next →</button></div>
 </div></section>`;
 const S=scrState;
 ['basis','sector','rev','margin','cagr','div'].forEach(k=>{const el=document.getElementById('f-'+k);el.value=S[k];el.onchange=()=>{S[k]=el.value;S.page=0;draw();};});
 document.querySelectorAll('th.s').forEach(th=>th.onclick=()=>{const k=th.dataset.k;
  if(k===S.key)S.dir*=-1;else{S.key=k;S.dir=(k==='ticker'||k==='name')?1:-1;}S.page=0;draw();});
 document.getElementById('prev').onclick=()=>{if(S.page>0){S.page--;draw();}};
 document.getElementById('next').onclick=()=>{S.page++;draw();};
 draw();
 function ttm(){return S.basis==='ttm';}
 function gv(r,k){if(k==='revenue')return ttm()&&r.ttm_revenue!=null?r.ttm_revenue:r.revenue;
  if(k==='net_income')return ttm()&&r.ttm_net_income!=null?r.ttm_net_income:r.net_income;
  if(k==='net_margin')return ttm()&&r.ttm_net_margin!=null?r.ttm_net_margin:r.net_margin;return r[k];}
 function draw(){
  document.getElementById('h-rev').textContent='Revenue'+(ttm()?' (TTM)':'');
  document.getElementById('h-ni').textContent='Net income'+(ttm()?' (TTM)':'');
  document.getElementById('h-nm').textContent='Net margin'+(ttm()?' (TTM)':'');
  let v=IDX.filter(r=>{
   if(S.sector&&r.sector!==S.sector)return false;
   if((gv(r,'revenue')||0)<parseFloat(S.rev))return false;
   const m=parseFloat(S.margin);if(m>-90&&(gv(r,'net_margin')==null||gv(r,'net_margin')<m))return false;
   const c=parseFloat(S.cagr);if(c>-90&&(r.rev_cagr_5y==null||r.rev_cagr_5y<c))return false;
   if(S.div==='1'&&!r.pays_dividend)return false;return true;});
  v.sort((a,b)=>{let x=gv(a,S.key),y=gv(b,S.key);
   if(typeof x==='string'||typeof y==='string')return S.dir*String(x||'').localeCompare(String(y||''));
   x=x==null?-Infinity:x;y=y==null?-Infinity:y;return S.dir*(x-y);});
  const per=100,pages=Math.max(1,Math.ceil(v.length/per));if(S.page>=pages)S.page=pages-1;
  const slice=v.slice(S.page*per,S.page*per+per);
  document.getElementById('sb').innerHTML=slice.map(r=>`<tr onclick="location.hash='#/stock/${r.ticker}'" style="cursor:pointer">
   <td class="l"><span class="t-ticker">${r.ticker}</span></td><td class="l t-name">${esc(r.name)}</td>
   <td class="num">${money(gv(r,'revenue'))}</td><td class="num ${cls(gv(r,'net_income'))}">${money(gv(r,'net_income'))}</td>
   <td class="num">${pct(gv(r,'net_margin'))}</td><td class="num">${pct(r.roe)}</td>
   <td class="num ${cls(r.rev_cagr_5y)}">${pct(r.rev_cagr_5y)}</td>
   <td class="num">${r.pays_dividend?usd(r.dividend_per_share):'—'}</td><td class="num">${rat(r.debt_to_equity)}</td></tr>`).join('');
  document.getElementById('count').textContent=v.length.toLocaleString()+' of '+IDX.length.toLocaleString()+(ttm()?' · TTM':'');
  document.getElementById('pg').textContent=`page ${S.page+1} / ${pages}`;
  document.getElementById('prev').disabled=S.page===0;document.getElementById('next').disabled=S.page>=pages-1;}}

/* ---------------- SECTORS ---------------- */
function sectors(){
 const g={};IDX.forEach(r=>{const s=r.sector||'Unclassified';(g[s]=g[s]||[]).push(r);});
 const cards=Object.entries(g).map(([s,rows])=>({s,n:rows.length,
  inds:new Set(rows.map(r=>r.industry||'Other')).size,tot:rows.reduce((a,r)=>a+(r.revenue||0),0)}))
  .sort((a,b)=>b.tot-a.tot);
 app.innerHTML=`<section class="section"><div class="wrap">
 <span class="kick">Sectors &amp; industries</span><h1 style="margin:8px 0 4px">Browse by sector</h1>
 <p class="muted">Eleven GICS sectors — the classification Fidelity uses — each split into industries.</p>
 <div class="card-grid">${cards.map(c=>`<a class="lcard" href="#/sector/${slug(c.s)}"><h3>${esc(c.s)}</h3>
 <div class="muted mono" style="font-size:.78rem">${c.n} companies · ${c.inds} industries</div>
 <div class="mono" style="font-size:.78rem;color:var(--accent);margin-top:4px">${money(c.tot)} revenue</div></a>`).join('')}</div>
 </div></section>`;}

function sectorPage(sl){
 const rows=IDX.filter(r=>slug(r.sector||'Unclassified')===sl);
 if(!rows.length){app.innerHTML='<section class="section"><div class="wrap"><p>Not found.</p></div></section>';return;}
 const name=rows[0].sector||'Unclassified';
 const g={};rows.forEach(r=>{const i=r.industry||'Other';(g[i]=g[i]||[]).push(r);});
 const inds=Object.entries(g).map(([i,rs])=>({i,n:rs.length,tot:rs.reduce((a,r)=>a+(r.revenue||0),0)})).sort((a,b)=>b.tot-a.tot);
 app.innerHTML=`<section class="section"><div class="wrap">
 <nav class="crumbs"><a href="#/sectors">Sectors</a> <span>/</span> ${esc(name)}</nav>
 <h1 style="margin:6px 0 4px">${esc(name)}</h1>
 <p class="muted">${rows.length} companies · ${inds.length} industries · ${money(rows.reduce((a,r)=>a+(r.revenue||0),0))} combined revenue</p>
 <h2>Industries</h2><div class="card-grid">${inds.map(c=>`<a class="lcard sm" href="#/industry/${sl}/${slug(c.i)}" style="display:flex;justify-content:space-between;align-items:center"><span>${esc(c.i)}</span><span class="muted">${c.n}</span></a>`).join('')}</div>
 <h2 style="margin-top:28px">Top companies</h2>${table(rows.sort((a,b)=>(b.revenue||0)-(a.revenue||0)).slice(0,150),true)}
 </div></section>`;}

function industryPage(sl,il){
 const rows=IDX.filter(r=>slug(r.sector||'Unclassified')===sl&&slug(r.industry||'Other')===il)
  .sort((a,b)=>(b.revenue||0)-(a.revenue||0));
 if(!rows.length){app.innerHTML='<section class="section"><div class="wrap"><p>Not found.</p></div></section>';return;}
 app.innerHTML=`<section class="section"><div class="wrap">
 <nav class="crumbs"><a href="#/sectors">Sectors</a> <span>/</span> <a href="#/sector/${sl}">${esc(rows[0].sector)}</a> <span>/</span> ${esc(rows[0].industry)}</nav>
 <h1 style="margin:6px 0 4px">${esc(rows[0].industry)}</h1><p class="muted">${rows.length} companies, ranked by revenue.</p>
 ${table(rows,true)}</div></section>`;}

function table(rows,showInd){
 return `<div class="tbl-wrap"><table><thead><tr><th class="l">Company</th>${showInd?'<th class="l">Industry</th>':''}
 <th>Revenue</th><th>Net income</th><th>Net margin</th><th>ROE</th><th>5y CAGR</th><th class="l">Trend</th></tr></thead><tbody>
 ${rows.map(r=>`<tr onclick="location.hash='#/stock/${r.ticker}'" style="cursor:pointer">
 <td class="l"><span class="t-ticker">${r.ticker}</span> <span class="t-name">${esc(r.name)}</span></td>
 ${showInd?`<td class="l muted" style="font-size:.8rem">${esc(r.industry||'—')}</td>`:''}
 <td class="num">${money(r.revenue)}</td><td class="num ${cls(r.net_income)}">${money(r.net_income)}</td>
 <td class="num">${pct(r.net_margin)}</td><td class="num">${pct(r.roe)}</td>
 <td class="num ${cls(r.rev_cagr_5y)}">${pct(r.rev_cagr_5y)}</td><td class="l">${spark(r.rev_spark)}</td></tr>`).join('')}
 </tbody></table></div>`;}

/* ---------------- LISTS ---------------- */
const LISTS=[
 ['most-profitable','Most Profitable Companies','Ranked by latest annual net income.','net_income',1,r=>(r.net_income||-1)>0,'money'],
 ['highest-net-margin','Highest Net Margin','Companies keeping the most of every revenue dollar.','net_margin',1,r=>(r.revenue||0)>=1e8&&r.net_margin!=null,'pct'],
 ['highest-roe','Highest Return on Equity','Net income relative to shareholder equity.','roe',1,r=>r.roe!=null&&(r.revenue||0)>=1e8&&r.roe<5,'pct'],
 ['fastest-growing','Fastest-Growing Revenue','Five-year revenue CAGR.','rev_cagr_5y',1,r=>r.rev_cagr_5y!=null&&(r.revenue||0)>=1e8,'pct'],
 ['highest-free-cash-flow','Highest Free Cash Flow','Operating cash flow minus capex.','fcf',1,r=>(r.fcf||0)>0,'money'],
 ['best-fcf-margin','Best Free-Cash-Flow Margin','FCF as a share of revenue.','fcf_margin',1,r=>(r.revenue||0)>=1e8&&r.fcf_margin!=null,'pct'],
 ['lowest-leverage','Lowest Leverage (Debt/Equity)','Profitable companies with least debt vs equity.','debt_to_equity',0,r=>r.debt_to_equity!=null&&r.debt_to_equity>=0&&(r.net_income||-1)>0,'ratio'],
 ['highest-ttm-revenue','Highest Revenue (TTM)','Trailing-twelve-month revenue.','ttm_revenue',1,r=>r.ttm_revenue!=null,'money'],
 ['most-profitable-ttm','Most Profitable (TTM)','Trailing-twelve-month net income.','ttm_net_income',1,r=>(r.ttm_net_income||-1)>0,'money'],
 ['top-dividend-payers','Top Dividend Payers','Highest dividend per share (latest FY).','dividend_per_share',1,r=>r.pays_dividend&&r.dividend_per_share,'usd'],
 ['best-dividend-growth','Best Dividend Growth','5-year growth of dividend per share.','dividend_cagr_5y',1,r=>r.dividend_cagr_5y!=null&&r.pays_dividend,'pct']];

function listsHub(){
 app.innerHTML=`<section class="section"><div class="wrap"><span class="kick">Lists</span>
 <h1 style="margin:8px 0 4px">Top companies, by the filed numbers</h1>
 <p class="muted">Rankings computed from SEC filings across all ${IDX.length.toLocaleString()} companies.</p>
 <div class="card-grid">${LISTS.map(l=>`<a class="lcard" href="#/list/${l[0]}"><h3>${l[1]}</h3><span class="kick">View ranking →</span></a>`).join('')}</div>
 </div></section>`;}

function listPage(id){
 const L=LISTS.find(l=>l[0]===id);if(!L){app.innerHTML='<div class="wrap"><p>Not found</p></div>';return;}
 const[,title,desc,key,dsc,filt,fmt]=L;
 const F=v=>fmt==='money'?money(v):fmt==='pct'?pct(v):fmt==='usd'?usd(v):rat(v);
 const rows=IDX.filter(filt).sort((a,b)=>{const x=a[key]==null?-Infinity:a[key],y=b[key]==null?-Infinity:b[key];return dsc?y-x:x-y;}).slice(0,100);
 app.innerHTML=`<section class="section"><div class="wrap">
 <nav class="crumbs"><a href="#/lists">Lists</a> <span>/</span> ${title}</nav>
 <h1 style="margin:6px 0 4px">${title}</h1><p class="muted">${desc} · top ${rows.length}</p>
 <div class="tbl-wrap"><table><thead><tr><th class="l">#</th><th class="l">Company</th><th>${fmt==='pct'?'Metric':fmt==='usd'?'Per share':'Value'}</th><th>Revenue</th><th>Net margin</th><th class="l">Trend</th></tr></thead><tbody>
 ${rows.map((r,i)=>`<tr onclick="location.hash='#/stock/${r.ticker}'" style="cursor:pointer">
 <td class="l num muted">${i+1}</td><td class="l"><span class="t-ticker">${r.ticker}</span> <span class="t-name">${esc(r.name)}</span></td>
 <td class="num"><strong>${F(r[key])}</strong></td><td class="num">${money(r.revenue)}</td>
 <td class="num">${pct(r.net_margin)}</td><td class="l">${spark(r.rev_spark)}</td></tr>`).join('')}
 </tbody></table></div>
 <div class="card-grid" style="margin-top:24px">${LISTS.filter(l=>l[0]!==id).map(l=>`<a class="lcard sm" href="#/list/${l[0]}">${l[1]} →</a>`).join('')}</div>
 </div></section>`;}

/* ---------------- COMPARE ---------------- */
let CMP=[];
function comparePage(){
 app.innerHTML=`<section class="section"><div class="wrap"><span class="kick">Compare</span>
 <h1 style="margin:8px 0 4px">Compare companies side by side</h1>
 <p class="muted">Add up to four tickers.</p>
 <div class="cmp-add"><div class="searchbox" style="max-width:340px">
 <input id="cq" placeholder="Add a ticker — AAPL, MSFT…" autocomplete="off"><div class="results" id="cres"></div></div>
 <div class="cmp-chips" id="chips"></div></div>
 <div id="cmpout"></div></div></section>`;
 const cq=document.getElementById('cq'),cres=document.getElementById('cres');
 cq.oninput=()=>{const v=cq.value.trim().toUpperCase();if(!v){cres.classList.remove('show');return;}
  const hits=IDX.filter(r=>r.ticker.startsWith(v)||r.name.toUpperCase().includes(v)).slice(0,8);
  cres.innerHTML=hits.map(r=>`<a href="#" data-add="${r.ticker}"><span class="tk">${r.ticker}</span><span class="nm">${esc(r.name)}</span></a>`).join('');
  cres.classList.toggle('show',hits.length>0);};
 cres.onclick=e=>{const a=e.target.closest('[data-add]');if(!a)return;e.preventDefault();
  if(CMP.length<4&&!CMP.includes(a.dataset.add))CMP.push(a.dataset.add);cq.value='';cres.classList.remove('show');drawCmp();};
 drawCmp();}
function drawCmp(){
 const chips=document.getElementById('chips'),out=document.getElementById('cmpout');
 if(!chips)return;
 chips.innerHTML=CMP.map(t=>`<span class="cmp-chip"><b>${t}</b><button data-rm="${t}">×</button></span>`).join('');
 chips.onclick=e=>{const b=e.target.closest('[data-rm]');if(!b)return;CMP=CMP.filter(x=>x!==b.dataset.rm);drawCmp();};
 if(!CMP.length){out.innerHTML='<p class="muted" style="margin-top:16px">No companies selected. <a href="#" id="cmpdemo">Try AAPL, MSFT, GOOGL</a>.</p>';
  const dm=document.getElementById('cmpdemo');
  if(dm)dm.onclick=e=>{e.preventDefault();CMP=['AAPL','MSFT','GOOGL'].filter(t=>BY[t]);drawCmp();};
  return;}
 const M=[['Revenue (FY)','revenue',money,1],['Net income','net_income',money,1],['Diluted EPS','eps',usd,1],
  ['Gross margin','gross_margin',pct,1],['Operating margin','operating_margin',pct,1],['Net margin','net_margin',pct,1],
  ['Free cash flow','fcf',money,1],['FCF margin','fcf_margin',pct,1],['Return on equity','roe',pct,1],
  ['Return on assets','roa',pct,1],['5y revenue CAGR','rev_cagr_5y',pct,1],['Debt / equity','debt_to_equity',rat,0],
  ['Current ratio','current_ratio',rat,1],['Dividend / share','dividend_per_share',usd,1],['DCF / share','dcf',usd,null]];
 let h='<div class="tbl-wrap" style="margin-top:18px"><table><tbody><tr><th class="l">Metric</th>'+
  CMP.map(t=>`<th><a href="#/stock/${t}" class="t-ticker">${t}</a><div class="cmp-nm">${esc(BY[t].name)}</div></th>`).join('')+'</tr>';
 M.forEach(([label,k,F,hi])=>{let bi=-1,bv=null;
  if(hi!=null)CMP.forEach((t,i)=>{const v=BY[t][k];if(v==null)return;if(bv==null||(hi?v>bv:v<bv)){bv=v;bi=i;}});
  h+=`<tr><td class="l">${label}</td>`+CMP.map((t,i)=>`<td class="num${i===bi?' cmp-win':''}">${F(BY[t][k])}</td>`).join('')+'</tr>';});
 out.innerHTML=h+'</tbody></table></div>';}

/* ---------------- STOCK ---------------- */
function stockPage(tk){
 const r=BY[tk];if(!r){app.innerHTML='<section class="section"><div class="wrap"><p>Unknown ticker.</p></div></section>';return;}
 const f=FULL[tk],p=PRICES[tk];
 let h=`<div class="stock-head"><div class="wrap"><div class="sh-id">
 <span class="tk">${tk}</span><h1>${esc(r.name)}</h1>
 <div class="sub">${f&&f.exchange?f.exchange+' · ':''}<a href="#/sector/${slug(r.sector)}">${esc(r.sector||'')}</a> · ${esc(r.industry||'')}${f&&f.cik?' · CIK '+f.cik:''}</div></div>
 <div class="sh-badges"><span class="badge">FY${r.fy} reported</span>
 ${r.net_margin>0?'<span class="badge g">Profitable</span>':''}
 ${r.rev_cagr_5y>0.1?`<span class="badge g">5y rev +${pct(r.rev_cagr_5y,0)}</span>`:''}</div></div></div><div class="wrap">`;
 h+=`<div class="kpi-grid">
 <div class="kpi"><div class="l">Revenue FY${r.fy}</div><div class="v">${money(r.revenue)}</div></div>
 <div class="kpi"><div class="l">Net income</div><div class="v ${cls(r.net_income)}">${money(r.net_income)}</div></div>
 <div class="kpi"><div class="l">Diluted EPS</div><div class="v">${usd(r.eps)}</div></div>
 <div class="kpi"><div class="l">Net margin</div><div class="v">${pct(r.net_margin)}</div></div>
 <div class="kpi"><div class="l">Free cash flow</div><div class="v ${cls(r.fcf)}">${money(r.fcf)}</div></div>
 <div class="kpi"><div class="l">ROE</div><div class="v">${pct(r.roe)}</div></div></div>`;
 if(r.ttm_revenue)h+=`<div class="ttm-strip"><div class="ttm-tag">Trailing 12 months <span class="muted">· through ${r.ttm_as_of||''}</span></div>
 <div class="ttm-vals"><div><span class="l">Revenue</span><span class="v">${money(r.ttm_revenue)}</span></div>
 <div><span class="l">Net income</span><span class="v ${cls(r.ttm_net_income)}">${money(r.ttm_net_income)}</span></div>
 <div><span class="l">Diluted EPS</span><span class="v">${usd(r.ttm_eps)}</span></div>
 <div><span class="l">Net margin</span><span class="v">${pct(r.ttm_net_margin)}</span></div></div></div>`;
 if(p){const per=['5-day','10-day','1-month','3-month','6-month','YTD','1-year','2-year','5-year','10-year'];
  h+=`<div class="panel"><div class="panel-head"><h2 style="margin:0">Price performance</h2><span class="muted" style="font-size:.8rem">total return · as of ${p.as_of}</span></div>
  <div class="perf-grid">${per.map(k=>{const v=p[k];return `<div class="perf-row"><span class="perf-l">${k}</span>
  <span class="perf-v ${v==null?'':(v>0?'pos':v<0?'neg':'')}">${v==null?'—':(v>0?'+':'')+v.toFixed(2)+'%'}</span></div>`;}).join('')}</div>
  <p class="skip-note muted" style="font-size:.78rem;margin-top:10px">Split- and dividend-adjusted total return from trailing-date closes.</p></div>`;}
 if(f){
  const yrs=f.years, S=f.series;
  const pairs=(m)=>yrs.map(y=>["'"+String(y%100).padStart(2,'0'),(S[m]||{})[String(y)]!=null?S[m][String(y)]:null]);
  h+=`<div class="panel"><div class="panel-head"><h2 style="margin:0">Revenue</h2><span class="muted" style="font-size:.8rem">${yrs[0]}–${yrs[yrs.length-1]}, USD</span></div>${chart(pairs('revenue'),'money')}</div>`;
  h+=`<div class="panel"><div class="panel-head"><h2 style="margin:0">Net income</h2><span class="muted" style="font-size:.8rem">USD</span></div>${chart(pairs('net_income'),'money')}</div>`;
  h+=`<div class="panel"><div class="panel-head"><h2 style="margin:0">Free cash flow</h2><span class="muted" style="font-size:.8rem">operating CF − capex</span></div>${chart(pairs('fcf'),'money')}</div>`;
  const ql=f.quarter_labels||[];
  if(ql.length){const qp=m=>ql.map(l=>[l.replace(/^FY/,''),(f.q_series[m]||{})[l]!=null?f.q_series[m][l]:null]);
   h+=`<div class="panel"><div class="panel-head"><h2 style="margin:0">Quarterly revenue</h2><span class="muted" style="font-size:.8rem">last ${ql.length} quarters</span></div>${chart(qp('revenue'),'money')}</div>`;
   h+=`<div class="panel"><div class="panel-head"><h2 style="margin:0">Quarterly diluted EPS</h2><span class="muted" style="font-size:.8rem">USD/share</span></div>${chart(qp('eps_diluted'),'usd')}</div>`;}
  if(f.dcf)h+=`<div class="panel"><div class="panel-head"><h2 style="margin:0">Valuation — DCF estimate</h2></div>
   <div class="dcf-box"><div><div class="big">${usd(f.dcf.intrinsic_per_share)}</div><div class="muted" style="font-size:.74rem">intrinsic value / share</div></div>
   <div class="note">Two-stage DCF from FY${r.fy} free cash flow of ${money(f.dcf.assumptions.base_fcf)}, growing ${pct(f.dcf.assumptions.growth_5y)} for 5 years then ${pct(f.dcf.assumptions.terminal_growth)} terminally, discounted at ${pct(f.dcf.assumptions.discount_rate)}. A model is only as good as its assumptions.</div></div></div>`;
  const stmt=(title,keys)=>{let t=`<div class="panel"><h2 style="margin-top:0">${title}</h2><div class="tbl-wrap"><table><thead><tr><th class="l">USD</th>${yrs.map(y=>`<th>FY${String(y%100).padStart(2,'0')}</th>`).join('')}</tr></thead><tbody>`;
   keys.forEach(([lab,k])=>{t+=`<tr><td class="l">${lab}</td>`+yrs.map(y=>{const v=(S[k]||{})[String(y)];
    return `<td class="num ${v<0?'neg':''}">${k==='eps_diluted'?usd(v==null?null:v):money(v==null?null:v)}</td>`;}).join('')+'</tr>';});
   return t+'</tbody></table></div></div>';};
  h+=stmt('Income statement',[['Revenue','revenue'],['Cost of revenue','cost_of_revenue'],['Gross profit','gross_profit'],['Operating income','operating_income'],['Net income','net_income'],['Diluted EPS','eps_diluted']]);
  h+=stmt('Balance sheet',[['Total assets','assets'],['Current assets','current_assets'],['Total liabilities','liabilities'],['Current liabilities','current_liabilities'],['Cash & equivalents','cash'],['Shareholder equity','equity']]);
  h+=stmt('Cash flow',[['Operating cash flow','op_cash_flow'],['Capital expenditure','capex'],['Free cash flow','fcf']]);
  const M=f.metrics;
  if(M.pays_dividend)h+=`<div class="panel"><h2 style="margin-top:0">Dividends</h2><div class="kpi-grid" style="box-shadow:none">
   <div class="kpi"><div class="l">Dividend / share</div><div class="v">${usd(M.dividend_per_share)}</div></div>
   <div class="kpi"><div class="l">Payout ratio</div><div class="v">${pct(M.payout_ratio)}</div></div>
   <div class="kpi"><div class="l">Dividends paid</div><div class="v">${money(M.dividends_paid)}</div></div>
   <div class="kpi"><div class="l">5y dividend growth</div><div class="v">${pct(M.dividend_cagr_5y)}</div></div></div></div>`;
  h+=`<div class="panel"><h2 style="margin-top:0">Key ratios (FY${r.fy})</h2><div class="kpi-grid" style="box-shadow:none">
   <div class="kpi"><div class="l">Gross margin</div><div class="v">${pct(M.gross_margin)}</div></div>
   <div class="kpi"><div class="l">Operating margin</div><div class="v">${pct(M.operating_margin)}</div></div>
   <div class="kpi"><div class="l">FCF margin</div><div class="v">${pct(M.fcf_margin)}</div></div>
   <div class="kpi"><div class="l">ROA</div><div class="v">${pct(M.roa)}</div></div>
   <div class="kpi"><div class="l">Debt / equity</div><div class="v">${rat(M.debt_to_equity)}</div></div>
   <div class="kpi"><div class="l">Current ratio</div><div class="v">${rat(M.current_ratio)}</div></div>
   <div class="kpi"><div class="l">Book value / share</div><div class="v">${usd(M.book_value_per_share)}</div></div>
   <div class="kpi"><div class="l">FCF / share</div><div class="v">${usd(M.fcf_per_share)}</div></div></div></div>`;
  h+=`<div class="disclaimer-strip">Data extracted from ${tk}'s XBRL filings on SEC EDGAR. Fiscal years labeled by period-end year. Verify against the original filing. Not investment advice.</div>`;
 } else {
  h+=`<div class="panel"><h2 style="margin-top:0">Summary</h2><div class="kpi-grid" style="box-shadow:none">
  <div class="kpi"><div class="l">Gross margin</div><div class="v">${pct(r.gross_margin)}</div></div>
  <div class="kpi"><div class="l">Operating margin</div><div class="v">${pct(r.operating_margin)}</div></div>
  <div class="kpi"><div class="l">ROA</div><div class="v">${pct(r.roa)}</div></div>
  <div class="kpi"><div class="l">Debt / equity</div><div class="v">${rat(r.debt_to_equity)}</div></div>
  <div class="kpi"><div class="l">Current ratio</div><div class="v">${rat(r.current_ratio)}</div></div>
  <div class="kpi"><div class="l">5y revenue CAGR</div><div class="v">${pct(r.rev_cagr_5y)}</div></div>
  ${r.pays_dividend?`<div class="kpi"><div class="l">Dividend / share</div><div class="v">${usd(r.dividend_per_share)}</div></div>`:''}
  ${r.dcf?`<div class="kpi"><div class="l">DCF / share</div><div class="v">${usd(r.dcf)}</div></div>`:''}</div>
  <div class="banner" style="margin-top:14px">Full statements, charts and quarterly data for this company are on the deployed site — this single-file preview inlines full detail only for the largest __FULLN__ companies by revenue, to keep the file openable.</div></div>`;}
 h+=`<div style="margin:22px 0 40px"><a class="lcard sm" href="#/sector/${slug(r.sector)}">← All ${esc(r.sector||'')} companies</a></div></div>`;
 app.innerHTML=h;}

/* ---------------- SEARCH + ROUTER ---------------- */
const q=document.getElementById('q'),res=document.getElementById('res');
q.addEventListener('input',()=>{const v=q.value.trim().toUpperCase();if(!v){res.classList.remove('show');return;}
 const st=[],ct=[];
 for(const r of IDX){if(r.ticker.startsWith(v))st.push(r);else if(r.ticker.includes(v)||r.name.toUpperCase().includes(v))ct.push(r);if(st.length>=8)break;}
 const hits=st.concat(ct).slice(0,8);
 res.innerHTML=hits.map(r=>`<a href="#/stock/${r.ticker}"><span class="tk">${r.ticker}</span><span class="nm">${esc(r.name)}</span></a>`).join('');
 res.classList.toggle('show',hits.length>0);});
q.addEventListener('keydown',e=>{if(e.key==='Enter'){const a=res.querySelector('a');if(a)location.hash=a.getAttribute('href');q.value='';res.classList.remove('show');}});
document.addEventListener('click',e=>{if(!q.contains(e.target)&&!res.contains(e.target))res.classList.remove('show');});
res.addEventListener('click',()=>{q.value='';res.classList.remove('show');});

function route(){
 const h=(location.hash||'#/').slice(2).split('/');
 document.querySelectorAll('[data-nav]').forEach(a=>a.classList.toggle('nav-active',a.dataset.nav===h[0]));
 window.scrollTo(0,0);
 switch(h[0]){
  case '':return home();
  case 'screener':return screener();
  case 'sectors':return sectors();
  case 'sector':return sectorPage(h[1]);
  case 'industry':return industryPage(h[1],h[2]);
  case 'lists':return listsHub();
  case 'list':return listPage(h[1]);
  case 'compare':return comparePage();
  case 'stock':return stockPage(decodeURIComponent(h[1]||''));
  default:return home();}}
window.addEventListener('hashchange',route);
route();
</script></body></html>"""

html = html.replace("__CSS__", css).replace("__PAYLOAD__", payload).replace("__FULLN__", str(len(full)))
out = Path("/mnt/user-data/outputs/stocksreviewer-FULL-SITE.html")
out.write_text(html, encoding="utf-8")
print("wrote", out, round(out.stat().st_size/1e6, 1), "MB")
print("full-detail companies:", len(full), "| index rows:", len(slim), "| priced:", len(prices))
