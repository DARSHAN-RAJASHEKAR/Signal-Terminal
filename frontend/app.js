/* ── BuyTheDip Terminal · app.js ────────────────────────────────── */

(() => {

  // ── Config ────────────────────────────────────────────────────
  const getApiBase = () => {
    const h = window.location.hostname;
    return (h === 'localhost' || h === '127.0.0.1')
      ? 'http://127.0.0.1:5001'
      : 'https://buythedip-2.onrender.com';
  };
  const API_BASE = getApiBase();

  const UNIVERSE_CONFIG = {
    india:  [
      { value: 'nifty50',   label: 'NIFTY 50',   count: '50'   },
      { value: 'nifty100',  label: 'NIFTY 100',  count: '100'  },
      { value: 'nifty200',  label: 'NIFTY 200',  count: '200'  },
      { value: 'nifty500',  label: 'NIFTY 500',  count: '500' },
    ],
    us: [
      { value: 'dow30',     label: 'DOW 30',     count: '30'  },
      { value: 'sp100',     label: 'S&P 100',    count: '100' },
      { value: 'nasdaq100', label: 'NASDAQ 100', count: '100' },
      { value: 'sp500',     label: 'S&P 500',    count: '500' },
    ],
    crypto: [
      { value: 'top50',     label: 'TOP 50',     count: '50'  },
      { value: 'top100',    label: 'TOP 100',    count: '100' },
      { value: 'top200',    label: 'TOP 200',    count: '200' },
      { value: 'top500',    label: 'TOP 500',    count: '500' },
    ],
  };

  const SECTOR_OPTIONS = {
    india: [
      { value: 'all', label: 'ALL' },
      { value: 'banking', label: 'BANKING' }, { value: 'it', label: 'IT' },
      { value: 'healthcare', label: 'HEALTHCARE' }, { value: 'auto', label: 'AUTO' },
      { value: 'fmcg', label: 'FMCG' }, { value: 'energy', label: 'ENERGY' },
      { value: 'metals', label: 'METALS' }, { value: 'cement', label: 'CEMENT' },
    ],
    us: [
      { value: 'all', label: 'ALL' },
      { value: 'technology', label: 'TECH' }, { value: 'healthcare', label: 'HEALTHCARE' },
      { value: 'financials', label: 'FINANCIALS' }, { value: 'consumer', label: 'CONSUMER' },
      { value: 'energy', label: 'ENERGY' }, { value: 'industrials', label: 'INDUSTRIALS' },
      { value: 'communication', label: 'COMM' }, { value: 'materials', label: 'MATERIALS' },
      { value: 'utilities', label: 'UTILITIES' }, { value: 'realestate', label: 'REAL ESTATE' },
    ],
    crypto: null,
  };

  const SECTOR_LABELS = {
    banking: 'Banking', it: 'IT', healthcare: 'Healthcare', auto: 'Auto',
    fmcg: 'FMCG', energy: 'Energy', metals: 'Metals', cement: 'Cement',
    consumer: 'Consumer', telecom: 'Telecom', infrastructure: 'Infra',
    capital_goods: 'Cap. Goods', realty: 'Realty', chemicals: 'Chemicals',
    construction: 'Construction', textiles: 'Textiles',
    technology: 'Tech', financials: 'Finance', industrials: 'Industrial',
    communication: 'Comm.', materials: 'Materials', utilities: 'Utilities',
    realestate: 'Real Estate', crypto: 'Crypto',
  };

  const UNIVERSE_LABELS = {
    nifty50: 'Nifty 50', nifty100: 'Nifty 100', nifty200: 'Nifty 200', nifty500: 'Nifty 500',
    dow30: 'DOW 30', sp100: 'S&P 100', nasdaq100: 'NASDAQ 100', sp500: 'S&P 500',
    top50: 'Top 50', top100: 'Top 100', top200: 'Top 200', top500: 'Top 500',
  };

  const CURRENCY = { india: '₹', us: '$', crypto: '$' };

  // ── State ─────────────────────────────────────────────────────
  let selectedMarket   = 'india';
  let selectedUniverse = 'nifty50';
  let scanResults      = [];
  let scanData         = null;
  let lastScanBody     = null;
  let loadingTimer     = null;
  let loadingStartTs   = 0;
  let sortCol          = 'monthly';
  let sortDir          = 'asc';

  // ── DOM helpers ───────────────────────────────────────────────
  const $ = (id) => document.getElementById(id);

  const modes = {
    idle:      $('modeIdle'),
    loading:   $('modeLoading'),
    results:   $('modeResults'),
    noResults: $('modeNoResults'),
    error:     $('modeError'),
  };

  function setMode(name) {
    Object.entries(modes).forEach(([k, el]) => { el.hidden = (k !== name); });
    const exportBtn = $('exportBtn');
    const showExport = (name === 'results');
    exportBtn.style.visibility = showExport ? 'visible' : 'hidden';
    exportBtn.style.pointerEvents = showExport ? 'auto' : 'none';
    exportBtn.disabled = !showExport;
    const cCfg = $('crumbConfigure');
    const cScan = $('crumbScanner');
    const cRes = $('crumbResult');
    cCfg.classList.remove('crumb-active');
    cScan.classList.remove('crumb-active');
    cRes.classList.remove('crumb-active');
    cScan.textContent = 'SCANNER';
    cRes.textContent = 'RESULTS';

    if (name === 'idle') {
      cCfg.classList.add('crumb-active');
    } else if (name === 'loading') {
      cScan.textContent = 'RUNNING SCAN';
      cScan.classList.add('crumb-active');
    } else if (name === 'results') {
      cRes.textContent = 'RESULTS';
      cRes.classList.add('crumb-active');
    } else if (name === 'noResults') {
      cRes.textContent = 'NO MATCHES';
      cRes.classList.add('crumb-active');
    } else {
      cRes.textContent = 'ERROR';
      cRes.classList.add('crumb-active');
    }
  }

  // ── Init ──────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    renderUniverse(selectedMarket);
    renderSector(selectedMarket);
    wireMarketRows();
    wireHomeNavigation();
    wireRunButton();
    wireExtraButtons();
    wireKeyboardShortcuts();
    wireMobile();
    wireSortHeaders();
    setStatus('connecting');
    setMode('idle');
    checkHealth();
    fetchTickers();
    setInterval(fetchTickers, 5000);  // refresh tickers every 5s
    updateClock();
    setInterval(updateClock, 1000);
  });

  function wireHomeNavigation() {
    const goToStart = () => {
      if (window.__es) {
        try { window.__es.close(); } catch {}
        window.__es = null;
      }
      $('scanBtn').disabled = false;
      $('buttonText').textContent = 'RUN SCAN';
      $('scanBtn').hidden = false;
      $('cancelBtn').hidden = true;
      setMode('idle');
    };

    const wireClickable = (el) => {
      if (!el) return;
      el.addEventListener('click', goToStart);
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          goToStart();
        }
      });
    };

    wireClickable($('homeBrand'));
    wireClickable($('crumbConfigure'));
  }

  // ── Markets / universes / sectors ─────────────────────────────
  function wireMarketRows() {
    document.querySelectorAll('.market-row').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.market-row').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        selectedMarket = btn.dataset.market;
        renderUniverse(selectedMarket);
        renderSector(selectedMarket);
      });
    });
  }

  function renderUniverse(market) {
    const grid = $('universeGrid');
    const opts = UNIVERSE_CONFIG[market];
    selectedUniverse = opts[0].value;
    grid.innerHTML = opts.map((o, i) => `
      <button class="uni-btn${i === 0 ? ' active' : ''}" data-uni="${o.value}">
        <span>${o.label}</span><span class="uni-count">${o.count}</span>
      </button>
    `).join('');
    grid.querySelectorAll('.uni-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        grid.querySelectorAll('.uni-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        selectedUniverse = btn.dataset.uni;
      });
    });
  }

  function renderSector(market) {
    const wrap = $('sectorFilterItem');
    const sel  = $('sectorFilter');
    const opts = SECTOR_OPTIONS[market];
    if (!opts) { wrap.style.display = 'none'; return; }
    wrap.style.display = '';
    sel.innerHTML = opts.map((o) => `<option value="${o.value}">${o.label}</option>`).join('');
  }

  // ── Backend health ────────────────────────────────────────────
  function setStatus(state, msg) {
    const dot  = $('statusDot');
    const text = $('statusText');
    dot.classList.remove('live', 'err');
    if (state === 'live')     { dot.classList.add('live'); text.textContent = msg || 'LIVE'; }
    else if (state === 'err') { dot.classList.add('err');  text.textContent = msg || 'OFFLINE'; }
    else                       { text.textContent = msg || 'CONNECTING'; }
  }

  async function checkHealth() {
    try {
      const r = await fetch(`${API_BASE}/health`, { headers: { Accept: 'application/json' } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      if (d.status === 'healthy') setStatus('live');
      else                        setStatus('err', 'UNHEALTHY');
    } catch (e) {
      setStatus('err', 'OFFLINE');
    }
  }

  // ── Ticker fetch ───────────────────────────────────────────────
  // Calls our own /tickers endpoint (added to backend/app.py).
  // Browser-side fetches to Yahoo / Stooq are CORS-blocked, so the
  // backend proxies them. Endpoint shape:
  //   { nifty: {value, change_pct}|null, dow: {...}, btc: {...} }
  async function fetchTickers() {
    try {
      const r = await fetch(`${API_BASE}/tickers`, { headers: { Accept: 'application/json' } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      paintTickerFromApi('nifty', d.nifty, { fractionDigits: 2 });
      paintTickerFromApi('sp500', d.sp500, { fractionDigits: 2 });
      paintTickerFromApi('dow',   d.dow,   { fractionDigits: 2 });
      paintTickerFromApi('btc',   d.btc,   { prefix: '$', fractionDigits: 0 });
    } catch (e) {
      paintTickerErr('nifty');
      paintTickerErr('sp500');
      paintTickerErr('dow');
      paintTickerErr('btc');
    }
  }

  function paintTickerFromApi(id, payload, opts = {}) {
    if (!payload || typeof payload.value !== 'number') { paintTickerErr(id); return; }
    const prefix = opts.prefix || '';
    const valueStr = prefix + payload.value.toLocaleString('en-US', {
      minimumFractionDigits: opts.fractionDigits || 0,
      maximumFractionDigits: opts.fractionDigits || 0,
    });
    const absStr = typeof payload.change_abs === 'number'
      ? (payload.change_abs >= 0 ? '+' : '') + payload.change_abs.toLocaleString('en-US', {
          minimumFractionDigits: opts.fractionDigits || 0,
          maximumFractionDigits: opts.fractionDigits || 0,
        })
      : null;
    paintTicker(id, valueStr, payload.change_pct, absStr);
  }

  function paintTicker(id, valueStr, changePct, absStr) {
    // Update both desktop (.sb-tick) and mobile (.sb-tick-m) tickers
    const roots = document.querySelectorAll(`.sb-tick[data-tick="${id}"], .sb-tick-m[data-tick-m="${id}"]`);
    roots.forEach((root) => {
      const valEl = root.querySelector('.sb-tick-val');
      const chgEl = root.querySelector('.sb-tick-chg');
      valEl.textContent = valueStr;
      chgEl.classList.remove('up', 'dn');
      if (typeof changePct === 'number' && isFinite(changePct)) {
        const sign = changePct >= 0 ? '+' : '';
        const absPart = absStr ? `${absStr} ` : '';
        chgEl.textContent = `${absPart}(${sign}${changePct.toFixed(2)}%)`;
        chgEl.classList.add(changePct >= 0 ? 'up' : 'dn');
      } else {
        chgEl.textContent = '—';
      }
    });
  }

  function paintTickerErr(id) {
    const roots = document.querySelectorAll(`.sb-tick[data-tick="${id}"], .sb-tick-m[data-tick-m="${id}"]`);
    roots.forEach((root) => {
      root.querySelector('.sb-tick-val').textContent = '—';
      root.querySelector('.sb-tick-chg').textContent = '';
    });
  }

  function updateClock() {
    const now = new Date();
    const opts = { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' };
    const t = now.toLocaleTimeString('en-GB', opts);
    const str = `${t} IST`;
    $('sbTime').textContent = str;
    $('sbTimeMobile').textContent = str;
  }

  // ── Run scan ──────────────────────────────────────────────────
  function wireRunButton() {
    $('scanBtn').addEventListener('click', runScan);
    $('cancelBtn').addEventListener('click', cancelScan);
  }

  function cancelScan() {
    if (window.__es) {
      try { window.__es.close(); } catch {}
      window.__es = null;
    }
    const btn = $('scanBtn');
    btn.disabled = false;
    $('buttonText').textContent = 'RUN SCAN';
    $('scanBtn').hidden = false;
    $('cancelBtn').hidden = true;
    setMode('idle');
  }

  function buildScanBody() {
    return {
      market:           selectedMarket,
      stockUniverse:    selectedUniverse,
      weeklyThreshold:  parseFloat($('weeklyThreshold').value) || 0,
      monthlyThreshold: parseFloat($('monthlyThreshold').value) || 0,
      marketCapFilter:  $('marketCapFilter').value,
      sectorFilter:     SECTOR_OPTIONS[selectedMarket] ? $('sectorFilter').value : 'all',
    };
  }

  function scanSubtitle(body) {
    const w = body.weeklyThreshold, m = body.monthlyThreshold;
    return `−${w}% / 1W &nbsp;·&nbsp; −${m}% / 1M`;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  async function runScan() {
    const btn = $('scanBtn');
    btn.disabled = true;
    $('buttonText').textContent = 'SCANNING…';
    $('scanBtn').hidden = true;
    $('cancelBtn').hidden = false;

    const body = buildScanBody();
    lastScanBody = body;
    const uniLabel = UNIVERSE_LABELS[body.stockUniverse] || body.stockUniverse;

    setMode('loading');
    $('loadUniverse').textContent = uniLabel.toUpperCase();
    $('loadFilters').innerHTML = scanSubtitle(body);
    $('progressFill').style.width = '0%';
    $('progressCount').textContent = '0/— fetched';
    $('progressEta').textContent = '—';
    $('lstatSymbols').textContent = '0 / —';
    $('lstatMatches').textContent = '0';

    // EventSource only supports GET, so encode params on the URL.
    const params = new URLSearchParams(body);
    const url = `${API_BASE}/scan-stream?${params.toString()}`;

    // Close any previous stream
    if (window.__es) { try { window.__es.close(); } catch {} window.__es = null; }

    const matches = [];
    let initData    = null;
    let scanStarted = Date.now();
    let lastTickTs  = scanStarted;
    let lastProcessed = 0;
    let avgMsPerSymbol = 250;  // initial guess, replaced once we get real data

    const es = new EventSource(url);
    window.__es = es;

    const cleanup = () => {
      try { es.close(); } catch {}
      window.__es = null;
      btn.disabled = false;
      $('buttonText').textContent = 'RUN SCAN';
      $('scanBtn').hidden = false;
      $('cancelBtn').hidden = true;
    };

    es.addEventListener('init', (e) => {
      initData = JSON.parse(e.data);
      $('progressCount').textContent = `0/${initData.total} fetched`;
      $('lstatSymbols').textContent = `0 / ${initData.total}`;
    });

    es.addEventListener('progress', (e) => {
      const d = JSON.parse(e.data);
      const pct = d.total > 0 ? (d.processed / d.total) * 100 : 0;
      $('progressFill').style.width = pct.toFixed(1) + '%';
      $('progressCount').textContent = `${d.processed}/${d.total} fetched`;
      $('lstatSymbols').textContent = `${d.processed} / ${d.total}`;
      $('lstatMatches').textContent = d.matches;

      // Smoothed ETA based on actual throughput
      const now = Date.now();
      const dt = now - lastTickTs;
      const dprocessed = d.processed - lastProcessed;
      if (dprocessed > 0 && dt > 0) {
        const instantMs = dt / dprocessed;
        avgMsPerSymbol = avgMsPerSymbol * 0.6 + instantMs * 0.4;  // EMA
      }
      const remaining = Math.max(0, d.total - d.processed);
      const etaSec = Math.ceil((remaining * avgMsPerSymbol) / 1000);
      $('progressEta').textContent = etaSec > 0 ? `~${etaSec}s` : '—';
      lastTickTs = now;
      lastProcessed = d.processed;
    });

    es.addEventListener('match', (e) => {
      matches.push(JSON.parse(e.data));
    });

    es.addEventListener('done', (e) => {
      const doneData = JSON.parse(e.data);
      const failed = doneData.failed_symbols || [];
      sortCol = 'monthly';
      sortDir = 'asc';
      scanResults = matches.slice();
      sortResults();
      scanData = { ...doneData, results: scanResults };
      $('progressFill').style.width = '100%';
      $('lstatMatches').textContent = scanResults.length;
      cleanup();
      if (scanResults.length > 0) { renderResults(); setMode('results'); }
      else { setMode('noResults'); }
    });

    es.addEventListener('error', (e) => {
      // EventSource fires 'error' on any disconnect, even normal closes.
      // Distinguish real errors by readyState.
      if (es.readyState === EventSource.CLOSED) {
        cleanup();
        return;
      }
      // Server-emitted error event with payload
      if (e.data) {
        try { const d = JSON.parse(e.data); showError(new Error(d.message || 'Scan failed')); }
        catch { showError(new Error('Scan failed')); }
      } else {
        showError(new Error('Connection to scan stream lost'));
      }
      cleanup();
    });
  }

  // ── Sort ──────────────────────────────────────────────────────
  function getSortValue(r, col) {
    switch (col) {
      case 'symbol':   return r.symbol.replace('.NS', '').toLowerCase();
      case 'sector':   return (r.sector || '').toLowerCase();
      case 'price':    return parseFloat(r.currentPrice) || 0;
      case 'weekly':   return parseFloat(r.weeklyChange) || 0;
      case 'monthly':  return parseFloat(r.monthlyChange) || 0;
      case 'weekAgo':  return parseFloat(r.priceOneWeekAgo) || 0;
      case 'monthAgo': return parseFloat(r.priceOneMonthAgo) || 0;
      case 'volume':   return typeof r.volume === 'number' ? r.volume : 0;
      default:         return 0;
    }
  }

  function sortResults() {
    const isStr = col => ['symbol', 'sector'].includes(col);
    scanResults.sort((a, b) => {
      const va = getSortValue(a, sortCol);
      const vb = getSortValue(b, sortCol);
      const cmp = isStr(sortCol) ? va.localeCompare(vb) : va - vb;
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }

  function updateSortHeaders() {
    document.querySelectorAll('.rtable thead th.sortable').forEach((th) => {
      th.classList.remove('sort-asc', 'sort-desc');
      if (th.dataset.sort === sortCol) {
        th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      }
    });
  }

  function wireSortHeaders() {
    document.querySelectorAll('.rtable thead th.sortable').forEach((th) => {
      th.addEventListener('click', () => {
        if (sortCol === th.dataset.sort) {
          sortDir = sortDir === 'asc' ? 'desc' : 'asc';
        } else {
          sortCol = th.dataset.sort;
          sortDir = 'asc';
        }
        sortResults();
        const wT = (lastScanBody && lastScanBody.weeklyThreshold) || 5;
        const mT = (lastScanBody && lastScanBody.monthlyThreshold) || 10;
        const cur    = CURRENCY[selectedMarket];
        const locale = selectedMarket === 'india' ? 'en-IN' : 'en-US';
        $('resultsBody').innerHTML = scanResults.map((r, i) => renderRow(r, i, wT, mT, cur, locale)).join('');
        updateSortHeaders();
      });
    });
  }

  // ── Render results ────────────────────────────────────────────
  function renderResults() {
    const wThresh = (lastScanBody && lastScanBody.weeklyThreshold) || 5;
    const mThresh = (lastScanBody && lastScanBody.monthlyThreshold) || 10;
    const cur     = CURRENCY[selectedMarket];
    const locale  = selectedMarket === 'india' ? 'en-IN' : 'en-US';
    const uniLabel = UNIVERSE_LABELS[scanData.stock_universe] || UNIVERSE_LABELS[selectedUniverse] || selectedUniverse;
    const total   = scanData.universe_size || 0;
    const success = scanData.success_rate || '—';

    // Header line
    $('resultsCount').textContent = scanResults.length;
    $('resultsMeta').textContent = `scanned ${total || '—'} · success ${success} · ${selectedMarket.toUpperCase()} · ${uniLabel}`;
    $('exportBtn').disabled = scanResults.length === 0;

    // Stat strip
    renderStatStrip();

    // Breakdown
    renderBreakdown();

    // Table rows
    const body = $('resultsBody');
    body.innerHTML = scanResults.map((r, i) => renderRow(r, i, wThresh, mThresh, cur, locale)).join('');

    // Footer
    $('footFeed').textContent = (scanResults[0] && scanResults[0].source || 'YH').toUpperCase();
    $('footTime').textContent = new Date().toLocaleTimeString('en-GB', { hour12: false, timeZone: 'Asia/Kolkata' }) + ' IST';
    updateSortHeaders();
  }

  function renderStatStrip() {
    if (!scanResults.length) { $('statStrip').innerHTML = ''; return; }
    const weekly  = scanResults.map((r) => parseFloat(r.weeklyChange));
    const monthly = scanResults.map((r) => parseFloat(r.monthlyChange));
    const avgW = weekly.reduce((a, b) => a + b, 0) / weekly.length;
    const avgM = monthly.reduce((a, b) => a + b, 0) / monthly.length;
    const deepest = scanResults.reduce((a, b) => parseFloat(a.monthlyChange) < parseFloat(b.monthlyChange) ? a : b, scanResults[0]);
    const mostLiquid = scanResults
      .filter((r) => typeof r.volume === 'number')
      .reduce((a, b) => (a === null || b.volume > a.volume) ? b : a, null);
    const sectors = new Set(scanResults.map((r) => r.sector).filter(Boolean));
    const cells = [
      { label: 'AVG 1W',      value: avgW.toFixed(2) + '%', cls: 'red' },
      { label: 'AVG 1M',      value: avgM.toFixed(2) + '%', cls: 'red' },
      { label: 'DEEPEST',     value: `${deepest.symbol.replace('.NS','')} ${parseFloat(deepest.monthlyChange).toFixed(2)}%`, cls: 'red' },
      { label: 'MOST LIQUID', value: mostLiquid ? `${mostLiquid.symbol.replace('.NS','')} ${fmtCompact(mostLiquid.volume)}` : '—', cls: '' },
      { label: 'SECTORS HIT', value: `${sectors.size}`, cls: '' },
    ];
    $('statStrip').innerHTML = cells.map((c) => `
      <div class="stat-cell">
        <div class="stat-cell-label">${c.label}</div>
        <div class="stat-cell-value ${c.cls}">${c.value}</div>
      </div>
    `).join('');
  }

  function renderBreakdown() {
    if (!scanResults.length) { $('breakdownList').innerHTML = ''; return; }
    const bySector = {};
    scanResults.forEach((r) => {
      const s = r.sector || 'other';
      if (!bySector[s]) bySector[s] = { count: 0, sum: 0 };
      bySector[s].count += 1;
      bySector[s].sum += parseFloat(r.monthlyChange);
    });
    const rows = Object.entries(bySector)
      .map(([k, v]) => ({ key: k, label: SECTOR_LABELS[k] || k, count: v.count, avg: v.sum / v.count }))
      .sort((a, b) => b.count - a.count);
    $('breakdownList').innerHTML = rows.map((r) => `
      <div class="bd-row">
        <span class="bd-row-name">${r.label}</span>
        <span class="bd-row-count">${r.count}</span>
        <span class="bd-row-avg">${r.avg.toFixed(2)}%</span>
      </div>
    `).join('');
  }

  function renderRow(r, i, wThresh, mThresh, cur, locale) {
    const w      = parseFloat(r.weeklyChange);
    const m      = parseFloat(r.monthlyChange);
    const symbol = r.symbol.replace('.NS', '');
    const sector = SECTOR_LABELS[r.sector] || r.sector || '—';
    const volume = typeof r.volume === 'number' ? fmtCompact(r.volume) : (r.volume || '—');

    return `
      <tr>
        <td class="td-num">${String(i + 1).padStart(2, '0')}</td>
        <td>
          <div class="td-sym-code">${symbol}</div>
          <div class="td-sym-name">${escapeHtml(r.name || '')}</div>
        </td>
        <td class="td-sec">${sector}</td>
        <td class="td-r td-price">${cur}${formatPrice(r.currentPrice, locale)}</td>
        <td class="td-r ${w < 0 ? 'td-chg-r' : 'td-chg-g'}">${w.toFixed(2)}%</td>
        <td class="td-r ${m < 0 ? 'td-chg-r' : 'td-chg-g'}">${m.toFixed(2)}%</td>
        <td class="td-r td-secondary">${formatPrice(r.priceOneWeekAgo, locale)}</td>
        <td class="td-r td-secondary">${formatPrice(r.priceOneMonthAgo, locale)}</td>
        <td class="td-r td-secondary">${volume}</td>
      </tr>
    `;
  }

  function formatPrice(p, locale) {
    const n = parseFloat(p);
    if (!isFinite(n)) return '—';
    return n.toLocaleString(locale || 'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function fmtCompact(n) {
    const v = Number(n);
    if (!isFinite(v)) return '—';
    if (v >= 1e7) return (v / 1e7).toFixed(2) + ' Cr';
    if (v >= 1e5) return (v / 1e5).toFixed(2) + ' L';
    if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
    return String(Math.round(v));
  }

  // ── CSV export ────────────────────────────────────────────────
  function exportCSV() {
    if (!scanResults.length) return;
    const cur = CURRENCY[selectedMarket];
    const headers = [
      'Symbol', 'Name', `Current Price (${cur})`,
      'Weekly Change (%)', 'Monthly Change (%)',
      `Price 1W Ago (${cur})`, `Price 1M Ago (${cur})`,
      'Volume', 'Sector', 'Market Cap', 'Source',
    ];
    const rows = scanResults.map((s) => [
      s.symbol, `"${(s.name || '').replace(/"/g, '""')}"`,
      s.currentPrice, s.weeklyChange, s.monthlyChange,
      s.priceOneWeekAgo, s.priceOneMonthAgo,
      typeof s.volume === 'number' ? s.volume : `"${s.volume || 'N/A'}"`,
      s.sector || '—', s.marketCap || '—', s.source || '—',
    ].join(','));
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `dips_${selectedMarket}_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ── Error state ───────────────────────────────────────────────
  function showError(err) {
    setMode('error');
    $('errorText').textContent = (err && err.message) ? err.message : 'Couldn\'t reach the scanner service.';
  }

  // ── Extra buttons / segments ──────────────────────────────────
  function wireExtraButtons() {
    $('exportBtn').addEventListener('click', exportCSV);
    $('emptyRetry').addEventListener('click', () => setMode('idle'));
    $('errorRetry').addEventListener('click', () => runScan());
  }

  // ── Keyboard ──────────────────────────────────────────────────
  function wireKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      const cmdOrCtrl = e.metaKey || e.ctrlKey;
      // Enter on threshold inputs triggers scan
      if (e.key === 'Enter' && e.target.matches('.field-input, .field-select')) {
        e.preventDefault();
        runScan();
        return;
      }
      // Cmd+Enter anywhere
      if (cmdOrCtrl && e.key === 'Enter') {
        e.preventDefault();
        runScan();
      }
      // Cmd+E export
      if (cmdOrCtrl && (e.key === 'e' || e.key === 'E')) {
        e.preventDefault();
        if (!$('exportBtn').disabled) exportCSV();
      }
    });
  }

  // ── Mobile ───────────────────────────────────────────────────
  function wireMobile() {
    const fab = $('mFilterFab');
    const rail = $('rail');
    fab.addEventListener('click', () => rail.classList.toggle('open'));
    // Auto-close rail after running scan on mobile
    $('scanBtn').addEventListener('click', () => rail.classList.remove('open'));
  }

})();
