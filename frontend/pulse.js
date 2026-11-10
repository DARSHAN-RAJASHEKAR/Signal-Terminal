/* ── Market Pulse · pulse.js ────────────────────────────────────────
   Reads the same /screener/snapshot as the Stocks Screener, so it costs
   no extra market-data calls. Everything here is aggregation + drawing. */

(() => {
  const { API_BASE, localTimeStr, setStatus } = window.Shell;
  const $ = (id) => document.getElementById(id);
  const STORE_KEY = 'pulse.state.v1';

  const SCOPES = [
    ['all', 'Nifty Total Market'], ['nifty50', 'Nifty 50'], ['nifty100', 'Nifty 100'],
    ['nifty500', 'Nifty 500'], ['midcap150', 'Nifty Midcap 150'], ['smallcap250', 'Nifty Smallcap 250'],
  ];
  const SCOPE_LABEL = Object.fromEntries(SCOPES);

  // Colour metric → field + diverging bin edges (in %). Intraday moves are
  // smaller, so their scale is tighter.
  const METRICS = {
    '1d': { field: 'chp', label: '1D', edges: [0.5, 1.5, 3] },
    '1h': { field: 'ch1h', label: '1H', edges: [0.2, 0.5, 1] },
    '15m': { field: 'ch15m', label: '15M', edges: [0.1, 0.25, 0.5] },
  };
  // Diverging ramp: red pole · neutral grey midpoint · green pole (finance
  // convention). Every tile also carries a signed % label, and the tooltip
  // spells it out, so colour is never the only cue.
  const RAMP = ['#b8333b', '#8a3036', '#552a2f', '#2b313c', '#1f4a3a', '#24704f', '#2c9a68'];

  const state = loadState();
  let rows = [];
  let meta = null;
  let version = null;
  let focus = null;           // sector name when zoomed in
  let sectorSort = { key: 'chg', dir: 'desc' };
  let pollTimer = null;
  let failCount = 0;

  function loadState() {
    const s = { scope: 'all', color: '1d', size: 'mcap' };
    try {
      const raw = JSON.parse(localStorage.getItem(STORE_KEY) || 'null') || {};
      if (SCOPE_LABEL[raw.scope]) s.scope = raw.scope;
      if (METRICS[raw.color]) s.color = raw.color;
      if (raw.size === 'mcap' || raw.size === 'equal') s.size = raw.size;
    } catch { /* storage unavailable */ }
    return s;
  }
  function saveState() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch { /* ignore */ }
  }

  // ── Formatting ──────────────────────────────────────────────────
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (n, d = 2) => (n == null || !isFinite(n) ? '—'
    : Number(n).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const signed = (n, d = 2) => (n == null || !isFinite(n) ? '—' : `${n >= 0 ? '+' : ''}${fmt(n, d)}`);
  const pctTxt = (n, d = 2) => (n == null || !isFinite(n) ? '—' : `${signed(n, d)}%`);
  const tone = (n) => (n == null ? '' : n > 0 ? 'up' : n < 0 ? 'dn' : '');
  function fmtCr(n) {
    if (n == null) return '—';
    if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)}L Cr`;
    if (n >= 1e3) return `₹${(n / 1e3).toFixed(1)}K Cr`;
    return `₹${Math.round(n)} Cr`;
  }

  function colorFor(v) {
    if (v == null || !isFinite(v)) return RAMP[3];
    const [a, b, c] = METRICS[state.color].edges;
    const m = Math.abs(v);
    const step = m < a ? 0 : m < b ? 1 : m < c ? 2 : 3;
    return v >= 0 ? RAMP[3 + step] : RAMP[3 - step];
  }

  // ── Aggregates ──────────────────────────────────────────────────
  const inScope = () => rows.filter((r) => state.scope === 'all' || (r.idx || []).includes(state.scope));

  function capWeighted(list, field = 'chp') {
    let w = 0, s = 0;
    list.forEach((r) => { if (r[field] != null && r.mcap) { w += r.mcap; s += r.mcap * r[field]; } });
    return w ? s / w : null;
  }
  const mean = (xs) => { const v = xs.filter((x) => x != null && isFinite(x)); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };

  function breadth(list) {
    const withChg = list.filter((r) => r.chp != null);
    return {
      adv: withChg.filter((r) => r.chp > 0).length,
      dec: withChg.filter((r) => r.chp < 0).length,
      unch: withChg.filter((r) => r.chp === 0).length,
    };
  }

  // ── Breadth panel ───────────────────────────────────────────────
  function renderBreadth(list) {
    const { adv, dec, unch } = breadth(list);
    const total = adv + dec + unch || 1;
    const seg = (n, cls, label) => (n ? `<div class="pl-ad-seg ${cls}" style="flex:${n}" title="${label}: ${n}"></div>` : '');
    $('adBar').innerHTML = `
      <div class="pl-ad-labels">
        <span><b class="up">${adv}</b> advancing · ${((adv / total) * 100).toFixed(0)}%</span>
        <span>${unch} unchanged</span>
        <span>${((dec / total) * 100).toFixed(0)}% · declining <b class="dn">${dec}</b></span>
      </div>
      <div class="pl-ad-track">${seg(adv, 'up', 'Advancing')}${seg(unch, 'flat', 'Unchanged')}${seg(dec, 'dn', 'Declining')}</div>`;

    const ratio = dec ? adv / dec : null;
    const cw = capWeighted(list);
    const ew = mean(list.map((r) => r.chp));
    const nearHi = list.filter((r) => r.hi52 != null && r.p >= r.hi52 * 0.98).length;
    const nearLo = list.filter((r) => r.lo52 != null && r.p <= r.lo52 * 1.02).length;
    const ob = list.filter((r) => r.rsi != null && r.rsi > 70).length;
    const os = list.filter((r) => r.rsi != null && r.rsi < 30).length;
    const bull = list.filter((r) => r.macdCross === 'bullish').length;
    const bear = list.filter((r) => r.macdCross === 'bearish').length;
    const big = list.filter((r) => r.chp != null && Math.abs(r.chp) > 3).length;

    const cells = [
      { label: 'ADV / DEC RATIO', value: ratio == null ? '—' : ratio.toFixed(2), cls: ratio == null ? '' : ratio >= 1 ? 'green' : 'red' },
      { label: 'CAP-WEIGHTED 1D', value: pctTxt(cw), cls: cw > 0 ? 'green' : cw < 0 ? 'red' : '' },
      { label: 'EQUAL-WEIGHTED 1D', value: pctTxt(ew), cls: ew > 0 ? 'green' : ew < 0 ? 'red' : '' },
      { label: 'NEAR 52W HIGH / LOW', value: `${nearHi} / ${nearLo}` },
      { label: 'RSI > 70 / < 30', value: `${ob} / ${os}` },
      { label: 'MACD CROSS ↑ / ↓', value: `${bull} / ${bear}` },
      { label: 'MOVED > 3% TODAY', value: `${big}` },
    ];
    $('breadthStats').innerHTML = cells.map((c) => `
      <div class="stat-cell">
        <div class="stat-cell-label">${c.label}</div>
        <div class="stat-cell-value ${c.cls || ''}">${c.value}</div>
      </div>`).join('');
    $('breadthNote').textContent = `${list.length} stocks · ${SCOPE_LABEL[state.scope]}`;
  }

  // ── Squarified treemap ──────────────────────────────────────────
  // Bruls et al. — lays items (sorted desc by value) into rows whose aspect
  // ratios stay close to 1, so tiles are readable squares, not slivers.
  function squarify(items, x, y, w, h) {
    const out = [];
    const total = items.reduce((s, i) => s + i.value, 0);
    if (!total || w <= 0 || h <= 0) return out;
    const scale = (w * h) / total;
    const nodes = items.map((i) => ({ item: i, area: i.value * scale }));
    let r = { x, y, w, h };
    let row = [];
    const worst = (rw, side) => {
      const s = rw.reduce((a, n) => a + n.area, 0);
      let max = 0, min = Infinity;
      rw.forEach((n) => { max = Math.max(max, n.area); min = Math.min(min, n.area); });
      return Math.max((side * side * max) / (s * s), (s * s) / (side * side * min));
    };
    const place = (rw) => {
      const s = rw.reduce((a, n) => a + n.area, 0);
      if (r.w >= r.h) {           // lay a column down the left edge
        const cw = s / r.h;
        let yy = r.y;
        rw.forEach((n) => { const nh = n.area / cw; out.push({ ...n.item, x: r.x, y: yy, w: cw, h: nh }); yy += nh; });
        r = { x: r.x + cw, y: r.y, w: r.w - cw, h: r.h };
      } else {                    // lay a row along the top edge
        const rh = s / r.w;
        let xx = r.x;
        rw.forEach((n) => { const nw = n.area / rh; out.push({ ...n.item, x: xx, y: r.y, w: nw, h: rh }); xx += nw; });
        r = { x: r.x, y: r.y + rh, w: r.w, h: r.h - rh };
      }
    };
    nodes.forEach((n) => {
      const side = Math.min(r.w, r.h);
      if (!row.length || worst([...row, n], side) <= worst(row, side)) row.push(n);
      else { place(row); row = [n]; }
    });
    if (row.length) place(row);
    return out;
  }

  const sizeOf = (r) => (state.size === 'equal' ? 1 : r.mcap || 0);

  // Taller canvas for bigger universes, so tiles stay big enough to label:
  // ~680px for Nifty 50 up to ~1100px for the full 750-stock market.
  function heatHeight(n, focused) {
    const narrow = window.innerWidth <= 880;
    if (focused) return narrow ? 440 : 640;
    const h = 420 + n * 0.9;
    return Math.round(Math.min(narrow ? 760 : 1150, Math.max(narrow ? 440 : 680, h)));
  }

  function renderHeatmap(list) {
    const el = $('heatmap');
    const shownCount = focus ? list.filter((r) => r.sec === focus).length : list.length;
    el.style.height = `${heatHeight(shownCount, !!focus)}px`;
    const W = el.clientWidth;
    const H = el.clientHeight;
    const field = METRICS[state.color].field;
    const usable = list.filter((r) => sizeOf(r) > 0);

    const bySector = new Map();
    usable.forEach((r) => {
      if (!bySector.has(r.sec)) bySector.set(r.sec, []);
      bySector.get(r.sec).push(r);
    });
    let sectors = [...bySector.entries()].map(([name, items]) => ({
      name, items, value: items.reduce((s, r) => s + sizeOf(r), 0),
    }));
    if (focus) sectors = sectors.filter((s) => s.name === focus);
    sectors.sort((a, b) => b.value - a.value);

    const HEADER = 18;
    const GAP = 3;          // inset per side → 6px of space between sectors
    const html = [];
    squarify(sectors, 0, 0, W, H).forEach((s) => {
      const showHead = s.h > HEADER + 18 && s.w > 40;
      const top = showHead ? HEADER : 0;
      const move = state.color === '1d' ? capWeighted(s.items, 'chp') : capWeighted(s.items, field);
      html.push(`<div class="pl-sec" style="left:${s.x + GAP}px;top:${s.y + GAP}px;width:${Math.max(0, s.w - 2 * GAP)}px;height:${Math.max(0, s.h - 2 * GAP)}px" data-sector="${esc(s.name)}">
        ${showHead ? `<div class="pl-sec-head"><span class="pl-sec-title"><span class="pl-sec-name">${esc(s.name)}</span>${focus ? '' : '<span class="pl-sec-arrow" aria-hidden="true">›</span>'}</span><span class="pl-sec-pct">${pctTxt(move)}</span></div>` : ''}
      </div>`);
      // Market cap: biggest company first (keeps tiles square). Equal size:
      // every tile is the same, so order by the colour metric instead —
      // top gainer first, top loser last, missing data at the end.
      const byMove = (a, b) => {
        const va = a.r[field], vb = b.r[field];
        if (va == null && vb == null) return 0;
        if (va == null) return 1;
        if (vb == null) return -1;
        return vb - va;
      };
      const tiles = squarify(
        s.items.map((r) => ({ r, value: sizeOf(r) }))
          .sort(state.size === 'equal' ? byMove : (a, b) => b.value - a.value),
        s.x + GAP, s.y + GAP + top, s.w - 2 * GAP, s.h - 2 * GAP - top,
      );
      tiles.forEach((t) => {
        const v = t.r[field];
        // Label tiers: big = symbol + %, two-line = smaller symbol + %,
        // tiny = symbol only (ellipsised). Below ~24×13px there's no room.
        const tier = t.w > 58 && t.h > 34 ? 'big'
          : t.w >= 38 && t.h >= 27 ? 'two'
            : t.w >= 24 && t.h >= 13 ? 'tiny' : '';
        const label = tier === 'big' || tier === 'two'
          ? `<span class="pl-t-sym">${esc(t.r.s)}</span><span class="pl-t-chg">${pctTxt(v)}</span>`
          : tier === 'tiny' ? `<span class="pl-t-sym">${esc(t.r.s)}</span>` : '';
        html.push(`<div class="pl-tile${tier ? ` ${tier}` : ''}" data-sym="${esc(t.r.s)}" style="left:${t.x}px;top:${t.y}px;width:${Math.max(0, t.w)}px;height:${Math.max(0, t.h)}px;background:${colorFor(v)}">${label}</div>`);
      });
    });
    el.innerHTML = html.join('');
    $('heatCrumbFocus').innerHTML = focus
      ? ` <span class="pl-crumb-sep">/</span> <span class="pl-crumb-focus">${esc(focus).toUpperCase()}</span> <button type="button" class="sc-link" id="unfocus">✕ ALL SECTORS</button>` : '';
    document.querySelector('.pl-heat-hint').textContent =
      `Tile size = ${state.size === 'equal' ? 'equal per stock' : 'market cap'} · colour = ${METRICS[state.color].label} price change · `
      + (focus ? 'click any tile to zoom back out' : 'click a sector to zoom in');
    renderLegend();
  }

  function renderLegend() {
    const [a, b, c] = METRICS[state.color].edges;
    const labels = [`< −${c}%`, `−${b}`, `−${a}`, '0', `+${a}`, `+${b}`, `> +${c}%`];
    $('heatLegend').innerHTML = RAMP.map((col, i) => `
      <span class="pl-leg"><span class="pl-leg-sw" style="background:${col}"></span>${labels[i]}</span>`).join('');
  }

  // ── Sector leaderboard ──────────────────────────────────────────
  function sectorStats(list) {
    const map = new Map();
    list.forEach((r) => { if (!map.has(r.sec)) map.set(r.sec, []); map.get(r.sec).push(r); });
    return [...map.entries()].map(([name, items]) => {
      const withChg = items.filter((r) => r.chp != null).sort((x, y) => y.chp - x.chp);
      return {
        name, items, count: items.length, ...breadth(items),
        chg: capWeighted(items), rsi: mean(items.map((r) => r.rsi)),
        top: withChg[0], bottom: withChg.length > 1 ? withChg[withChg.length - 1] : null,
      };
    });
  }

  function renderSectors(list) {
    const stats = sectorStats(list);
    const { key, dir } = sectorSort;
    stats.sort((a, b) => {
      const va = a[key], vb = b[key];
      if (key === 'name') return dir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
      if (va == null) return 1;
      if (vb == null) return -1;
      return dir === 'asc' ? va - vb : vb - va;
    });
    const mover = (r) => (r ? `<span class="pl-mv">${esc(r.s)} <span class="${tone(r.chp)}">${pctTxt(r.chp)}</span></span>` : '<span class="td-secondary">—</span>');
    $('sectorBody').innerHTML = stats.map((s) => {
      const t = s.adv + s.dec + s.unch || 1;
      return `
        <tr class="pl-sec-row${focus === s.name ? ' active' : ''}" data-sector="${esc(s.name)}" tabindex="0">
          <td class="pl-sec-name">${esc(s.name)}</td>
          <td class="td-r td-secondary">${s.count}</td>
          <td>
            <div class="pl-mini" title="${s.adv} advancing · ${s.unch} unchanged · ${s.dec} declining">
              <span class="pl-mini-n up">${s.adv}</span>
              <span class="pl-mini-bar">
                ${s.adv ? `<span class="up" style="flex:${s.adv}"></span>` : ''}${s.unch ? `<span class="flat" style="flex:${s.unch}"></span>` : ''}${s.dec ? `<span class="dn" style="flex:${s.dec}"></span>` : ''}
              </span>
              <span class="pl-mini-n dn">${s.dec}</span>
            </div>
          </td>
          <td class="td-r ${s.chg > 0 ? 'td-chg-g' : s.chg < 0 ? 'td-chg-r' : ''}">${pctTxt(s.chg)}</td>
          <td class="td-r td-secondary">${s.rsi == null ? '—' : s.rsi.toFixed(1)}</td>
          <td>${mover(s.top)}</td>
          <td>${mover(s.bottom)}</td>
        </tr>`;
    }).join('');
    document.querySelectorAll('.pl-sectors th.sortable').forEach((th) => {
      th.classList.remove('sort-asc', 'sort-desc');
      if (th.dataset.sort === key) th.classList.add(dir === 'asc' ? 'sort-asc' : 'sort-desc');
    });
  }

  // ── Movers ──────────────────────────────────────────────────────
  function renderMovers(list) {
    const withChg = list.filter((r) => r.chp != null);
    // In a small sector, don't pad "losers" with stocks that are actually up.
    const gainers = withChg.filter((r) => r.chp > 0).sort((a, b) => b.chp - a.chp).slice(0, 8);
    const losers = withChg.filter((r) => r.chp < 0).sort((a, b) => a.chp - b.chp).slice(0, 8);
    const vol = list.filter((r) => r.volDiff != null && r.avgVol > 0).sort((a, b) => b.volDiff - a.volDiff).slice(0, 8);
    const item = (r, right) => `
      <li class="pl-li" data-sym="${esc(r.s)}">
        <span class="pl-li-main"><b>${esc(r.s)}</b><span>${esc(r.n)}</span></span>
        <span class="pl-li-right">${right}</span>
      </li>`;
    const empty = (msg) => `<li class="pl-li-empty">${msg}</li>`;
    $('listGainers').innerHTML = gainers.map((r) => item(r, `<span>₹${fmt(r.p)}</span><b class="up">${pctTxt(r.chp)}</b>`)).join('') || empty('No stocks up today');
    $('listLosers').innerHTML = losers.map((r) => item(r, `<span>₹${fmt(r.p)}</span><b class="dn">${pctTxt(r.chp)}</b>`)).join('') || empty('No stocks down today');
    $('listVolume').innerHTML = vol.map((r) => item(r, `<span class="${tone(r.chp)}">${pctTxt(r.chp)}</span><b>${(r.vol / r.avgVol).toFixed(1)}×</b>`)).join('') || empty('No volume data');
  }

  // ── Tooltip ─────────────────────────────────────────────────────
  let bySym = new Map();
  function showTip(e, html) {
    const tip = $('tip');
    tip.innerHTML = html;
    tip.hidden = false;
    const pad = 14;
    const { innerWidth: vw, innerHeight: vh } = window;
    const r = tip.getBoundingClientRect();
    let x = e.clientX + pad, y = e.clientY + pad;
    if (x + r.width > vw - 8) x = e.clientX - r.width - pad;
    if (y + r.height > vh - 8) y = e.clientY - r.height - pad;
    tip.style.transform = `translate(${Math.max(8, x)}px, ${Math.max(8, y)}px)`;
  }
  const hideTip = () => { $('tip').hidden = true; };

  function stockTip(r) {
    const line = (k, v, cls = '') => `<div class="pl-tip-row"><span>${k}</span><b class="${cls}">${v}</b></div>`;
    return `
      <div class="pl-tip-head"><b>${esc(r.s)}</b><span>${esc(r.sec)}</span></div>
      <div class="pl-tip-name">${esc(r.n)}</div>
      ${line('Price', `₹${fmt(r.p)}`)}
      ${line('1D', `${signed(r.ch)} (${pctTxt(r.chp)})`, tone(r.chp))}
      ${line('1H', pctTxt(r.ch1h), tone(r.ch1h))}
      ${line('15M', pctTxt(r.ch15m), tone(r.ch15m))}
      ${line('Market cap', fmtCr(r.mcap))}
      ${line('RSI (14)', r.rsi == null ? '—' : r.rsi.toFixed(1))}`;
  }

  function sectorTip(name) {
    const items = inScope().filter((r) => r.sec === name);
    const b = breadth(items);
    return `
      <div class="pl-tip-head"><b>${esc(name)}</b></div>
      <div class="pl-tip-row"><span>Stocks</span><b>${items.length}</b></div>
      <div class="pl-tip-row"><span>Cap-weighted 1D</span><b class="${tone(capWeighted(items))}">${pctTxt(capWeighted(items))}</b></div>
      <div class="pl-tip-row"><span>Advancing / declining</span><b>${b.adv} / ${b.dec}</b></div>`;
  }

  // ── Render all ──────────────────────────────────────────────────
  function render() {
    if (!rows.length) return;
    bySym = new Map(rows.map((r) => [r.s, r]));
    const list = inScope();
    if (focus && !list.some((r) => r.sec === focus)) focus = null;
    renderBreadth(list);
    renderHeatmap(list);
    renderSectors(list);
    // Movers follow the heatmap zoom: a focused sector shows only its stocks.
    renderMovers(focus ? list.filter((r) => r.sec === focus) : list);
    document.querySelectorAll('.pl-mv-scope').forEach((el) => {
      el.textContent = focus ? ` · ${focus.toUpperCase()}` : '';
    });
    renderControls();
    if (meta) {
      const asOf = meta.as_of ? localTimeStr(new Date(meta.as_of)) : '—';
      $('plMeta').textContent = `${SCOPE_LABEL[state.scope]} · ${list.length} stocks · as of ${asOf} · ${meta.market_open ? 'market open' : 'market closed'}`;
      $('footRight').textContent = `UPDATED ${asOf}`;
    }
  }

  function renderControls() {
    $('scopeSelect').innerHTML = SCOPES.map(([v, l]) => `<option value="${v}"${v === state.scope ? ' selected' : ''}>${l}</option>`).join('');
    document.querySelectorAll('#colorSeg button').forEach((b) => b.classList.toggle('active', b.dataset.v === state.color));
    document.querySelectorAll('#sizeSeg button').forEach((b) => b.classList.toggle('active', b.dataset.v === state.size));
  }

  function wire() {
    $('scopeSelect').addEventListener('change', (e) => { state.scope = e.target.value; focus = null; saveState(); render(); });
    $('colorSeg').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      state.color = b.dataset.v; saveState(); render();
    });
    $('sizeSeg').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      state.size = b.dataset.v; saveState(); render();
    });

    const heat = $('heatmap');
    heat.addEventListener('mousemove', (e) => {
      const tile = e.target.closest('.pl-tile');
      if (tile && bySym.has(tile.dataset.sym)) return showTip(e, stockTip(bySym.get(tile.dataset.sym)));
      const sec = e.target.closest('.pl-sec');
      if (sec) return showTip(e, sectorTip(sec.dataset.sector));
      hideTip();
    });
    heat.addEventListener('mouseleave', hideTip);
    heat.addEventListener('click', (e) => {
      if (focus) { focus = null; render(); return; }
      const tile = e.target.closest('.pl-tile');
      const sym = tile && bySym.get(tile.dataset.sym);
      const sec = sym ? sym.sec : (e.target.closest('.pl-sec') || {}).dataset?.sector;
      if (sec) { focus = sec; hideTip(); render(); }
    });
    document.addEventListener('click', (e) => {
      if (e.target.id === 'unfocus') { focus = null; render(); }
    });

    const body = $('sectorBody');
    const pick = (row) => {
      const name = row.dataset.sector;
      focus = focus === name ? null : name;
      render();
      $('heatmap').scrollIntoView({ behavior: 'smooth', block: 'center' });
    };
    body.addEventListener('click', (e) => { const row = e.target.closest('.pl-sec-row'); if (row) pick(row); });
    body.addEventListener('keydown', (e) => {
      const row = e.target.closest('.pl-sec-row');
      if (row && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); pick(row); }
    });
    document.querySelectorAll('.pl-sectors th.sortable').forEach((th) => {
      th.addEventListener('click', () => {
        const key = th.dataset.sort;
        sectorSort = sectorSort.key === key
          ? { key, dir: sectorSort.dir === 'asc' ? 'desc' : 'asc' }
          : { key, dir: key === 'name' ? 'asc' : 'desc' };
        renderSectors(inScope());
      });
    });

    document.querySelector('.pl-movers').addEventListener('mousemove', (e) => {
      const li = e.target.closest('.pl-li');
      if (li && bySym.has(li.dataset.sym)) showTip(e, stockTip(bySym.get(li.dataset.sym)));
      else hideTip();
    });
    document.querySelector('.pl-movers').addEventListener('mouseleave', hideTip);

    let resizeT;
    window.addEventListener('resize', () => { clearTimeout(resizeT); resizeT = setTimeout(() => rows.length && renderHeatmap(inScope()), 120); });
    $('errorRetry').addEventListener('click', () => { failCount = 0; setView('loading'); poll(); });
  }

  // ── Polling (same contract as the Screener) ─────────────────────
  function setView(name) {
    $('plLoading').hidden = name !== 'loading';
    $('plError').hidden = name !== 'error';
    $('plBody').hidden = name !== 'ready';
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
    let delay = 10000;
    try {
      const res = await fetch(`${API_BASE}/screener/snapshot${version ? `?since=${version}` : ''}`, { headers: { Accept: 'application/json' }, cache: 'no-store' });
      const d = await res.json().catch(() => null);
      if (!d) throw new Error(`Market data service returned HTTP ${res.status}`);
      failCount = 0;
      if (d.status === 'warming') {
        if (!rows.length) {
          setView('loading');
          const { done, total } = d.progress || {};
          $('progressFill').style.width = `${total ? (done / total) * 100 : 0}%`;
          $('progressCount').textContent = total ? `${done}/${total} stocks` : 'starting…';
          $('loadingSub').textContent = 'Fetching prices for every stock';
        }
        delay = 3000;
      } else if (d.status === 'error') {
        if (!rows.length) { setView('error'); $('errorText').textContent = d.message || 'Market data unavailable.'; }
        delay = 60000;
      } else {
        const firstPaint = !rows.length;
        if (!d.unchanged) { rows = d.rows; version = d.version; meta = d; }
        else meta = { ...meta, market_open: d.market_open };
        setView('ready');
        setStatus('live');
        if (firstPaint || !d.unchanged) render();
        delay = d.refreshing ? 5000 : 10000;
      }
    } catch (e) {
      failCount += 1;
      setStatus('err', 'RECONNECTING');
      if (!rows.length && failCount > 18) {
        setView('error');
        $('errorText').textContent = e.message || "Couldn't reach the market data service.";
        return;
      }
      if (!rows.length) $('loadingSub').textContent = 'Waking up the market data service…';
      delay = rows.length ? 15000 : 5000;
    }
    pollTimer = setTimeout(poll, document.hidden ? Math.max(delay, 60000) : delay);
  }

  document.addEventListener('DOMContentLoaded', () => {
    window.Shell.start();
    renderControls();
    wire();
    setView('loading');
    poll();
    document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
  });
})();
