/* ── Stocks Screener · screener.js ─────────────────────────────────
   The backend serves one snapshot of the whole universe (~750 rows);
   every filter, facet count and sort below runs in the browser, so
   changing a filter never waits on the network. The snapshot is polled
   with ?since=<version> so unchanged polls cost a few bytes. */

(() => {
  const { API_BASE, localTimeStr, setStatus } = window.Shell;
  const $ = (id) => document.getElementById(id);
  const PAGE = 100;
  const STORE_KEY = 'screener.state.v1';

  // ── Config ──────────────────────────────────────────────────────
  const SORTS = [
    { key: 'popularity', label: 'Popularity', hint: "Ranked by today's traded value" },
    { key: 'volume', label: 'High volume', variants: [['today', 'Today'], ['5m', 'Last 5 min']] },
    { key: 'price', label: 'Market price', variants: [['desc', 'High to low'], ['asc', 'Low to high']] },
    { key: 'change', label: '1D price change', variants: [['desc', 'High to low'], ['asc', 'Low to high']] },
    { key: 'mcap', label: 'Market cap', variants: [['desc', 'High to low'], ['asc', 'Low to high']] },
  ];

  const FILTERS = [
    {
      key: 'move', label: 'PRICE CHANGE > 1%',
      desc: 'Stocks that moved more than 1%, up or down, within the chosen time frame. Useful for spotting big moves quickly.',
      options: [['', 'None'], ['5m', 'Last 5 min'], ['15m', 'Last 15 min'], ['1h', 'Last 1 hour'], ['today', 'Today']],
      test: (r, v) => {
        const x = v === '5m' ? r.ch5m : v === '15m' ? r.ch15m : v === '1h' ? r.ch1h : r.chp;
        return x != null && Math.abs(x) > 1;
      },
    },
    {
      key: 'w52', label: '52W PERFORMANCE',
      desc: 'Trading within 2% of the 52-week high or low. Near the high can mean strong momentum; near the low may suggest a recovery opportunity.',
      options: [['', 'None'], ['high', 'Near 52W high'], ['low', 'Near 52W low']],
      test: (r, v) => r.hi52 != null && (v === 'high' ? r.p >= r.hi52 * 0.98 : r.p <= r.lo52 * 1.02),
    },
    {
      key: 'rsi', label: 'RSI (14)',
      desc: '14-day Relative Strength Index, using the live price for today.',
      options: [['', 'None'], ['oversold', 'Oversold < 30'], ['overbought', 'Overbought > 70']],
      test: (r, v) => r.rsi != null && (v === 'oversold' ? r.rsi < 30 : r.rsi > 70),
    },
    {
      key: 'macd', label: 'MACD (12, 26, 9)',
      desc: 'MACD compares the 12-day and 26-day EMAs against a 9-day EMA signal line. Bullish / Bearish: MACD crossed above / below the signal line in the last 3 sessions. Positive / Negative: MACD line above / below zero.',
      options: [['', 'None'], ['bullish', 'Bullish'], ['positive', 'Positive'], ['bearish', 'Bearish'], ['negative', 'Negative']],
      test: (r, v) => {
        if (v === 'bullish' || v === 'bearish') return r.macdCross === v;
        if (r.macd == null) return false;
        return v === 'positive' ? r.macd > 0 : r.macd < 0;
      },
    },
    {
      key: 'pivot', label: 'NEAR BREAKOUT',
      desc: 'Pivot-point resistance from the previous session. A stock near a resistance level may reverse there (within 1% below it); a breakout above it can signal a bullish trend.',
      options: [['', 'None'], ['near_r1', 'Near R1'], ['r1_breakout', 'R1 breakout'], ['near_r2', 'Near R2'],
        ['r2_breakout', 'R2 breakout'], ['near_r3', 'Near R3'], ['r3_breakout', 'R3 breakout']],
      test: (r, v) => r.pivZone === v,
    },
  ];
  const FILTER_BY_KEY = Object.fromEntries(FILTERS.map((f) => [f.key, f]));

  const INDICES = [
    ['all', 'All'], ['nifty50', 'Nifty 50'], ['nifty100', 'Nifty 100'], ['nifty500', 'Nifty 500'],
    ['midcap100', 'Nifty Midcap 100'], ['midcap150', 'Nifty Midcap 150'],
    ['smallcap100', 'Nifty Smallcap 100'], ['smallcap250', 'Nifty Smallcap 250'],
    ['total', 'Nifty Total Market'],
  ];
  const INDEX_LABEL = Object.fromEntries(INDICES);

  const SECTORS = [
    'Agriculture & Allied Industries', 'Apparel and Clothes', 'Auto Ancillary', 'Auto Manufacturers',
    'Auto Retail', 'Aviation', 'Banks', 'Batteries', 'Bearings', 'Building Materials', 'Cement',
    'Ceramic Products', 'Chemicals', 'Defence', 'Distributors', 'E-Commerce/App based Aggregator',
    'Education', 'Electrical Appliances', 'Electrical Equipment', 'Electronic Manufacturers',
    'Engineering', 'Financial Services', 'FMCG', 'Food & Beverages', 'Footwear', 'Furniture',
    'Gas Distribution', 'Healthcare', 'Hospitality', 'Infrastructure', 'Information Technology',
    'Insurance', 'Jewellery', 'Leather', 'Logistics', 'Maritime Industries', 'Media & Entertainment',
    'Metals & Mining', 'Oil', 'Packaging', 'Paints', 'Paper', 'Pharmaceuticals', 'Plastic and Polymers',
    'Power', 'Professional Services', 'Railways', 'Rating Agencies', 'Real Estate',
    'Real Estate Investment Trusts', 'Refractories', 'Retail Chains', 'Rubber Products', 'Sugar',
    'Telecom', 'Telecom Equipment & Infra Services', 'Textiles', 'Tyre', 'Waste Management',
    'Water Distribution',
  ];

  const CAPS = [
    { key: 'large', label: 'Largecap', range: '₹1L Cr and above' },
    { key: 'mid', label: 'Midcap', range: '₹30K Cr to ₹1L Cr' },
    { key: 'small', label: 'Smallcap', range: '₹5K Cr to ₹30K Cr' },
    { key: 'micro', label: 'Microcap', range: 'Below ₹5K Cr' },
  ];
  const capBand = (m) => (m == null ? null : m >= 1e5 ? 'large' : m >= 3e4 ? 'mid' : m >= 5e3 ? 'small' : 'micro');

  // ── State ───────────────────────────────────────────────────────
  const DEFAULT_STATE = () => ({
    sort: { key: 'popularity', variant: null },
    move: '', w52: '', rsi: '', macd: '', pivot: '',
    index: 'all', sectors: new Set(), caps: new Set(),
  });
  let state = loadState();
  let rows = [];
  let meta = null;
  let version = null;
  let shown = PAGE;
  let lastFiltered = [];
  let pollTimer = null;
  let failCount = 0;
  let sectorQuery = '';

  function loadState() {
    const s = DEFAULT_STATE();
    try {
      const raw = JSON.parse(localStorage.getItem(STORE_KEY) || 'null');
      if (!raw) return s;
      if (raw.sort && SORTS.some((x) => x.key === raw.sort.key)) s.sort = raw.sort;
      FILTERS.forEach((f) => { if (f.options.some(([v]) => v === raw[f.key])) s[f.key] = raw[f.key]; });
      if (INDEX_LABEL[raw.index]) s.index = raw.index;
      s.sectors = new Set((raw.sectors || []).filter((x) => SECTORS.includes(x)));
      s.caps = new Set((raw.caps || []).filter((x) => CAPS.some((c) => c.key === x)));
    } catch { /* storage unavailable or corrupt — use defaults */ }
    return s;
  }

  function saveState() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({
        ...state, sectors: [...state.sectors], caps: [...state.caps],
      }));
    } catch { /* private mode etc. */ }
  }

  // ── Filtering & sorting ─────────────────────────────────────────
  // `skip` leaves one facet out, so each option's count reflects what you'd
  // get by switching that facet while keeping every other filter.
  function passes(r, skip) {
    for (const f of FILTERS) {
      if (f.key !== skip && state[f.key] && !f.test(r, state[f.key])) return false;
    }
    if (skip !== 'index' && state.index !== 'all' && state.index !== 'total' && !r.idx.includes(state.index)) return false;
    if (skip !== 'sector' && state.sectors.size && !state.sectors.has(r.sec)) return false;
    if (skip !== 'cap' && state.caps.size && !state.caps.has(capBand(r.mcap))) return false;
    return true;
  }

  function sortValue(r) {
    switch (state.sort.key) {
      case 'volume': return state.sort.variant === '5m' ? r.vol5m : r.vol;
      case 'price': return r.p;
      case 'change': return r.chp;
      case 'mcap': return r.mcap;
      default: return r.turnover;
    }
  }

  function sorted(list) {
    const { key, variant } = state.sort;
    const desc = key === 'popularity' || key === 'volume' || variant !== 'asc';
    return list.slice().sort((a, b) => {
      const va = sortValue(a), vb = sortValue(b);
      if (va == null && vb == null) return (b.turnover || 0) - (a.turnover || 0);
      if (va == null) return 1;   // missing values always last
      if (vb == null) return -1;
      if (va === vb) return (b.turnover || 0) - (a.turnover || 0);
      return desc ? vb - va : va - vb;
    });
  }

  function activeFilterCount() {
    return FILTERS.filter((f) => state[f.key]).length
      + (state.index !== 'all' ? 1 : 0)
      + (state.sectors.size ? 1 : 0)
      + (state.caps.size ? 1 : 0);
  }

  // ── Formatting ──────────────────────────────────────────────────
  const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmtNum = (n, d = 2) => (n == null || !isFinite(n) ? '—'
    : Number(n).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const fmtSigned = (n, d = 2) => (n == null ? '—' : `${n >= 0 ? '+' : ''}${fmtNum(n, d)}`);
  function fmtCompact(n) {
    const v = Number(n);
    if (n == null || !isFinite(v)) return '—';
    if (v >= 1e7) return (v / 1e7).toFixed(2) + ' Cr';
    if (v >= 1e5) return (v / 1e5).toFixed(2) + ' L';
    if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
    return String(Math.round(v));
  }
  const tone = (n) => (n == null ? '' : n > 0 ? 'td-chg-g' : n < 0 ? 'td-chg-r' : '');

  // ── Rail: build once, then update in place ──────────────────────
  function buildRail() {
    $('sortList').innerHTML = SORTS.map((s) => `
      <div class="sc-sort" data-sort="${s.key}" role="radio" tabindex="0">
        <span class="sc-radio"></span>
        <span class="sc-sort-label">${s.label}${s.hint ? `<span class="sc-sort-hint">${s.hint}</span>` : ''}</span>
        ${s.variants ? `<span class="sc-seg">${s.variants.map(([v, l]) => `<button type="button" data-variant="${v}">${l}</button>`).join('')}</span>` : ''}
      </div>`).join('');

    const pillGroups = FILTERS.map((f) => `
      <div class="sc-fgroup" data-filter="${f.key}">
        <div class="sc-flabel">${f.label}</div>
        <div class="sc-fdesc">${f.desc}</div>
        <div class="sc-pills${f.key === 'pivot' ? ' sc-pills-grid' : ''}">
          ${f.options.map(([v, l]) => `<button type="button" class="sc-pill${v ? '' : ' sc-pill-none'}" data-v="${v}">${l}${v ? '<span class="sc-pill-n"></span>' : ''}</button>`).join('')}
        </div>
      </div>`).join('');

    $('filterStack').innerHTML = `
      ${pillGroups}
      <div class="sc-fgroup">
        <label class="sc-flabel" for="indexSelect">INDEX</label>
        <select class="field-select" id="indexSelect"></select>
      </div>
      <div class="sc-fgroup">
        <div class="sc-flabel">SECTOR <span class="sc-fsub" id="sectorSummary"></span></div>
        <div class="sc-picker">
          <input class="sc-search" id="sectorSearch" type="search" placeholder="Search ${SECTORS.length} sectors" autocomplete="off" />
          <div class="sc-picker-list" id="sectorList"></div>
          <div class="sc-picker-foot">
            <span id="sectorSelCount">None selected · showing all</span>
            <button type="button" class="sc-link" id="sectorClear">CLEAR</button>
          </div>
        </div>
      </div>
      <div class="sc-fgroup">
        <div class="sc-flabel">MARKET CAP</div>
        <div class="sc-checks" id="capList">
          ${CAPS.map((c) => `
            <label class="sc-check">
              <input type="checkbox" value="${c.key}" />
              <span class="sc-box"></span>
              <span class="sc-check-text"><b>${c.label}</b><span>${c.range}</span></span>
              <span class="sc-check-n" data-cap-n="${c.key}"></span>
            </label>`).join('')}
        </div>
      </div>`;

    wireRail();
  }

  function wireRail() {
    $('sortList').addEventListener('click', (e) => {
      const row = e.target.closest('.sc-sort');
      if (!row) return;
      const def = SORTS.find((s) => s.key === row.dataset.sort);
      const btn = e.target.closest('[data-variant]');
      let variant = btn ? btn.dataset.variant : null;
      if (!variant && def.variants) {
        variant = state.sort.key === def.key ? state.sort.variant : def.variants[0][0];
      }
      state.sort = { key: def.key, variant };
      changed({ keepPage: true });
    });
    $('sortList').addEventListener('keydown', (e) => {
      if ((e.key === 'Enter' || e.key === ' ') && e.target.classList.contains('sc-sort')) {
        e.preventDefault();
        e.target.click();
      }
    });

    $('filterStack').addEventListener('click', (e) => {
      const pill = e.target.closest('.sc-pill');
      if (!pill) return;
      const key = pill.closest('.sc-fgroup').dataset.filter;
      const v = pill.dataset.v;
      state[key] = state[key] === v ? '' : v;   // clicking the active option clears it
      changed();
    });

    $('indexSelect').addEventListener('change', (e) => { state.index = e.target.value; changed(); });

    $('sectorSearch').addEventListener('input', (e) => { sectorQuery = e.target.value.trim().toLowerCase(); renderSectorList(); });
    $('sectorList').addEventListener('change', (e) => {
      const cb = e.target;
      if (cb.type !== 'checkbox') return;
      if (cb.checked) state.sectors.add(cb.value); else state.sectors.delete(cb.value);
      changed();
    });
    $('sectorClear').addEventListener('click', () => { state.sectors.clear(); changed(); });

    $('capList').addEventListener('change', (e) => {
      const cb = e.target;
      if (cb.checked) state.caps.add(cb.value); else state.caps.delete(cb.value);
      changed();
    });
  }

  function renderRail() {
    document.querySelectorAll('.sc-sort').forEach((row) => {
      const on = row.dataset.sort === state.sort.key;
      row.classList.toggle('active', on);
      row.setAttribute('aria-checked', on);
      row.querySelectorAll('[data-variant]').forEach((b) => b.classList.toggle('active', on && b.dataset.variant === state.sort.variant));
    });

    FILTERS.forEach((f) => {
      const group = document.querySelector(`.sc-fgroup[data-filter="${f.key}"]`);
      const base = rows.filter((r) => passes(r, f.key));
      group.classList.toggle('is-set', !!state[f.key]);
      group.querySelectorAll('.sc-pill').forEach((p) => {
        p.classList.toggle('active', p.dataset.v === state[f.key]);
        const n = p.querySelector('.sc-pill-n');
        if (n) {
          const c = rows.length ? base.filter((r) => f.test(r, p.dataset.v)).length : null;
          n.textContent = c == null ? '' : c;
          p.classList.toggle('is-zero', c === 0);
        }
      });
    });

    const idxBase = rows.filter((r) => passes(r, 'index'));
    $('indexSelect').innerHTML = INDICES.map(([v, l]) => {
      const c = !rows.length ? '' : (v === 'all' || v === 'total') ? idxBase.length : idxBase.filter((r) => r.idx.includes(v)).length;
      return `<option value="${v}"${v === state.index ? ' selected' : ''}>${l}${c === '' ? '' : `  (${c})`}</option>`;
    }).join('');

    renderSectorList();

    const capBase = rows.filter((r) => passes(r, 'cap'));
    document.querySelectorAll('#capList input').forEach((cb) => { cb.checked = state.caps.has(cb.value); });
    CAPS.forEach((c) => {
      const el = document.querySelector(`[data-cap-n="${c.key}"]`);
      el.textContent = rows.length ? capBase.filter((r) => capBand(r.mcap) === c.key).length : '';
    });

    const n = activeFilterCount();
    $('activeCount').textContent = n ? `${n} filter${n > 1 ? 's' : ''} applied` : 'No filters applied';
    $('resetBtn').disabled = n === 0;
  }

  function renderSectorList() {
    const base = rows.filter((r) => passes(r, 'sector'));
    const counts = {};
    base.forEach((r) => { counts[r.sec] = (counts[r.sec] || 0) + 1; });
    const list = SECTORS.filter((s) => !sectorQuery || s.toLowerCase().includes(sectorQuery));
    $('sectorList').innerHTML = list.length ? list.map((s) => {
      const c = rows.length ? (counts[s] || 0) : '';
      return `
        <label class="sc-check sc-check-sm${c === 0 ? ' is-zero' : ''}">
          <input type="checkbox" value="${escapeHtml(s)}"${state.sectors.has(s) ? ' checked' : ''} />
          <span class="sc-box"></span>
          <span class="sc-check-text">${escapeHtml(s)}</span>
          <span class="sc-check-n">${c}</span>
        </label>`;
    }).join('') : '<div class="sc-picker-empty">No sector matches</div>';
    const k = state.sectors.size;
    $('sectorSummary').textContent = k ? `${k} selected` : '';
    $('sectorSelCount').textContent = k ? `${k} of ${SECTORS.length} selected` : 'None selected · showing all';
    $('sectorClear').disabled = k === 0;
  }

  // ── Results ─────────────────────────────────────────────────────
  function changed(opts = {}) {
    if (!opts.keepPage) shown = PAGE;
    saveState();
    renderRail();
    renderResults();
  }

  function renderResults() {
    if (!rows.length) return;
    lastFiltered = sorted(rows.filter((r) => passes(r)));
    const total = lastFiltered.length;

    $('resultsCount').textContent = total.toLocaleString('en-IN');
    $('resultsNoun').textContent = total === 1 ? 'stock' : 'stocks';
    $('crumbIndex').textContent = (state.index === 'all' ? 'ALL STOCKS' : INDEX_LABEL[state.index]).toUpperCase();
    renderMeta();
    renderChips();

    const tbody = $('resultsBody');
    tbody.innerHTML = lastFiltered.slice(0, shown).map(renderRow).join('');
    $('moreWrap').hidden = total <= shown;
    $('moreBtn').textContent = `SHOW MORE · ${Math.min(PAGE, total - shown)} OF ${(total - shown).toLocaleString('en-IN')} LEFT`;
    $('emptyState').hidden = total > 0;
    document.querySelector('.sc-table').hidden = total === 0;
    $('exportBtn').disabled = total === 0;
    updateSortHeaders();
  }

  function renderMeta() {
    if (!meta) return;
    const asOf = meta.as_of ? localTimeStr(new Date(meta.as_of)) : '—';
    const session = meta.market_open ? 'market open' : 'market closed';
    $('resultsMeta').textContent = `of ${rows.length.toLocaleString('en-IN')} · Nifty Total Market · as of ${asOf} · ${session}`;
    $('footRight').textContent = `UPDATED ${asOf}`;
  }

  function renderChips() {
    const chips = [];
    FILTERS.forEach((f) => {
      if (!state[f.key]) return;
      const label = f.options.find(([v]) => v === state[f.key])[1];
      chips.push({ id: f.key, text: f.key === 'move' ? `>1% · ${label}` : `${f.label.split(' (')[0]} · ${label}` });
    });
    if (state.index !== 'all') chips.push({ id: 'index', text: INDEX_LABEL[state.index] });
    if (state.sectors.size) {
      const list = [...state.sectors];
      chips.push({ id: 'sector', text: list.length <= 2 ? list.join(', ') : `${list.length} sectors` });
    }
    if (state.caps.size) {
      chips.push({ id: 'cap', text: CAPS.filter((c) => state.caps.has(c.key)).map((c) => c.label).join(', ') });
    }
    const el = $('activeChips');
    el.hidden = chips.length === 0;
    el.innerHTML = chips.map((c) => `<button type="button" class="sc-chip" data-chip="${c.id}">${escapeHtml(c.text)} <span aria-hidden="true">✕</span></button>`).join('')
      + (chips.length > 1 ? '<button type="button" class="sc-link" data-chip="all">CLEAR ALL</button>' : '');
  }

  function signalTags(r) {
    const tags = [];
    if (state.move) {
      const x = { '5m': r.ch5m, '15m': r.ch15m, '1h': r.ch1h, today: r.chp }[state.move];
      const lbl = { '5m': '5M', '15m': '15M', '1h': '1H', today: '1D' }[state.move];
      if (x != null) tags.push([`${lbl} ${fmtSigned(x)}%`, x >= 0 ? 'up' : 'dn']);
    }
    if (state.rsi && r.rsi != null) tags.push([`RSI ${r.rsi.toFixed(1)}`, state.rsi === 'oversold' ? 'dn' : 'up']);
    if (state.macd && r.macd != null) {
      const txt = r.macdCross ? `MACD ${r.macdCross === 'bullish' ? '↑' : '↓'} CROSS` : `MACD ${fmtSigned(r.macd)}`;
      tags.push([txt, (r.macdCross ? r.macdCross === 'bullish' : r.macd > 0) ? 'up' : 'dn']);
    }
    if (state.pivot && r.piv) {
      const lvl = state.pivot.match(/r\d/)[0];
      tags.push([`${lvl.toUpperCase()} ₹${fmtNum(r.piv[lvl])}`, state.pivot.endsWith('breakout') ? 'up' : '']);
    }
    if (r.stale) tags.push(['DELAYED', 'off']);
    return tags.length ? `<div class="sc-tags">${tags.map(([t, c]) => `<span class="sc-tag ${c}">${t}</span>`).join('')}</div>` : '';
  }

  function render52w(r) {
    if (r.hi52 == null || r.lo52 == null) return '<span class="td-secondary">—</span>';
    const span = r.hi52 - r.lo52;
    const pos = span > 0 ? Math.min(100, Math.max(0, ((r.p - r.lo52) / span) * 100)) : 50;
    return `
      <div class="w52" title="52W low ₹${fmtNum(r.lo52)} · high ₹${fmtNum(r.hi52)}">
        <span class="w52-v">${fmtNum(r.lo52)}</span>
        <span class="w52-bar"><span class="w52-fill" style="width:${pos.toFixed(1)}%"></span><span class="w52-dot" style="left:${pos.toFixed(1)}%"></span></span>
        <span class="w52-v">${fmtNum(r.hi52)}</span>
      </div>`;
  }

  function renderRow(r, i) {
    const chTxt = r.ch == null ? '—' : `${fmtSigned(r.ch)} <span class="sc-pct">(${fmtSigned(r.chp)}%)</span>`;
    const volSub = state.sort.key === 'volume' && state.sort.variant === '5m'
      ? `<div class="td-sub">5m ${fmtCompact(r.vol5m)}</div>` : '';
    return `
      <tr>
        <td class="td-num">${String(i + 1).padStart(2, '0')}</td>
        <td class="sc-td-co">
          <div class="td-sym-code">${escapeHtml(r.s)}</div>
          <div class="td-sym-name">${escapeHtml(r.n)}</div>
          <div class="sc-sec">${escapeHtml(r.sec)}</div>
          ${signalTags(r)}
        </td>
        <td class="td-r td-price">₹${fmtNum(r.p)}</td>
        <td class="td-r ${tone(r.ch)}">${chTxt}</td>
        <td class="td-r td-secondary">${fmtCompact(r.vol)}${volSub}</td>
        <td class="td-r ${tone(r.volDiff)}">${r.volDiff == null ? '—' : fmtSigned(r.volDiff, 1) + '%'}</td>
        <td class="sc-td-52w">${render52w(r)}</td>
        <td class="td-r td-secondary">${r.mcap == null ? '—' : fmtNum(r.mcap, 0)}</td>
      </tr>`;
  }

  // Header clicks map onto the same sort model as the rail.
  const HEADER_SORT = { price: 'price', change: 'change', volume: 'volume', mcap: 'mcap' };

  function updateSortHeaders() {
    document.querySelectorAll('.sc-table th.sortable').forEach((th) => {
      th.classList.remove('sort-asc', 'sort-desc');
      if (HEADER_SORT[th.dataset.sort] === state.sort.key) {
        th.classList.add(state.sort.variant === 'asc' ? 'sort-asc' : 'sort-desc');
      }
    });
  }

  function wireResults() {
    document.querySelectorAll('.sc-table th.sortable').forEach((th) => {
      th.addEventListener('click', () => {
        const key = HEADER_SORT[th.dataset.sort];
        if (key === 'volume') state.sort = { key, variant: 'today' };
        else if (state.sort.key === key) state.sort = { key, variant: state.sort.variant === 'desc' ? 'asc' : 'desc' };
        else state.sort = { key, variant: 'desc' };
        changed({ keepPage: true });
      });
    });

    $('activeChips').addEventListener('click', (e) => {
      const chip = e.target.closest('[data-chip]');
      if (!chip) return;
      const id = chip.dataset.chip;
      if (id === 'all') return resetFilters();
      if (id === 'index') state.index = 'all';
      else if (id === 'sector') state.sectors.clear();
      else if (id === 'cap') state.caps.clear();
      else state[id] = '';
      changed();
    });

    $('moreBtn').addEventListener('click', () => { shown += PAGE; renderResults(); });
    $('resetBtn').addEventListener('click', resetFilters);
    $('emptyReset').addEventListener('click', resetFilters);
    $('exportBtn').addEventListener('click', exportCSV);
    $('errorRetry').addEventListener('click', () => { failCount = 0; setMode('loading'); poll(); });

    const rail = $('rail');
    $('mFilterFab').addEventListener('click', () => rail.classList.toggle('open'));
    $('mobileDone').addEventListener('click', () => rail.classList.remove('open'));
  }

  function resetFilters() {
    const sort = state.sort;
    state = { ...DEFAULT_STATE(), sort };
    sectorQuery = '';
    $('sectorSearch').value = '';
    changed();
  }

  // ── CSV ─────────────────────────────────────────────────────────
  function exportCSV() {
    if (!lastFiltered.length) return;
    const q = (s) => `"${String(s ?? '').replace(/"/g, '""')}"`;
    const headers = ['Symbol', 'Company', 'Sector', 'Price (₹)', '1D Change (₹)', '1D Change (%)',
      '1D Volume', '1W Avg Volume', '1W Avg Vol Diff (%)', '52W Low', '52W High', 'Market Cap (Cr)',
      'RSI (14)', 'MACD', 'MACD Signal', 'Pivot R1', 'Pivot R2', 'Pivot R3', 'Indices'];
    const lines = lastFiltered.map((r) => [
      r.s, q(r.n), q(r.sec), r.p, r.ch, r.chp, r.vol, r.avgVol, r.volDiff, r.lo52, r.hi52, r.mcap,
      r.rsi, r.macd, r.macdSig, r.piv && r.piv.r1, r.piv && r.piv.r2, r.piv && r.piv.r3, q((r.idx || []).join(' ')),
    ].map((v) => (v == null ? '' : v)).join(','));
    const blob = new Blob([[headers.join(','), ...lines].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `screener_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  // ── Modes & polling ─────────────────────────────────────────────
  function setMode(name) {
    $('modeLoading').hidden = name !== 'loading';
    $('modeResults').hidden = name !== 'results';
    $('modeError').hidden = name !== 'error';
    const showExport = name === 'results';
    $('exportBtn').style.visibility = showExport ? 'visible' : 'hidden';
  }

  function showWarming(d) {
    setMode('loading');
    const { done, total } = d.progress || {};
    const pct = total ? (done / total) * 100 : 0;
    $('progressFill').style.width = `${pct.toFixed(1)}%`;
    $('progressCount').textContent = total ? `${done}/${total} stocks` : 'starting…';
    $('loadingSub').textContent = 'Fetching prices, volumes and indicators for every stock';
  }

  function showError(message) {
    setMode('error');
    $('errorText').textContent = message || "Couldn't reach the screener service.";
    setStatus('err', 'OFFLINE');
  }

  function updateRefreshState(d) {
    const el = $('refreshState');
    if (d.refreshing && rows.length) {
      const { done, total } = d.progress || {};
      el.innerHTML = `<span class="live-pulse">●</span> UPDATING${total ? ` ${done}/${total}` : ''}`;
    } else if (meta && meta.as_of) {
      el.textContent = `${d.market_open ? 'LIVE' : 'CLOSED'} · ${localTimeStr(new Date(meta.as_of))}`;
    } else {
      el.textContent = '';
    }
  }

  // One poll at a time: a tab switch mid-request used to start a second,
  // independent polling loop.
  let polling = false;
  async function poll() {
    if (polling) return;
    polling = true;
    try { await pollOnce(); } finally { polling = false; }
  }

  async function pollOnce() {
    clearTimeout(pollTimer);
    let delay = 30000;
    try {
      const url = `${API_BASE}/screener/snapshot${version ? `?since=${version}` : ''}`;
      const res = await fetch(url, { headers: { Accept: 'application/json' }, cache: 'no-store' });
      const d = await res.json().catch(() => null);
      if (!d) throw new Error(`Screener service returned HTTP ${res.status}`);
      failCount = 0;

      if (d.status === 'warming') {
        if (!rows.length) showWarming(d);
        delay = 3000;
      } else if (d.status === 'error') {
        if (!rows.length) showError(d.message);
        delay = 60000;
      } else {
        if (!d.unchanged) {
          rows = d.rows;
          version = d.version;
          meta = d;
          renderRail();
          renderResults();
        } else {
          meta = { ...meta, market_open: d.market_open };
        }
        setMode('results');
        setStatus('live');
        delay = d.refreshing ? 5000 : 10000;
      }
      updateRefreshState(d);
    } catch (e) {
      failCount += 1;
      if (!rows.length && failCount > 18) {
        showError(e.message || "Couldn't reach the screener service.");
        return;   // RETRY button restarts polling
      }
      if (!rows.length) {
        // Render free instances take ~30–60s to wake up; keep the loader up meanwhile.
        $('loadingSub').textContent = 'Waking up the market data service…';
        delay = 5000;
      } else {
        delay = 15000;
      }
      setStatus('err', 'RECONNECTING');
    }
    pollTimer = setTimeout(poll, document.hidden ? Math.max(delay, 60000) : delay);
  }

  // ── Init ────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    window.Shell.start();
    buildRail();
    renderRail();
    wireResults();
    setMode('loading');
    poll();
    document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
  });
})();
