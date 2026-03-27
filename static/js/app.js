/* ── API Helper ────────────────────────────────────────────────────── */
const API = '/api';

async function api(path) {
  const resp = await fetch(API + path);
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

/* ── State ─────────────────────────────────────────────────────────── */
let activeTab = 'markets';
let indexChart = null;
let forexChart = null;
let cryptoChart = null;
let pcOiChart = null;
let ivChart = null;
let selectedIndex = null;
let selectedForex = null;
let selectedCrypto = null;

/* ── Tab Navigation ────────────────────────────────────────────────── */
document.querySelectorAll('.nav-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    activeTab = tab.dataset.tab;
    document.querySelectorAll('.tab-content').forEach(s => s.style.display = 'none');
    document.getElementById('tab-' + activeTab).style.display = 'block';

    if (activeTab === 'markets') loadIndices();
    if (activeTab === 'forex') loadForex();
    if (activeTab === 'crypto') loadCrypto();
    if (activeTab === 'news') loadNewsImpact();
    if (activeTab === 'predictions') loadAllPredictions();
  });
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
          <div class="mini-chart"><canvas id="mini-${idx.id}" height="50"></canvas></div>
        </div>`;
    });
    data.indices.forEach(idx => loadMiniChart(idx.id, 'index'));
  } catch (e) {
    grid.innerHTML = `<div class="empty-state">Failed to load market data. ${e.message}</div>`;
  }
}

async function selectIndex(indexId) {
  selectedIndex = indexId;
  const detail = document.getElementById('index-detail');
  detail.style.display = 'block';
  detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
  loadIndexChart(indexId, '1m');
  loadPredictionCards(indexId, 'index', 'index-predictions');
}

async function loadIndexChart(indexId, period) {
  try {
    const data = await api(`/markets/indices/${indexId}?period=${period}`);
    document.getElementById('index-detail-name').textContent = data.name;
    renderChart('index-chart', data, 'indexChart');
  } catch (e) {
    console.error('Chart load failed:', e);
  }
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
      const changeClass = (pair.change_pct || 0) >= 0 ? 'up' : 'down';
      const changeSign = (pair.change_pct || 0) >= 0 ? '+' : '';
      const rate = pair.current_rate ? pair.current_rate.toFixed(4) : 'N/A';
      grid.innerHTML += `
        <div class="market-tile" onclick="selectForex('${pair.id}')">
          <div class="name">${pair.name}</div>
          <div class="country">${pair.base} / ${pair.quote}</div>
          <div class="price">${rate}</div>
          <div class="change ${changeClass}">${changeSign}${(pair.change_pct || 0).toFixed(2)}%</div>
          <div class="mini-chart"><canvas id="mini-${pair.id}" height="50"></canvas></div>
        </div>`;
    });
    data.forex.forEach(pair => loadMiniChart(pair.id, 'forex'));
  } catch (e) {
    grid.innerHTML = `<div class="empty-state">Failed to load forex data. ${e.message}</div>`;
  }
}

async function selectForex(pairId) {
  selectedForex = pairId;
  const detail = document.getElementById('forex-detail');
  detail.style.display = 'block';
  detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
  loadForexChart(pairId, '1m');
  loadPredictionCards(pairId, 'forex', 'forex-predictions');
}

async function loadForexChart(pairId, period) {
  try {
    const data = await api(`/markets/forex/${pairId}?period=${period}`);
    document.getElementById('forex-detail-name').textContent = data.name;
    renderChart('forex-chart', data, 'forexChart');
  } catch (e) {
    console.error('Chart load failed:', e);
  }
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
      const change = c.change_24h_pct || 0;
      const changeClass = change >= 0 ? 'up' : 'down';
      const changeSign = change >= 0 ? '+' : '';
      const price = c.current_price ? formatNumber(c.current_price) : 'N/A';
      const mcap = c.market_cap ? '$' + formatLargeNumber(c.market_cap) : '';
      const vol = c.volume_24h ? '$' + formatLargeNumber(c.volume_24h) : '';

      grid.innerHTML += `
        <div class="market-tile" onclick="selectCrypto('${c.id}')">
          <div class="name">${c.name} <span style="color:var(--text-dim);font-weight:400;">${c.symbol}</span></div>
          <div class="price">$${price}</div>
          <div class="change ${changeClass}">${changeSign}${change.toFixed(2)}% (24h)</div>
          <div class="crypto-meta">
            <span>MCap: ${mcap}</span>
            <span>Vol: ${vol}</span>
            ${c.change_7d_pct != null ? `<span>7d: ${c.change_7d_pct >= 0 ? '+' : ''}${c.change_7d_pct.toFixed(2)}%</span>` : ''}
          </div>
          <div class="mini-chart"><canvas id="mini-${c.id}" height="50"></canvas></div>
        </div>`;
    });
    data.crypto.forEach(c => loadMiniChart(c.id, 'crypto'));
  } catch (e) {
    grid.innerHTML = `<div class="empty-state">Failed to load crypto data. ${e.message}</div>`;
  }
}

async function selectCrypto(cryptoId) {
  selectedCrypto = cryptoId;
  const detail = document.getElementById('crypto-detail');
  detail.style.display = 'block';
  detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
  loadCryptoChart(cryptoId, '1m');
  loadPredictionCards(cryptoId, 'crypto', 'crypto-predictions');
  loadOptionsData(cryptoId);
}

async function loadCryptoChart(cryptoId, period) {
  try {
    const data = await api(`/markets/crypto/${cryptoId}?period=${period}`);
    document.getElementById('crypto-detail-name').textContent = data.name + ' (' + data.symbol + ')';
    renderChart('crypto-chart', data, 'cryptoChart');
  } catch (e) {
    console.error('Crypto chart load failed:', e);
  }
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
  statsDiv.innerHTML = '<div class="loading"><div class="spinner"></div> Loading options data...</div>';

  try {
    const data = await api(`/markets/crypto/${cryptoId}/options`);
    document.getElementById('options-title').textContent = `${data.name} Options (Deribit)`;

    // Stats tiles
    const pcColor = data.put_call_ratio > 1 ? 'var(--red)' : data.put_call_ratio < 0.7 ? 'var(--green)' : 'var(--orange)';
    statsDiv.innerHTML = `
      <div class="stat-tile">
        <div class="stat-label">Index Price</div>
        <div class="stat-value">$${formatNumber(data.index_price)}</div>
      </div>
      <div class="stat-tile">
        <div class="stat-label">Put/Call Ratio</div>
        <div class="stat-value" style="color:${pcColor}">${data.put_call_ratio != null ? data.put_call_ratio.toFixed(3) : 'N/A'}</div>
        <div class="stat-sub">${data.put_call_ratio > 1 ? 'Bearish bias' : data.put_call_ratio < 0.7 ? 'Bullish bias' : 'Neutral'}</div>
      </div>
      <div class="stat-tile">
        <div class="stat-label">Avg Implied Vol</div>
        <div class="stat-value">${data.implied_volatility != null ? data.implied_volatility.toFixed(1) + '%' : 'N/A'}</div>
      </div>
      <div class="stat-tile">
        <div class="stat-label">Total Open Interest</div>
        <div class="stat-value">${formatLargeNumber(data.open_interest_total)}</div>
        <div class="stat-sub">Calls: ${formatLargeNumber(data.calls_oi)} | Puts: ${formatLargeNumber(data.puts_oi)}</div>
      </div>
      <div class="stat-tile">
        <div class="stat-label">24h Volume</div>
        <div class="stat-value">${formatLargeNumber(data.volume_24h_total)}</div>
        <div class="stat-sub">${data.symbol} contracts</div>
      </div>
    `;

    // Put/Call OI doughnut chart
    renderPCChart(data.calls_oi, data.puts_oi);

    // IV by expiration bar chart
    renderIVChart(data.key_expirations || []);

    // Expirations table
    const tbody = document.getElementById('expirations-body');
    tbody.innerHTML = '';
    (data.key_expirations || []).forEach(exp => {
      const pcStyle = exp.pc_ratio > 1 ? 'color:var(--red)' : exp.pc_ratio < 0.7 ? 'color:var(--green)' : '';
      tbody.innerHTML += `
        <tr>
          <td style="text-align:left;font-weight:500;">${exp.expiration}</td>
          <td style="text-align:right;">${formatLargeNumber(exp.call_oi)}</td>
          <td style="text-align:right;">${formatLargeNumber(exp.put_oi)}</td>
          <td style="text-align:right;font-weight:600;">${formatLargeNumber(exp.total_oi)}</td>
          <td style="text-align:right;${pcStyle}">${exp.pc_ratio != null ? exp.pc_ratio.toFixed(3) : '-'}</td>
          <td style="text-align:right;">${exp.avg_iv != null ? exp.avg_iv.toFixed(1) + '%' : '-'}</td>
          <td style="text-align:right;">${exp.call_volume.toFixed(1)}</td>
          <td style="text-align:right;">${exp.put_volume.toFixed(1)}</td>
        </tr>`;
    });

  } catch (e) {
    statsDiv.innerHTML = `<div class="empty-state">Failed to load options data. ${e.message}</div>`;
  }
}

function renderPCChart(callsOi, putsOi) {
  const canvas = document.getElementById('pc-oi-chart');
  if (pcOiChart) pcOiChart.destroy();

  pcOiChart = new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: ['Calls', 'Puts'],
      datasets: [{
        data: [callsOi, putsOi],
        backgroundColor: ['rgba(34,197,94,0.7)', 'rgba(239,68,68,0.7)'],
        borderColor: ['#22c55e', '#ef4444'],
        borderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#8b8fa3', padding: 16 } },
        tooltip: {
          backgroundColor: '#1a1d27',
          titleColor: '#e4e6eb',
          bodyColor: '#e4e6eb',
          callbacks: {
            label: ctx => `${ctx.label}: ${formatLargeNumber(ctx.parsed)}`
          }
        }
      }
    }
  });
}

function renderIVChart(expirations) {
  const canvas = document.getElementById('iv-chart');
  if (ivChart) ivChart.destroy();

  const labels = expirations.map(e => e.expiration).slice(0, 8);
  const ivData = expirations.map(e => e.avg_iv).slice(0, 8);

  ivChart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Avg IV %',
        data: ivData,
        backgroundColor: 'rgba(168,85,247,0.5)',
        borderColor: '#a855f7',
        borderWidth: 1,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a1d27',
          titleColor: '#e4e6eb',
          bodyColor: '#e4e6eb',
          callbacks: { label: ctx => `IV: ${ctx.parsed.y?.toFixed(1)}%` }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(42,45,58,0.5)' },
          ticks: { color: '#8b8fa3', font: { size: 10 } }
        },
        y: {
          grid: { color: 'rgba(42,45,58,0.5)' },
          ticks: { color: '#8b8fa3', callback: v => v + '%' }
        }
      }
    }
  });
}

/* ── Chart Rendering ──────────────────────────────────────────────── */
function renderChart(canvasId, data, chartRef) {
  const canvas = document.getElementById(canvasId);
  const ctx = canvas.getContext('2d');

  if (chartRef === 'indexChart' && indexChart) indexChart.destroy();
  if (chartRef === 'forexChart' && forexChart) forexChart.destroy();
  if (chartRef === 'cryptoChart' && cryptoChart) cryptoChart.destroy();

  const timestamps = (data.timestamps || []).map(t => {
    const d = new Date(t * 1000);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  });
  const prices = data.prices || [];

  const isUp = prices.length >= 2 && prices[prices.length - 1] >= prices[0];
  const lineColor = isUp ? '#22c55e' : '#ef4444';
  const fillColor = isUp ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)';

  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: timestamps,
      datasets: [{
        label: 'Price',
        data: prices,
        borderColor: lineColor,
        backgroundColor: fillColor,
        borderWidth: 2,
        fill: true,
        pointRadius: 0,
        pointHitRadius: 10,
        tension: 0.3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a1d27',
          titleColor: '#e4e6eb',
          bodyColor: '#e4e6eb',
          borderColor: '#2a2d3a',
          borderWidth: 1,
          callbacks: {
            label: ctx => `Price: ${formatNumber(ctx.parsed.y)}`
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(42,45,58,0.5)' },
          ticks: { color: '#8b8fa3', maxTicksLimit: 10 }
        },
        y: {
          grid: { color: 'rgba(42,45,58,0.5)' },
          ticks: { color: '#8b8fa3', callback: v => formatNumber(v) }
        }
      }
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
    let endpoint;
    if (type === 'index') endpoint = `/markets/indices/${assetId}?period=1w`;
    else if (type === 'forex') endpoint = `/markets/forex/${assetId}?period=1w`;
    else endpoint = `/markets/crypto/${assetId}?period=1w`;

    const data = await api(endpoint);
    const prices = (data.prices || []).filter(p => p != null);
    if (prices.length < 2) return;

    const isUp = prices[prices.length - 1] >= prices[0];
    const color = isUp ? '#22c55e' : '#ef4444';

    new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels: prices.map((_, i) => i),
        datasets: [{
          data: prices,
          borderColor: color,
          borderWidth: 1.5,
          fill: false,
          pointRadius: 0,
          tension: 0.4,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: { x: { display: false }, y: { display: false } },
        animation: { duration: 500 },
      }
    });
  } catch (e) { /* Mini chart failure is non-critical */ }
}

/* ── Predictions ──────────────────────────────────────────────────── */
async function loadPredictionCards(assetId, assetType, containerId) {
  const container = document.getElementById(containerId);
  container.innerHTML = '<div class="loading"><div class="spinner"></div> Generating predictions...</div>';

  try {
    const data = await api(`/predictions/${assetType}/${assetId}`);
    container.innerHTML = '';

    const horizons = ['weekly', 'monthly', 'quarterly', 'yearly'];
    horizons.forEach(h => {
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
          <div class="target">
            Target: ${formatNumber(pred.target_low)} — <strong>${formatNumber(pred.target_mid)}</strong> — ${formatNumber(pred.target_high)}
          </div>
          <div class="target" style="margin-top:4px;" title="${pred.reasoning || ''}">
            ${(pred.key_drivers || []).slice(0, 2).join(' | ')}
          </div>
          <div class="confidence-bar">
            <div class="confidence-fill" style="width:${conf}%;background:${confColor};"></div>
          </div>
          <div class="target" style="margin-top:4px;">Confidence: ${conf}%</div>
        </div>`;
    });
  } catch (e) {
    container.innerHTML = `<div class="empty-state">Failed to load predictions. ${e.message}</div>`;
  }
}

async function loadAllPredictions() {
  const container = document.getElementById('all-predictions');
  container.innerHTML = '<div class="loading"><div class="spinner"></div> Loading all predictions...</div>';

  const indices = ['sp500', 'nasdaq', 'dow', 'kospi', 'shanghai', 'nikkei', 'ftse', 'dax', 'eurostoxx'];
  const forex = ['usd_krw', 'usd_cny', 'usd_jpy', 'eur_usd', 'gbp_usd'];
  const crypto = ['btc', 'eth'];
  let html = '';

  html += '<div class="section-label" style="margin-top:16px;">Stock Index Predictions</div>';
  for (const id of indices) {
    html += `<div class="card"><div class="card-header"><h2>${id.toUpperCase()}</h2></div>
      <div class="predictions-grid" id="pred-cards-${id}"><div class="loading"><div class="spinner"></div></div></div></div>`;
  }

  html += '<div class="section-label" style="margin-top:24px;">Forex Predictions</div>';
  for (const id of forex) {
    html += `<div class="card"><div class="card-header"><h2>${id.replace('_', '/').toUpperCase()}</h2></div>
      <div class="predictions-grid" id="pred-cards-${id}"><div class="loading"><div class="spinner"></div></div></div></div>`;
  }

  html += '<div class="section-label" style="margin-top:24px;">Crypto Predictions</div>';
  for (const id of crypto) {
    html += `<div class="card"><div class="card-header"><h2>${id.toUpperCase()}</h2></div>
      <div class="predictions-grid" id="pred-cards-${id}"><div class="loading"><div class="spinner"></div></div></div></div>`;
  }

  container.innerHTML = html;

  const loadBatch = async (ids, type) => {
    for (const id of ids) {
      loadPredictionCards(id, type, `pred-cards-${id}`);
    }
  };
  loadBatch(indices, 'index');
  loadBatch(forex, 'forex');
  loadBatch(crypto, 'crypto');
}

/* ── News Impact ──────────────────────────────────────────────────── */
async function loadNewsImpact() {
  const list = document.getElementById('news-list');
  list.innerHTML = '<div class="loading"><div class="spinner"></div> Analyzing news impact...</div>';

  try {
    const data = await api('/news/impact');
    list.innerHTML = '';

    if (!data.articles || data.articles.length === 0) {
      list.innerHTML = '<div class="empty-state">No news articles available.</div>';
      return;
    }

    data.articles.forEach(article => {
      const impactClass = article.impact_score >= 86 ? 'extreme'
        : article.impact_score >= 71 ? 'high'
        : article.impact_score >= 31 ? 'moderate'
        : 'low';

      const sentimentColor = article.sentiment === 'positive' ? 'var(--green)'
        : article.sentiment === 'negative' ? 'var(--red)' : 'var(--text-dim)';

      const tags = [...(article.affected_markets || []), ...(article.affected_forex || [])];

      list.innerHTML += `
        <li class="news-item" onclick="openNewsDetail('${article.id}')">
          <div class="impact-badge ${impactClass}">${article.impact_score}</div>
          <div class="news-content">
            <div class="title">${escapeHtml(article.title)}</div>
            <div class="meta">
              <span>${escapeHtml(article.source)}</span>
              <span style="color:${sentimentColor};margin-left:8px;">${article.sentiment || ''}</span>
              ${article.published ? `<span style="margin-left:8px;">${new Date(article.published).toLocaleDateString()}</span>` : ''}
            </div>
            <div class="reasoning">${escapeHtml(article.impact_reasoning || '')}</div>
            <div class="affected">
              ${tags.map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}
            </div>
          </div>
        </li>`;
    });
  } catch (e) {
    list.innerHTML = `<div class="empty-state">Failed to analyze news. ${e.message}</div>`;
  }
}

/* ── News Detail Modal ────────────────────────────────────────────── */
async function openNewsDetail(newsId) {
  const modal = document.getElementById('news-modal');
  const content = document.getElementById('modal-content');
  modal.classList.add('open');

  content.innerHTML = '<div class="loading"><div class="spinner"></div> Loading...</div>';

  try {
    const data = await api(`/news/${newsId}`);
    const article = data.article;
    const related = data.related || [];

    const impactClass = article.impact_score >= 86 ? 'extreme'
      : article.impact_score >= 71 ? 'high'
      : article.impact_score >= 31 ? 'moderate' : 'low';

    const sentimentColor = article.sentiment === 'positive' ? 'var(--green)'
      : article.sentiment === 'negative' ? 'var(--red)' : 'var(--text-dim)';

    let html = `
      <div class="impact-header">
        <div class="impact-badge ${impactClass}" style="width:64px;height:64px;font-size:22px;">${article.impact_score}</div>
        <div>
          <h2>${escapeHtml(article.title)}</h2>
          <div class="meta" style="color:var(--text-dim);font-size:13px;">
            ${escapeHtml(article.source)}
            <span style="color:${sentimentColor};margin-left:8px;">${article.sentiment}</span>
            ${article.published ? ` | ${new Date(article.published).toLocaleDateString()}` : ''}
          </div>
        </div>
      </div>

      <div style="margin-bottom:12px;">
        <strong>Why it matters:</strong>
        <p style="color:var(--text-dim);margin-top:4px;">${escapeHtml(article.impact_reasoning || '')}</p>
      </div>

      <div style="margin-bottom:12px;">
        <strong>Affected Markets:</strong>
        <div class="affected" style="margin-top:4px;">
          ${(article.affected_markets || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}
          ${(article.affected_forex || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('')}
        </div>
      </div>

      <div class="article-body">${escapeHtml(article.full_text || 'Full article text not available.')}</div>

      ${article.url ? `<a href="${escapeHtml(article.url)}" target="_blank" class="source-link">Read Original Source</a>` : ''}
    `;

    if (related.length > 0) {
      html += `<div class="related-section">
        <h3>Related News</h3>
        <ul class="news-list">`;
      related.forEach(r => {
        const rClass = r.impact_score >= 71 ? 'high' : r.impact_score >= 31 ? 'moderate' : 'low';
        html += `
          <li class="news-item" onclick="openNewsDetail('${r.id}')">
            <div class="impact-badge ${rClass}" style="width:36px;height:36px;font-size:12px;">${r.impact_score}</div>
            <div class="news-content">
              <div class="title" style="font-size:13px;">${escapeHtml(r.title)}</div>
              <div class="meta">${escapeHtml(r.source)}</div>
            </div>
          </li>`;
      });
      html += '</ul></div>';
    }

    content.innerHTML = html;
  } catch (e) {
    content.innerHTML = `<div class="empty-state">Failed to load article. ${e.message}</div>`;
  }
}

function closeModal() {
  document.getElementById('news-modal').classList.remove('open');
}
document.getElementById('news-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeModal();
});

/* ── Prediction Change Alerts ─────────────────────────────────────── */
async function checkPredictionChanges() {
  try {
    const data = await api('/predictions/changes');
    const alertsDiv = document.getElementById('change-alerts');
    if (data.changes && data.changes.length > 0) {
      alertsDiv.innerHTML = data.changes.map(c => {
        const changeDetails = c.changes.map(ch =>
          `${ch.horizon}: ${ch.field} changed from ${ch.old} to ${ch.new}`
        ).join(', ');
        return `<div class="change-alert">
          <span class="icon">!</span>
          <span><strong>${c.asset_id.toUpperCase()}</strong> prediction updated: ${changeDetails}</span>
        </div>`;
      }).join('');
    }
  } catch (e) { /* Non-critical */ }
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
loadIndices();
setInterval(checkPredictionChanges, 60000);
