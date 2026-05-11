const $ = id => document.getElementById(id);

let port = null;

function connect() {
  port = chrome.runtime.connect({ name: 'popup' });
  port.onMessage.addListener(onMessage);
  port.onDisconnect.addListener(() => { port = null; });
}

function send(msg) {
  if (!port) connect();
  port.postMessage(msg);
}

function setUI(scraping) {
  $('startBtn').disabled = scraping;
  $('stopBtn').disabled  = !scraping;
  $('keyword').disabled  = scraping;
  $('pages').disabled    = scraping;
}

function onMessage(msg) {
  switch (msg.type) {
    case 'SCRAPING':
      setUI(true);
      break;

    case 'STARTED':
      $('status').textContent = 'Starting...';
      $('log').textContent = '';
      $('progressWrap').style.display = 'none';
      setUI(true);
      break;

    case 'SEARCHING':
      $('status').textContent = `Collecting gig URLs from page ${msg.page} / ${msg.maxPages}...`;
      break;

    case 'FOUND':
      $('status').textContent = `Found ${msg.total} gigs. Scraping detail pages...`;
      $('progressWrap').style.display = 'block';
      $('bar').style.width = '0%';
      break;

    case 'PROGRESS': {
      const pct = msg.total ? Math.round((msg.done / msg.total) * 100) : 0;
      $('status').textContent = `Scraped ${msg.done} / ${msg.total} gigs...`;
      $('bar').style.width = pct + '%';
      break;
    }

    case 'DONE':
      $('status').textContent = `Done! ${msg.total} gigs scraped.`;
      $('bar').style.width = '100%';
      $('log').textContent = `Saved: ${msg.filename}`;
      setUI(false);
      break;

    case 'STOPPED':
      $('status').textContent = 'Stopped.';
      setUI(false);
      break;

    case 'ERROR':
      $('status').textContent = `Error: ${msg.error}`;
      setUI(false);
      break;
  }
}

$('startBtn').addEventListener('click', () => {
  const keyword = $('keyword').value.trim();
  if (!keyword) { $('status').textContent = 'Enter a keyword first.'; return; }
  const pages = Math.max(1, parseInt($('pages').value, 10) || 1);
  send({ type: 'START_SCRAPE', keyword, pages });
});

$('stopBtn').addEventListener('click', () => {
  send({ type: 'STOP_SCRAPE' });
  $('status').textContent = 'Stopping...';
});

connect();
