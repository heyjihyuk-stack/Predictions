/* ── API ───────────────────────────────────────────────────────────── */
const API = '/api';
async function api(path) {
  const resp = await fetch(API + path);
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

/* ── State ─────────────────────────────────────────────────────────── */
let activeTab = 'dashboard';
let indexChart = null, forexChart = null, cryptoChart = null, pcOiChart = null, ivChart = null;
let selectedIndex = null, selectedForex = null, selectedCrypto = null;
let currentNewsSort = 'impact';
let cachedNewsData = null;

/* ── Tab Navigation ────────────────────────────────────────────────── */
document.querySelectorAll('.nav-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    activeTab = tab.dataset.tab;
    document.querySelectorAll('.tab-content').forEach(s => s.style.display = 'none');
    document.getElementById('tab-' + activeTab).style.display = 'block';
    if (activeTab === 'dashboard') loadDashboard();
    if (activeTab === 'markets') loadIndices();
    if (activeTab === 'forex') loadForex();
    if (activeTab === 'crypto') loadCrypto();
    if (activeTab === 'news') loadNewsImpact();
    if (activeTab === 'predictions') loadAllPredictions();
  });
});

/* ── Dashboard ─────────────────────────────────────────────────────── */
async function loadDashboard() {
  const loading = document.getElementById('dashboard-loading');
  const content = document.getElementById('dashboard-content');
  loading.style.display = 'flex';
  content.style.display = 'none';

  try {
    const data = await api('/dashboard');
    loading.style.display = 'none';
    content.style.display = 'block';

    // Fear & Greed + Sentiment gauges
    renderFearGreedGauge(data.fear_greed, 'fg-gauge');
    renderSentimentGauge(data.sentiment, 'sentiment-gauge');

    // Market snapshot
    const mkts = document.getElementById('dash-markets');
    let html = '';
    (data.indices || []).forEach(m => {
      html += miniTile(m.id, m.name, m.current_price, m.change_pct, m.country);
    });
    (data.forex || []).forEach(m => {
      html += miniTile(m.id, m.name, m.current_rate, m.change_pct, `${m.base}/${m.quote}`);
    });
    (data.crypto || []).forEach(m => {
      html += miniTile(m.id, m.name, m.current_price, m.change_24h_pct, m.symbol);
    });
    mkts.innerHTML = html;

    // Top news clusters
    const newsDiv = document.getElementById('dash-top-news');
    renderClusters(data.top_news || [], newsDiv);

  } catch (e) {
    loading.innerHTML = `<div class="empty-state">Failed to load dashboard. ${e.message}</div>`;
  }
}

function miniTile(id, name, price, changePct, sub) {
  const chg = changePct || 0;
  const cls = chg >= 0 ? 'up' : 'down';
  const sign = chg >= 0 ? '+' : '';
  const p = price != null ? formatNumber(price) : 'N/A';
  return `<div class="market-tile">
    <div class="name">${name}</div>
    <div class="country">${sub}</div>
    <div class="price">${p}</div>
    <div class="change ${cls}">${sign}${chg.toFixed(2)}%</div>
  </div>`;
}

function renderDelta(val, suffix = '') {
  if (val == null) return '';
  const sign = val >= 0 ? '+' : '';
  const color = val > 0 ? 'var(--green)' : val < 0 ? 'var(--red)' : 'var(--text-dim)';
  return `<span style="color:${color};font-size:12px;font-weight:500;">${sign}${val}${suffix}</span>`;
}

function renderFearGreedGauge(fg, containerId) {
  if (!fg) return;
  const color = fg.score >= 60 ? 'var(--green)' : fg.score <= 40 ? 'var(--red)' : 'var(--orange)';
  const pct = fg.score;
  document.getElementById(containerId).innerHTML = `
    <div style="text-align:center;">
      <div class="sentiment-score-big" style="color:${color}">${fg.score}</div>
      <div class="sentiment-label" style="color:${color}">${fg.label}</div>
      <div class="sentiment-stats" style="margin-top:6px;">
        ${fg.delta_1d != null ? `<span>24h: ${renderDelta(fg.delta_1d)}</span>` : ''}
        ${fg.delta_7d != null ? `<span>7d: ${renderDelta(fg.delta_7d)}</span>` : ''}
      </div>
      <div style="margin-top:10px;height:8px;background:linear-gradient(to right, var(--red), var(--orange), var(--green));border-radius:4px;position:relative;">
        <div style="position:absolute;left:${pct}%;top:-3px;width:14px;height:14px;background:#fff;border-radius:50%;transform:translateX(-50%);border:2px solid ${color};"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--text-dim);margin-top:4px;">
        <span>Fear</span><span>Greed</span>
      </div>
    </div>`;
}

function renderSentimentGauge(s, containerId) {
  if (!s) return;
  const color = s.overall === 'bullish' ? 'var(--green)' : s.overall === 'bearish' ? 'var(--red)' : 'var(--text-dim)';
  document.getElementById(containerId).innerHTML = `
    <div class="sentiment-row">
      <div style="text-align:center;">
        <div class="sentiment-score-big" style="color:${color}">${s.score}</div>
        <div class="sentiment-label" style="color:${color}">${s.overall.toUpperCase()}</div>
        <div class="sentiment-stats">
          <span style="color:var(--green)">Bull ${s.bullish_pct}%</span>
          <span>Neutral ${s.neutral_pct || 0}%</span>
          <span style="color:var(--red)">Bear ${s.bearish_pct}%</span>
        </div>
        <div class="sentiment-stats" style="margin-top:4px;">
          ${s.delta_1d != null ? `<span>24h: ${renderDelta(s.delta_1d)}</span>` : ''}
          ${s.delta_7d != null ? `<span>7d: ${renderDelta(s.delta_7d)}</span>` : ''}
        </div>
      </div>
      <div class="sentiment-meter">
        <div class="sentiment-bar-track">
          <div class="bar-bull" style="width:${s.bullish_pct}%"></div>
          <div class="bar-neutral" style="width:${s.neutral_pct || 0}%"></div>
          <div class="bar-bear" style="width:${s.bearish_pct}%"></div>
        </div>
        <div class="sentiment-labels">
          <span>Bullish</span>
          <span>${s.total_articles || 0} articles</span>
          <span>Bearish</span>
        </div>
      </div>
    </div>`;
}

/* ── News Clusters ─────────────────────────────────────────────────── */
async function loadNewsImpact() {
  const container = document.getElementById('news-clusters');
  container.innerHTML = '<div class="loading"><div class="spinner"></div> Analyzing news impact...</div>';

  try {
    const data = await api(`/news/impact?sort=${currentNewsSort}`);
    cachedNewsData = data;

    // Sentiment bar
    renderSentimentGauge(data.sentiment, 'news-sentiment-bar');

    renderClusters(data.clusters || [], container);
  } catch (e) {
    container.innerHTML = `<div class="empty-state">Failed to analyze news. ${e.message}</div>`;
  }
}

function renderClusters(clusters, container) {
  if (!clusters.length) {
    container.innerHTML = '<div class="empty-state">No news articles available.</div>';
    return;
  }

  let html = '';
  clusters.forEach(cluster => {
    const topArticle = cluster.articles[0];
    const impactClass = cluster.max_impact >= 86 ? 'extreme' : cluster.max_impact >= 71 ? 'high' : cluster.max_impact >= 31 ? 'moderate' : 'low';
    const isSeries = cluster.is_series;
    const tags = [...(cluster.affected_markets || []), ...(cluster.affected_forex || [])].slice(0, 4);
    const sentClass = cluster.sentiment;

    html += `<div class="news-cluster">
      <div class="cluster-header ${isSeries ? 'has-series' : ''}"
           onclick="${isSeries ? `toggleTimeline('${cluster.cluster_id}', this)` : `openNewsDetail('${topArticle.id}')`}">
        <div class="cluster-badge-col">
          <div class="impact-badge ${impactClass}">${cluster.max_impact}</div>
          <div class="sentiment-dot ${sentClass}" title="${sentClass}"></div>
        </div>
        <div class="cluster-info">
          <div class="cluster-title">${escapeHtml(cluster.cluster_label)}</div>
          <div class="cluster-meta">
            <span>${escapeHtml(topArticle.source || '')}</span>
            <span style="color:${sentClass === 'bullish' ? 'var(--green)' : sentClass === 'bearish' ? 'var(--red)' : 'var(--text-dim)'}">${sentClass}</span>
            ${topArticle.published ? `<span>${new Date(topArticle.published).toLocaleDateString()}</span>` : ''}
          </div>
          <div class="affected">
            ${tags.map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}
          </div>
        </div>
        ${isSeries ? `<span class="cluster-count">${cluster.article_count} articles</span>` : ''}
      </div>`;

    // Timeline for series
    if (isSeries) {
      html += `<div class="cluster-timeline" id="timeline-${cluster.cluster_id}">`;
      cluster.articles.forEach(a => {
        html += `
          <div class="timeline-item" onclick="openNewsDetail('${a.id}')">
            <div class="timeline-dot"></div>
            <div class="timeline-content">
              <div class="tl-title">${escapeHtml(a.title)}</div>
              <div class="tl-meta">
                ${escapeHtml(a.source || '')}
                ${a.published ? ` | ${new Date(a.published).toLocaleString()}` : ''}
                | Impact: ${a.impact_score}
                | <span style="color:${a.sentiment === 'bullish' ? 'var(--green)' : a.sentiment === 'bearish' ? 'var(--red)' : 'var(--text-dim)'}">${a.sentiment}</span>
              </div>
            </div>
          </div>`;
      });
      html += '</div>';
    }

    html += '</div>';
  });

  container.innerHTML = html;
}

function toggleTimeline(clusterId, headerEl) {
  const timeline = document.getElementById('timeline-' + clusterId);
  const isOpen = timeline.classList.contains('open');
  timeline.classList.toggle('open');
  headerEl.classList.toggle('expanded');
  if (isOpen) {
    headerEl.classList.add('has-series');
  } else {
    headerEl.classList.remove('has-series');
  }
}

// News sort selector
document.getElementById('news-sort-selector')?.addEventListener('click', e => {
  if (e.target.classList.contains('period-btn')) {
    document.querySelectorAll('#news-sort-selector .period-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentNewsSort = e.target.dataset.sort;
    loadNewsImpact();
  }
});

/* ── Market Indices ────────────────────────────────────────────────── */
async function loadIndices() {
  const grid = document.getElementById('indices-grid');
  try {
    const data = await api('/markets/indices');
    grid.innerHTML = '';
    data.indices.forEach(idx => {
      const changeClass = (idx.change_pct || 0) >= 0 ? 'up' : 'down';
      const changeSign = (idx.change_pct || 0) >= 0 ? '+' : '';
      const price = idx.current_price ? formatNumber(idx.current_price) : 'N/A';
      grid.innerHTML += `
        <div class="market-tile" onclick="selectIndex('${idx.id}')">
          <div class="name">${idx.name}</div>
          <div class="country">${idx.country}</div>
          <div class="price">${price}</div>
          <div class="change ${changeClass}">${changeSign}${(idx.change_pct || 0).toFixed(2)}%</div>
          <div class="mini-chart"><canvas id="mini-${idx.id}" height="40"></canvas></div>
        </div>`;
    });
    data.indices.forEach(idx => loadMiniChart(idx.id, 'index'));
  } catch (e) {
    grid.innerHTML = `<div class="empty-state">Failed to load. ${e.message}</div>`;
  }
}

async function selectIndex(id) {
  selectedIndex = id;
  document.getElementById('index-detail').style.display = 'block';
  document.getElementById('index-detail').scrollIntoView({ behavior: 'smooth' });
  loadIndexChart(id, '1m');
  loadPredictionCards(id, 'index', 'index-predictions');
}

async function loadIndexChart(id, period) {
  try {
    const data = await api(`/markets/indices/${id}?period=${period}`);
    document.getElementById('index-detail-name').textContent = data.name;
    renderChart('index-chart', data, 'indexChart');
  } catch (e) { console.error(e); }
}

document.getElementById('index-period-selector')?.addEventListener('click', e => {
  if (e.target.classList.contains('period-btn') && selectedIndex) {
    document.querySelectorAll('#index-period-selector .period-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    loadIndexChart(selectedIndex, e.target.dataset.period);
  }
});

/* ── Forex ─────────────────────────────────────────────────────────── */
async function loadForex() {
  const grid = document.getElementById('forex-grid');
  try {
    const data = await api('/markets/forex');
    grid.innerHTML = '';
    data.forex.forEach(pair => {
      const cls = (pair.change_pct || 0) >= 0 ? 'up' : 'down';
      const sign = (pair.change_pct || 0) >= 0 ? '+' : '';
      const rate = pair.current_rate ? pair.current_rate.toFixed(4) : 'N/A';
      grid.innerHTML += `
        <div class="market-tile" onclick="selectForex('${pair.id}')">
          <div class="name">${pair.name}</div>
          <div class="country">${pair.base} / ${pair.quote}</div>
          <div class="price">${rate}</div>
          <div class="change ${cls}">${sign}${(pair.change_pct || 0).toFixed(2)}%</div>
          <div class="mini-chart"><canvas id="mini-${pair.id}" height="40"></canvas></div>
        </div>`;
    });
    data.forex.forEach(pair => loadMiniChart(pair.id, 'forex'));
  } catch (e) {
    grid.innerHTML = `<div class="empty-state">Failed to load. ${e.message}</div>`;
  }
}

async function selectForex(id) {
  selectedForex = id;
  document.getElementById('forex-detail').style.display = 'block';
  document.getElementById('forex-detail').scrollIntoView({ behavior: 'smooth' });
  loadForexChart(id, '1m');
  loadPredictionCards(id, 'forex', 'forex-predictions');
}

async function loadForexChart(id, period) {
  try {
    const data = await api(`/markets/forex/${id}?period=${period}`);
    document.getElementById('forex-detail-name').textContent = data.name;
    renderChart('forex-chart', data, 'forexChart');
  } catch (e) { console.error(e); }
}

document.getElementById('forex-period-selector')?.addEventListener('click', e => {
  if (e.target.classList.contains('period-btn') && selectedForex) {
    document.querySelectorAll('#forex-period-selector .period-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    loadForexChart(selectedForex, e.target.dataset.period);
  }
});

/* ── Crypto ────────────────────────────────────────────────────────── */
async function loadCrypto() {
  const grid = document.getElementById('crypto-grid');
  try {
    const data = await api('/markets/crypto');
    grid.innerHTML = '';
    data.crypto.forEach(c => {
      const chg = c.change_24h_pct || 0;
      const cls = chg >= 0 ? 'up' : 'down';
      const sign = chg >= 0 ? '+' : '';
      const price = c.current_price ? formatNumber(c.current_price) : 'N/A';
      grid.innerHTML += `
        <div class="market-tile" onclick="selectCrypto('${c.id}')">
          <div class="name">${c.name} <span style="color:var(--text-dim);font-weight:400;">${c.symbol}</span></div>
          <div class="price">$${price}</div>
          <div class="change ${cls}">${sign}${chg.toFixed(2)}% (24h)</div>
          <div class="crypto-meta">
            <span>MCap: ${c.market_cap ? '$' + formatLargeNumber(c.market_cap) : 'N/A'}</span>
            <span>Vol: ${c.volume_24h ? '$' + formatLargeNumber(c.volume_24h) : 'N/A'}</span>
          </div>
          <div class="mini-chart"><canvas id="mini-${c.id}" height="40"></canvas></div>
        </div>`;
    });
    data.crypto.forEach(c => loadMiniChart(c.id, 'crypto'));
  } catch (e) {
    grid.innerHTML = `<div class="empty-state">Failed to load. ${e.message}</div>`;
  }
}

async function selectCrypto(id) {
  selectedCrypto = id;
  document.getElementById('crypto-detail').style.display = 'block';
  document.getElementById('crypto-detail').scrollIntoView({ behavior: 'smooth' });
  loadCryptoChart(id, '1m');
  loadPredictionCards(id, 'crypto', 'crypto-predictions');
  loadOptionsData(id);
}

async function loadCryptoChart(id, period) {
  try {
    const data = await api(`/markets/crypto/${id}?period=${period}`);
    document.getElementById('crypto-detail-name').textContent = data.name + ' (' + data.symbol + ')';
    renderChart('crypto-chart', data, 'cryptoChart');
  } catch (e) { console.error(e); }
}

document.getElementById('crypto-period-selector')?.addEventListener('click', e => {
  if (e.target.classList.contains('period-btn') && selectedCrypto) {
    document.querySelectorAll('#crypto-period-selector .period-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    loadCryptoChart(selectedCrypto, e.target.dataset.period);
  }
});

/* ── Options Data ─────────────────────────────────────────────────── */
async function loadOptionsData(cryptoId) {
  const panel = document.getElementById('options-panel');
  panel.style.display = 'block';
  const statsDiv = document.getElementById('options-stats');
  statsDiv.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const data = await api(`/markets/crypto/${cryptoId}/options`);
    document.getElementById('options-title').textContent = `${data.name} Options (Deribit)`;
    const pcColor = data.put_call_ratio > 1 ? 'var(--red)' : data.put_call_ratio < 0.7 ? 'var(--green)' : 'var(--orange)';
    statsDiv.innerHTML = `
      <div class="stat-tile"><div class="stat-label">Index Price</div><div class="stat-value">$${formatNumber(data.index_price)}</div></div>
      <div class="stat-tile"><div class="stat-label">P/C Ratio</div><div class="stat-value" style="color:${pcColor}">${data.put_call_ratio != null ? data.put_call_ratio.toFixed(3) : 'N/A'}</div>
        <div class="stat-sub">${data.put_call_ratio > 1 ? 'Bearish' : data.put_call_ratio < 0.7 ? 'Bullish' : 'Neutral'}</div></div>
      <div class="stat-tile"><div class="stat-label">Avg IV</div><div class="stat-value">${data.implied_volatility != null ? data.implied_volatility.toFixed(1) + '%' : 'N/A'}</div></div>
      <div class="stat-tile"><div class="stat-label">Open Interest</div><div class="stat-value">${formatLargeNumber(data.open_interest_total)}</div>
        <div class="stat-sub">C:${formatLargeNumber(data.calls_oi)} P:${formatLargeNumber(data.puts_oi)}</div></div>
      <div class="stat-tile"><div class="stat-label">24h Vol</div><div class="stat-value">${formatLargeNumber(data.volume_24h_total)}</div></div>`;
    renderPCChart(data.calls_oi, data.puts_oi);
    renderIVChart(data.key_expirations || []);
    const tbody = document.getElementById('expirations-body');
    tbody.innerHTML = (data.key_expirations || []).map(exp => {
      const pcStyle = exp.pc_ratio > 1 ? 'color:var(--red)' : exp.pc_ratio < 0.7 ? 'color:var(--green)' : '';
      return `<tr>
        <td style="text-align:left;font-weight:500;">${exp.expiration}</td>
        <td style="text-align:right;">${formatLargeNumber(exp.call_oi)}</td>
        <td style="text-align:right;">${formatLargeNumber(exp.put_oi)}</td>
        <td style="text-align:right;font-weight:600;">${formatLargeNumber(exp.total_oi)}</td>
        <td style="text-align:right;${pcStyle}">${exp.pc_ratio != null ? exp.pc_ratio.toFixed(3) : '-'}</td>
        <td style="text-align:right;">${exp.avg_iv != null ? exp.avg_iv.toFixed(1) + '%' : '-'}</td>
        <td style="text-align:right;">${exp.call_volume.toFixed(1)}</td>
        <td style="text-align:right;">${exp.put_volume.toFixed(1)}</td>
      </tr>`;
    }).join('');
  } catch (e) {
    statsDiv.innerHTML = `<div class="empty-state">Options data unavailable. ${e.message}</div>`;
  }
}

function renderPCChart(calls, puts) {
  const canvas = document.getElementById('pc-oi-chart');
  if (pcOiChart) pcOiChart.destroy();
  pcOiChart = new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: { labels: ['Calls', 'Puts'], datasets: [{ data: [calls, puts], backgroundColor: ['rgba(34,197,94,0.7)', 'rgba(239,68,68,0.7)'], borderWidth: 0 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { color: '#8b8fa3' } } } }
  });
}

function renderIVChart(exps) {
  const canvas = document.getElementById('iv-chart');
  if (ivChart) ivChart.destroy();
  ivChart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: { labels: exps.map(e => e.expiration).slice(0, 8), datasets: [{ label: 'IV%', data: exps.map(e => e.avg_iv).slice(0, 8), backgroundColor: 'rgba(168,85,247,0.5)', borderRadius: 4 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { color: 'rgba(42,45,58,0.5)' }, ticks: { color: '#8b8fa3', font: { size: 10 } } }, y: { grid: { color: 'rgba(42,45,58,0.5)' }, ticks: { color: '#8b8fa3', callback: v => v + '%' } } } }
  });
}

/* ── Chart Rendering ──────────────────────────────────────────────── */
function renderChart(canvasId, data, chartRef) {
  const canvas = document.getElementById(canvasId);
  if (chartRef === 'indexChart' && indexChart) indexChart.destroy();
  if (chartRef === 'forexChart' && forexChart) forexChart.destroy();
  if (chartRef === 'cryptoChart' && cryptoChart) cryptoChart.destroy();

  const timestamps = (data.timestamps || []).map(t => new Date(t * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
  const prices = data.prices || [];
  const isUp = prices.length >= 2 && prices[prices.length - 1] >= prices[0];
  const lineColor = isUp ? '#22c55e' : '#ef4444';
  const fillColor = isUp ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)';

  const chart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: { labels: timestamps, datasets: [{ label: 'Price', data: prices, borderColor: lineColor, backgroundColor: fillColor, borderWidth: 2, fill: true, pointRadius: 0, pointHitRadius: 10, tension: 0.3 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: { legend: { display: false }, tooltip: { backgroundColor: '#1a1d27', titleColor: '#e4e6eb', bodyColor: '#e4e6eb', borderColor: '#2a2d3a', borderWidth: 1, callbacks: { label: ctx => `Price: ${formatNumber(ctx.parsed.y)}` } } },
      scales: { x: { grid: { color: 'rgba(42,45,58,0.5)' }, ticks: { color: '#8b8fa3', maxTicksLimit: 10 } }, y: { grid: { color: 'rgba(42,45,58,0.5)' }, ticks: { color: '#8b8fa3', callback: v => formatNumber(v) } } }
    }
  });

  if (chartRef === 'indexChart') indexChart = chart;
  if (chartRef === 'forexChart') forexChart = chart;
  if (chartRef === 'cryptoChart') cryptoChart = chart;
}

async function loadMiniChart(assetId, type) {
  const canvas = document.getElementById('mini-' + assetId);
  if (!canvas) return;
  try {
    let ep = type === 'index' ? `/markets/indices/${assetId}?period=1w` : type === 'forex' ? `/markets/forex/${assetId}?period=1w` : `/markets/crypto/${assetId}?period=1w`;
    const data = await api(ep);
    const prices = (data.prices || []).filter(p => p != null);
    if (prices.length < 2) return;
    const isUp = prices[prices.length - 1] >= prices[0];
    new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: { labels: prices.map((_, i) => i), datasets: [{ data: prices, borderColor: isUp ? '#22c55e' : '#ef4444', borderWidth: 1.5, fill: false, pointRadius: 0, tension: 0.4 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { display: false }, y: { display: false } }, animation: { duration: 400 } }
    });
  } catch (e) {}
}

/* ── Predictions ──────────────────────────────────────────────────── */
async function loadPredictionCards(assetId, assetType, containerId) {
  const container = document.getElementById(containerId);
  container.innerHTML = '<div class="loading"><div class="spinner"></div> Generating predictions...</div>';

  try {
    const data = await api(`/predictions/${assetType}/${assetId}`);
    container.innerHTML = '';
    ['daily', 'weekly', 'monthly', 'quarterly', 'yearly'].forEach(h => {
      const pred = data.predictions?.[h];
      if (!pred) return;
      const dirClass = pred.direction === 'up' ? 'up' : pred.direction === 'down' ? 'down' : 'sideways';
      const dirLabel = pred.direction === 'up' ? 'Bullish' : pred.direction === 'down' ? 'Bearish' : 'Sideways';
      const conf = (pred.confidence * 100).toFixed(0);
      const confColor = pred.confidence > 0.6 ? 'var(--green)' : pred.confidence > 0.4 ? 'var(--orange)' : 'var(--red)';
      container.innerHTML += `
        <div class="prediction-card">
          <div class="horizon">${h}</div>
          <div class="direction ${dirClass}">${dirLabel}</div>
          <div class="target">${formatNumber(pred.target_low)} — <strong>${formatNumber(pred.target_mid)}</strong> — ${formatNumber(pred.target_high)}</div>
          <div class="target" style="margin-top:3px;" title="${pred.reasoning || ''}">${(pred.key_drivers || []).slice(0, 2).join(' | ')}</div>
          <div class="confidence-bar"><div class="confidence-fill" style="width:${conf}%;background:${confColor};"></div></div>
          <div class="target" style="margin-top:3px;">Confidence: ${conf}%</div>
        </div>`;
    });
  } catch (e) {
    container.innerHTML = `<div class="empty-state">Predictions unavailable. ${e.message}</div>`;
  }
}

async function loadAllPredictions() {
  const container = document.getElementById('all-predictions');
  const indices = ['sp500', 'nasdaq', 'dow', 'kospi', 'shanghai', 'nikkei', 'ftse', 'dax', 'eurostoxx'];
  const forex = ['usd_krw', 'usd_cny', 'usd_jpy', 'eur_usd', 'gbp_usd'];
  const crypto = ['btc', 'eth'];
  let html = '<div class="section-label">Stock Indices</div>';
  indices.forEach(id => { html += `<div class="card"><div class="card-header"><h2>${id.toUpperCase()}</h2></div><div class="predictions-grid" id="pred-cards-${id}"><div class="loading"><div class="spinner"></div></div></div></div>`; });
  html += '<div class="section-label" style="margin-top:20px;">Forex</div>';
  forex.forEach(id => { html += `<div class="card"><div class="card-header"><h2>${id.replace('_', '/').toUpperCase()}</h2></div><div class="predictions-grid" id="pred-cards-${id}"><div class="loading"><div class="spinner"></div></div></div></div>`; });
  html += '<div class="section-label" style="margin-top:20px;">Crypto</div>';
  crypto.forEach(id => { html += `<div class="card"><div class="card-header"><h2>${id.toUpperCase()}</h2></div><div class="predictions-grid" id="pred-cards-${id}"><div class="loading"><div class="spinner"></div></div></div></div>`; });
  container.innerHTML = html;
  indices.forEach(id => loadPredictionCards(id, 'index', `pred-cards-${id}`));
  forex.forEach(id => loadPredictionCards(id, 'forex', `pred-cards-${id}`));
  crypto.forEach(id => loadPredictionCards(id, 'crypto', `pred-cards-${id}`));
}

/* ── News Detail Modal ────────────────────────────────────────────── */
async function openNewsDetail(newsId) {
  const modal = document.getElementById('news-modal');
  const content = document.getElementById('modal-content');
  modal.classList.add('open');
  content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const data = await api(`/news/${newsId}`);
    const a = data.article;
    const related = data.related || [];
    const impactClass = a.impact_score >= 86 ? 'extreme' : a.impact_score >= 71 ? 'high' : a.impact_score >= 31 ? 'moderate' : 'low';
    const sentColor = a.sentiment === 'bullish' ? 'var(--green)' : a.sentiment === 'bearish' ? 'var(--red)' : 'var(--text-dim)';

    let html = `
      <div class="impact-header">
        <div class="impact-badge ${impactClass}" style="width:56px;height:56px;font-size:20px;">${a.impact_score}</div>
        <div>
          <h2>${escapeHtml(a.title)}</h2>
          <div style="font-size:13px;color:var(--text-dim);">
            ${escapeHtml(a.source)} <span style="color:${sentColor};margin-left:6px;">${a.sentiment}</span>
            ${a.published ? ` | ${new Date(a.published).toLocaleString()}` : ''}
          </div>
        </div>
      </div>
      <div style="margin-bottom:12px;"><strong>Why it matters:</strong><p style="color:var(--text-dim);margin-top:4px;">${escapeHtml(a.impact_reasoning || '')}</p></div>
      <div style="margin-bottom:12px;"><strong>Affected:</strong>
        <div class="affected" style="margin-top:4px;">
          ${(a.affected_markets || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}
          ${(a.affected_forex || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}
        </div>
      </div>
      <div class="article-body">${escapeHtml(a.full_text || '')}</div>
      ${a.url ? `<a href="${escapeHtml(a.url)}" target="_blank" class="source-link">Read Source</a>` : ''}`;

    if (related.length) {
      html += '<div class="related-section"><h3>Related</h3><ul class="news-list">';
      related.forEach(r => {
        const rc = r.impact_score >= 71 ? 'high' : r.impact_score >= 31 ? 'moderate' : 'low';
        html += `<li class="news-item" style="padding:8px 0;" onclick="openNewsDetail('${r.id}')">
          <div class="impact-badge ${rc}" style="width:32px;height:32px;font-size:11px;">${r.impact_score}</div>
          <div class="news-content"><div class="title" style="font-size:13px;">${escapeHtml(r.title)}</div><div class="meta">${escapeHtml(r.source)}</div></div>
        </li>`;
      });
      html += '</ul></div>';
    }
    content.innerHTML = html;
  } catch (e) {
    content.innerHTML = `<div class="empty-state">Failed to load. ${e.message}</div>`;
  }
}

function closeModal() { document.getElementById('news-modal').classList.remove('open'); }
document.getElementById('news-modal').addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });

/* ── Prediction Change Alerts ─────────────────────────────────────── */
async function checkPredictionChanges() {
  try {
    const data = await api('/predictions/changes');
    const div = document.getElementById('change-alerts');
    if (data.changes?.length) {
      div.innerHTML = data.changes.map(c => `<div class="change-alert"><span><strong>${c.asset_id.toUpperCase()}</strong> prediction updated: ${c.changes.map(ch => `${ch.horizon} ${ch.field}: ${ch.old} -> ${ch.new}`).join(', ')}</span></div>`).join('');
    }
  } catch (e) {}
}

/* ── Utilities ─────────────────────────────────────────────────────── */
function formatNumber(n) {
  if (n == null) return 'N/A';
  if (Math.abs(n) >= 1000) return n.toLocaleString('en-US', { maximumFractionDigits: 2 });
  if (Math.abs(n) >= 1) return n.toFixed(2);
  return n.toFixed(4);
}
function formatLargeNumber(n) {
  if (n == null) return 'N/A';
  if (n >= 1e12) return (n / 1e12).toFixed(2) + 'T';
  if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n.toLocaleString('en-US', { maximumFractionDigits: 1 });
}
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/* ── Init ──────────────────────────────────────────────────────────── */
loadDashboard();
setInterval(checkPredictionChanges, 60000);
