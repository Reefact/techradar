# Architecture

## Vue d'ensemble

```mermaid
flowchart LR
    T["Tâche planifiée Claude<br/>lun-ven 6h06 Paris"] -->|"push reports/AAAA/AAAAMMJJ.html"| G[("GitHub<br/>Reefact/techradar<br/>branche main")]
    G -->|"push dans reports/"| A["GitHub Action<br/>feed.yml"]
    A -->|"commit feed.xml"| G
    G -->|"push sur main"| C["Workers Builds<br/>Cloudflare"]
    C -->|"build_site.sh puis<br/>wrangler deploy"| W["Worker techradar<br/>(static assets)"]
    W --> U["Toi, navigateur<br/>index.html + flux Atom"]
```

Tout est **statique** : pas de base de données, pas de code serveur. Le « backend » est la tâche planifiée qui écrit des fichiers HTML dans Git.

## Structure du dépôt

| Chemin | Rôle |
|---|---|
| `index.html` | Page d'accueil : bandeau, barre latérale, rapport en iframe, radar animé |
| `reports/AAAA/AAAAMMJJ.html` | Un rapport par jour (publié, listé dans l'index et le flux) |
| `drafts/AAAA/AAAAMMJJ-HHMM.html` | Versions régénérées d'un jour déjà publié (jamais listées) |
| `assets/report.css` | Feuille de style partagée par tous les rapports |
| `assets/favicon.svg`, `favicon-32.png`, `apple-touch-icon.png` | Icône radar du site (index et rapports) |
| `feed.xml` | Flux Atom **généré** ; sert aussi de liste de découverte pour l'index |
| `tools/build_feed.py` | Génère `feed.xml` à partir des rapports |
| `tools/build_site.sh` | Assemble `dist/` (ce qui est réellement déployé) |
| `tools/report-template.html` | Gabarit que la tâche de veille doit suivre |
| `wrangler.jsonc` | Config Cloudflare (Worker `techradar`, assets dans `dist/`) |
| `.github/workflows/` | `feed.yml` (flux automatique), `promote.yml` (promotion manuelle) |
| `.claude/skills/promote-draft/` | Skill Claude Code pour promouvoir un brouillon |
| `docs/` | Cette documentation |

## Le site

### Page d'accueil (`index.html`)
- **Bandeau fixe** : nom, description, bouton « S'abonner » (flux Atom).
- **Barre latérale** : rapports classés par mois et par jour.
- **Découverte** : au chargement, le JavaScript lit `feed.xml` (un `fetch`) et en tire la date et le lien de chaque rapport. Il n'y a donc pas de liste à maintenir à la main. Cela exige un serveur HTTP : `index.html` ne marche pas en `file://`.
- **Navigation** : le rapport choisi s'affiche dans une **iframe** ; l'URL garde le jour dans le hash (`index.html#2026-11-24`). Par défaut, le plus récent.

```mermaid
sequenceDiagram
    participant N as Navigateur
    participant I as index.html
    participant F as feed.xml
    participant R as rapport (iframe)
    N->>I: charge la page
    I->>F: fetch feed.xml
    F-->>I: entrées (date + lien)
    I->>I: construit la barre latérale
    I->>R: iframe src = dernier rapport (ou #date)
    R-->>I: évènement load
    I->>R: injecte un fond transparent
    I->>R: lit le sommaire, crée les blips du radar
```

### Radar d'arrière-plan
Trois couches empilées derrière l'iframe, plus un voile CRT par-dessus :
1. **Cadran** (canvas peint une seule fois) : anneaux, graduations, relèvements, échelle.
2. **Balayage** : un `conic-gradient` qui tourne via l'API d'animation du navigateur (un tour = 16 s).
3. **Blips** (petit canvas redessiné en continu) : un point carré par article du sommaire, coloré par catégorie ; il s'allume quand le faisceau passe dessus. S'y ajoutent des « échos » (anneaux) et de la poussière de phosphore.
- Le radar suit légèrement le défilement du rapport (parallaxe).
- `prefers-reduced-motion` : radar statique. L'animation se met en pause quand l'onglet est caché.
- Les blips dépendent du fait que l'iframe est de même origine (c'est le cas sur le site déployé).

### Un rapport
- Un fichier HTML qui suit `tools/report-template.html`, avec `assets/report.css` en `<link>`.
- **Obligatoires** : `<title>`, `<meta name="date" content="AAAA-MM-JJ">` (l'index et le flux s'en servent), le bloc `<div class="card tldr">` (résumé du flux), et dans le sommaire un `<span class="badge b-…">` par catégorie suivi de ses `<a class="item">` (les blips en dépendent).
- Ouvert seul, un rapport est lisible avec son thème (sans le radar).

### Style
Thème sombre noir-vert, accent turquoise, couleurs par catégorie. Polices Google Fonts : **VT323** (titres), **IBM Plex Sans** (texte), **IBM Plex Mono** (badges). C'est un appel externe ; elles pourraient être hébergées dans `assets/fonts/`.

### Flux Atom
`feed.xml` : une entrée par rapport (titre, date, lien, résumé = les puces « À retenir »). Les liens sont relatifs tant que la variable `SITE_URL` n'est pas définie.

### Boutons « Claude » sur chaque sujet
- L'index injecte (depuis `index.html`, dans l'iframe de même origine) un bouton sous chaque `<article class="card" id="…">` d'un rapport. Rien à écrire dans les rapports, anciens ou nouveaux.
- Le prompt est construit à partir de la carte : titre, résumé, ligne « pourquoi ça compte », sources, date du brief.
- **Bouton « Claude Code »** (violet) : sur les cartes qui portent `data-repo="Reefact/nom"` (sujets du radar : **un article par dépôt**, jamais de mélange, et seulement s'il y a un vrai signal pour ce dépôt). Il ouvre `https://claude.ai/code?repositories=…&prompt=…` : dépôt présélectionné, prompt pré-rempli, **non envoyé** (documenté officiellement). Le dépôt privé exige l'app GitHub Claude installée dessus.
- **Bouton « Claude »** (turquoise) : sur les autres cartes. Il ouvre `https://claude.ai/new?q=…` — ce pré-remplissage n'est **pas documenté** — et **copie aussi le prompt dans le presse-papiers** (un message le signale) pour le coller si la conversation s'ouvre vide.
- La tâche de veille ajoute `data-repo` sur les cartes du radar (règle dans son prompt et dans `tools/report-template.html`).

### Liens externes
Tout lien externe d'un rapport s'ouvre dans un nouvel onglet. Double sécurité : le gabarit impose `target="_blank" rel="noopener"` (le rapport ouvert seul se comporte aussi bien), et l'index l'applique de lui-même à tout lien externe de l'iframe (filet de sécurité si la tâche l'oublie). Les ancres internes (`#a1`, `#top`) restent dans la page.
