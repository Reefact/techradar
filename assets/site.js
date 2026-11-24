// ---------- Radar d'arrière-plan ----------
// Cadran peint UNE fois (canvas hors écran) ; le balayage tourne en CSS/WAAPI (compositeur) ;
// seul un petit canvas redessine les blips, les échos et la poussière de phosphore.
const Radar = (() => {
  const root = document.getElementById('radar'), dial = document.getElementById('dial'),
        sweep = document.getElementById('sweep'), cv = document.getElementById('blips'), ctx = cv.getContext('2d');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const COLORS = {alert:'#fb7185',dotnet:'#a78bfa',ia:'#60a5fa',ddd:'#f0abfc',api:'#fbbf24',tool:'#34d399',retail:'#fb923c',conf:'#38bdf8',radar:'#f472b6',def:'#5eead4'};
  const PERIOD = 16000, TAU = Math.PI * 2; // un tour de balayage = 16 s
  let D = 0, dpr = 1, blips = [], dust = [], pings = [], nextPing = 0, raf = 0, anim = null;

  const hash = str => { let h = 2166136261; for (const c of str) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return (h >>> 0) / 4294967295; };

  // --- cadran : anneaux, graduations, relèvements, échelle de distance ---
  function paintDial() {
    const S = Math.min(2048, Math.max(1024, Math.ceil(D * dpr / 256) * 256)), R = S / 2, k = S / 1600;
    const c = dial, g = c.getContext('2d');
    c.width = c.height = S; g.clearRect(0, 0, S, S); g.translate(R, R);
    g.lineWidth = Math.max(1, k * 1.2);
    for (let i = 1; i <= 6; i++) {
      g.strokeStyle = `rgba(94,234,212,${i === 6 ? .34 : .16})`;
      g.beginPath(); g.arc(0, 0, R * .96 * i / 6, 0, TAU); g.stroke();
    }
    g.strokeStyle = 'rgba(94,234,212,.12)';
    g.beginPath(); g.moveTo(-R * .96, 0); g.lineTo(R * .96, 0); g.moveTo(0, -R * .96); g.lineTo(0, R * .96); g.stroke();
    for (let d = 0; d < 360; d += 2) {                               // graduations tous les 2°, plus longues tous les 10°
      const t = d * Math.PI / 180, long = d % 10 === 0, r0 = R * .96, r1 = r0 - R * (long ? .03 : .014);
      g.strokeStyle = `rgba(94,234,212,${long ? .5 : .24})`;
      g.beginPath(); g.moveTo(Math.sin(t) * r0, -Math.cos(t) * r0); g.lineTo(Math.sin(t) * r1, -Math.cos(t) * r1); g.stroke();
    }
    g.fillStyle = 'rgba(94,234,212,.6)'; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.font = `${Math.round(34 * k)}px VT323, "IBM Plex Mono", monospace`;
    for (let d = 0; d < 360; d += 30) {                              // relèvements 000, 030, ...
      const t = d * Math.PI / 180, r = R * .89;
      g.fillText(String(d).padStart(3, '0'), Math.sin(t) * r, -Math.cos(t) * r);
    }
    g.fillStyle = 'rgba(94,234,212,.38)'; g.textAlign = 'left';
    g.font = `${Math.round(26 * k)}px VT323, "IBM Plex Mono", monospace`;
    for (let i = 1; i <= 5; i++) g.fillText(String(i * 10) + ' NM', R * .96 * i / 6 + 6 * k, -6 * k);   // échelle de distance
  }

  function layout() {
    const r = root.getBoundingClientRect();
    dpr = Math.min(devicePixelRatio || 1, 2);
    D = Math.max(r.width, r.height) * 1.25;
    for (const el of [dial, sweep, cv]) { el.style.width = el.style.height = D + 'px'; }
    cv.width = cv.height = Math.round(D * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    dust = Array.from({length: Math.round(D * D / 9000)}, () => {
      const a = Math.random() * TAU, r2 = Math.sqrt(Math.random()) * D * .48;
      return {x: D / 2 + Math.cos(a) * r2, y: D / 2 + Math.sin(a) * r2, r: .5 + Math.random() * 1.1, p: Math.random() * TAU, s: .4 + Math.random() * 1.4};
    });
    paintDial();
    if (reduce) draw(0, 0);
  }

  // blips = éléments du rapport affiché ; alertes près du centre
  function setItems(items) {
    blips = items.map(({title, cat}) => {
      const a = hash(title) * TAU, rr = (cat === 'alert' ? .12 : .28) + hash(title + '#') * (cat === 'alert' ? .28 : .62);
      return {a, r: rr, color: COLORS[cat] || COLORS.def, glow: 0};
    });
    if (reduce) draw(0, 0);
  }

  const beamAngle = () => anim ? ((anim.currentTime % PERIOD) / PERIOD) * TAU : 0;   // 0 = haut, sens horaire

  function draw(now, dt) {
    const R = D / 2;
    ctx.clearRect(0, 0, D, D);
    for (const d of dust) {                                          // poussière de phosphore qui scintille
      const tw = reduce ? .6 : .5 + .5 * Math.sin(now / 1000 * d.s + d.p);
      ctx.fillStyle = `rgba(94,234,212,${.05 + .22 * tw})`;
      ctx.beginPath(); ctx.arc(d.x, d.y, d.r, 0, TAU); ctx.fill();
    }
    const beam = beamAngle();
    for (const b of blips) {
      if (!reduce) {
        const prev = ((beam - (dt * TAU) / PERIOD) + TAU) % TAU;
        if (((beam - b.a) + TAU) % TAU < ((prev - b.a) + TAU) % TAU) b.glow = 1;  // le faisceau vient de passer
        b.glow = Math.max(0, b.glow - dt / 2800);
      }
      const x = R + Math.sin(b.a) * b.r * R, y = R - Math.cos(b.a) * b.r * R, g = reduce ? .5 : b.glow;
      ctx.globalAlpha = .35 + .65 * g; ctx.fillStyle = b.color;
      ctx.fillRect(x - 3 - 2 * g, y - 3 - 2 * g, 6 + 4 * g, 6 + 4 * g);   // blips carrés, esprit écran rétro
      if (g > .05) { ctx.globalAlpha = g * .5; ctx.strokeStyle = b.color; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(x, y, 8 + 22 * (1 - g), 0, TAU); ctx.stroke(); }
    }
    ctx.globalAlpha = 1;
    if (!reduce) {                                                   // échos : anneaux qui s'étendent à intervalles irréguliers
      if (now > nextPing) { const a = Math.random() * TAU, r = .15 + Math.random() * .7; pings.push({x: R + Math.sin(a) * r * R, y: R - Math.cos(a) * r * R, t: 0}); nextPing = now + 2500 + Math.random() * 5000; }
      pings = pings.filter(p => p.t < 1);
      for (const p of pings) { p.t += dt / 2600; ctx.strokeStyle = `rgba(94,234,212,${.5 * (1 - p.t)})`; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.arc(p.x, p.y, 4 + p.t * 46, 0, TAU); ctx.stroke(); }
    }
  }

  let last = 0;
  function frame(t) { const dt = Math.min(t - last, 100); last = t; draw(t, dt); raf = requestAnimationFrame(frame); }
  const start = () => { if (reduce || raf) return; last = performance.now(); raf = requestAnimationFrame(frame); anim && anim.play(); };
  const stop = () => { cancelAnimationFrame(raf); raf = 0; anim && anim.pause(); };

  if (!reduce) anim = sweep.animate([{transform: 'rotate(0deg)'}, {transform: 'rotate(360deg)'}], {duration: PERIOD, iterations: Infinity});
  new ResizeObserver(layout).observe(root); layout();
  document.fonts && document.fonts.ready.then(paintDial);           // repeint quand VT323 est chargée
  document.addEventListener('visibilitychange', () => document.hidden ? stop() : start());
  start();
  return {setItems, scroll: y => { root.style.setProperty('--py', `${-y * .06}px`); }};
})();

// ---------- Index ----------
(async () => {
  const list = document.getElementById('list'), view = document.getElementById('view');
  const DOSSIER = document.documentElement.dataset.kind === 'dossier';   // page /dossier/ : dossiers du jour au lieu des rapports publiés
  const ATOM = 'http://www.w3.org/2005/Atom';
  let reports = [];
  try {
    if (DOSSIER) {
      // Dossiers du jour : dossier.json, généré au build par tools/render.py (un jour par fichier de data/days/).
      const res = await fetch('dossier.json', {cache: 'no-cache'});
      if (!res.ok) throw new Error(res.status);
      reports = (await res.json()).map(d => ({key: d.date, date: d.date, href: d.href, statuts: d.statuts}))
        .sort((a, b) => b.key.localeCompare(a.key));
    } else {
      // Découverte : feed.xml (généré au build par tools/render.py depuis data/days/).
      const res = await fetch('feed.xml', {cache: 'no-cache'});
      if (!res.ok) throw new Error(res.status);
      const xml = new DOMParser().parseFromString(await res.text(), 'application/xml');
      reports = [...xml.getElementsByTagNameNS(ATOM, 'entry')].map(e => {
        const date = e.getElementsByTagNameNS(ATOM, 'updated')[0].textContent.slice(0, 10);
        return {key: date, date, href: e.getElementsByTagNameNS(ATOM, 'link')[0].getAttribute('href')};
      }).sort((a, b) => b.key.localeCompare(a.key));
    }
  } catch (err) {
    list.innerHTML = `<p class="msg">Impossible de charger la liste des ${DOSSIER ? 'dossiers' : 'rapports'} (servir le site en HTTP, pas via file://).</p>`;
    return;
  }
  if (!reports.length) { list.innerHTML = `<p class="msg">Aucun ${DOSSIER ? 'dossier' : 'rapport'} pour le moment.</p>`; return; }

  const fmtDay = d => new Date(d + 'T12:00:00').toLocaleDateString('fr-FR', {weekday: 'short', day: 'numeric'});
  const fmtMonth = d => new Date(d + 'T12:00:00').toLocaleDateString('fr-FR', {month: 'long', year: 'numeric'});
  let html = '', month = '';
  for (const r of reports) {
    const m = r.date.slice(0, 7);
    if (m !== month) { if (month) html += '</ul>'; html += `<div class="month">${fmtMonth(r.date)}</div><ul>`; month = m; }
    const st = r.statuts ? ` title="${r.statuts.publie || 0} publiés · ${r.statuts.candidat || 0} candidats · ${r.statuts['mis-de-cote'] || 0} mis de côté · ${r.statuts.ecarte || 0} écartés"` : '';
    const cnt = r.statuts ? ` <span class="cnt">${(r.statuts.candidat || 0) + (r.statuts['mis-de-cote'] || 0)} à revoir</span>` : '';
    html += `<li><a href="#${r.key}" data-key="${r.key}"${st}>${fmtDay(r.date)}${cnt}</a></li>`;
  }
  list.innerHTML = html + '</ul>';

  function show() {
    const wanted = location.hash.slice(1);
    const r = reports.find(x => x.key === wanted) || reports[0]; // par défaut : le plus récent
    list.querySelectorAll('a').forEach(a => { if (a.dataset.key === r.key) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
    const target = new URL(r.href, location.href).href;
    if (view.src !== target) view.src = target;
  }
  // ---------- Boutons « travailler ce sujet avec Claude » ----------
  const toast = document.getElementById('toast'); let toastTimer = 0;
  const say = msg => { toast.textContent = msg; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 4500); };
  const copy = async text => {
    try { await navigator.clipboard.writeText(text); return true; } catch (e) {}
    try { const t = document.createElement('textarea'); t.value = text; t.style.cssText = 'position:fixed;opacity:0'; document.body.appendChild(t); t.select(); const ok = document.execCommand('copy'); t.remove(); return ok; } catch (e) { return false; }
  };
  const clip = (s, n) => s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s;
  function topicPrompt(card, date, repos) {
    const title = card.querySelector('h3').textContent.trim();
    const paras = [...card.querySelectorAll(':scope > p:not(.why)')].map(p => p.textContent.replace(/\s+/g, ' ').trim()).filter(Boolean);
    const why = (card.querySelector(':scope > p.why') || {}).textContent;
    const src = [...card.querySelectorAll(':scope > a[href^="http"]')].map(a => `${a.textContent.trim()} : ${a.href}`);
    let t = `Je souhaite travailler autour de ce sujet issu de ma veille TechRadar du ${date} : « ${title} ».\n\n`;
    if (repos.length) t += `Il concerne ${repos.length > 1 ? 'mes projets' : 'mon projet'} ${repos.join(', ')} (le dépôt est présélectionné).\n\n`;
    t += `Résumé du brief :\n${clip(paras.join('\n'), 1800)}\n`;
    if (why) t += `\n${why.replace(/\s+/g, ' ').trim()}\n`;
    if (src.length) t += `\nSources :\n${src.join('\n')}\n`;
    t += repos.length ? `\nCommence par explorer le dépôt pour voir comment ce sujet le concerne et dis-moi ce que tu constates, puis demande-moi ce que je veux en faire. Ne modifie rien tant qu'on n'a pas décidé ensemble de la suite.`
                      : `\nCommence par me poser quelques questions pour cerner ce que je veux en faire.`;
    return t;
  }
  function addActions(doc, date) {
    const st = doc.createElement('style');
    st.textContent = '.tr-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}'
      + '.tr-btn{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:999px;border:1px solid currentColor;text-decoration:none;font:600 .74rem/1 var(--font-m);letter-spacing:.06em;text-transform:uppercase;cursor:pointer;transition:box-shadow .2s,background .2s}'
      + '.tr-btn.chat{color:var(--accent)}.tr-btn.code{color:var(--dotnet)}'
      + '.tr-btn:hover{background:rgba(255,255,255,.06);box-shadow:0 0 14px currentColor}'
      + '.tr-btn svg{width:14px;height:14px;flex:none}';
    doc.head.appendChild(st);
    const ICON = {chat: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M2 3h12v8H7l-3 3v-3H2z"/></svg>',
                  code: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4 2 8l4 4M10 4l4 4-4 4"/></svg>'};
    doc.querySelectorAll('article.card[id]').forEach(card => {
      if (!card.querySelector('h3')) return;
      const repos = (card.dataset.repo || '').split(',').map(x => x.trim()).filter(x => /^[\w.-]+\/[\w.-]+$/.test(x));
      const prompt = topicPrompt(card, date, repos);
      const a = doc.createElement('a');
      a.className = 'tr-btn ' + (repos.length ? 'code' : 'chat');
      a.target = '_blank'; a.rel = 'noopener';
      a.innerHTML = ICON[repos.length ? 'code' : 'chat'] + `<span>${repos.length ? 'Claude Code' : 'Claude'}</span>`;
      a.title = repos.length ? `Ouvre une session Claude Code sur ${repos.join(', ')} avec ce sujet` : 'Ouvre une conversation Claude avec ce sujet';
      if (repos.length) {
        a.href = 'https://claude.ai/code?repositories=' + encodeURIComponent(repos.join(',')) + '&prompt=' + encodeURIComponent(prompt);
        a.addEventListener('click', () => say('Session Claude Code ouverte : relis le prompt pré-rempli, puis envoie-le.'));
      } else {
        a.href = 'https://claude.ai/new?q=' + encodeURIComponent(prompt);   // pré-remplissage non documenté : on copie aussi le prompt
        a.addEventListener('click', async () => { say((await copy(prompt)) ? 'Prompt copié : si la conversation s\'ouvre vide, colle-le (Ctrl/Cmd+V).' : 'Conversation ouverte (copie du prompt impossible).'); });
      }
      const box = doc.createElement('div'); box.className = 'tr-actions'; box.appendChild(a); card.appendChild(box);
    });
  }

  // Quand le rapport est chargé : fond transparent (le radar reste visible) + blips tirés de son sommaire.
  view.addEventListener('load', () => {
    try {
      const doc = view.contentDocument;
      const st = doc.createElement('style');
      st.textContent = 'html,body{background:transparent!important}body::before{display:none!important}';
      doc.head.appendChild(st);
      const items = [];
      let cat = '';
      doc.querySelectorAll('.toc > .badge, .toc > a.item').forEach(el => {
        if (el.classList.contains('badge')) cat = ([...el.classList].find(c => c.startsWith('b-')) || '').slice(2);
        else items.push({title: el.textContent, cat});
      });
      Radar.setItems(items);
      // Liens externes : toujours dans un nouvel onglet (les ancres #… restent dans le rapport).
      doc.querySelectorAll('a[href]').forEach(l => {
        if (/^https?:$/.test(l.protocol) && l.origin !== doc.location.origin) { l.target = '_blank'; l.rel = 'noopener'; }
      });
      addActions(doc, (reports.find(x => new URL(x.href, location.href).href === view.src) || {}).date || '');
      Radar.scroll(0);
      view.contentWindow.addEventListener('scroll', () => Radar.scroll(view.contentWindow.scrollY), {passive: true});
    } catch (e) { /* iframe inaccessible : on garde le fond seul */ }
  });
  addEventListener('hashchange', show);
  show();
})();
