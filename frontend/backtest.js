/* ── BuyTheDip · Dip backtest panel ────────────────────────────────
   Opened from a result row's BACKTEST button. The button carries the
   scan's own symbol, market and thresholds, so the backtest tests exactly
   the signal the user just saw. */

(() => {
  const { API_BASE } = window.Shell;
  const $ = (id) => document.getElementById(id);
  const STORE_KEY = 'bt.years.v1';

  let current = null;      // { sym, name, market, weekly, monthly, cur }
  let years = loadYears();
  let reqId = 0;
  let lastFocus = null;
  let hideTimer = null;

  function loadYears() {
    try { const y = parseInt(localStorage.getItem(STORE_KEY), 10); return [3, 5, 10].includes(y) ? y : 5; } catch { return 5; }
  }

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const signed = (n, d = 2) => (n == null || !isFinite(n) ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(d)}%`);
  const tone = (n) => (n == null ? '' : n > 0 ? 'up' : n < 0 ? 'dn' : '');
  const displaySym = (s) => s.replace(/\.NS$/, '');
  const fmtDate = (iso) => new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });
  const fmtPrice = (n, cur) => `${cur}${Number(n).toLocaleString(cur === '₹' ? 'en-IN' : 'en-US', { maximumFractionDigits: n < 10 ? 4 : 2, minimumFractionDigits: 2 })}`;

  // ── Open / close ────────────────────────────────────────────────
  function open(btn) {
    clearTimeout(hideTimer);   // reopened before the close animation finished
    lastFocus = btn;
    current = {
      sym: btn.dataset.sym, name: btn.dataset.name, market: btn.dataset.market,
      weekly: parseFloat(btn.dataset.weekly), monthly: parseFloat(btn.dataset.monthly), cur: btn.dataset.cur || '',
    };
    $('btTitle').textContent = displaySym(current.sym);
    $('btSub').textContent = current.name && current.name !== displaySym(current.sym) ? current.name : '';
    $('btOverlay').hidden = false;
    $('btDrawer').hidden = false;
    document.body.classList.add('bt-open-body');
    requestAnimationFrame(() => $('btDrawer').classList.add('is-open'));
    $('btClose').focus();
    load();
  }

  function close() {
    $('btDrawer').classList.remove('is-open');
    $('btOverlay').hidden = true;
    document.body.classList.remove('bt-open-body');
    hideTimer = setTimeout(() => { $('btDrawer').hidden = true; }, 180);
    reqId += 1;   // drop any in-flight response
    if (lastFocus) lastFocus.focus();
  }

  function paintYears() {
    document.querySelectorAll('#btYears button').forEach((b) => b.classList.toggle('active', +b.dataset.y === years));
  }

  // ── Fetch ───────────────────────────────────────────────────────
  async function load() {
    paintYears();
    const id = ++reqId;
    const c = current;
    $('btBody').innerHTML = `
      <div class="bt-loading">
        <div class="progress-bar"><div class="progress-fill bt-indet"></div></div>
        <div class="bt-note">Fetching ${years} years of ${esc(displaySym(c.sym))} history…</div>
      </div>`;
    const qs = new URLSearchParams({ symbol: c.sym, market: c.market, weekly: c.weekly, monthly: c.monthly, years });
    try {
      const res = await fetch(`${API_BASE}/backtest?${qs}`, { headers: { Accept: 'application/json' } });
      const d = await res.json().catch(() => null);
      if (id !== reqId) return;
      if (!res.ok || !d || d.error) throw new Error((d && d.error) || `HTTP ${res.status}`);
      render(d);
    } catch (e) {
      if (id !== reqId) return;
      $('btBody').innerHTML = `
        <div class="bt-error">
          <div class="empty-title">BACKTEST UNAVAILABLE</div>
          <div class="empty-desc">${esc(e.message || 'Something went wrong.')}</div>
          <button type="button" class="cta-ghost" id="btRetry">RETRY</button>
        </div>`;
      $('btRetry').addEventListener('click', load);
    }
  }

  // ── Render ──────────────────────────────────────────────────────
  function render(d) {
    const { summary: s, events, params: p, series } = d;
    const c = current;
    const sym = esc(displaySym(c.sym));
    const span = `${fmtDate(p.from)} – ${fmtDate(p.to)}`;
    const rule = `fell ≥${p.weekly}% in a week and ≥${p.monthly}% in a month`;

    if (!s.count) {
      $('btBody').innerHTML = `
        <p class="bt-q">Every time <b>${sym}</b> ${rule}, over ${span}:</p>
        <div class="bt-empty">
          <div class="empty-glyph">⌀</div>
          <div class="empty-title">NO PAST DIPS LIKE THIS</div>
          <div class="empty-desc">${sym} never fell this hard in the window. Try a longer lookback.</div>
        </div>
        ${chart(series, [], c.cur)}
        ${method()}`;
      return;
    }

    const h = s.horizons, b = s.baseline;
    const tiles = [
      { label: 'DIPS FOUND', value: s.count },
      { label: 'RECOVERED ≤ 3M', value: s.recovery_rate == null ? '—' : `${s.recovery_rate.toFixed(0)}%` },
      { label: 'MEDIAN DAYS TO RECOVER', value: s.median_days_to_recover == null ? '—' : `${Math.round(s.median_days_to_recover)}d` },
    ];
    const rows = [['1w', '1 WEEK'], ['1m', '1 MONTH'], ['3m', '3 MONTHS']].map(([k, label]) => {
      const x = h[k], y = b[k];
      if (!x) return `<tr><td>${label}</td><td colspan="4" class="bt-muted">not enough time has passed yet</td></tr>`;
      const edge = y ? x.avg - y.avg : null;
      return `
        <tr>
          <td>${label}<span class="bt-n">${x.n} dip${x.n > 1 ? 's' : ''}</span></td>
          <td class="td-r">${x.win_rate.toFixed(0)}%<span class="bt-vs">${y ? `vs ${y.win_rate.toFixed(0)}%` : ''}</span></td>
          <td class="td-r ${tone(x.avg)}">${signed(x.avg)}<span class="bt-vs">${y ? `vs ${signed(y.avg)}` : ''}</span></td>
          <td class="td-r ${tone(x.median)}">${signed(x.median)}</td>
          <td class="td-r ${tone(edge)}">${signed(edge)}</td>
        </tr>`;
    }).join('');

    const verdict = headline(h, b);
    $('btBody').innerHTML = `
      <p class="bt-q">Every time <b>${sym}</b> ${rule}, over ${span}:</p>
      ${verdict}
      <div class="bt-tiles">${tiles.map((t) => `<div class="bt-tile"><div class="stat-cell-label">${t.label}</div><div class="bt-tile-v">${t.value}</div></div>`).join('')}</div>

      <div class="rail-label bt-sec">WHAT HAPPENED NEXT</div>
      <table class="rtable bt-table">
        <thead><tr><th>AFTER</th><th class="th-r">WIN RATE</th><th class="th-r">AVG</th><th class="th-r">MEDIAN</th><th class="th-r" title="Average after a dip minus average after any day">EDGE</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <div class="bt-note">"vs" = buying on <i>any</i> day in the same period. Edge = dip average minus any-day average.</div>

      <div class="rail-label bt-sec">PRICE &amp; PAST DIPS</div>
      ${chart(series, events, c.cur)}

      <div class="rail-label bt-sec">EVERY DIP · NEWEST FIRST</div>
      <div class="bt-events-wrap">
        <table class="rtable bt-events">
          <thead><tr><th>DATE</th><th class="th-r">1M DROP</th><th class="th-r">+1W</th><th class="th-r">+1M</th><th class="th-r">+3M</th><th class="th-r" title="Deepest further fall within 3 months">WORST</th><th class="th-r">RECOVERED</th></tr></thead>
          <tbody>${events.slice().reverse().map((e) => `
            <tr>
              <td>${fmtDate(e.date)}<span class="bt-n">${fmtPrice(e.close, c.cur)}</span></td>
              <td class="td-r dn">${signed(e.monthly, 1)}</td>
              <td class="td-r ${tone(e.fwd['1w'])}">${signed(e.fwd['1w'], 1)}</td>
              <td class="td-r ${tone(e.fwd['1m'])}">${signed(e.fwd['1m'], 1)}</td>
              <td class="td-r ${tone(e.fwd['3m'])}">${signed(e.fwd['3m'], 1)}</td>
              <td class="td-r ${tone(e.max_further_drop)}">${e.max_further_drop ? signed(e.max_further_drop, 1) : '—'}</td>
              <td class="td-r">${e.recovered === true ? `<span class="up">✓ ${e.recovered_days}d</span>` : e.recovered === false ? '<span class="dn">✕ not in 3M</span>' : '<span class="bt-muted">in progress</span>'}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
      ${method()}`;
  }

  function headline(h, b) {
    const x = h['1m'], y = b['1m'];
    if (!x || !y) return '';
    const better = x.avg > y.avg && x.win_rate >= y.win_rate;
    const worse = x.avg < y.avg && x.win_rate <= y.win_rate;
    const cls = better ? 'good' : worse ? 'bad' : 'mixed';
    const icon = better ? '▲' : worse ? '▼' : '◆';
    const text = better
      ? `Historically, buying this dip beat buying on an average day: ${signed(x.avg)} after a month vs ${signed(y.avg)}.`
      : worse
        ? `Historically, this dip kept falling more often than not: ${signed(x.avg)} after a month vs ${signed(y.avg)} on an average day.`
        : `Mixed history: ${signed(x.avg)} after a month (${x.win_rate.toFixed(0)}% win rate) vs ${signed(y.avg)} (${y.win_rate.toFixed(0)}%) on an average day.`;
    return `<div class="bt-verdict ${cls}"><span class="bt-verdict-icon" aria-hidden="true">${icon}</span><span>${text}</span></div>`;
  }

  function method() {
    return `
      <details class="bt-method">
        <summary>How this is calculated</summary>
        <ul>
          <li>A <b>dip</b> is any day where the close is down at least your weekly % vs 7 days earlier <i>and</i> your monthly % vs 30 days earlier, the same rule as the scan.</li>
          <li>After a dip, the next one only counts 30+ days later, so one long slide isn't counted many times.</li>
          <li>Returns are from the dip-day close to the close 1 week, 1 month and 3 months later.</li>
          <li><b>Recovered</b> = closed back at the price from 30 days before the dip, within 3 months.</li>
          <li>Past results don't predict future returns. Not financial advice.</li>
        </ul>
      </details>`;
  }

  // ── Chart: price line + dip markers (inline SVG) ────────────────
  function chart(series, events, cur) {
    if (!series || series.length < 2) return '';
    const W = 560, H = 180, P = { l: 8, r: 8, t: 10, b: 20 };
    const t = (iso) => Date.parse(`${iso}T00:00:00Z`);
    const xs = series.map(([dt]) => t(dt));
    const ys = series.map(([, v]) => v);
    const x0 = xs[0], x1 = xs[xs.length - 1];
    let lo = Math.min(...ys, ...events.map((e) => e.close));
    let hi = Math.max(...ys, ...events.map((e) => e.close));
    const pad = (hi - lo) * 0.06 || 1;
    lo -= pad; hi += pad;
    const X = (v) => P.l + ((v - x0) / (x1 - x0)) * (W - P.l - P.r);
    const Y = (v) => P.t + (1 - (v - lo) / (hi - lo)) * (H - P.t - P.b);
    const path = series.map(([dt, v], i) => `${i ? 'L' : 'M'}${X(t(dt)).toFixed(1)},${Y(v).toFixed(1)}`).join('');
    const area = `${path}L${X(x1).toFixed(1)},${H - P.b}L${X(x0).toFixed(1)},${H - P.b}Z`;
    // year ticks
    const ticks = [];
    for (let yr = new Date(x0).getUTCFullYear() + 1; yr <= new Date(x1).getUTCFullYear(); yr++) {
      const tx = Date.UTC(yr, 0, 1);
      if (tx > x0 && tx < x1) ticks.push(`<g><line x1="${X(tx)}" x2="${X(tx)}" y1="${P.t}" y2="${H - P.b}" class="bt-grid"/><text x="${X(tx)}" y="${H - 6}" class="bt-axis">${yr}</text></g>`);
    }
    const marks = events.map((e) => {
      const r = e.fwd['1m'];
      const cls = r == null ? 'pending' : r > 0 ? 'win' : 'loss';
      return `<g class="bt-mark ${cls}" transform="translate(${X(t(e.date)).toFixed(1)},${Y(e.close).toFixed(1)})">
        <circle r="9" class="bt-hit"/><circle r="4.5"/>
        <title>${fmtDate(e.date)} · ${fmtPrice(e.close, cur)} · month ${signed(e.monthly, 1)}${r == null ? '' : ` → ${signed(r, 1)} a month later`}</title>
      </g>`;
    }).join('');
    const legend = events.length ? `
      <div class="bt-legend">
        <span><i class="bt-dot win"></i>Dip · up 1M later</span>
        <span><i class="bt-dot loss"></i>Dip · down 1M later</span>
        ${events.some((e) => e.fwd['1m'] == null) ? '<span><i class="bt-dot pending"></i>Too recent</span>' : ''}
      </div>` : '';
    return `
      <div class="bt-chart">
        <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Price history with past dips marked">
          ${ticks.join('')}
          <path d="${area}" class="bt-area"/>
          <path d="${path}" class="bt-line" vector-effect="non-scaling-stroke"/>
          ${marks}
        </svg>
        <div class="bt-range"><span>${fmtPrice(series[0][1], cur)}</span><span>${fmtPrice(series[series.length - 1][1], cur)}</span></div>
      </div>
      ${legend}`;
  }

  // ── Wiring ──────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    $('resultsBody').addEventListener('click', (e) => {
      const btn = e.target.closest('.bt-open');
      if (btn) open(btn);
    });
    $('btClose').addEventListener('click', close);
    $('btOverlay').addEventListener('click', close);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !$('btDrawer').hidden) close();
    });
    $('btYears').addEventListener('click', (e) => {
      const b = e.target.closest('button');
      if (!b || !current) return;
      years = +b.dataset.y;
      try { localStorage.setItem(STORE_KEY, String(years)); } catch { /* ignore */ }
      load();
    });
  });
})();
