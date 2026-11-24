# Vérification des affirmations (agent vérificateur)

Ce fichier sert à deux choses : il dit **quand** vérifier un sujet, et il contient le **brief** à donner à l'agent vérificateur. La tâche de veille (`tools/veille-prompt.md`, §3 bis) et le skill `veille-publier` s'en servent. La liste des sources de référence et les catégories à risque sont dans `config/sujets/sources.json` (bloc `verification`).

## Quand vérifier

Un sujet est vérifié quand il contient une **affirmation qui pourrait être fausse** (faille, incident, attaque, fuite, attribution, rumeur, chiffre) **et** que cette affirmation n'est portée :
- ni par **l'auteur du fait** (l'éditeur qui annonce sa version, le projet qui présente son outil, l'entreprise qui annonce sa stratégie) ;
- ni par une **source de référence** (`verification.references`).

Ce qui compte, c'est **la source qui porte l'affirmation**. Un article du Monde Informatique dans la liste ne couvre pas une attribution que seul un autre site avance.

**Toujours vérifiés** : les **chiffres centraux** d'un incident (nombre de victimes, de magasins, de comptes). Même les sources de référence divergent ; on les recoupe.

**Jamais vérifiés** : un outil présenté par son propre dépôt, une annonce d'un éditeur sur son produit, les dates d'une conférence sur son site.

Dans les catégories à risque (`categories_a_risque`), le validateur exige une vérification pour tout sujet publié **sans aucune source de référence**. Si le fait est annoncé par son auteur (communiqué repris par un site non référencé), mets à la place `"verification_non_requise": "<raison>"`.

## Rebaser le sujet sur une source fiable

Le but n'est pas d'écarter un sujet réel parce que sa première source est faible, mais de le **rebaser** sur la meilleure source disponible. L'agent cherche donc, pour le même fait, une source primaire ou de référence (avis de l'éditeur, CERT, communiqué, AFP, presse de référence). S'il en trouve une :
- elle devient la **première source** du sujet (la source d'origine reste citée après) ;
- le titre, le résumé, la ligne `meta` et les `details` sont réécrits **à partir d'elle** ;
- ce que seule la source d'origine affirmait va dans `retirees`.

**Revendications.** Une fuite ou une attaque revendiquée (forum, site de rançongiciel) est un fait vérifiable : l'annonce existe ou non. Si aucune source fiable ne confirme l'incident mais qu'**au moins deux sources indépendantes** ont constaté et analysé l'annonce elle-même (pas une reprise l'une de l'autre), le sujet est publiable **comme revendication** : titre qui le dit (« Fuite revendiquée : … », « … revendique … »), résumé qui attribue chaque chiffre à qui l'avance, et précise qu'aucune confirmation n'a été trouvée. Le verdict est alors `vrai` : ce qui est affirmé (la revendication) est prouvé.

Seul un sujet pour lequel on ne trouve **ni source fiable, ni deux constats indépendants** reste `indetermine`.

## Effet du verdict

Le verdict est **binaire**, pour le sujet comme pour chaque affirmation.

| Verdict | Statut du sujet |
|---|---|
| `vrai` : le cœur de l'information est prouvé | publiable ; le résumé ne garde **que** les affirmations prouvées |
| `faux` : l'information est démentie | `ecarte`, motif `infirme` |
| `indetermine` : ni source fiable, ni revendication constatée par deux sources indépendantes | jamais publié : `mis-de-cote`, revérifié à l'exécution suivante |

Une affirmation non prouvée **sort du résumé** et va dans `retirees`. Une revendication peut rester si elle est formulée comme telle (« le groupe X **revendique** 46 000 comptes ») : le fait vérifié est alors l'existence de la revendication. Pour des chiffres divergents, le résumé dit qui annonce quoi, et `ecarts` le consigne.

## Format (champ `verification` du sujet)

```json
"verification": {
  "date": "2026-11-25T06:42:00+01:00",
  "verdict": "vrai",
  "resume": "Markdown court : ce qui est établi, en deux ou trois phrases.",
  "source": { "nom": "FrenchBreaches", "nature": "veille cyber bénévole ; a déjà révélé de vraies fuites, relaie aussi des revendications non recoupées" },
  "affirmations": [
    { "texte": "Une fuite touche un éditeur de logiciel RH commun à plusieurs enseignes", "preuves": [ { "texte": "Lixora, communiqué du 13 nov.", "url": "https://…" } ] }
  ],
  "retirees": [ { "texte": "Compromission du SI d'Intermarché", "raison": "aucune source ne le démontre" } ],
  "ecarts": [ "46 619 lignes selon FrenchBreaches, 42 406 salariés selon Fuites Infos" ],
  "recoupements": [ { "texte": "Le Monde, 18 mars 2026", "url": "https://…" } ]
}
```

`date`, `verdict` et `resume` sont toujours requis. Pour `vrai`, il faut aussi `source` (nom, nature) et au moins une affirmation, chacune avec au moins une preuve (URL). Le rapport affiche une icône « badge vérifié » sur la carte ; un clic ouvre ce détail dans une fenêtre.

## Brief de l'agent vérificateur

Lance **un sous-agent par sujet** (outil Agent). Donne-lui **seulement** le titre, les affirmations à vérifier (une par ligne) et les URL d'origine, **sans ton avis** : un agent à qui on donne une conclusion a tendance à la confirmer. Les sujets indépendants se vérifient en parallèle. Le brief :

> Tu vérifies des affirmations publiées sur le Web, pour une veille technologique. Tu dois dire, pour chacune, si elle est **vraie** (prouvée) ou non. Rien n'est vrai par défaut.
>
> 1. **Qui est la source ?** Nature (organisme officiel, éditeur, média de référence, blog, agrégateur, forum, site rédigé par une IA), rédaction identifiée ou non, antécédents (vraies révélations, emballements, articles critiques à son sujet).
> 2. **Source primaire.** Cherche le fait à la source : avis de l'éditeur, fiche CVE (NVD, cve.org), avis CERT-FR ou CISA, communiqué officiel, déclaration à l'AFP, dépôt ou ticket d'origine.
> 3. **Recoupement indépendant.** Trouve des sources qui ont vérifié par elles-mêmes. Une reprise de la même revendication ne compte pas comme recoupement ; remonte la chaîne de citations jusqu'à l'origine.
> 4. **Chiffres.** Compare les chiffres entre sources et note les écarts (qui annonce quoi, à quelle date).
> 5. **Dates.** Vérifie que l'information n'est pas ancienne et republiée.
> 6. **Démentis.** Cherche explicitement un démenti ou une correction (« fake », « hoax », « démenti », « erratum », mise à jour de l'article).
> 7. **Meilleure source.** Si la source d'origine n'est pas fiable, cherche activement la meilleure source fiable du même fait (source primaire, CERT, AFP, presse de référence) : c'est sur elle que le sujet sera réécrit. Pour une fuite ou une attaque revendiquée sans confirmation, dis si l'annonce elle-même a été constatée par au moins deux sources indépendantes.
>
> Fais plusieurs recherches distinctes (mode « extended » pour les faits récents) et ouvre les pages avant de conclure. Ne prétends jamais avoir lu une page que tu n'as pas pu ouvrir.
>
> Réponds en français, avec :
> - **verdict** : `vrai` si le cœur de l'information est prouvé par une source primaire ou par deux sources de référence indépendantes, ou, pour une revendication non confirmée, si l'annonce a été constatée par deux sources indépendantes (préciser alors « revendication ») ; `faux` si elle est démentie ; `indetermine` sinon ;
> - **source_fiable** : la meilleure source fiable trouvée pour le fait (texte court et URL), ou rien ;
> - **resume** : deux ou trois phrases ;
> - **source** : nom et nature de la source d'origine (une ligne) ;
> - **affirmations** prouvées, chacune avec ses preuves (texte court et URL) ;
> - **retirees** : affirmations non prouvées ou fausses, avec la raison ;
> - **ecarts** : divergences de chiffres entre sources ;
> - **recoupements** : sources consultées qui confirment (texte court et URL).

## Après la vérification

1. Écris le bloc `verification` dans le sujet (paraphrase, citations de moins de 15 mots).
2. Si le verdict est `vrai`, rebase le sujet : la source fiable trouvée passe en tête des `sources`, et le titre, le résumé, `meta` et `details` sont réécrits à partir d'elle, avec seulement les affirmations prouvées. Pour une revendication : le titre le dit.
3. Applique le statut du tableau ci-dessus et ajoute une entrée à `historique`.
4. Compte les vérifications dans `journal.verifications_sources` : `{"lancees": n, "vrai": n, "faux": n, "indetermine": n}`.
