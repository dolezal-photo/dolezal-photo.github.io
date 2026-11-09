(() => {
  if (location.origin !== 'https://dolezal-photo.github.io') return;

  const path = location.pathname.replace(/\/index\.html$/, '/');
  window.goatcounter = { path };

  const tracker = document.createElement('script');
  tracker.async = true;
  tracker.dataset.goatcounter = 'https://fotograf.goatcounter.com/count';
  tracker.src = 'https://gc.zgo.at/count.js';
  document.head.append(tracker);

  document.addEventListener('click', (event) => {
    const contact = event.target.closest?.('a[href^="mailto:"], a[href^="tel:"]');
    if (!contact || !window.goatcounter.count) return;

    const channel = contact.protocol === 'mailto:' ? 'email' : 'telefon';
    window.goatcounter.count({
      event: true,
      path: `kontakt-${channel}:${path}`,
      title: `Kliknutí na ${channel} · ${document.title}`,
    });
  });
})();
