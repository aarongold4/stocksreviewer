// compare.js — side-by-side fundamentals, up to 4 tickers
(function () {
  let rows = [], byTicker = {}, selected = [];
  const MAX = 4;
  const q = document.getElementById('cmp-q');
  const res = document.getElementById('cmp-results');
  const chips = document.getElementById('cmp-chips');
  const out = document.getElementById('cmp-out');
  const empty = document.getElementById('cmp-empty');
  const tbody = document.querySelector('#cmp-table tbody');

  const money = v => { if (v == null) return '—'; const a = Math.abs(v), s = v < 0 ? '-' : ''; if (a >= 1e12) return `${s}$${(a/1e12).toFixed(2)}T`; if (a >= 1e9) return `${s}$${(a/1e9).toFixed(1)}B`; if (a >= 1e6) return `${s}$${(a/1e6).toFixed(1)}M`; return `${s}$${a.toFixed(0)}`; };
  const pct = v => v == null ? '—' : `${(v*100).toFixed(1)}%`;
  const rat = v => v == null ? '—' : v.toFixed(2);
  const usd = v => v == null ? '—' : `$${v.toFixed(2)}`;
  const title = s => s.replace(/\b\w/g, c => c.toUpperCase());

  // metric rows: [label, key, formatter, higherIsBetter|null]
  const METRICS = [
    ['Revenue (FY)', 'revenue', money, 1],
    ['Net income', 'net_income', money, 1],
    ['Diluted EPS', 'eps', usd, 1],
    ['Gross margin', 'gross_margin', pct, 1],
    ['Operating margin', 'operating_margin', pct, 1],
    ['Net margin', 'net_margin', pct, 1],
    ['Free cash flow', 'fcf', money, 1],
    ['FCF margin', 'fcf_margin', pct, 1],
    ['Return on equity', 'roe', pct, 1],
    ['Return on assets', 'roa', pct, 1],
    ['5y revenue CAGR', 'rev_cagr_5y', pct, 1],
    ['Debt / equity', 'debt_to_equity', rat, 0],
    ['Current ratio', 'current_ratio', rat, 1],
    ['DCF / share', 'dcf', usd, null],
  ];

  function add(t) {
    t = t.toUpperCase();
    if (selected.includes(t) || !byTicker[t] || selected.length >= MAX) return;
    selected.push(t); q.value = ''; res.classList.remove('show'); render();
  }
  function remove(t) { selected = selected.filter(x => x !== t); render(); }

  function bestIndex(key, higher) {
    if (higher == null) return -1;
    let bi = -1, bv = null;
    selected.forEach((t, i) => {
      const v = byTicker[t][key];
      if (v == null) return;
      if (bv == null || (higher ? v > bv : v < bv)) { bv = v; bi = i; }
    });
    return bi;
  }

  function render() {
    chips.innerHTML = selected.map(t =>
      `<span class="cmp-chip"><b>${t}</b><button data-rm="${t}">×</button></span>`).join('');
    if (!selected.length) { out.style.display = 'none'; empty.style.display = ''; return; }
    empty.style.display = 'none'; out.style.display = '';

    let html = '<tr><th class="l">Metric</th>' +
      selected.map(t => `<th><a href="/stocks/${t.replace('/','-')}/" class="t-ticker">${t}</a><div class="cmp-nm">${byTicker[t].name}</div></th>`).join('') + '</tr>';
    for (const [label, key, fmt, higher] of METRICS) {
      const bi = bestIndex(key, higher);
      html += `<tr><td class="l">${label}</td>` + selected.map((t, i) => {
        const v = byTicker[t][key];
        const win = i === bi ? ' cmp-win' : '';
        return `<td class="num${win}">${fmt(v)}</td>`;
      }).join('') + '</tr>';
    }
    tbody.innerHTML = html;
  }

  // autocomplete
  q.addEventListener('input', () => {
    const v = q.value.trim().toUpperCase();
    if (!v) { res.classList.remove('show'); return; }
    const hits = rows.filter(r => r.ticker.startsWith(v) || r.name.toUpperCase().includes(v)).slice(0, 8);
    res.innerHTML = hits.map(r => `<a href="#" data-add="${r.ticker}"><span class="tk">${r.ticker}</span><span class="nm">${r.name}</span></a>`).join('');
    res.classList.toggle('show', hits.length > 0);
  });
  document.addEventListener('click', e => {
    const a = e.target.closest('[data-add]');
    if (a) { e.preventDefault(); add(a.dataset.add); }
    const rm = e.target.closest('[data-rm]');
    if (rm) { e.preventDefault(); remove(rm.dataset.rm); }
    if (!q.contains(e.target) && !res.contains(e.target)) res.classList.remove('show');
  });

  fetch('/screener-index.json').then(r => r.json()).then(d => {
    rows = d; d.forEach(r => byTicker[r.ticker] = r);
    // support /compare/?tickers=AAPL,MSFT
    const p = new URLSearchParams(location.search).get('tickers');
    if (p) p.split(',').forEach(t => add(t.trim()));
    render();
  });
})();
