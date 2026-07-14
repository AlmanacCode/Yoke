// Harbor wiki — shared behavior: reading progress + in-page scrollspy.
// No dependencies. Each page includes this once before </body>.

(function () {
  const bar = document.getElementById('progress');
  if (bar) {
    const onScroll = () => {
      const h = document.documentElement;
      const max = h.scrollHeight - h.clientHeight;
      bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
    };
    document.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  const links = [...document.querySelectorAll('nav.toc a')];
  if (links.length) {
    const byId = new Map(
      links
        .filter(a => a.getAttribute('href').startsWith('#'))
        .map(a => [a.getAttribute('href').slice(1), a])
    );
    const sections = [...document.querySelectorAll('main section[id]')];
    const spy = new IntersectionObserver(
      entries => {
        entries.forEach(e => {
          if (e.isIntersecting) {
            links.forEach(a => a.classList.remove('active'));
            byId.get(e.target.id)?.classList.add('active');
          }
        });
      },
      { rootMargin: '-45% 0px -50% 0px', threshold: 0 }
    );
    sections.forEach(s => spy.observe(s));
  }
})();
