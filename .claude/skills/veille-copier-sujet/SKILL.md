---
name: veille-copier-sujet
description: Copie un ou plusieurs sujets (cartes de résumé, lignes « En bref ») d'un brouillon vers le rapport publié du MÊME jour, sans remplacer tout le rapport : insère la carte dans la bonne catégorie, met à jour le sommaire, contrôle la structure. À utiliser quand un brouillon contient des sujets à ajouter ou à remplacer dans le rapport du jour.
---

# Copier des sujets d'un brouillon vers le rapport du jour

Le travail d'insertion est fait par un **script déterministe** (`tools/merge_topic.py`), pas par réécriture libre du HTML. Le skill sert à choisir, montrer, faire valider, appliquer.

Limites : même jour uniquement (la date `<meta name="date">` du brouillon doit avoir son rapport publié ; sinon utiliser le skill `promote-draft`) ; les **cartes de conférence** et le bloc **« À retenir aujourd'hui »** ne sont pas gérés (à faire à la main).

## 1. Choisir le brouillon

Lister `drafts/AAAA/*.html` (`git fetch origin main` d'abord) ; prendre celui que l'utilisateur nomme, sinon le plus récent du jour demandé (le dire).

## 2. Voir ce qui diffère

```bash
python3 tools/merge_topic.py list drafts/AAAA/AAAAMMJJ-HHMM.html
```
La sortie classe les cartes du brouillon :
- **NOUVEAUX** : aucune de leurs sources n'est dans le rapport ;
- **DIFFÉRENTS** : même source que celle d'une carte du rapport, mais texte différent (le jumeau est indiqué : « ≈ a1 ») ;
- identiques, conférences (non gérées), sans lien source ;
- lignes **« En bref »** nouvelles (numérotées).

Présenter cette liste à l'utilisateur en français clair (titre, catégorie), et lui demander **quoi copier** : identifiants de cartes, numéros de lignes « En bref ». Pour un sujet « différent », lui demander : **remplacer** la carte existante (`--replace NOUVEAU=ANCIEN`, la carte garde l'identifiant de l'ancienne) ou ne rien faire. Ne jamais ajouter en double un sujet déjà présent.

## 3. Essai à blanc

```bash
python3 tools/merge_topic.py copy <brouillon> --card a7,n4 --brief 1,2 [--replace t3=t3]
```
Sans `--apply`, rien n'est écrit : le script affiche ce qui serait copié (nouveaux identifiants si collision, catégorie) et un extrait du diff. Il **refuse** la copie si elle introduit une nouvelle erreur de `tools/check_report.py`. Montrer l'aperçu à l'utilisateur.

Lui rappeler ce que le script ne fait pas : le bloc « À retenir aujourd'hui » reste tel quel (demander s'il doit mentionner un sujet copié), le pied de page (liste des sources) n'est pas complété, et un sujet copié garde le texte et les dates du brouillon.

## 4. Appliquer, relire, publier

1. **Accord explicite** de l'utilisateur (le rapport est publié). Sans accord : s'arrêter ici.
2. Relancer la même commande avec `--apply`.
3. `python3 tools/check_report.py reports/AAAA/AAAAMMJJ.html` : pas d'erreur. Regarder les lignes `? (langue)` ; si l'utilisateur le souhaite, faire passer la relecture du français (skill `veille-relecture`) sur les cartes copiées.
4. `git diff --stat` : seul `reports/AAAA/AAAAMMJJ.html` doit avoir changé.
5. Commit sur `main`, sans branche ni PR : « Sujets copiés du brouillon HHMM : <ids> ». Le push déclenche l'Action (flux et mémoire) puis le déploiement Cloudflare ; ne pas commiter `feed.xml` ni `data/memory.json` à la main.
6. Optionnel : vérifier en ligne après le déploiement (le sujet apparaît dans le sommaire et dans les résumés).

## Règles

- Ne rien écrire dans `reports/` avant l'accord de l'utilisateur ; passer par le script, jamais par un copier-coller manuel de HTML.
- Si le script refuse (erreur de structure, conférence, ligne déjà présente), le dire tel quel et proposer une alternative ; ne pas contourner.
- L'ancienne version du rapport reste dans l'historique Git (restaurable avec `git revert`).
