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
    const values = (el, g) => g === 'cat' ? el.dataset.cat.split(' ')
      : g === 'statut' ? [el.dataset.statut]
      : g === 'projet' ? [el.dataset.repo || '']
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
      if (chip && !chip.closest('.fsort')) { chip.setAttribute('aria-pressed', chip.getAttribute('aria-pressed') !== 'true'); apply(); }
    });
    reset.addEventListener('click', () => { bar.querySelectorAll('.fgroup .chip').forEach(c => c.setAttribute('aria-pressed', 'false')); apply(); });
    expand.addEventListener('click', () => { const open = expand.textContent === 'Tout déplier'; visible().forEach(el => { el.open = open; }); syncExpand(); });
    items.forEach(el => el.addEventListener('toggle', syncExpand));
    apply();

    // ---------- Tri : les clés choisies, dans l'ordre des clics (rang 1, 2…), puis les autres dans l'ordre par défaut ----------
    const sortBar = bar.querySelector('.fsort');
    if (sortBar) {
      const chips = [...sortBar.querySelectorAll('.chip')], all = chips.map(c => c.dataset.k), LABEL = {};
      chips.forEach(c => { LABEL[c.dataset.k] = c.textContent.trim(); });
      const def = sortBar.querySelector('.sdefault');
      const STATUTS = ['publie', 'candidat', 'mis-de-cote', 'ecarte'];
      const val = {statut: el => STATUTS.indexOf(el.dataset.statut), cat: el => +el.dataset.ordre,
                   date: el => -(+(el.dataset.date || '').replace(/-/g, '') || 0)};
      const store = 'techradar-tri2-' + (document.querySelector('.dossier') ? 'dossier' : 'rapport');
      let chosen = [];
      function sortNow(save) {
        const keys = [...chosen, ...all.filter(k => !chosen.includes(k))];
        items.sort((a, b) => { for (const k of keys) { const x = val[k](a), y = val[k](b); if (x < y) return -1; if (x > y) return 1; } return 0; });
        items.forEach(el => sum.appendChild(el));
        chips.forEach(c => { const r = chosen.indexOf(c.dataset.k); c.setAttribute('aria-pressed', r >= 0); c.querySelector('.rank').textContent = r >= 0 ? r + 1 : ''; });
        def.hidden = !chosen.length;
        sortBar.querySelector('.sorder').textContent = keys.map(k => LABEL[k]).join(' › ');
        if (save) { try { localStorage.setItem(store, JSON.stringify(chosen)); } catch (e) { /* stockage indisponible : tri non retenu */ } }
      }
      sortBar.addEventListener('click', e => {
        const c = e.target.closest('.chip');
        if (c) { const k = c.dataset.k; chosen = chosen.includes(k) ? chosen.filter(x => x !== k) : [...chosen, k]; sortNow(true); }
      });
      def.addEventListener('click', () => { chosen = []; sortNow(true); });
      try { const s = JSON.parse(localStorage.getItem(store) || '[]'); if (Array.isArray(s)) chosen = s.filter(k => all.includes(k)); } catch (e) { /* stockage indisponible */ }
      if (chosen.length) sortNow(false);
    }
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
