// search.js — ticker/company autocomplete over /search-index.json
(function () {
  let idx = [];
  fetch(window.SEARCH_URL).then(r => r.json()).then(d => { idx = d; }).catch(() => {});

  function wire(inputId, resultsId) {
    const input = document.getElementById(inputId);
    const box = document.getElementById(resultsId);
    if (!input || !box) return;
    function render(items) {
      if (!items.length) { box.classList.remove('show'); box.innerHTML = ''; return; }
      box.innerHTML = items.map(it =>
        `<a href="/stocks/${it.t.replace('/', '-')}/"><span class="tk">${it.t}</span><span class="nm">${it.n}</span></a>`
      ).join('');
      box.classList.add('show');
    }
    input.addEventListener('input', () => {
      const q = input.value.trim().toUpperCase();
      if (!q) { render([]); return; }
      const starts = [], contains = [];
      for (const it of idx) {
        const t = it.t.toUpperCase(), n = it.n.toUpperCase();
        if (t.startsWith(q)) starts.push(it);
        else if (t.includes(q) || n.includes(q)) contains.push(it);
        if (starts.length >= 8) break;
      }
      render(starts.concat(contains).slice(0, 8));
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') { const a = box.querySelector('a'); if (a) location.href = a.href; }
      if (e.key === 'Escape') render([]);
    });
    document.addEventListener('click', e => { if (!input.contains(e.target) && !box.contains(e.target)) render([]); });
  }
  wire('q', 'results');
  wire('q2', 'results2');
})();
