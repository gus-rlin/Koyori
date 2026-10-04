# Koyori — Journal de développement

Historique des choix, réalisations, difficultés, réussites et validations. Les règles de tenue figurent dans [AGENTS.md](AGENTS.md). Dates : `Europe/Paris`.

## Contexte initial

Au démarrage de ce journal, le dépôt contient une note de concept pour Koyori, agent personnel de la maison accessible par la voix via Alexa. Les scénarios décrivent la vision ; aucune application ni intégration AWS n’est encore implémentée dans ce dépôt.

La stratégie du concours vise la piste Alexa+ et les deux mini-défis AWS Builder et Open Source. Les choix précis de services, de contribution publique et de licence restent ouverts. L’inscription et la soumission ne sont pas effectuées.

Ce contexte résume les documents et décisions déjà présents ; il ne reconstitue pas un historique d’exécutions antérieures.

## JRN-001 — 2026-10-04 — Consignes du dépôt et stratégie des mini-défis

### Objectif et état

Créer les consignes destinées aux agents de code, initialiser le journal et inscrire les deux mini-défis dans la note de concept. État : terminé, vérifications documentaires effectuées.

### Réalisations

- Création d’[AGENTS.md](AGENTS.md) : application de `senior-code-basics`, tenue du journal, retours sur les outils et preuves pour les mini-défis.
- Création de ce journal avec une première entrée factuelle.
- Mise à jour de la [note de concept](<Koyori — L’agent personnel de la maison.md>) pour retenir Alexa+, AWS Builder et Open Source dans la stratégie de candidature.

### Choix et raisons

- Un journal unique à la racine facilite sa découverte et la reprise du travail tant que le projet est petit.
- Des entrées par tâche significative conservent les décisions et résultats utiles sans recopier toutes les opérations élémentaires.
- Les rubriques de retour sur les outils et de friction préparent les éléments du dossier de concours à partir d’observations réelles.
- Les deux mini-défis deviennent des objectifs retenus à la demande de l’utilisateur. Les technologies et la contribution open source restent à sélectionner ; aucune intégration n’est annoncée comme réalisée.

### Difficultés et résolution

Aucun problème observé pendant cette tâche. Le point à clarifier dans les documents était la distinction entre objectif de candidature, travail à réaliser et admissibilité effectivement démontrée.

### Ce qui a bien fonctionné

La note de concept contenait déjà les conditions et les liens officiels vérifiés dans l’échange précédent. Ils permettent de préciser la stratégie sans réécrire la vision du produit.

### Vérifications

- Relecture des fichiers enregistrés : consignes, rubriques du journal et stratégie de candidature cohérentes.
- Contrôle PowerShell des liens Markdown locaux avec `Test-Path` : aucune cible manquante dans les trois documents.
- Contrôle de l’encodage : aucun caractère de remplacement détecté.
- Recherche avec `rg` : les deux mini-défis sont marqués comme retenus ; l’ancienne recommandation conditionnelle a été retirée.
- `git status --short` : seuls `AGENTS.md`, `JOURNAL.md` et la note de concept apparaissent, tous non suivis dans ce dépôt sans commit.
- Aucun test applicatif exécuté : seuls des documents sont modifiés et aucune application n’existe encore dans le dépôt.

### Retour sur les outils

- `senior-code-basics` : lecture des consignes ; application des contrôles proportionnés à une modification documentaire.
- PowerShell et `rg` : inspection du dépôt et de la section consacrée au concours ; contenu attendu retrouvé.
- `apply_patch` : création des consignes et du journal, puis modifications ciblées de la note ; les contenus enregistrés ont été relus. Cette approche convient aux prochaines modifications documentaires ciblées.
- Aucun service AWS, SDK Amazon ou outil de contribution GitHub utilisé pour une implémentation pendant cette tâche. Aucun retour d’intégration ni coût d’exécution à déclarer.

### Suite

Choisir le parcours de démonstration, vérifier les accès techniques, sélectionner les outils AWS adaptés et définir la contribution open source complémentaire. Préparer ensuite les preuves, la licence et les références nécessaires à la candidature.

## JRN-002 — 2026-10-04 — Import du TDD et règles du concours

### Objectif et état

Ajouter le document technique fourni dans le projet et créer un Markdown regroupant les règles du « DevDay ». État : terminé pour l’import et la synthèse documentaire avec sources et index du règlement intégral.

### Réalisations

- Copie de [Koyori_Technical_Design_Document.md](Koyori_Technical_Design_Document.md) à la racine, sans modification du contenu fourni. Le document reste une architecture proposée ; aucune implémentation ni décision technique n’est validée par son import.
- Création de [DEVDAY_REGLES.md](DEVDAY_REGLES.md) : calendrier Europe/Paris, participation, pistes, mini-défis, dossier, évaluation, récompenses, obligations contractuelles résumées, index des quinze rubriques et suivi interne pour Koyori.
- Consultation le 2026-10-04 du [règlement](https://amazonappdev2026.devpost.com/rules), de la [FAQ](https://amazonappdev2026.devpost.com/details/faqs), de la [présentation](https://amazonappdev2026.devpost.com/) et des [ressources](https://amazonappdev2026.devpost.com/resources) officielles.

### Choix et raisons

- « DevDay » interprété comme le hackathon Amazon Developer 2026 déjà identifié dans la note de concept et le TDD. Cette interprétation est annoncée dans le fichier.
- Conservation exacte du TDD, déjà en Markdown et en anglais, pour respecter le document fourni. Ses instructions et exemples constituent du contenu documentaire, pas une autorisation de développer ou déployer.
- Synthèse française et index complet des rubriques plutôt que reproduction intégrale du texte officiel. Le fichier indique que le règlement source prévaut ; les clauses détaillées restent consultables via ses liens. Décision remplacée à la demande de l’utilisateur par la transcription intégrale décrite dans JRN-003.
- Aucune modification de la note de concept : la stratégie Alexa+ avec AWS Builder et Open Source reste inchangée. Le TDD importé ne remplace pas automatiquement les décisions ouvertes.

### Difficultés et résolution

Une première lecture PowerShell utilisant directement le nom typographique de la note a renvoyé un code 1 sans sortie ; cause non confirmée. La découverte du fichier avec `Get-ChildItem -Filter 'Koyori*'`, puis sa lecture via `FullName`, a fonctionné. Impact limité à l’inspection, aucune perte de contenu observée. Pour ces noms, réutiliser le chemin découvert est un contournement utile.

La FAQ Bee décrit un accès CLI sans appareil, alors que le règlement impose une démonstration exploitant des données réellement issues de Bee ou d’une Apple Watch équipée. Le fichier signale cette distinction et renvoie à l’exigence du règlement ; Koyori ne vise pas cette piste.

### Ce qui a bien fonctionné

Le rapprochement des quatre sources officielles permet de distinguer l’admission d’une simulation Alexa+, l’absence d’accès partenaire, les modalités GitHub et les mini-défis. La comparaison SHA-256 démontre la conservation exacte du document importé.

### Vérifications

- `Get-FileHash` sur l’original et la copie : empreintes SHA-256 identiques ; fichier de 139 148 octets.
- Relecture du fichier de règles et comparaison avec les sources consultées : clôture le 2026-10-23 à 21 h Europe/Paris, simulation admise, MCP 2025-11-25 minimum, contribution Open Source complémentaire et fusion non obligatoire.
- Contrôle PowerShell des liens Markdown locaux dans tous les documents présents avant cette entrée : aucune cible manquante ; aucun caractère de remplacement Unicode détecté.
- `git status --short` : les cinq documents à la racine sont non suivis ; aucun commit ni publication réalisé.
- Aucun test applicatif exécuté : tâche documentaire. Les affirmations techniques du TDD n’ont pas fait l’objet d’une revue exhaustive ni de tests d’intégration.

### Retour sur les outils

- PowerShell : lecture, copie, comparaison des empreintes et contrôle des liens ; copie et contrôles aboutis. Friction de lecture du nom typographique décrite ci-dessus ; version non relevée.
- `web.run` : accès aux quatre pages officielles Devpost ; contenu exploitable obtenu. Réutilisation utile pour recontrôler les règles avant candidature.
- `apply_patch` : création du fichier de règles et ajout de cette entrée ; modifications documentaires ciblées.
- Aucun outil AWS, SDK Amazon ou service de publication utilisé. Aucun coût AWS ni ressource active créé pendant cette tâche.

### Suite

Confirmer que le concours désigné par « DevDay » est bien celui retenu. Reconsulter les règles avant soumission et examiner le TDD lors du choix du périmètre d’implémentation. Inscription, admissibilité individuelle, développement, contribution publique, choix de licence et candidature restent à réaliser ou confirmer.

## JRN-003 — 2026-10-04 — Remplacement de la synthèse par le règlement fourni

### Objectif et état

Remplacer la synthèse de `DEVDAY_REGLES.md` par le texte intégral fourni par l’utilisateur, uniquement les règles, sans conseils pour Koyori. État : terminé.

### Réalisations

[DEVDAY_REGLES.md](DEVDAY_REGLES.md) contient désormais l’intégralité du texte français fourni, avec ses quinze rubriques, ses conditions de participation et ses prix. Seuls les marqueurs de titres Markdown et les espaces de présentation ont changé. Les commentaires, la synthèse, l’index ajouté et les conseils propres au projet ont été retirés.

### Choix et raisons

La demande de l’utilisateur remplace le choix documentaire de JRN-002. Conservation des formulations et des horaires du texte fourni, sans corriger la traduction ni ajouter de FAQ, de conversion horaire ou de recommandations. Les impératifs présents dans le règlement sont conservés comme contenu documentaire ; aucune inscription ou autre action externe n’est exécutée.

### Difficultés et résolution

Aucun problème observé. Le texte collé fournit le contenu complet à transcrire ; il permet le remplacement demandé après l’échange précédent.

### Ce qui a bien fonctionné

Une comparaison automatisée avec le texte source, après retrait des marqueurs de titres et normalisation des espaces, confirme qu’aucun mot ni passage n’a été ajouté ou supprimé.

### Vérifications

- PowerShell : égalité exacte du contenu normalisé entre le texte fourni et le fichier enregistré.
- Contrôle des titres : quinze rubriques principales présentes.
- Encodage UTF-8 : aucun caractère de remplacement détecté ; relecture du début et des rubriques du fichier.
- Aucun test applicatif ni nouvelle vérification externe : seule la transcription du texte fourni est demandée. La fidélité au texte collé est vérifiée, pas l’exactitude juridique de sa traduction.

### Retour sur les outils

PowerShell et les API .NET de fichiers : lecture, mise en forme mécanique et comparaison du contenu, avec résultat conforme. `apply_patch` : mise à jour ciblée du journal. Aucun service AWS ni outil de publication utilisé ; aucun coût ou ressource créé. Non applicable pour les retours sur une intégration applicative.

### Suite

Aucune action restante pour cette demande. Le document conserve les formulations du texte fourni ; les éventuelles corrections de traduction nécessiteraient une demande distincte.

## JRN-004 — 2026-10-04 — Inscription déclarée et exigences des dépôts

### Objectif et état

Clarifier si un dépôt open source est obligatoire après l’inscription. État : terminé. L’utilisateur déclare avoir effectué son inscription ; aucune vérification de compte n’a été réalisée.

### Réalisations

Consultation du [règlement officiel](https://amazonappdev2026.devpost.com/rules) et de la [FAQ](https://amazonappdev2026.devpost.com/details/faqs), le 2026-10-04. Distinction entre le dépôt GitHub exigé pour la soumission principale et la contribution complémentaire du mini-défi Open Source. Aucun dépôt créé ou publié.

### Choix et raisons

Le dépôt principal peut être public avec un fichier de licence open source visible, ou privé avec accès aux évaluateurs désignés dans le règlement. Le mini-défi exige un nouveau projet open source supplémentaire ou une contribution à un dépôt public pendant la période du concours ; une branche, un fork ou une pull request sont admis, sans obligation de fusion. L’ouverture du dépôt principal ne démontre donc pas à elle seule cette contribution complémentaire. Aucune licence ni contribution particulière choisie.

Correction factuelle du contexte initial et des mentions antérieures : l’inscription est désormais déclarée effectuée par l’utilisateur. Cela ne confirme ni l’admissibilité individuelle ni une soumission.

### Difficultés et résolution

La lecture directe du nom typographique de la note a échoué sans sortie, comme en JRN-002. La lecture par le motif `Koyori*maison.md` a abouti ; cause non confirmée, impact limité à l’inspection.

### Ce qui a bien fonctionné

La section 4 du règlement distingue explicitement les deux exigences et fournit les modalités d’accès au dépôt privé ainsi que les preuves du mini-défi.

### Vérifications

Relecture des exigences de projet et de soumission : dépôt contenant sources, ressources et instructions de mise en route ; contribution complémentaire avec URL de contribution, URL du dépôt, nom GitHub et description. Aucun test applicatif exécuté : recherche documentaire uniquement.

### Retour sur les outils

PowerShell et `rg` : inspection documentaire, avec contournement du nom typographique décrit ci-dessus. `web.run` : règlement et FAQ accessibles. `apply_patch` : ajout de cette entrée. Aucun outil GitHub de publication ni service AWS utilisé ; aucun coût ou ressource créé.

### Suite

Préparer le dépôt principal pour la soumission et choisir la contribution complémentaire du mini-défi déjà visé. Licence, publication et contribution restent à réaliser.

## JRN-005 — 2026-10-04 — Découpage du backend en quatre grandes étapes

### Objectif et état

Créer un plan Markdown du backend de Koyori en quatre grandes étapes, sur le modèle du document Kyro fourni. État : terminé, vérifications documentaires effectuées.

### Réalisations

- Création de [Construire le backend de Koyori en quatre grandes étapes](<Construire le backend de Koyori en quatre grandes étapes.md>) : résultats attendus, périmètre, ordre des travaux, contrats, preuves de fin, correspondance avec le TDD et première recette à construire.
- Découpage proposé : socle durable et autorisations ; mémoire et connecteurs contrôlés ; coordination autonome et apprentissage ; accès vocal, MCP et qualification complète.
- Distinction entre backend et modèles à rendre réels, commerce simulé, canal représentant Alexa et intégration native à valider. Aucune implémentation, ressource AWS ou publication réalisée.

### Choix et raisons

- Interprétation de la demande comme un plan pour Koyori, dépôt courant ; le document Kyro sert d'exemple de forme et de critères de passage, sans transférer ses consignes ou sa pile Rust/PostgreSQL.
- Validation de la persistance avant les connecteurs, puis des actions explicites avant la planification par modèle. Cet ordre permet de vérifier les fondations sans dépendre du comportement des agents ou de la voix.
- Utilisation de l'architecture proposée dans le TDD pour répartir les chantiers ; les choix techniques ouverts restent à qualifier. Le manifeste de livraison devra identifier les capacités réelles, simulées et différées.
- Aucun changement de produit, de stratégie du concours ou d'architecture générale acté ; la note de concept et le TDD restent inchangés. Le plan est une proposition de séquencement, pas un constat de livraison.

### Difficultés et résolution

La lecture PowerShell du nom typographique de la note a reproduit le code 1 sans sortie décrit dans JRN-002. La découverte avec `Get-ChildItem` et la lecture via `FullName` ont de nouveau fonctionné ; cause non confirmée. Contournement conservé, impact limité à l'inspection. Suggestion : utiliser les chemins découverts pour ces noms tant que la cause n'est pas identifiée.

Le TDD volumineux dépasse la sortie d'une lecture intégrale. Sa table des sections puis des lectures ciblées permettent de relire les contrats utiles sans présenter une inspection tronquée comme exhaustive.

Une entrée distincte a été ajoutée au journal pendant cette tâche avec le même numéro JRN-004. Doublon détecté lors de la relecture finale ; seule l'entrée de cette tâche a été déplacée à la fin et renumérotée JRN-005, en conservant intégralement l'autre entrée. Impact limité aux identifiants du journal. Relever le dernier numéro au moment de l'ajout final réduit cette friction lors de travaux concurrents.

La première renumérotation PowerShell a échoué sur le format numérique `D3` et a laissé temporairement le titre de cette entrée sans identifiant : l'erreur n'arrêtait pas le script. Correction ciblée avec `apply_patch`, puis contrôle de tous les identifiants. Pour ce type de transformation, convertir explicitement le numéro en entier et arrêter le script à la première erreur avant toute écriture.

### Ce qui a bien fonctionné

Le rapprochement des quatre catégories de mémoire et des parcours de la note de concept avec les contrats du TDD permet de conserver l'ambition transversale tout en définissant des points de validation successifs. L'exemple Kyro apporte une structure directement réutilisable pour les résultats et preuves de fin.

### Vérifications

- Relecture du plan enregistré et comparaison avec les sections pertinentes du TDD : quatre étapes successives, contrôles cumulatifs, ambition produit et limites des intégrations conservées.
- Contrôle PowerShell des six documents Markdown : seize références locales vérifiées, aucune cible manquante, y compris le document Kyro situé dans le projet voisin.
- Lecture UTF-8 stricte et recherche du caractère de remplacement Unicode : aucun problème détecté.
- Contrôle des titres : exactement quatre grandes étapes numérotées de 1 à 4 ; aucune case de recette future marquée comme réussie.
- Contrôle final du journal : identifiants uniques et croissants de JRN-001 à JRN-005 ; l'entrée distincte JRN-004 est conservée.
- `git status --short` : les cinq documents initiaux et le nouveau plan restent non suivis ; aucun commit ni publication effectué.
- Aucun test applicatif ni appel à un service externe exécuté : tâche documentaire, aucune application présente ni modifiée. Les recettes du nouveau plan restent des contrôles à réaliser.

### Retour sur les outils

- `senior-code-basics` : lecture et application de vérifications proportionnées à la portée documentaire.
- PowerShell et `rg` : inventaire, lecture des consignes, du journal, du concept et des sections pertinentes du TDD ; contournement de la friction de nom typographique confirmé, comme dans JRN-002. Version PowerShell non relevée.
- `apply_patch` : création du plan et mise à jour de cette entrée ; contenu enregistré relu et contrôlé. Réutilisation adaptée aux modifications documentaires ciblées.
- `open_in_codex` : ouverture du plan demandée dans le panneau de cette conversation ; réponse `queued`, affichage effectif non confirmé. Réutilisation utile pour présenter un document créé.
- Aucun service AWS, API de modèle, SDK agentique ou outil de publication utilisé. Aucun coût AWS ni ressource créée pendant cette tâche ; les services cités restent des propositions documentaires.

### Suite

Aucune action restante pour la demande documentaire. Lors d'une tâche d'implémentation distincte, commencer par le manifeste de livraison et la recette du socle durable. Accès techniques, périmètre concret des connecteurs et contribution Open Source complémentaire restent à qualifier ou choisir.

## JRN-006 — 2026-10-04 — Connexion au dépôt GitHub

### Objectif et état

Relier le dépôt local à `https://github.com/gus-rlin/Koyori`. État : terminé pour la connexion et la récupération des références distantes.

### Réalisations

Ajout du remote `origin` avec l’URL HTTPS `https://github.com/gus-rlin/Koyori.git`. Accès distant vérifié et références récupérées. Aucun commit local ni envoi des documents effectué.

### Choix et raisons

Réutilisation du dépôt Git local existant et conservation de ses fichiers. La demande porte sur la connexion ; la publication des documents ne fait pas partie de cette opération. La branche locale `main` n’a pas encore de commit, tandis que le dépôt distant possède déjà une branche `main`.

### Difficultés et résolution

Aucun problème observé lors de la connexion. L’absence de commit local est un état initial constaté ; les historiques devront être alignés avant le premier envoi.

### Ce qui a bien fonctionné

`git ls-remote origin` a confirmé l’accès à GitHub et la présence de `main` sans modifier les documents locaux.

### Vérifications

`git remote -v` : URL attendue pour fetch et push. `git ls-remote origin` : succès, branche `main` présente. `git fetch origin` : références distantes récupérées. `git status --short` : les six documents existants restent non suivis. Aucun test applicatif : modification de configuration Git uniquement.

### Retour sur les outils

`senior-code-basics` : consignes lues, contrôles proportionnés à la configuration. Git via PowerShell : ajout du remote et lecture distante aboutis. `apply_patch` : ajout de cette entrée. Aucun service AWS utilisé ni ressource créée.

### Suite

Aligner la branche locale sur l’historique distant avant de créer et envoyer le premier commit des documents. La connexion ne constitue pas une publication ni une contribution complémentaire au mini-défi Open Source.

## JRN-007 — 2026-10-05 — Étape 1 : orchestration et socle durable

### Objectif et état

Implémenter le plan accepté : backend local durable, accès administrables par API, données synthétiques et préparation AWS. État : en cours ; la qualification des services AWS reste en attente d'accès fédéré. Le passage du mode Plan au mode d'exécution est explicitement demandé par l'utilisateur.

### Réalisations

- Exploration préparatoire par trois sous-agents Luna en lecture seule : périmètre de l'étape 1, outils locaux et contrats AWS. Aucun fichier ni worktree n'a été créé pendant cette phase Plan.
- Choix confirmés par l'utilisateur : local avec préparation AWS, services Docker, gestion des membres, partages et délégations par API.
- Branche d'intégration `gus-rlin/koyori-etape1` créée depuis `origin/main` ; licence Apache 2.0 distante conservée. Les documents existants sont préservés avant les worktrees d'exécution.

### Choix et raisons

Python 3.12, FastAPI/Pydantic, boto3, DynamoDB Local et ElasticMQ pour le local ; même logique de domaine et même adaptateur DynamoDB pour la préparation AWS. L'opération `synthetic.checkpoint` valide la persistance sans modèle ni fournisseur. L'état canonique et les intentions de reprise restent durables ; les messages ne sont pas la seule preuve d'un travail à effectuer.

Chaque sous-agent d'exécution utilisera son propre worktree et une branche dédiée. Les contrats précèdent les chantiers parallèles ; le test indépendant et une revue Sol sont obligatoires avant acceptation. L'orchestrateur est le seul rédacteur de cette entrée pour éviter les doublons d'identifiants observés en JRN-005.

### Difficultés et résolution

Python 3.12 absent sur l'hôte, qui possède Python 3.10 et 3.14 ; Docker et uv disponibles. Le runtime du projet sera fourni explicitement. Aucun autre problème observé à ce stade. Le dépôt local sans commit a été aligné sur l'historique distant avant l'enregistrement des documents, sans remplacer leur contenu.

### Ce qui a bien fonctionné

Les recettes du découpage et la distinction entre preuves locales et AWS ont permis de fixer un périmètre vérifiable sans clés fournisseurs. Les trois explorations ont terminé et leurs résultats ont été rapprochés du TDD.

### Vérifications

Inspection des six documents et de Git ; `origin/main` contient un commit initial et la licence Apache 2.0. Docker client/serveur 29.8.0, Git 2.52.0, Node 24.18.0 et uv 0.11.28 relevés pendant l'exploration. Aucun test applicatif encore exécuté ; aucun logiciel applicatif n'existait au démarrage.

### Retour sur les outils

`sol-orchestrator` et `senior-code-basics` lus et appliqués. Sous-agents `luna-explorer` et `luna-researcher` réellement utilisés pendant la planification ; worktrees impossibles dans cette phase en lecture seule. Sources primaires DynamoDB Local, ElasticMQ, CDK, Mangum et Cognito consultées le 2026-10-05. Les émulateurs ne prouvent pas les garanties des services AWS. Aucun appel fournisseur authentifié, ressource AWS, coût AWS ou publication créé.

### Suite

Stabiliser les contrats, implémenter dans des worktrees isolés, intégrer puis vérifier les crashs, droits, réparations, restauration et artefacts. Compléter cette entrée avec les résultats réels et les limites avant la livraison.

### Exécution du plan validé — 2026-10-05

L'utilisateur demande explicitement l'implémentation du plan. Le mode d'exécution est désormais actif. La livraison attendue est le backend local complet, les preuves de vérification et les artefacts AWS contrôlés statiquement ; la qualification sur les services AWS reste distincte, sans accès au compte ni déploiement pendant cette tâche.

La nouvelle exploration préparatoire a réellement utilisé les agents Luna `explore_step1_contract`, `explore_validation_environment` et `research_stage1_aws_compatibility`, tous terminés en lecture seule. Le dépôt ne contient toujours pas d'application. Le changement local préexistant du journal est préservé. Le worktree documentaire existant est propre et ses commits sont déjà dans la branche d'intégration.

Correction factuelle de l'environnement décrit plus haut : Python 3.12.13 est installé via uv 0.11.28 ; le Python du PATH est 3.10.6. Docker Engine 29.8.0 et Compose 5.5.1 sont opérationnels. Les images DynamoDB Local et ElasticMQ devront être obtenues. Un worker `activity` dédié est retenu pour lever l'option de consommation du flux d'activité dans le contrat.

Les sources primaires consultées le 2026-10-05 confirment deux limites à intégrer aux recettes : DynamoDB Local ne reproduit pas les conflits transactionnels du service et ne prouve pas sa cohérence de lecture ; ElasticMQ exige une persistance des messages explicite. Les tests de conflits incluront une injection contrôlée. La production ne doit pas accepter l'émetteur d'identité synthétique local.

La prochaine étape est le chantier contrats et stockage dans son propre worktree, puis les lots accès/API, travail durable, infrastructure et documentation. Aucun contrôle applicatif n'est encore possible ; aucune ressource AWS ni publication n'a été créée.
