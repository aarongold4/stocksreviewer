// screener.js — client-side filter + sort over /screener-index.json
(function () {
  let rows = [];
  let sortKey = 'revenue', sortDir = -1;
  const body = document.getElementById('scr-body');
  const count = document.getElementById('count');
  const F = {
    basis: document.getElementById('f-basis'),
    sector: document.getElementById('f-sector'),
    rev: document.getElementById('f-rev'),
    margin: document.getElementById('f-margin'),
    cagr: document.getElementById('f-cagr'),
    div: document.getElementById('f-div'),
  };

  const money = v => { if (v == null) return '—'; const a = Math.abs(v), s = v < 0 ? '-' : ''; if (a >= 1e12) return `${s}$${(a/1e12).toFixed(1)}T`; if (a >= 1e9) return `${s}$${(a/1e9).toFixed(1)}B`; if (a >= 1e6) return `${s}$${(a/1e6).toFixed(1)}M`; return `${s}$${a.toFixed(0)}`; };
  const pct = v => v == null ? '—' : `${(v*100).toFixed(1)}%`;
  const rat = v => v == null ? '—' : v.toFixed(2);
  const usd = v => v == null ? '—' : `$${v.toFixed(2)}`;
  const cls = v => v == null ? '' : (v < 0 ? 'neg' : (v > 0 ? 'pos' : ''));
  const title = s => s.replace(/\b\w/g, c => c.toUpperCase());

  const ttm = () => F.basis.value === 'ttm';
  const rev = r => ttm() ? (r.ttm_revenue != null ? r.ttm_revenue : r.revenue) : r.revenue;
  const ni = r => ttm() ? (r.ttm_net_income != null ? r.ttm_net_income : r.net_income) : r.net_income;
  const nm = r => ttm() ? (r.ttm_net_margin != null ? r.ttm_net_margin : r.net_margin) : r.net_margin;

  function passes(r) {
    if (F.sector.value && r.sector !== F.sector.value) return false;
    if ((rev(r) || 0) < parseFloat(F.rev.value)) return false;
    const m = parseFloat(F.margin.value);
    if (m > -90 && (nm(r) == null || nm(r) < m)) return false;
    const c = parseFloat(F.cagr.value);
    if (c > -90 && (r.rev_cagr_5y == null || r.rev_cagr_5y < c)) return false;
    if (F.div.value === '1' && !r.pays_dividend) return false;
    return true;
  }

  function getKey(r, k) {
    if (k === 'revenue') return rev(r);
    if (k === 'net_income') return ni(r);
    if (k === 'net_margin') return nm(r);
    return r[k];
  }

  function render() {
    const suffix = ttm() ? ' (TTM)' : '';
    document.getElementById('h-rev').childNodes[0].nodeValue = 'Revenue' + suffix + ' ';
    document.getElementById('h-ni').textContent = 'Net income' + suffix;
    document.getElementById('h-nm').textContent = 'Net margin' + suffix;

    let view = rows.filter(passes);
    view.sort((a, b) => {
      let x = getKey(a, sortKey), y = getKey(b, sortKey);
      if (typeof x === 'string' || typeof y === 'string') { x = x || ''; y = y || ''; return sortDir * String(x).localeCompare(String(y)); }
      x = x == null ? -Infinity : x; y = y == null ? -Infinity : y;
      return sortDir * (x - y);
    });
    body.innerHTML = view.map(r => `
      <tr onclick="location.href='/stocks/${r.ticker.replace('/', '-')}/'" style="cursor:pointer">
        <td class="l"><span class="t-ticker">${r.ticker}</span></td>
        <td class="l t-name">${r.name}</td>
        <td class="num">${money(rev(r))}</td>
        <td class="num ${cls(ni(r))}">${money(ni(r))}</td>
        <td class="num">${pct(nm(r))}</td>
        <td class="num">${pct(r.roe)}</td>
        <td class="num ${cls(r.rev_cagr_5y)}">${pct(r.rev_cagr_5y)}</td>
        <td class="num">${r.pays_dividend ? usd(r.dividend_per_share) : '—'}</td>
        <td class="num">${rat(r.debt_to_equity)}</td>
      </tr>`).join('');
    count.textContent = `${view.length} of ${rows.length}${ttm() ? ' · TTM basis' : ''}`;
  }

  document.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const k = th.dataset.k;
      if (k === sortKey) sortDir *= -1;
      else { sortKey = k; sortDir = th.dataset.num ? -1 : 1; }
      document.querySelectorAll('th.sortable').forEach(t => { t.classList.remove('act'); const a = t.querySelector('.arw'); if (a) a.remove(); });
      th.classList.add('act');
      th.insertAdjacentHTML('beforeend', ` <span class="arw">${sortDir < 0 ? '▼' : '▲'}</span>`);
      render();
    });
  });
  Object.values(F).forEach(el => el.addEventListener('change', render));

  fetch('/screener-index.json').then(r => r.json()).then(d => { rows = d; render(); });
})();
