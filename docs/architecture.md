# Architecture

## Vue d'ensemble

```mermaid
flowchart LR
    C["config/<br/>catégories, tags, sujets"] --> T["Tâche planifiée<br/>lun-ven 6h06 Paris"]
    P["tools/veille-prompt.md<br/>(processus)"] --> T
    T -->|"push data/days/AAAA/AAAAMMJJ.json"| G[("GitHub<br/>Reefact/techradar<br/>main")]
    G -->|"Action memory.yml"| M["data/memory.json<br/>+ contrôles"]
    G -->|"Workers Builds"| B["tools/build_site.sh<br/>(render.py)"]
    B --> W["Worker techradar<br/>techradar.reefact.net"]
    W --> U1["/ : rapports publiés"]
    W --> U2["/dossier/ : dossier du jour"]
    W --> U3["feed.xml"]
```

Tout est **statique**. La source de vérité est un **fichier de données par jour** (`data/days/AAAA/AAAAMMJJ.json`) qui contient tous les sujets analysés avec leur statut ; le site est **rendu** à partir de ces fichiers au moment du déploiement. La tâche planifiée n'écrit jamais de HTML.

## Structure du dépôt

| Chemin | Rôle |
|---|---|
| `config/categories.json` | Catégories : clé stable → libellé, libellé de carte, classe CSS, préfixe d'identifiant, ordre, minimum, plafond, description |
| `config/tags.json` | Tags (badges) : clé stable → libellé, classe CSS, description (règle d'application) |
| `config/sujets.json` | Index des fichiers « quoi chercher » (chemin, rôle, actif) |
| `config/sujets/` | `perimetre.json` (priorités, exclusions, fenêtre, volumes), `sources.json`, `recherche/<catégorie>.json`, `outils.json`, `radar.json`, `conferences.json` |
| `data/days/AAAA/AAAAMMJJ.json` | Fichier du jour : sujets (publiés, candidats, mis de côté, écartés), « À retenir », « En bref », journal de recherche, exécutions |
| `data/demande.json` | (Ponctuel) demande de l'utilisateur pour la prochaine exécution : date cible, consignes |
| `data/memory.json` | Mémoire dérivée des jours (générée par l'Action, ne pas éditer) |
| `data/notes.md` | Notes non déductibles (préférences, versions vues, vérifications en attente) |
| `tools/veille-prompt.md` | Processus de la tâche (comment travailler) |
| `tools/veille-bootstrap.md` | Texte d'amorçage collé dans la tâche (il lui fait lire le processus) |
| `tools/veille_lib.py` | Fonctions partagées : configuration, Markdown simple, dates |
| `tools/render.py` | Rendu : rapports publiés, dossiers du jour, `dossier.json`, flux Atom |
| `tools/check_config.py` | Validation de la configuration |
| `tools/check_day.py` | Validation d'un fichier du jour (schéma, volumes, radar, journal, immuabilité, rendu, langue) |
| `tools/check_report.py` | Contrôle du HTML rendu (structure, liens, signaux de langue) ; appelé par `check_day.py` |
| `tools/statut.py` | Change le statut de sujets (utilisé par le skill `veille-publier`) |
| `tools/build_memory.py` | Mémoire : `--seen`, `--due`, `--reconsiderer` |
| `tools/build_site.sh` | Build Cloudflare : contrôle de la configuration, rendu, interface → `dist/` |
| `index.html`, `dossier/index.html` | Interface : accueil (rapports publiés) et page du dossier du jour |
| `assets/` | `site.css`, `site.js` (interface et radar), `report.css` (rapports et dossiers), icônes Reefact |
| `.github/workflows/memory.yml` | Contrôles et régénération de la mémoire à chaque push |
| `.claude/skills/` | Skills Claude Code : voir [skills.md](skills.md) |
| `wrangler.jsonc` | Configuration Cloudflare (Worker `techradar`, assets dans `dist/`) |
| `docs/` | Cette documentation |

## Le fichier du jour

Un sujet a un **statut** : `publie` (dans le rapport) · `candidat` (bon, non retenu ou trouvé lors d'une relance) · `mis-de-cote` (à réexaminer) · `ecarte` (avec un motif : `deja-publie`, `hors-fenetre`, `hors-perimetre`, `non-verifiable`, `doublon`, `trop-mineur`, `plafond-atteint`, `exclu-config`, `rien-de-neuf`, `infirme`).

Champs principaux d'un sujet : `id` (préfixe de catégorie + numéro), `categorie`, `statut`, `motif`, `tags`, `titre`, `resume` (Markdown simple), `pourquoi`, `details`, `sources`, `meta` (ligne du sommaire), `depot` (radar), `conference` (dates, lieu, CFP), `verification` (vérification des affirmations, voir ci-dessous), `historique`. Le détail est dans [`tools/veille-prompt.md`](../tools/veille-prompt.md) (§4) et la référence est le fichier existant `data/days/2026/20261124.json`.

**Vérification des affirmations.** Un sujet qui contient une affirmation qui pourrait être fausse (faille, incident, fuite, attribution, chiffre), portée ni par l'auteur du fait ni par une source de référence (`config/sujets/sources.json`, bloc `verification`), passe par un sous-agent vérificateur indépendant. Le verdict est binaire : `vrai` (publiable ; le résumé ne garde que ce qui est prouvé), `faux` (écarté, motif `infirme`), ou `indetermine` (mis de côté, revérifié le lendemain). Le résultat est stocké dans le champ `verification` du sujet ; le rapport affiche une icône « badge vérifié » sur la carte, qui ouvre le détail dans une fenêtre (API `popover`, sans JavaScript). Règles et brief de l'agent : [`tools/veille-verification.md`](../tools/veille-verification.md).

Le texte est en **Markdown simple** (`**gras**`, `` `code` ``, `[texte](https://…)`, paragraphes, listes « - ») ; le rendu garantit les classes CSS, les ancres, `target="_blank"` sur les liens externes, les badges et `data-repo`.

## Le site

### Accueil (`/`)
Bandeau « Reefact | TechRadar » (liens vers reefact.net et vers l'accueil), barre latérale des rapports publiés (découverts via `feed.xml`), rapport affiché en iframe (le jour dans l'adresse : `/#2026-11-24`, par défaut le plus récent), radar animé en fond (les « blips » viennent du sommaire du rapport), boutons « Claude » / « Claude Code » sur chaque sujet, liens externes en nouvel onglet.

### Dossier du jour (`/dossier/`)
Même interface, mais la barre latérale liste les jours (avec le nombre de sujets à revoir) et l'iframe affiche le **dossier** : journal de recherche, compteurs par statut, filtres, tous les sujets (écartés en lignes compactes avec leur motif), légende des catégories et des tags, et un bouton « Demander la publication » sur chaque candidat qui copie la demande à coller dans Claude. Non indexé par les moteurs. L'ancienne adresse `/drafts/` redirige ici.

### Rapport publié (`/reports/AAAA/AAAAMMJJ`)
Rendu des seuls sujets publiés : « À retenir », sommaire, conférences (tableau), « En bref », résumés, pied de page. Titre d'onglet : « Veille technologique du mardi 24 novembre 2026 – Reefact ».

### Boutons « Claude » sur chaque sujet
L'interface ajoute un bouton sous chaque sujet : « Claude Code » (violet) pour un sujet du radar, qui ouvre `claude.ai/code` avec le dépôt présélectionné et le prompt pré-rempli (non envoyé) ; « Claude » (turquoise) pour les autres, qui ouvre `claude.ai/new` et copie aussi le prompt dans le presse-papiers.

### Style
Thème sombre noir-vert, accent turquoise, « Reefact » en bleu (#5eaedb, couleur du logo). Polices Google Fonts : VT323 (titres), IBM Plex Sans (texte), IBM Plex Mono (badges). Icônes du site = logo Reefact.

### Flux Atom
`feed.xml` : une entrée par jour publié (titre, lien, résumé = « À retenir »), liens absolus grâce à la variable `SITE_URL` du build.
