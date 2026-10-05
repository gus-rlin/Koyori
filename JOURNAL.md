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

Implémenter le plan accepté : backend local durable, accès administrables par API, données synthétiques et préparation AWS. État : **terminé pour ce périmètre**, avec revue finale **9,3/10, PASS** ; la qualification des services AWS reste distincte. Le passage du mode Plan au mode d'exécution et l'implémentation individuelle suivie d'une revue sont explicitement demandés par l'utilisateur. Les jalons ci-dessous conservent l'historique et les états intermédiaires.

### Réalisations

- Exploration préparatoire par trois sous-agents Luna en lecture seule : périmètre de l'étape 1, outils locaux et contrats AWS. Aucun fichier ni worktree n'a été créé pendant cette phase Plan.
- Choix confirmés par l'utilisateur : local avec préparation AWS, services Docker, gestion des membres, partages et délégations par API.
- Branche d'intégration `gus-rlin/koyori-etape1` créée depuis `origin/main` ; licence Apache 2.0 distante conservée. Les documents existants sont préservés avant les worktrees d'exécution.

### Choix et raisons

Python 3.12, FastAPI/Pydantic, boto3, DynamoDB Local et ElasticMQ pour le local ; même logique de domaine et même adaptateur DynamoDB pour la préparation AWS. L'opération `synthetic.checkpoint` valide la persistance sans modèle ni fournisseur. L'état canonique et les intentions de reprise restent durables ; les messages ne sont pas la seule preuve d'un travail à effectuer.

L'organisation initiale prévoyait des sous-agents d'exécution avec worktrees et branches dédiés. Elle a été remplacée par la demande d'exécution individuelle décrite plus bas : l'agent principal a écrit et corrigé le code seul, et `review_stage1` a effectué les revues finales en lecture seule. L'agent principal reste le seul rédacteur de cette entrée pour éviter les doublons d'identifiants observés en JRN-005.

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

### Exécution individuelle demandée — 2026-10-05

La dernière consigne de l'utilisateur remplace l'organisation parallèle : implémentation de l'étape 1 par l'agent principal seul, puis sous-agent de revue final avec seuil minimal de 9/10. Le périmètre local Docker et préparation AWS du contrat est conservé. Aucun déploiement AWS n'est autorisé ou réalisé par cette consigne.

Premier incident de mise en route : `uv sync --group infra` (uv 0.11.28, Windows) refuse le certificat présenté pour PyPI (`UnknownIssuer`). Résolution proposée par uv : utiliser le magasin de certificats système avec `--system-certs`, sans désactiver TLS. Impact : installation initiale des dépendances interrompue ; le résultat du contournement sera consigné ci-dessous.

### Premier jalon applicatif — 2026-10-05

`uv --system-certs sync --group infra` a abouti : environnement Python 3.12.13 et 70 paquets verrouillés dans `uv.lock`. API FastAPI, stockage transactionnel, autorisations, preuves fraîches, worker synthétique, publication et projection d'activité sont présents. Les 33 premières recettes unitaires passent ; l'image Linux et le bundle Lambda ont été construits. Synthèse CDK locale effectuée sans credentials ni déploiement. Ces résultats intermédiaires ne constituent pas encore la recette finale.

Frictions observées : le tag ElasticMQ `1.7.4` essayé n'existe pas ; consultation de la publication officielle et récupération de `1.7.1`, avec empreinte d'image fixée. Le démarrage Compose a ensuite échoué avec `all predefined address pools have been fully subnetted` (Docker 29.8.0). Les sous-réseaux existants ont été inspectés ; `10.253.42.0/24`, libre au contrôle, est explicitement réservé dans Compose et peut être remplacé avec `KOYORI_DOCKER_SUBNET`. Aucun réseau tiers supprimé. Les premières tentatives d'intégration ne peuvent passer tant que les services n'ont pas démarré ; relancer après résolution et conserver le résultat réel.

Friction de CDK/jsii sous Windows : l'import des dépendances a affiché une erreur de nettoyage temporaire Node `ENOTEMPTY` à la fermeture, tout en terminant avec code 0. La synthèse ultérieure a terminé avec code 0 sans cette erreur. Ne pas confondre l'erreur de nettoyage et l'état de synthèse ; les assertions du template restent à exécuter.

### Recettes sur émulateurs et conteneurs — 2026-10-05

Les tests sur DynamoDB Local 3.3.0 ont révélé qu'un `begins_with` avec un préfixe vide ne convient pas à une clé d'index. L'adaptateur omet désormais la condition de sort key quand aucun préfixe n'est demandé. La transaction à condition invalide confirme le rollback de tous les records du lot. Les échanges réels avec ElasticMQ 1.7.1 démontrent le doublon après publication interrompue et une seule mutation par inbox. La première tentative d'intégration, avant démarrage des services, a échoué faute de connexion ; ces résultats ne sont pas présentés comme réussis.

Le port hôte 8080 était déjà attribué à un autre conteneur. Le port de Koyori est désormais 8088, configurable par `KOYORI_API_PORT`, sans arrêter le service tiers. `scripts/verify_local.py` a réellement tué un worker vivant après le checkpoint 1, redémarré DynamoDB, ElasticMQ et l'API, puis retrouvé le même taskId, la réponse idempotente et un succès synthétique avec activité durable. Rapport `artifacts/local-recovery.json` : PASS. La restauration d'essai dans de nouvelles tables retrouve droits, checkpoint et intentions puis reprend la tâche.

Choix de sécurité ajoutés : grants d'exécution et délégations liés aux générations d'accès ; une réinscription ne restaure pas les anciens grants. La liste canonique des membres actifs est bornée dans le foyer et modifiée atomiquement ; un historique de révocations ne doit pas masquer les destinataires actuels de l'activité. Les sweeps répartissent leur budget entre shards pour éviter une famine par un shard occupé.

`pytest` avec intégrations et assertions du template : 48 tests passés au jalon ; ruff sans erreur. Audit du bundle runtime : aucune vulnérabilité connue trouvée, SBOM CycloneDX généré. Un avertissement du client de test Starlette indique la dépréciation de son adaptateur httpx ; il ne concerne pas le runtime HTTP.

Reconstruction du bundle Lambda : un timeout de téléchargement pip a interrompu l'installation. Le builder prépare désormais un répertoire temporaire, garde le dernier bundle valide jusqu'à installation complète, vérifie les empreintes des roues, augmente le timeout et réutilise un cache isolé. La reconstruction suivante et la synthèse CDK ont terminé avec code 0. Aucun service AWS n'a été exécuté ni déployé.

La note de concept décrit désormais ce socle local et les étapes différées. Correction factuelle de l'ancien état d'inscription : la déclaration de l'utilisateur en JRN-004 est reprise ; aucune admissibilité ni soumission n'est déduite.

### Préparation de la revue — 2026-10-05

Le rattrapage d'activité garde un `resumeCursor` après la dernière page ; les curseurs authentifiés sont chiffrés avec AES-GCM pour protéger les clés privées rencontrées lors de la découverte. Les tests de confidentialité et de rattrapage ainsi que la recette Docker ont été rejoués après ce changement.

La génération des preuves en heure de Paris a révélé l'absence de base IANA dans le Python Windows (`ZoneInfoNotFoundError`). Les tests précédents utilisaient le fuseau par défaut du modèle, qui n'était pas revalidé ; ils ne prouvaient donc pas la validation d'un fuseau fourni explicitement sur Windows. `tzdata` 2026.5, paquet maintenu pour Python, est désormais une dépendance verrouillée. Une recette supplémentaire fournit explicitement `Europe/Paris` et refuse un fuseau inexistant. Référence consultée le 2026-10-05 : [zoneinfo Python](https://docs.python.org/3.12/library/zoneinfo.html).

Les preuves générées enregistrent les empreintes des sources, du lock, du bundle Linux, du template et de l'image, ainsi que les comptes de tests et checks de reprise sans données des fixtures. La revue finale n'a pas encore attribué de score à ce jalon.

### Première revue et corrections — 2026-10-05

Le sous-agent `review_stage1` a attribué **8,1/10, FAIL** au jalon `c7368732f13a2534b229f34fb2fd78b66351718ab5a12c8f542a9d4e79169f1c`, après avoir rejoué les 53 tests et vérifié les empreintes. Il a reproduit un défaut élevé sur DynamoDB Local et ElasticMQ : une commande acceptée, publiée puis perdue avant consommation restait `READY` sans `RUN`, avec quota occupé ; une première livraison après quinze jours ne la réparait pas. L'ancien test de message vieux confirmait l'absence d'intention et ne couvrait pas cette garantie. L'intention est désormais créée dans la transaction d'acceptation et à chaque transition vers `READY`, puis clôturée lors d'une pause ou annulation. Le consommateur ancien réconcilie la tâche canonique sans rejouer le réveil, et l'exécution contrôle toujours les droits actuels. Les recettes de perte de file et livraison tardive sont ajoutées, notamment sur les émulateurs réels ; leur validation finale reste à effectuer.

Deux autres écarts sont corrigés : la préparation Cognito conservait le Hosted UI classique, incompatible avec `prompt=login` documenté. CDK 2.272.0 prépare explicitement Essentials, managed login v2 et un branding du client avec les valeurs Cognito. Sources consultées le 2026-10-05 : [authorization endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html) et [ManagedLoginBranding CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-cognito-managedloginbranding.html). Aucun essai Cognito ni coût AWS n'est déduit de ce correctif. La réduction d'une durée d'accès ne demande plus une preuve fraîche ; prolongation, suppression d'expiration et réactivation continuent à l'exiger. Un nouveau test de réactivation a d'abord échoué car son horloge de domaine était avancée tandis que l'émetteur JWT conservait l'heure réelle ; la fixture place maintenant l'appartenance dans le passé puis revient à l'heure réelle avant la preuve, sans relâcher les validations applicatives.

Lors de l'inspection des signatures CDK sur Windows, le nettoyage jsii/Node a de nouveau affiché `ENOTEMPTY` après sortie utile et code 0. Les références générées doivent être contrôlées par une nouvelle synthèse et les assertions, indépendamment de ce symptôme de nettoyage. Suggestion d'amélioration : rendre le nettoyage temporaire jsii robuste aux verrous de fichiers transitoires Windows et distinguer clairement son diagnostic du résultat de synthèse.

### Validation des corrections de revue — 2026-10-05

`KOYORI_INTEGRATION=1 uv run --no-sync pytest -q --junitxml=artifacts/all-tests.xml` : **65 tests passés, aucune exclusion**, avec l'avertissement du client Starlette déjà documenté. Les files isolées réellement créées dans ElasticMQ sont purgées ou livrées tardivement puis supprimées par leurs propres tests ; la réparation termine la même tâche et libère son quota sans dépendre du message. Les tests protègent également reprise et amendement, bail valide, état suspendu/terminal, révocation actuelle et générations d'accès. `ruff check` et contrôle de format : succès. La réduction et l'expansion d'expiration passent désormais leurs recettes API.

Image runtime reconstruite puis services recréés. Le service utilitaire de permissions emploie maintenant aussi l'empreinte Python déjà fixée. `scripts/verify_local.py` : nouveau **PASS**, worker vivant tué après checkpoint, stockage/API redémarrés, même réponse idempotente, autre foyer refusé, même tâche achevée et activité retrouvée. Bundle Lambda reconstruit avec les dépendances inchangées ; synthèse CDK finale terminée avec code 0 et sans diagnostic de nettoyage. `pip-audit --path artifacts/lambda` : aucune vulnérabilité connue trouvée ; SBOM mis à jour. Le certificat public du magasin système est utilisé pour l'audit hôte, sans désactivation TLS.

Les preuves et l'historique des revues sont conservés dans `docs/verification`. La seconde revue indépendante reste à effectuer ; aucun PASS de revue n'est encore annoncé. Les services Docker locaux restent actifs pour la démonstration. Aucun compte AWS contacté, aucune ressource ni coût AWS observé, aucun commit applicatif encore publié.

### Livraison finale — 2026-10-05

**Objectif et état :** première partie intégrale dans le périmètre accepté, terminée. La seconde revue de `review_stage1` donne **9,3/10, PASS**, sans constat actionnable restant observé ni défaut critique ou élevé restant. Révision examinée : sources `47056365fd20371e8ac97fbc314b78d5bfe0bb481a49fd989e81774982433f4a`, branche `gus-rlin/koyori-etape1`, base `81bb3d2505dcee08dc69dbb73e73cbf775422c5c`. Les mises à jour après ce verdict concernent uniquement les traces documentaires de livraison.

**Réalisations :** API FastAPI versionnée (`src/koyori/control`, contrats dans `docs/api.md`), droits personnels/partagés, foyers, membres, délégations, preuve fraîche et idempotence transactionnelle (`domain.py`, `security.py`, `store.py`). Tâches finies, checkpoints, inbox/outbox, intentions, baux, fencing, activité et repair (`src/koyori/workers`). Environnement Docker persistant (`compose.yaml`, `local/elasticmq.conf`), outils de clés et fixtures synthétiques (`demo.py`, `bootstrap.py`), sauvegarde/restauration isolée (`backup.py`), CI et scripts de preuve. Infrastructure AWS et bundle Lambda préparés (`infrastructure`, `scripts/build_lambda.py`). Documentation de lancement, exploitation, manifeste et note de concept actualisées. L'opération et l'émetteur local sont explicitement synthétiques ; aucun fournisseur, modèle, voix, MCP ou Alexa+ n'est connecté à cette étape.

**Choix et raisons :** une logique de domaine commune aux transports et une persistance canonique indépendante des files. Intentions enregistrées avec l'acceptation ou le contrôle des tâches ; le repair peut agir sans première consommation. Autorité et versions relues puis protégées transactionnellement, identités et générations distinctes des préférences futures. Step Functions Standard reste proposé pour la coordination de l'étape 3 ; les tentatives synthétiques finies utilisent les workers existants. Préparation Cognito Essentials/managed login v2/branding pour le parcours documenté de preuve fraîche. Aucun accès cloud, déploiement ou publication nécessaire à cette livraison locale.

**Difficultés et résolution :** incidents de certificats, tags d'image, pool réseau Docker, port occupé, préfixe d'index vide, timezone Windows, téléchargement du bundle et nettoyage jsii documentés aux jalons. Les trois écarts de la première revue sont corrigés et confirmés levés par une seconde revue, sans les présenter comme acceptables parce que les tests initiaux passaient. Le contrôle documentaire a d'abord utilisé le décodage implicite Windows pour les chemins Git accentués ; un décodage UTF-8 explicite a résolu la lecture sans renommer de fichier. Aucun blocage restant dans le périmètre livré.

**Ce qui a bien fonctionné :** test du même adaptateur sur DynamoDB Local, vraies files ElasticMQ isolées, injection de courses et revue indépendante au-delà des tests existants. Le reviewer a ajouté quatre conflits (réception/pause, réception/annulation, checkpoint/pause, acquisition/amendement), tous traités par refus des écritures périmées. La recette avec worker vivant interrompu et services redémarrés conserve le même taskId et checkpoint. Les empreintes relient les sources aux artefacts réellement exécutés.

**Vérifications :** 65 tests passés, zéro échec/erreur/exclusion, rejoués indépendamment ; ruff et format passent. Docker recovery PASS ; restauration complète dans de nouvelles tables et reprise validées par intégration. Bundle Linux construit avec roues et empreintes du lock, synthèse CDK sans compte et assertions du template réussies. Audit du runtime : aucune vulnérabilité connue trouvée ; il ne constitue pas une preuve générale de sécurité. Liens Markdown locaux résolus, diff Git sans erreur d'espacement, aucun fichier privé ou artefact runtime généré stagé. Les cinq services actifs correspondent à l'image enregistrée ; `/health/ready` répond 200 sur le port 8088. Preuves : `docs/verification/stage1.md`, `review-stage1.md`, `artifact-evidence.json` ; rapports bruts et SBOM générés sous `artifacts`, ignorés par Git. Qualification réelle AWS et exécution distante GitHub non effectuées.

**Retour sur les outils :** `senior-code-basics` a servi à comprendre les chemins, vérifier les effets et adapter les recettes aux risques. uv 0.11.28 et Python 3.12.13 fournissent un environnement reproductible après utilisation du magasin système de certificats ; réutilisation souhaitée pour le lock commun local/Linux. FastAPI/Pydantic rendent les schémas et erreurs observables, boto3 sert effectivement DynamoDB Local et ElasticMQ ; réutilisation retenue grâce au même adaptateur et aux validations transactionnelles. Docker 29.8.0/Compose 5.5.1 démontrent la persistance et le redémarrage ; sous-réseau et port explicites limitent les conflits locaux. CDK 2.272.0 produit les ressources et IAM contrôlés par assertions ; réutilisation retenue, nettoyage Windows jsii à surveiller. PyJWT/cryptography vérifient les identités et protègent les curseurs ; aucun secret embarqué dans l'image API/workers. pytest/ruff/pip-audit apportent des résultats inspectables ; l'avertissement Starlette/httpx reste une dépréciation de l'outil de test. Le sous-agent Sol a réellement trouvé un défaut malgré 53 tests verts puis confirmé les corrections à 9,3/10. Aucun outil agentique, Kiro, Bedrock ou AgentCore utilisé. Aucun coût ni ressource AWS créés ; services locaux seuls actifs.

**Suite :** aucune implémentation restante pour la première partie locale acceptée. Développer mémoire et connecteurs lors de l'étape 2, puis coordination et canaux aux étapes prévues. Avant toute activation AWS, qualifier login/PKCE et preuve fraîche Cognito, IAM exécuté, conflits distribués, bus/SQS/DLQ, alarmes et restauration en quarantaine, et relever coûts et ressources réellement actives. Apache 2.0 est conservée ; le dépôt et la contribution Open Source complémentaire n'ont pas été publiés par cette tâche, aucune pull request ni fusion n'est revendiquée. La stratégie Alexa+ avec AWS Builder et Open Source reste celle de la note de concept ; admissibilité, contribution complémentaire et dossier anglais restent à préparer sur des observations réelles.

## JRN-008 — 2026-10-05 — Retouches ciblées avant PR

### Objectif et état

Polir la première partie avec les plus petits changements possibles avant l'envoi de la PR. État : terminé. Travail sur la branche existante `gus-rlin/koyori-etape1`, initialement propre au commit `4cb4393` ; modifications laissées dans l'arbre de travail pour inspection.

### Réalisations

Lecture du concept, du journal, des contrats et des chemins API, droits, persistance, workers, démonstration et vérification. Deux corrections dans `src/koyori/control/app.py` : les rejets précoces 413/422 passent par les en-têtes et la trace communs ; le gestionnaire HTTP conserve les en-têtes de Starlette, notamment `Allow` pour une réponse 405. Les recettes de `tests/test_control.py` vérifient aussi le JSON malformé, l'encodage invalide et l'absence de contenu métier dans les erreurs et logs. Contrat HTTP et preuves actualisés dans `docs/api.md` et `docs/verification`.

### Choix et raisons

Conserver le périmètre livré et limiter les retouches aux réponses d'erreur HTTP : en-têtes et trace communs pour les rejets précoces, conservation de l'en-tête `Allow` des réponses 405. Aucun ajout de dépendance ni refonte. La note de concept reste pertinente.

### Difficultés et résolution

Les réponses 413 pour un corps dépassant 32 KiB et 422 pour les arguments interdits sortaient du middleware avant ses en-têtes et son log communs. Le gestionnaire des erreurs HTTP perdait aussi l'en-tête `Allow` transmis par Starlette. Cinq cas ciblés reproduisent ces défauts avant correction, puis passent après correction ; impact limité au diagnostic HTTP et au contrat de méthode. La lecture du nom typographique du concept nécessite toujours le chemin découvert, comme en JRN-005. Ruff a normalisé les fins de ligne des deux fichiers Python après les patches ; le contrôle final passe. Aucun problème observé lors des constructions et de la recette Docker.

### Ce qui a bien fonctionné

La suite de référence passe sur les émulateurs existants ; renforcer les tests de frontière expose les écarts sans changer les règles métier. Les cinq cas ciblés échouent sur l'ancienne version et réussissent sur la correction. La vérification supplémentaire de l'API en conteneur confirme le comportement HTTP, avec un corps envoyé sans Content-Length pour le cas 413.

### Vérifications

- Référence avant modification : `KOYORI_INTEGRATION=1 uv run --no-sync pytest -q --junitxml=artifacts/polish-baseline-tests.xml` : 65 tests passés, aucune exclusion.
- Cinq cas HTTP ciblés : échecs attendus sur les en-têtes manquants avant correction, puis cinq succès. Suite complète corrigée avec `--junitxml=artifacts/all-tests.xml` : **68 tests passés, aucune exclusion**. L'avertissement Starlette/httpx de JRN-007 demeure.
- `ruff check src tests scripts infrastructure` et `ruff format --check src tests scripts infrastructure` : succès. Relecture du diff et contrôle d'espacement Git réalisés ; changements applicatifs limités au fichier API et à ses tests.
- `docker compose build api`, puis `docker compose up -d --no-build` : image reconstruite et services recréés. `scripts/verify_local.py` : **PASS**, même tâche récupérée après interruption du worker et redémarrage. Trois requêtes HTTP sur l'API en conteneur confirment 413/422/405, en-têtes communs, requestId et Allow ; santé prête 200.
- `scripts/build_lambda.py` et `python -m infrastructure.app` : bundle Linux et synthèse CDK reconstruits, codes de sortie 0. Les cinq tests de `tests/test_infrastructure.py` passent sur le nouveau template.
- `scripts/record_evidence.py` : concordance des sources embarquées confirmée, nouvelles empreintes et résultats enregistrés dans [les preuves d'artefacts](docs/verification/artifact-evidence.json). L'audit des dépendances de JRN-007 est conservé : lock et dépendances inchangés ; aucun nouvel audit exécuté.
- Pas de nouvelle revue par sous-agent ni de note attribuée aux retouches. Les documents distinguent explicitement la revue initiale à 9,3/10 de cette validation. Aucun contrôle AWS distant ou GitHub exécuté.
- Contrôle documentaire final : treize fichiers Markdown lus en UTF-8, trente références locales résolues, identifiants JRN-001 à JRN-008 uniques et croissants, rapport JSON cohérent. Les cinq services runtime actifs utilisent l'image enregistrée dans les preuves.

### Retour sur les outils

`senior-code-basics`, PowerShell, Git, rg, uv, pytest, Ruff et apply_patch : inspection, reproduction et correction ciblées utiles, réutilisation souhaitée ; retours généraux inchangés depuis JRN-007. FastAPI/Starlette et httpx servent réellement les contrôles de réponses et de traces. Docker/Compose reconstruit l'image et valide de nouveau la récupération ; boto3 exerce DynamoDB Local et ElasticMQ via les tests dans des namespaces isolés. CDK synthétise le bundle actualisé sans compte. Aucun appel AWS, coût cloud ou publication effectué ; les services Docker locaux restent actifs.

### Suite

Aucune action restante pour ces retouches. Commit et envoi de la PR restent à l'utilisateur. La qualification AWS réelle, la voix, les modèles et les connecteurs conservent les limites de JRN-007 et du manifeste. La licence Apache 2.0 est inchangée ; aucune contribution Open Source complémentaire ni publication n'est revendiquée.
