// Comportement des rapports et des dossiers du jour (tools/render.py) : filtres, blocs dépliants, retour en haut.
// Sans JavaScript, la page reste lisible : les sujets sont des <details> natifs et la barre de filtres reste masquée.
(() => {
  const items = [...document.querySelectorAll('.sum > details.card')];
  const bar = document.getElementById('filtres');
  const sum = document.querySelector('.sum');

  // ---------- Filtres : OU dans un groupe, ET entre les groupes ----------
  if (bar && items.length) {
    bar.hidden = false;
    const groups = [...bar.querySelectorAll('.fgroup')];
    const count = bar.querySelector('.count'), reset = bar.querySelector('.reset'), expand = bar.querySelector('.expand');
    const empty = document.createElement('p'); empty.className = 'empty'; empty.textContent = 'Aucun sujet ne correspond à ces filtres.'; empty.hidden = true;
    sum.after(empty);
    const values = (el, g) => g === 'cat' ? [el.dataset.cat]
      : g === 'statut' ? [el.dataset.statut]
      : (el.dataset.tags || '').split(' ').filter(Boolean).concat('frais' in el.dataset ? ['frais'] : []);
    const visible = () => items.filter(el => !el.hidden);
    function apply() {
      const sel = groups.map(g => [g.dataset.g, [...g.querySelectorAll('.chip[aria-pressed="true"]')].map(b => b.dataset.v)]);
      let n = 0;
      items.forEach(el => {
        const ok = sel.every(([g, vs]) => !vs.length || values(el, g).some(v => vs.includes(v)));
        el.hidden = !ok; n += ok;
      });
      const active = sel.some(([, vs]) => vs.length);
      count.textContent = active ? `${n} sujet${n > 1 ? 's' : ''} sur ${items.length}` : `${items.length} sujet${items.length > 1 ? 's' : ''}`;
      reset.hidden = !active; empty.hidden = n > 0;
      syncExpand();
    }
    function syncExpand() { expand.textContent = visible().length && visible().every(el => el.open) ? 'Tout replier' : 'Tout déplier'; }
    bar.addEventListener('click', e => {
      const chip = e.target.closest('.chip');
      if (chip) { chip.setAttribute('aria-pressed', chip.getAttribute('aria-pressed') !== 'true'); apply(); }
    });
    reset.addEventListener('click', () => { bar.querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', 'false')); apply(); });
    expand.addEventListener('click', () => { const open = expand.textContent === 'Tout déplier'; visible().forEach(el => { el.open = open; }); syncExpand(); });
    items.forEach(el => el.addEventListener('toggle', syncExpand));
    apply();
  }

  // ---------- Chevron « Replier ce sujet » : replie et ramène à l'en-tête ----------
  document.addEventListener('click', e => {
    const fold = e.target.closest('a.fold');
    if (!fold) return;
    e.preventDefault();
    const card = fold.closest('details');
    card.open = false;
    card.scrollIntoView({block: 'nearest', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
  });

  // ---------- Lien direct #id : ouvre le sujet visé ----------
  function openHash() {
    const id = decodeURIComponent(location.hash.slice(1));
    const el = id && document.getElementById(id);
    if (el && el.tagName === 'DETAILS') { el.hidden = false; el.open = true; el.scrollIntoView({block: 'start'}); }
  }
  addEventListener('hashchange', openHash);
  openHash();

  // ---------- Bouton flottant « Revenir en haut » ----------
  const top = document.querySelector('.totop');
  if (top) {
    const onScroll = () => top.classList.toggle('on', scrollY > 400);
    addEventListener('scroll', onScroll, {passive: true}); onScroll();
    top.addEventListener('click', e => { e.preventDefault(); scrollTo({top: 0, behavior: 'smooth'}); });
  }

  // ---------- Dossier : « Demander la publication » prépare la demande à coller dans Claude ----------
  document.querySelectorAll('button.ask').forEach(b => b.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(b.dataset.ask); b.textContent = 'Demande copiée : colle-la dans Claude'; }
    catch (e) { prompt('Copie cette demande et colle-la dans Claude :', b.dataset.ask); }
  }));
})();
