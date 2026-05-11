const state = {
  active: false,
  keyword: '',
  maxPages: 1,
  currentPage: 1,
  gigs: [],      // [{url, title, seller_name, ...}] from search pages
  results: [],   // fully scraped gig objects
  idx: 0,        // next gig index to process
  currentTabId: null,
  popupPort: null,
};

// ── Popup connection (bi-directional) ─────────────────────────────────────────
chrome.runtime.onConnect.addListener(port => {
  if (port.name !== 'popup') return;
  state.popupPort = port;

  // Restore UI state when popup reopens during active scrape
  if (state.active) {
    notify({ type: 'SCRAPING' });
    if (state.gigs.length > 0) {
      notify({ type: 'FOUND', total: state.gigs.length });
      notify({ type: 'PROGRESS', done: state.results.length, total: state.gigs.length });
    } else {
      notify({ type: 'SEARCHING', page: state.currentPage, maxPages: state.maxPages });
    }
  }

  port.onMessage.addListener(msg => {
    if (msg.type === 'START_SCRAPE') startScrape(msg.keyword, msg.pages);
    if (msg.type === 'STOP_SCRAPE')  stopScrape();
  });

  port.onDisconnect.addListener(() => { state.popupPort = null; });
});

function notify(msg) {
  try { state.popupPort?.postMessage(msg); } catch (_) {}
}

// ── Messages from injected content scripts ────────────────────────────────────
chrome.runtime.onMessage.addListener((msg, sender) => {
  const tabId = sender?.tab?.id;

  switch (msg.type) {
    case 'SEARCH_RESULTS':
      state.gigs.push(...msg.gigs);
      closeTab(tabId);
      if (msg.gigs.length > 0 && state.currentPage < state.maxPages) {
        state.currentPage++;
        openSearchPage();
      } else {
        notify({ type: 'FOUND', total: state.gigs.length });
        openNextGig();
      }
      break;

    case 'SEARCH_ERROR':
      closeTab(tabId);
      notify({ type: 'ERROR', error: msg.error });
      state.active = false;
      break;

    case 'GIG_DATA':
      state.results.push(msg.data);
      state.idx++;
      closeTab(tabId);
      notify({ type: 'PROGRESS', done: state.results.length, total: state.gigs.length });
      openNextGig();
      break;

    case 'GIG_SKIP':
      state.idx++;
      closeTab(tabId);
      openNextGig();
      break;
  }
});

// ── Inject scripts when tab finishes loading ──────────────────────────────────
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== 'complete') return;
  if (!state.active || tabId !== state.currentTabId) return;

  const url = tab.url || '';
  if (url.includes('fiverr.com/search/gigs')) {
    inject(tabId, 'content_search.js');
  } else if (isGigUrl(url)) {
    inject(tabId, 'content_gig.js');
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function isGigUrl(url) {
  try {
    const u = new URL(url);
    if (!u.hostname.endsWith('fiverr.com')) return false;
    const parts = u.pathname.split('/').filter(Boolean);
    if (parts.length !== 2) return false;
    const skip = ['search', 'categories', 'pages', 'pro', 'users', 'business', 'gigs', 'support'];
    return !skip.includes(parts[0]);
  } catch { return false; }
}

function inject(tabId, file) {
  chrome.scripting.executeScript({ target: { tabId }, files: [file] })
    .catch(err => console.error('[bg] inject failed:', file, err.message));
}

function closeTab(tabId) {
  if (tabId) chrome.tabs.remove(tabId).catch(() => {});
}

// ── Core flow ─────────────────────────────────────────────────────────────────
function startScrape(keyword, maxPages = 1) {
  if (state.active) return; // one scrape at a time
  Object.assign(state, {
    active: true, keyword,
    maxPages: Math.max(1, maxPages),
    currentPage: 1,
    gigs: [], results: [], idx: 0, currentTabId: null,
  });

  notify({ type: 'STARTED' });
  openSearchPage();
}

function openSearchPage() {
  notify({ type: 'SEARCHING', page: state.currentPage, maxPages: state.maxPages });
  const url = `https://www.fiverr.com/search/gigs?query=${encodeURIComponent(state.keyword)}&page=${state.currentPage}`;
  chrome.tabs.create({ url, active: false }, tab => {
    state.currentTabId = tab.id;
  });
}

function stopScrape() {
  state.active = false;
  if (state.currentTabId) closeTab(state.currentTabId);
  state.currentTabId = null;
  // Download whatever was scraped before stopping
  if (state.results.length > 0) downloadResults();
  else notify({ type: 'STOPPED' });
}

function openNextGig() {
  if (!state.active) return;
  if (state.idx >= state.gigs.length) { downloadResults(); return; }

  const gig = state.gigs[state.idx];
  chrome.tabs.create({ url: gig.url, active: false }, tab => {
    state.currentTabId = tab.id;
  });
}

// ── Output generation ─────────────────────────────────────────────────────────
function downloadResults() {
  state.active = false;

  if (!state.results.length) {
    notify({ type: 'ERROR', error: 'No gig data collected.' });
    return;
  }

  const lines = [
    'FIVERR GIG ANALYSIS',
    `Query   : "${state.keyword}"`,
    `Date    : ${new Date().toLocaleString()}`,
    `Gigs    : ${state.results.length}`,
    '='.repeat(70),
    '',
  ];

  state.results.forEach((gig, i) => {
    lines.push(`[${i + 1}] ${gig.title}`);
    lines.push(`Seller  : ${gig.seller.username}  |  ${gig.seller.country}${gig.seller.is_pro ? '  |  PRO' : ''}`);
    if (gig.seller.one_liner) lines.push(`Bio     : ${gig.seller.one_liner}`);
    lines.push(`Rating  : ${gig.rating} stars (${gig.ratings_count} reviews)  |  Queue: ${gig.orders_in_queue} orders`);
    lines.push(`Member  : ${gig.seller.member_since}  |  Response: ${gig.seller.response_time}h`);

    if (gig.packages?.length) {
      lines.push('Packages:');
      gig.packages.forEach(p => {
        lines.push(`  ${p.name.padEnd(9)}: $${p.price} / ${p.delivery_days} days  —  ${p.title}`);
        if (p.description) lines.push(`             ${p.description.substring(0, 120)}`);
      });
    }

    if (gig.description) lines.push(`Desc    : ${gig.description}`);
    if (gig.tags?.length) lines.push(`Tags    : ${gig.tags.join(', ')}`);

    if (gig.faqs?.length) {
      lines.push('FAQs:');
      gig.faqs.forEach(f => {
        lines.push(`  Q: ${f.q}`);
        lines.push(`  A: ${(f.a || '').substring(0, 200)}`);
      });
    }

    lines.push(`URL     : ${gig.url}`);
    lines.push('-'.repeat(70));
    lines.push('');
  });

  const content = lines.join('\n');
  const dataUrl = 'data:text/plain;charset=utf-8,' + encodeURIComponent(content);
  const filename = `fiverr_${state.keyword.replace(/\W+/g, '_')}_${Date.now()}.txt`;

  chrome.downloads.download({ url: dataUrl, filename })
    .then(() => notify({ type: 'DONE', total: state.results.length, filename }))
    .catch(err => notify({ type: 'ERROR', error: 'Download failed: ' + err.message }));
}
