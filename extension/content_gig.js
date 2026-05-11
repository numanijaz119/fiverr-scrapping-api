(() => {
  const el = document.getElementById('perseus-initial-props');
  if (!el) { chrome.runtime.sendMessage({ type: 'GIG_SKIP' }); return; }

  let data;
  try { data = JSON.parse(el.textContent); }
  catch (e) { chrome.runtime.sendMessage({ type: 'GIG_SKIP' }); return; }

  // Confirm this is a gig page (not a profile or category page)
  if (!data?.overview?.gig?.title) {
    chrome.runtime.sendMessage({ type: 'GIG_SKIP' });
    return;
  }

  const gig        = data.overview?.gig        || {};
  const seller     = data.overview?.seller     || {};
  const sellerCard = data.sellerCard           || {};
  const pkgList    = data.packages?.packageList || [];
  const rawDesc    = data.description?.content || '';
  const faqs       = data.faqs?.list           || [];
  const tags       = data.tags?.tagsGigList    || [];

  const stripHtml = s => s.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim().substring(0, 800);

  chrome.runtime.sendMessage({
    type: 'GIG_DATA',
    data: {
      url: location.href,
      title: gig.title || '',
      rating: gig.rating || 0,
      ratings_count: gig.ratingsCount || 0,
      orders_in_queue: gig.ordersInQueue || 0,
      seller: {
        username:      seller.username      || '',
        country:       seller.countryCode   || '',
        is_pro:        seller.isPro         || false,
        one_liner:     sellerCard.oneLiner  || '',
        member_since:  sellerCard.memberSince || '',
        response_time: sellerCard.responseTime || 0,
      },
      packages: pkgList.map((p, i) => ({
        name:          ['Basic', 'Standard', 'Premium'][i] || `Package ${i + 1}`,
        title:         p.title       || '',
        price:         (p.price      || 0) / 100,
        delivery_days: Math.round((p.duration || 0) / 24),
        description:   p.description || '',
      })),
      description: stripHtml(rawDesc),
      tags: tags.map(t => t.name || t.slug).filter(Boolean),
      faqs: faqs.slice(0, 5).map(f => ({ q: f.question || '', a: f.answer || '' })),
    },
  });
})();
