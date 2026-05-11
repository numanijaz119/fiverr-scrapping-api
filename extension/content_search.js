(() => {
  const el = document.getElementById('perseus-initial-props');
  if (!el) {
    chrome.runtime.sendMessage({ type: 'SEARCH_ERROR', error: 'No perseus-initial-props on search page. Cloudflare may be blocking.' });
    return;
  }

  let data;
  try { data = JSON.parse(el.textContent); }
  catch (e) {
    chrome.runtime.sendMessage({ type: 'SEARCH_ERROR', error: 'JSON parse failed on search props.' });
    return;
  }

  const rawGigs = data?.listings?.[0]?.gigs;
  if (!rawGigs?.length) {
    chrome.runtime.sendMessage({ type: 'SEARCH_ERROR', error: 'listings[0].gigs is empty or missing.' });
    return;
  }

  const gigs = rawGigs
    .map(g => ({
      url: 'https://www.fiverr.com' + (g.gig_url || ''),
      title: g.title || '',
      seller_name: g.seller_name || '',
      gig_id: g.gig_id || '',
      price: g.price_i || 0,
      seller_level: g.seller_level || '',
      seller_rating: g.seller_rating?.score || 0,
    }))
    .filter(g => g.url.length > 'https://www.fiverr.com'.length);

  chrome.runtime.sendMessage({ type: 'SEARCH_RESULTS', gigs });
})();
