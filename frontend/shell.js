/* ── Shared status bar (home + screener) ─────────────────────────────
   Same tickers / clock / health dot as the BuyTheDip terminal. app.js keeps
   its own copy so the BuyTheDip page stays fully self-contained. */

(() => {
  const h = window.location.hostname;
  const API_BASE = (h === 'localhost' || h === '127.0.0.1')
    ? 'http://127.0.0.1:5001'
    : 'https://buythedip-2.onrender.com';

  const $ = (id) => document.getElementById(id);

  // en-US only has short names for US zones; elsewhere it prints an offset
  // like "GMT+5:30". Map common long names to their real abbreviations
  // (guessing from initials gets e.g. CET wrong: "Central European
  // Standard Time" → CEST). Unknown zones keep the offset.
  const TZ_ABBR = {
    'India Standard Time': 'IST', 'Nepal Time': 'NPT', 'Pakistan Standard Time': 'PKT',
    'Gulf Standard Time': 'GST', 'Singapore Standard Time': 'SGT', 'Hong Kong Standard Time': 'HKT',
    'China Standard Time': 'CST', 'Japan Standard Time': 'JST', 'Korean Standard Time': 'KST',
    'Greenwich Mean Time': 'GMT', 'British Summer Time': 'BST',
    'Central European Standard Time': 'CET', 'Central European Summer Time': 'CEST',
    'Eastern European Standard Time': 'EET', 'Eastern European Summer Time': 'EEST',
    'Western European Standard Time': 'WET', 'Western European Summer Time': 'WEST',
    'Australian Eastern Standard Time': 'AEST', 'Australian Eastern Daylight Time': 'AEDT',
    'Australian Western Standard Time': 'AWST', 'New Zealand Standard Time': 'NZST',
    'New Zealand Daylight Time': 'NZDT',
  };

  function tzAbbr(now, tz) {
    const short = now.toLocaleTimeString('en-US', { timeZoneName: 'short', timeZone: tz }).split(' ').pop();
    if (!/^(GMT|UTC)[+-]/.test(short)) return short;   // EST, PDT, UTC, GMT… are fine as-is
    const long = now.toLocaleTimeString('en-US', { timeZoneName: 'long', timeZone: tz })
      .replace(/^[\d:\s]+(AM|PM)?\s*/i, '');
    return TZ_ABBR[long] || short;
  }

  function localTimeStr(date) {
    const now = date || new Date();
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const time = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: tz });
    return `${time} ${tzAbbr(now, tz)}`;
  }

  function setStatus(state, msg) {
    const dot = $('statusDot');
    const text = $('statusText');
    if (!dot || !text) return;
    dot.classList.remove('live', 'err');
    if (state === 'live') { dot.classList.add('live'); text.textContent = msg || 'LIVE'; }
    else if (state === 'err') { dot.classList.add('err'); text.textContent = msg || 'OFFLINE'; }
    else { text.textContent = msg || 'CONNECTING'; }
  }

  async function checkHealth() {
    try {
      const r = await fetch(`${API_BASE}/health`, { headers: { Accept: 'application/json' } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setStatus(d.status === 'healthy' ? 'live' : 'err', d.status === 'healthy' ? 'LIVE' : 'UNHEALTHY');
    } catch {
      setStatus('err', 'OFFLINE');
    }
  }

  function paintTicker(id, payload, opts) {
    const roots = document.querySelectorAll(`.sb-tick[data-tick="${id}"], .sb-tick-m[data-tick-m="${id}"]`);
    const ok = payload && typeof payload.value === 'number';
    const fmt = (n) => n.toLocaleString('en-US', { minimumFractionDigits: opts.digits, maximumFractionDigits: opts.digits });
    roots.forEach((root) => {
      const valEl = root.querySelector('.sb-tick-val');
      const chgEl = root.querySelector('.sb-tick-chg');
      chgEl.classList.remove('up', 'dn');
      if (!ok) { valEl.textContent = '—'; chgEl.textContent = ''; return; }
      valEl.textContent = (opts.prefix || '') + fmt(payload.value);
      const pct = payload.change_pct;
      if (typeof pct === 'number' && isFinite(pct)) {
        const abs = typeof payload.change_abs === 'number'
          ? `${payload.change_abs >= 0 ? '+' : ''}${fmt(payload.change_abs)} ` : '';
        chgEl.textContent = `${abs}(${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)`;
        chgEl.classList.add(pct >= 0 ? 'up' : 'dn');
      } else {
        chgEl.textContent = '—';
      }
    });
  }

  async function fetchTickers() {
    let d = {};
    try {
      const r = await fetch(`${API_BASE}/tickers`, { headers: { Accept: 'application/json' } });
      if (r.ok) d = await r.json();
    } catch { /* paint dashes below */ }
    paintTicker('nifty', d.nifty, { digits: 2 });
    paintTicker('sp500', d.sp500, { digits: 2 });
    paintTicker('dow', d.dow, { digits: 2 });
    paintTicker('btc', d.btc, { digits: 0, prefix: '$' });
  }

  function updateClock() {
    const str = localTimeStr();
    if ($('sbTime')) $('sbTime').textContent = str;
    if ($('sbTimeMobile')) $('sbTimeMobile').textContent = str;
  }

  function start() {
    setStatus('connecting');
    checkHealth();
    fetchTickers();
    setInterval(fetchTickers, 15000);
    updateClock();
    setInterval(updateClock, 1000);
  }

  window.Shell = { API_BASE, localTimeStr, setStatus, start };
})();
