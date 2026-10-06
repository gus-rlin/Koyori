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

## JRN-009 — 2026-10-05 — Publication de la branche et ouverture de la PR

### Objectif et état

Pousser la branche et ouvrir une PR, sur demande explicite de l'utilisateur. État : terminé pour la publication et l'ouverture ; contrôles GitHub en cours. Cette demande remplace la suite de JRN-008 qui laissait la publication à l'utilisateur.

### Réalisations

Retouches enregistrées dans le commit `dbebb13` (`fix: preserve HTTP error headers and request traces`). Branche `gus-rlin/koyori-etape1` poussée sur `origin` avec suivi distant. [PR #1](https://github.com/gus-rlin/Koyori/pull/1) ouverte, non draft, vers `main`, et attachée à cette conversation. La PR couvre le socle complet et les retouches ; sa description distingue les preuves locales et les capacités AWS préparées. Publication consignée dans le présent journal et dans `docs/verification/stage1.md`.

### Choix et raisons

Conserver la branche existante et ses commits ; aucune réécriture ni fusion. Vérifier la branche distante, la base et l'absence de PR ouverte avant création pour éviter un doublon. Ajouter un commit documentaire après l'ouverture afin de conserver l'URL réelle et l'état observé des contrôles. Les preuves JSON de JRN-008 restent un relevé local antérieur à la publication.

### Difficultés et résolution

Aucun problème observé. Les avertissements Git de normalisation LF/CRLF n'empêchent pas les contrôles ni la publication.

### Ce qui a bien fonctionné

Git et GitHub CLI permettent de pousser la branche, créer la PR avec une description enregistrée dans un fichier ignoré et relire ses métadonnées. L'attachement Codex de la PR aboutit.

### Vérifications

`git fetch origin` et contrôle d'ascendance : `origin/main` reste la base de la branche. `git diff --cached --check` : succès. Aucun fichier de clés, `.env`, dump local ou artefact runtime généré suivi dans Git. Lecture GitHub : PR ouverte, non draft, base `main`, head correspondant au commit poussé ; deux contrôles `verify` observés en cours à l'ouverture. Les 68 tests, Ruff, recette Docker et synthèse CDK de JRN-008 restent les résultats locaux précédents ; aucun test applicatif répété pour cette publication. La réussite de la CI distante n'est pas encore établie.

### Retour sur les outils

`senior-code-basics` : contrôles proportionnés à une publication. Git via PowerShell : commit et push réussis. GitHub CLI 2.88.0 : création et inspection de PR réussies, réutilisation souhaitée pour les publications suivantes. `attach_artifact` : PR liée à la tâche avec succès. Aucun déploiement, coût ni ressource AWS créé.

### Suite

Examiner le résultat des contrôles GitHub et la revue avant fusion. La PR est ouverte, aucune fusion réalisée. Licence Apache 2.0 conservée ; cette publication du dépôt principal ne prouve pas la contribution complémentaire du mini-défi Open Source.

## JRN-010 — 2026-10-05 — Corrections de la revue automatisée de la PR #1

### Objectif et état

Corriger les deux constats de la revue automatisée du commit `dbebb13a4b`, avec la plus petite diff possible, puis enregistrer et pousser la mise à jour sur la [PR #1](https://github.com/gus-rlin/Koyori/pull/1). État : terminé pour les corrections et vérifications. Cette entrée accompagne leur commit et publication sur la branche de la PR.

### Réalisations

`scripts/build_lambda.py` fixe le conteneur du bundle sur `linux/amd64`, correspondant aux fonctions Lambda x86_64 préparées. `src/koyori/domain.py` retire logiquement le lien de découverte et décrémente `householdCount` avec la révocation ; ajout et création de foyer utilisent ce compteur protégé transactionnellement. Une réinscription réactive le lien et réserve une place, en conservant la nouvelle génération d'accès. Régressions ciblées dans les tests de contrôle et d'intégration ; assertion de l'architecture dans le test du template. Preuves actualisées dans `docs/verification` et description de la PR actualisée en conservant son texte anglais.

### Choix et raisons

Réutiliser le compteur et les écritures conditionnelles existants plutôt qu'ajouter une suppression au magasin ou compter un historique paginé. Les tombstones conservent l'historique et la réinscription, sans restaurer les anciens grants. Fixer seulement la plateforme du builder suffit à conserver l'architecture CDK existante. Sources officielles consultées le 2026-10-05 : [paquets Python Lambda](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html) et [docker run](https://docs.docker.com/reference/cli/docker/container/run/).

### Difficultés et résolution

Quatre cas reproduisent les défauts de révocation avant correction et passent après correction : compteur non décrémenté, refus après huit révocations, création de foyer également bloquée et lien de réinscription non réactivé explicitement. Aucun hôte ARM64 réel n'a été utilisé ; le build a été exécuté avec un défaut Docker ARM64 et les trois bibliothèques natives produites ont été vérifiées directement comme x86_64.

GitHub CLI 2.88.0 : `gh pr edit 1 --repo gus-rlin/Koyori --body-file .local/pr-stage1-body.md` échoue avec `missing required scopes [read:project]`, alors qu'une simple modification de description est demandée. Impact : édition bloquée par cette commande. Contournement réussi : `gh api --method PATCH repos/gus-rlin/Koyori/pulls/1 --input .local/pr-stage1-update.json`, avec le même accès au dépôt, sans élargir les permissions. Suggestion d'amélioration : ne pas exiger la lecture des projets pour une édition limitée au corps de la PR. Aucun blocage restant.

### Ce qui a bien fonctionné

Les fixtures existantes permettent de reproduire le plafond et de vérifier les anciennes délégations sans ajouter de dépendance ni modifier l'API de stockage. Le test DynamoDB Local démontre que l'ajout concurrent invalide toute la révocation préparée, puis que le rejeu HTTP ne décrémente pas deux fois le quota. La vérification ELF et les imports du bundle démontrent la concordance d'architecture sans la déduire de la réussite de la synthèse.

### Vérifications

- Quatre régressions de contrôle échouent avant correction puis passent après correction. `KOYORI_INTEGRATION=1 uv run --no-sync pytest -q --junitxml=artifacts/all-tests.xml` : **71 tests passés, aucune exclusion**. Ruff et contrôle de format : succès ; avertissement Starlette/httpx déjà décrit en JRN-007.
- Build Lambda avec `DOCKER_DEFAULT_PLATFORM=linux/arm64` : succès. Trois bibliothèques `.so` vérifiées ELF x86_64 ; imports de cryptography, pydantic-core et cffi réussis dans le conteneur x86_64.
- Synthèse CDK : code 0, puis cinq tests d'infrastructure réussis, dont architecture x86_64. Image Docker reconstruite et services recréés ; `scripts/verify_local.py` : **PASS**. `scripts/record_evidence.py` confirme la concordance des sources embarquées et actualise les empreintes et résultats.
- Dépendances et lock inchangés : audit de JRN-007 conservé, non réexécuté. Aucun essai sur hôte ARM64 physique ni sur Lambda déployée ; aucune nouvelle note de revue indépendante.
- Les deux contrôles GitHub du commit précédent `4a63a3a` sont réussis. Le résultat de la CI du correctif doit être consulté après publication ; aucun succès distant de ce correctif n'est anticipé.

### Retour sur les outils

`senior-code-basics`, Git, PowerShell, uv, pytest, Ruff et apply_patch : inspection et correction ciblées ; retours inchangés depuis JRN-008. `web.run` : documentations officielles AWS/Docker accessibles. Docker et CDK : bundle, architecture, récupération et template effectivement vérifiés. GitHub CLI : PR et CI précédentes inspectées, édition REST réussie après la friction ci-dessus ; PR attachée à la conversation. Réutilisation de ces outils retenue avec ce contournement pour la description. Aucun compte AWS contacté ni déploiement réalisé ; services locaux seuls actifs.

### Suite

Consulter la CI du correctif et les nouveaux retours de la PR avant fusion. Les mêmes limites de qualification AWS et de contribution Open Source complémentaire demeurent ; aucune fusion réalisée. Les traces de revue antérieures restent historiques, distinctes des deux corrections présentes.

## JRN-011 — 2026-10-05 — Réconciliation des pauses et des adhésions expirées, origine des preuves

### Objectif et état

Terminé pour les corrections et les vérifications des trois constats de la revue du commit `c8b7df1`. Cette entrée accompagne leur commit et leur publication sur la branche de la PR #1 ; aucune fusion demandée.

### Réalisations

Les tâches en pause gardent une intention durable de contrôle des droits. Le worker reprogramme ce contrôle tant que l'autorisation reste valable, sans checkpoint ni bail ; sinon il termine la tâche et libère son quota. L'ajout d'un membre retire les adhésions expirées, leurs liens et compteurs dans sa propre transaction. Le rapport distingue l'exécution GitHub Actions via `GITHUB_ACTIONS`.

### Choix et raisons

Réutiliser les intentions, révisions, révocations et transactions existantes ; aucune dépendance ni nouveau service. Le contrôle des pauses utilise l'intervalle de bail existant et le sweep de réparation. Les retraits d'adhésions sont regroupés avec une seule écriture du foyer ; le remplacement d'une adhésion expirée par celle du même principal conserve sa place mais change sa génération d'accès. Le signal GitHub est confirmé dans la [documentation officielle](https://docs.github.com/en/actions/reference/workflows-and-actions/variables), consultée le 2026-10-05.

### Difficultés et résolution

Les six régressions pertinentes échouent avant correction : trois pertes d'autorisation d'une pause, deux admissions après expiration, un rapport sous signal Actions. Après correction, le test DynamoDB atteint l'authentification mais échoue parce que son horloge est avancée de dix secondes alors que l'émetteur de preuve utilise l'heure réelle. Le scénario est repositionné dix secondes dans le passé, puis amené à l'expiration à l'heure réelle, sans modifier le contrôle de fraîcheur du produit.

### Ce qui a bien fonctionné

Les tests ciblés vérifient les défauts avant modification et réutilisent le même domaine contre MemoryStore et DynamoDB Local. L'injection d'une mise à jour concurrente du profil confirme le rollback des retraits préparés.

### Vérifications

- `KOYORI_INTEGRATION=1 uv run --no-sync pytest -q --junitxml=artifacts/all-tests.xml` : **79 tests passés, aucune exclusion**. Les six régressions auparavant en échec passent ; deux contrôles du rapport local restent passants. Ruff et format : succès. Avertissement Starlette/httpx déjà consigné en JRN-007.
- Image Docker et bundle Linux Lambda reconstruits ; services recréés. `scripts/verify_local.py` : **PASS**, avec interruption après checkpoint, redémarrage du stockage/API et reprise de la même tâche. Synthèse CDK : code 0 ; cinq tests du nouveau template réussis.
- `scripts/record_evidence.py` contrôle la concordance des sources embarquées et régénère les empreintes avec 79 tests. Le rapport effectivement généré localement garde `githubWorkflowExecuted: false` ; les valeurs absent/faux/vrai du signal sont testées avec des artefacts synthétiques, sans prétendre à une exécution distante.
- Dépendances et lock inchangés : audit de JRN-007 réutilisé, non réexécuté. Aucun déploiement ou qualification AWS, ni nouvelle note de revue indépendante. Les deux contrôles GitHub de `c8b7df1` sont réussis ; aucun résultat distant du nouveau correctif n'est anticipé.

### Retour sur les outils

`senior-code-basics`, Git, uv, pytest, Ruff, PowerShell et apply_patch : retours inchangés de JRN-010. DynamoDB Local permet l'injection d'un conflit réel ; `web.run` confirme le signal officiel GitHub Actions. Docker et CDK vérifient les artefacts reconstruits et la reprise. GitHub CLI inspecte la PR et permet de mettre à jour sa description via l'API REST, contournement documenté en JRN-010. Aucun service AWS distant utilisé ; services Koyori locaux actifs.

### Suite

Consulter la CI et les nouveaux retours de la PR avant fusion. La libération des quotas de tâches en pause intervient au contrôle périodique des droits ; le retrait des adhésions expirées est réalisé à l'admission suivante. Le socle n'étant pas déployé sur AWS, aucun rattrapage de données de production n'est requis. Les limites de qualification AWS et de contribution complémentaire Open Source demeurent.

## JRN-012 — 2026-10-05 — Estimation qualitative du chantier le plus long

- **Objectif et état** : terminé ; identifier le chantier probablement le plus long à coder, sans établir de calendrier chiffré.
- **Réalisations** : lecture de la note de concept, du plan en quatre étapes et des dernières entrées du journal. Estimation : étape 3, orchestration autonome persistante, pour la combinaison planification, reprise, replanification, échéances et apprentissage. L'étape 2 constitue un autre chantier lourd par la mémoire et la fiabilité des connecteurs.
- **Choix et raisons** : estimation qualitative fondée sur les dépendances et cas de panne décrits ; aucune durée mesurée ni décision de changement de périmètre. Le socle dispose de validations locales consignées en JRN-011 ; sa qualification AWS reste à faire. L'accès effectif à Alexa peut influer sur le calendrier indépendamment du volume de code.
- **Difficultés et résolution** : aucun problème observé dans l'analyse documentaire ; absence de mesures de durée par chantier, donc classement provisoire.
- **Ce qui a bien fonctionné** : le découpage par contrats et preuves de fin permet de distinguer volume de développement, validation et dépendances externes.
- **Vérifications** : cohérence relue avec les étapes 2 à 4 du plan et JRN-011 ; aucune inspection de code ni exécution de tests, non nécessaires à cette estimation.
- **Retour sur les outils** : PowerShell, rg et apply_patch utilisés pour consulter les documents et enregistrer l'estimation ; aucune API externe utilisée.
- **Suite** : affiner les estimations au démarrage de chaque étape à partir d'un périmètre et de critères de fin concrets.

## JRN-013 — 2026-10-05 — Seconde partie : mémoire et connecteurs contrôlés

- **Objectif et état** : terminé le 2026-10-06 ; étape 2 implémentée seule par l'agent principal, puis revue indépendante finale **9,3/10**, au-dessus du seuil demandé. Cette livraison est du code validé localement et de la préparation AWS ; les fournisseurs distants restent à qualifier.
- **Réalisations** : mémoire, contexte, engagements dérivés, connecteurs, budgets, devis/approbations et registre d'actions dans `src/koyori/{memory,semantic,calendar,actions,stage2,stage2_contracts}.py`, routes HTTP et workers dédiés. Commerce persistant simulé ; adaptateurs Google/Titan/S3 présents et testés avec doubles explicites. Quatrième table, KMS, index vectoriel, séparation IAM et sept Lambda préparés dans `infrastructure/`. Recettes, tests, documentation et note de concept actualisés. Branche `gus-rlin/koyori-etape2` ; entrées JRN-012/JRN-014 et fichier Devpost d'une autre tâche conservés.
- **Choix et raisons** : réutiliser identité, transactions conditionnelles et outbox du socle ; Google Calendar OAuth, commerce persistant simulé, Titan V2 et S3 Vectors selon le TDD. Les fonctionnalités de coordination, voix et MCP restent aux étapes suivantes.
- **Difficultés et résolution** : Docker arrêté, erreurs de fixture et de recette, compatibilité des anciens membres, chaîne TLS, disque plein et sept défauts reproduits en revue : détails et solutions ci-dessous. Aucun blocage de code restant.
- **Ce qui a bien fonctionné** : lecture préalable du skill `senior-code-basics`, des documents et de l'historique ; réutilisation des transactions conditionnelles ; tests de courses déterministes puis DynamoDB Local ; traces durables indépendantes de l'effet externe ; revue reproduisant des défauts absents de la première suite.
- **Vérifications** : **135 tests passés, aucune exclusion**, dont 13 intégrations ; Ruff, format, contrôle du diff, synthèse CDK, image et bundle reconstruits ; deux recettes Docker PASS et audit runtime sans vulnérabilité connue. [Preuves](docs/verification/stage2.md), [rapport de revue](docs/verification/stage2-review.md), [empreintes](docs/verification/artifact-evidence.json). Aucun déploiement, appel réel Google/Titan/S3 Vectors ou workflow GitHub exécuté pour ce diff.
- **Retour sur les outils** : `senior-code-basics`, PowerShell, rg, Git, apply_patch, uv 0.11.28, Python 3.12.13, pytest, Ruff, Docker 29.8.0/Compose 5.5.1, CDK, boto3/Botocore 1.43.108, httpx 0.28.1 et cryptography 50.0.2 utilisés. DynamoDB Local/ElasticMQ valident persistance et transactions ; HTTPX MockTransport et transport Botocore intercepté vérifient les contrats sans appels externes. Ces outils sont réutilisables, avec les limites et frictions ci-dessous. Documentations officielles via web.run consultées les 2026-10-05/06. Aucun coût ou ressource AWS distante observé ; services locaux Koyori actifs. Aucune contribution Open Source complémentaire publiée ou fusionnée dans cette tâche.
- **Suite** : qualifier Google OAuth/sync/push/révocation, Titan/S3 Vectors, IAM exécuté et restauration sur un compte de recette avant usage distant ; conserver coûts et retours réels. Coordination, apprentissage inféré, voix et MCP restent aux étapes 3/4. Aucun commit, push ou PR de cette étape créé dans cette tâche.

### Point de contrôle — implémentation et premières validations

- Mémoire canonique, index chronologique/journalier, contexte borné, engagements dérivés, préférences et procédures déclaratives implémentés. Correction/effacement modifient la révision et l'époque de confidentialité ; les vecteurs sont rechargés depuis les objets actuels. Les reçus d'idempotence ne conservent pas le texte effacé.
- Devis, approbations avec preuve fraîche, budgets entiers et réservations transactionnelles, intentions commerciales stables, modification/annulation et fournisseur simulé persistant implémentés. Une réponse absente conserve les fonds et déclenche seulement le rapprochement ; la révocation bloque les envois encore non engagés.
- Google Calendar : OAuth à état unique, PKCE, sélection de calendriers, scopes de lecture, chiffrement AES-GCM avec contexte propriétaire/connexion, refresh sous bail, sync incrémental paginé, expiration de curseur et notifications vérifiées. Adaptateurs Titan V2/S3 Vectors et plafond journalier d'appels préparés ; aucun appel réel Google/Bedrock/S3 Vectors exécuté.
- Premiers résultats : 30 tests ciblés passés avec doubles explicites, 3 recettes supplémentaires passées contre DynamoDB Local et 6 assertions du template AWS passées. Suite complète et recettes Docker encore en cours à ce point ; aucune note de revue anticipée.
- Docker Desktop a pu être lancé par `docker desktop start` ; services locaux récupérés et quatrième table `Connections` créée. CDK fournit sept fonctions et un index de 512 dimensions, sans déploiement. L'inspection CDK a affiché un avertissement de nettoyage temporaire jsii/Node `ENOTEMPTY` sous Windows ; l'inspection et la synthèse se sont néanmoins achevées. Impact observé limité au message de nettoyage ; aucune donnée du dépôt supprimée.
- Les premiers tests ont détecté une erreur du test de révocation : il passait la projection publique (sans clé fournisseur interne) à la méthode interne de recherche du simulateur. Test corrigé pour relire le registre canonique ; aucun défaut produit masqué. Les vérifications de chronologie ont motivé des index de références sans texte, plutôt qu'une recherche bornée par identifiants aléatoires.
- Réutilisation réussie du magasin transactionnel et des fixtures d'identité. `httpx` devient une dépendance runtime pour l'adaptateur HTTP ; `cryptography`, déjà verrouillé transitivement, est déclaré directement pour AES-GCM. Aucun SDK de planification, de voix ou MCP ajouté. L'avertissement Starlette/httpx déjà connu demeure.

### Difficultés de recette et corrections

La recette `scripts/verify_stage2.py` a finalement produit **PASS** : rappel de la bonne journée, correction/effacement, arrêt d'un processus vivant après commit fournisseur et avant reçu, réservation maintenue, stockage/API redémarrés, rejeu de la même action et rapprochement de la même opération. L'audit du bundle runtime a d'abord échoué sur la chaîne TLS Windows/PyPI ; le certificat public du magasin système est ajouté au bundle public de confiance local, sans désactiver TLS. Le nouvel audit retourne **aucune vulnérabilité connue trouvée**. Des avertissements de désérialisation du cache ont été ignorés par l'outil, qui a refait les requêtes ; aucun échec d'audit restant. La séparation des foyers et la priorité des purges ont aussi été vérifiées face à un quota d'embedding épuisé : le foyer bloqué ne suspend pas les autres projections, et une purge ne consomme pas d'appel de modèle.

La suite complète avec émulateurs a réussi : **113 tests passés, aucune exclusion**, avant les régressions supplémentaires. La recette Docker stage 2 a d'abord échoué dans son émission de preuve fraîche : arguments du helper `demo` incompatibles avec son contrat. Le script appelle désormais directement la fonction d'émission synthétique dans le conteneur privé, sans afficher le jeton. Une seconde exécution a atteint la réservation et reçu HTTP 503. Inspection canonique : `KeyError` sur `accessEpoch`, absent des anciens membres du volume local. Cause confirmée ; les nouveaux connecteurs reprennent la valeur historique 1 déjà utilisée par le socle. Régression ajoutée et réussie sur un membre privé de ce champ, avec commande confirmée. Trois nouvelles vérifications d'actions (compatibilité, webhook signé/dédupliqué, expiration avant envoi) portent les tests ciblés d'actions à 13 réussites. Les erreurs serveur consignent maintenant seulement la classe d'exception, en plus du request ID, pour faciliter le diagnostic sans exposer le contenu.

### Revue indépendante et corrections — 2026-10-06

Première revue du sous-agent `review_stage2` : **7,3/10, FAIL**, sur 117 tests rejoués réussis et aucune exclusion. Cinq défauts reproduits : écriture S3 tardive après correction/effacement déjà projeté ; seconde révocation Google ouvrant un chiffrement déjà effacé et panne bloquant les autres connexions ; traces HTTPX contenant calendrier et curseurs privés ; vingt anciens échecs monopolisant les lots ; retries Botocore hors plafond d'appels Bedrock. Ce résultat est conservé et ne satisfait pas le seuil demandé.

Corrections en cours : un enregistrement indépendant `MEMWORK` précède chaque effet S3, survit au remplacement de l'intention et réarme la version canonique même après `DONE`, avec réparation après interruption ; délai de reprise durable et priorité temporelle des intentions ; quota différé au prochain jour UTC ; une seule tentative HTTP par réservation Bedrock. Révocation locale répétée stable, erreurs isolées par connexion, réponse Google `invalid_token` reconnue comme terminale, distinction `invalid_client`/`invalid_grant` et logs HTTPX/httpcore restreints. Contrat Google de révocation consulté par le reviewer le 2026-10-06 : [revocation endpoint](https://developers.google.com/identity/openid-connect/reference#revocation-endpoint). Les tests utilisent explicitement transports interceptés et fournisseur vectoriel factice ; ils ne qualifient pas ces services à distance.

Difficulté supplémentaire : disque système saturé pendant une écriture, laissant `calendar.py` vide. La copie du bundle Linux construit avant modification est conservée et permet la restauration. La compression NTFS des sorties CDK puis la suppression ciblée de leurs fichiers générés ont rendu de l'espace disponible ; aucune source ni donnée locale de Koyori supprimée. La suppression récursive du répertoire avait été rejetée par la politique de l'outil ; nettoyage limité aux fichiers régénérables sous le chemin vérifié. Le template devra être régénéré avant toute preuve finale. Les deux premières régressions ajoutées avaient aussi des erreurs de fixture (forme des clés MemoryStore ; horloge avancée avant une preuve fraîche issue à l'heure réelle) : fixtures corrigées, sans assouplir le produit. **25 tests ciblés réussis**, incluant correction/effacement concurrents, interruption, plus de vingt intentions, reprise, transport Botocore, révocation et confidentialité des logs. Nouvelle revue et vérifications complètes encore à exécuter.

### Clôture et retour sur les frictions — 2026-10-06

La seconde relecture a détecté deux erreurs dans les premiers correctifs : le no-op de révocation assimilait perte d'accès et révocation terminée, laissant l'enveloppe ; le réarmement d'un échec S3 réinitialisait `retries`, gardant le délai à 30 secondes. Les tests reproduisent maintenant retrait d'accès puis DELETE, et trois pannes S3 avec délais 30/60/120 secondes. Révocation achevée identifiée par jeton effacé, demande en cours par `revokePending` ; compteur conservé pour la même révision. **29 tests ciblés** réussis et **4 tests stage 2 DynamoDB Local** réussis après correction.

Une trace `MEMWORK` indépendante a été préférée au seul réarmement après réponse : elle conserve la réparation si le processus meurt avant ce réarmement. Des clés vectorielles par révision auraient complexifié la purge et le bornage des candidats ; la clé par souvenir est conservée avec réparation durable et relecture canonique obligatoire. La réparation après interruption attend 120 secondes, contre un runtime Lambda borné à 60 secondes ; la qualification réelle de cette frontière reste à faire.

Après saturation, Docker Desktop renvoyait HTTP 500 ; ses logs signalaient `WSL_E_USER_VHD_ALREADY_ATTACHED` et un détachement impossible. Un premier redémarrage ne suffit pas. Arrêt Desktop, `wsl --shutdown` puis démarrage rétablissent le moteur ; les volumes et les données de démonstration sont conservés, comme l'attestent les recettes finales. Impact : reconstructions momentanément bloquées. Suggestion réutilisable : diagnostiquer et détacher proprement avant d'envisager une réinitialisation des données.

La reconstruction Linux rencontre ensuite `CERTIFICATE_VERIFY_FAILED`/`UnknownIssuer` sur PyPI. Le bundle public de confiance du poste est monté en lecture seule : `KOYORI_BUILD_CA_FILE` pour le builder Lambda, secret BuildKit temporaire `trusted_ca` pour l'image. Les builds réussissent avec TLS et hashes verrouillés ; le certificat supplémentaire du poste reste hors des artefacts. Procédure dans [docs/operations.md](docs/operations.md). Besoin important pour la reproductibilité sur ce réseau ; les autres postes gardent la configuration standard. Pour apply_patch, l'écriture interrompue par le disque plein a tronqué le fichier : gravité importante, résolution par copie du bundle précédent puis application des correctifs et vérification des sources. Amélioration souhaitable de l'outil : écriture atomique temporaire et conservation du fichier original si l'espace est insuffisant ; version de cet outil non disponible.

Validation finale : `KOYORI_INTEGRATION=1 uv run --no-sync pytest -q --junitxml=artifacts/all-tests.xml` : **135 réussites, zéro échec/erreur/exclusion**. Ruff, format et `git diff --check` réussissent ; image, bundle Linux et CDK régénérés. `scripts/verify_local.py` et `scripts/verify_stage2.py` : **PASS** sur les nouveaux artefacts. `pip-audit` : aucune vulnérabilité connue. `scripts/record_evidence.py` vérifie les sources du bundle et enregistre l'empreinte `1adbd296685194580166ad3569a31f95b28eb4b88903dba4365e8ee7e339ae86`. Avertissement Starlette/httpx préexistant inchangé. La note finale indépendante est **PASS, 9,3/10**, aucun constat confirmé ouvert : 116 tests hors intégration et 6 contrôles CDK rejoués par le reviewer, JUnit complet et nouvelles preuves relus. [Rapport complet](docs/verification/stage2-review.md). Le seuil demandé est atteint dans la portée code/local/préparation AWS, sans prétendre à une qualification distante.

## JRN-014 — 2026-10-05 — Conservation du rappel Devpost sur la candidature

- **Objectif et état** : terminé ; conserver dans un fichier Markdown l'e-mail fourni par l'utilisateur sur les retours produit et les conseils de soumission Build, Ship, Shape.
- **Réalisations** : création de [docs/hackathon-devpost-feedback-reminder.md](docs/hackathon-devpost-feedback-reminder.md), avec le texte anglais, l'échéance citée et des références aux documents du projet. Aucun élément simulé.
- **Choix et raisons** : conserver le contenu utile et sa langue d'origine ; retirer les tableaux vides, le logo et les liens de suivi du courriel. Distinguer la date d'archivage de la date d'envoi non fournie. Aucun changement de stratégie ou de périmètre produit.
- **Difficultés et résolution** : une première commande de lecture groupée échoue sans diagnostic ; les lectures séparées permettent de consulter les documents. Aucun blocage restant.
- **Ce qui a bien fonctionné** : le contenu fourni suffit à constituer l'archive sans dépendre des liens de suivi ni d'images distantes.
- **Vérifications** : relecture du fichier créé et comparaison avec le texte fourni ; contrôle des références locales. Aucun test de code nécessaire. Conditions du concours non revérifiées en ligne pour cette simple transcription.
- **Retour sur les outils** : PowerShell et rg pour la consultation, apply_patch pour l'écriture documentaire ; aucun outil, API ou SDK du concours utilisé dans cette tâche.
- **Suite** : utiliser ce rappel lors de la préparation du dossier et poursuivre les retours factuels dans le journal. L'entrée JRN-013 reste en cours indépendamment de cet archivage.

## JRN-015 — 2026-10-06 — Publication de l'étape 2 et ouverture de la PR

- **Objectif et état** : terminé pour le push et l'ouverture de la PR de l'étape 2, sur demande explicite de l'utilisateur ; contrôles GitHub en cours. Cette demande reprend la publication laissée ouverte à la fin de JRN-013.
- **Réalisations** : branche `gus-rlin/koyori-etape2` avancée vers `origin/main` (`29a3eb3`), dont l'arbre est identique à la base locale ; la PR #1 du socle est déjà fusionnée. Commit `076e59b` enregistré et poussé sur `origin` avec suivi distant. [PR #2](https://github.com/gus-rlin/Koyori/pull/2) ouverte vers `main`, non draft, et attachée à cette conversation. Un commit documentaire complémentaire conserve ce résultat réel dans le journal.
- **Choix et raisons** : PR vers `main`, sans inclure le rappel Devpost ni les entrées JRN-012/JRN-014 d'autres tâches. Ces changements restent dans le workspace ; sélection du contenu du journal dans l'index Git, sans réécrire leur historique local. Publication limitée au code et aux preuves de l'étape 2.
- **Difficultés et résolution** : la première lecture groupée de la note de concept échoue ; lecture par chemin obtenu avec `Get-ChildItem` réussie. Le premier staging via Python décode les noms Git avec l'encodage Windows par défaut et échoue sur le nom Unicode de la note ; décodage UTF-8 explicite des listes Git `-z`, puis staging réussi. Aucun fichier de travail modifié par ce contournement.
- **Ce qui a bien fonctionné** : inspection de GitHub avant publication pour éviter doublon/base incorrecte ; fast-forward sans changement de fichiers ; staging séparé des entrées du journal sans effacer les travaux voisins. Description anglaise enregistrée dans un fichier ignoré et passée avec `--body-file`, puis métadonnées de PR relues.
- **Vérifications** : empreinte des sources inchangée et identique à la preuve de JRN-013 (`1adbd296685194580166ad3569a31f95b28eb4b88903dba4365e8ee7e339ae86`) ; 50 fichiers staged comparés au workspace, en tenant compte de LF/CRLF, et `git diff --cached --check` réussi. Aucun secret, certificat PEM, `.local`, dump ou bundle généré ajouté. Résultats locaux conservés : 135 tests, deux recettes PASS, audit et revue 9,3/10 ; aucun test applicatif répété pour une publication sans modification de code. Lecture GitHub : PR ouverte/non draft, base et head corrects. Au premier contrôle, deux jobs `verify` sont queued/in progress pour push et pull_request ; aucune réussite CI distante anticipée.
- **Retour sur les outils** : `senior-code-basics`, PowerShell, Git et GitHub CLI 2.88.0 permettent commit, push, création et inspection de PR ; `attach_artifact` réussit. Réutilisation souhaitée de cette procédure, avec décodage UTF-8 explicite sous Windows. Retours antérieurs en JRN-009/JRN-010 ; aucune ressource AWS créée.
- **Suite** : examiner CI et revue avant fusion. Google/Titan/S3 Vectors et IAM réels restent à qualifier ; la publication du dépôt principal ne prouve pas la contribution complémentaire Open Source.

## JRN-016 — 2026-10-06 — Corrections de la revue automatique de la PR #2

- **Objectif et état** : terminé pour les correctifs, la validation, le commit/push et la mise à jour de la [PR #2](https://github.com/gus-rlin/Koyori/pull/2), conformément à la demande de l'utilisateur ; suite CI distante encore en cours à la clôture.
- **Réalisations** : PATCH conserve les champs omis et valide le résultat fusionné ; une clé expirée devient réutilisable sous garde canonique et transactionnelle, sans que l'effacement de l'ancien souvenir libère la nouvelle clé ; le contexte journalier lit les partitions UTC de la plus récente à la plus ancienne ; les projections planifient une purge durable à expiration, sans embedding ; l'empreinte source utilise LF et un tri explicite des chemins POSIX, les bundles gardant une empreinte des octets exacts.
- **Choix et raisons** : réutiliser les primitives de transaction et les intentions `MEMERASE` existantes. Le hash d'idempotence et la preuve fraîche du PATCH portent sur les champs fournis, tandis que la validation porte sur le contenu fusionné. Les changements voisins JRN-012/JRN-014 et le rappel Devpost sont conservés hors de cette publication.
- **Difficultés et résolution** : les cinq défauts sont confirmés par lecture et régression. **Correction factuelle de JRN-013/JRN-015** : l'empreinte `1adbd296685194580166ad3569a31f95b28eb4b88903dba4365e8ee7e339ae86` concernait le checkout Windows ; elle ne correspondait pas aux octets normalisés par Git dans le commit publié. Le tri implicite des chemins était aussi dépendant de la plateforme. La nouvelle convention sera comparée aux blobs Git avant publication. Les notes de revue antérieures restent historiques ; elles ne couvrent pas ces défauts signalés ensuite.
- **Ce qui a bien fonctionné** : régressions exécutées avant correction, garde des deux ordres de concurrence sur DynamoDB Local, reprise des index anciens, puis comparaison de l'empreinte aux blobs Git. Les 42 tests ciblés et les 149 tests complets passent ; revue indépendante 9,4/10.
- **Vérifications** : `uv run --no-sync pytest -q tests/test_stage2_memory.py tests/test_evidence.py` avant correction : 8 échecs attendus, 12 réussites. Après correction : mémoire, adaptateurs sémantiques et preuves, 32 réussites. CI des commits précédents : les deux jobs GitHub sont désormais réussis. Vérifications complètes, reconstruction et revue finale encore à exécuter.
- **Retour sur les outils** : skill `senior-code-basics`, PowerShell, Git, apply_patch, uv, pytest et Ruff effectivement utilisés ; primitives existantes adaptées sans nouvelle dépendance. Aucun appel réel Google/Bedrock/S3 Vectors ni déploiement AWS.
- **Suite** : examiner la fin de CI et les retours de la PR avant fusion. La réparation des vecteurs legacy peut nécessiter un premier rappel puis le passage du worker ; comportement documenté et testé. Les fournisseurs distants et IAM restent à qualifier.

### Point de contrôle — compatibilité et concurrence

Le sous-agent `review_stage2` a reproduit deux cas complémentaires : des vecteurs créés par le worker publié restent `DONE` et ne sont pas purgés par le nouveau sweep ; un renouvellement préparé avant expiration peut committer après le remplacement de sa clé et laisser deux préférences actives. Le rappel réarme maintenant les anciens candidats expirés sous garde canonique et CAS de l'intention. La première recherche legacy peut rester vide jusqu'au prochain passage du worker ; le test couvre rappel, redémarrage, purge et retour du candidat vivant. `Memory.change` garde également le slot de la clé : le renouvellement préparé perd face au remplacement. La course inverse a échoué sur DynamoDB Local avant correction, puis les **42 tests ciblés** passent après correction, dont les cinq intégrations stage 2.

L'expiration pendant une écriture S3 est couverte par un double fournisseur ; la purge après redémarrage réussit avec un quota d'embedding déjà épuisé. Le renouvellement remplace l'ancien calendrier de purge. Les lectures d'archive respectent exactement la borne de 500 même sur deux partitions. Le contrôle `record_evidence.py --check-source` vérifie la preuve publiée et rejette une source altérée ; il est ajouté à la CI avant les builds. Les artefacts runtime sont reconstruits après ces derniers changements, sans appel fournisseur réel ni nouvelle dépendance.

### Validation finale et revue

`KOYORI_INTEGRATION=1 uv run --no-sync pytest -q --junitxml=artifacts/all-tests.xml` : **149 réussites, zéro échec/erreur/exclusion**, dont 14 intégrations DynamoDB Local. Ruff, format et contrôle du diff passent. Image Linux, bundle Lambda et CDK reconstruits ; les deux recettes `verify_local.py`/`verify_stage2.py` produisent **PASS** sur ces nouveaux artefacts. `pip-audit` ne trouve aucune vulnérabilité connue. Avertissement Starlette/httpx préexistant inchangé.

La preuve JSON et `--check-source` concordent avec le checkout. Contrôle additionnel du staging : empreinte recalculée directement depuis les **59 blobs Git** = `8d9f8807e64aacc060643b11fe00c4fae738a2c1fff553e155044fb9afa4b5d2`, identique à la preuve staged ; `git diff --cached --check` passe. Cela remplace la convention erronée de JRN-013/JRN-015 sans réécrire l'historique.

Verdict indépendant final du même reviewer : **PASS, 9,4/10**, aucun constat confirmé ouvert. Il a rejoué 37 tests ciblés et 135 tests hors intégration (14 intégrations désélectionnées explicitement), recalculé l'empreinte des blobs, vérifié les sources et hashes des artefacts, puis relu JUnit complet, recettes et SBOM. [Rapport actualisé](docs/verification/stage2-review.md). Google/Titan/S3 Vectors et IAM réels restent non qualifiés. GitHub CI du nouveau commit encore à observer à ce point ; aucune réussite distante anticipée.

### Publication et premier contrôle distant

Commit `ecf9669` (`fix: preserve memory patches and repair expiration lifecycle`) créé et poussé sur `gus-rlin/koyori-etape2`. La PR #2 reste ouverte vers `main` ; son head relu correspond au commit. Sa description expose les comportements corrigés, 149 tests et la revue 9,4/10 ; l'attachement à cette conversation réussit. Le journal et le rapport conservent les anciennes observations comme historiques, avec correction factuelle explicite de l'empreinte. Les travaux voisins JRN-012/JRN-014 et le rappel Devpost restent hors de ces commits.

GitHub CLI 2.88.0 : `gh pr edit --body-file` échoue car son chemin GraphQL exige `read:project`, bien que seule la description soit modifiée. Impact limité à la mise à jour de la description ; aucun blocage du push. Contournement réussi avec `gh api --method PATCH repos/gus-rlin/Koyori/pulls/2 --input` et fichier JSON local ignoré, sans demander de nouveaux scopes ni afficher de jeton. Friction déjà rencontrée en JRN-010 ; suggestion : ne pas exiger la lecture des projets pour modifier seulement une description.

Vérification après commit : les 59 blobs de `HEAD` produisent l'empreinte publiée exacte. Runs GitHub push `37384010450` et pull_request `37384015358` démarrés pour `ecf9669`, encore en cours au contrôle. Le job pull_request a déjà réussi le nouveau `--check-source` sur Linux, Ruff, format et le build Docker ; build Lambda en cours. La suite distante complète n'est pas déclarée réussie. Un commit documentaire complémentaire conserve ce résultat réel de publication.

## JRN-017 — 2026-10-06 — Seconde série de corrections de la PR #2

- **Objectif et état** : terminé pour les correctifs, conservés dans `b80d5b1`, puis validés et publiés avec l’étape 3 ; clôture et preuves cumulatives dans JRN-019. La PR #2 étant déjà fusionnée, ces corrections sont publiées sur les deux branches réunies.
- **Réalisations** : le worker sémantique désactivé termine les intentions sans vecteur ni embedding, sous garde de la révision canonique ; les dates de contexte sans bornes civiles représentables sont refusées en 422 ; les partitions UTC utilisent une arithmétique indépendante de la plage timestamp du système. La perte d'appartenance, de profil personnel ou de génération d'accès déclenche une révocation durable du connecteur, puis révocation Google et effacement chiffré du jeton. Les admissions WATCH/CHANNEL sont écrites avant le fournisseur et récupérables après interruption ou notification initiale.
- **Choix et raisons** : conserver les primitives de transaction, la boucle CALRUN et l'enveloppe existantes. L'autorité perdue est un état terminal du compte connecté, distinct d'une panne temporaire de Google ; sa restauration concurrente invalide la décision de révocation sous gardes. Un watch utilise une seule tentative avec identité préadmise et expiration explicite à deux heures ; une réponse perdue attend une notification authentifiée ou cette expiration avant nouvelle création. Le polling continue pendant l'incertitude. Aucun retry aveugle du watch ni nouvelle dépendance.
- **Difficultés et résolution** : les régressions initiales produisent 12 échecs et 35 réussites. Sur ce poste, les dates voisines pourtant représentables produisaient aussi `OSError` via `datetime.fromtimestamp` ; calcul des dates UTC par ajout à l'époque, sans fonction C du système. Le commentaire ancien annonçait à tort que l'admission précédait l'appel Google ; l'ordre réel et le commentaire sont maintenant corrigés. Les résultats fournisseur restent des doubles et transports interceptés.
- **Ce qui a bien fonctionné** : régressions avant modification, tests de réponse watch perdue et de notification arrivant avant la réponse, tests des deux issues d'un conflit de finalisation ; réutilisation des gardes d'autorité pour éviter une révocation basée sur une lecture dépassée. Les 47 premiers tests ciblés passent ; contrôles supplémentaires de concurrence et DynamoDB Local en cours.
- **Vérifications** : mémoire/calendrier avant correction : 12 échecs, 35 réussites ; après correction : 47 réussites. Ruff et format passent. Les deux CI de `f823a82` sont maintenant réussies (push `37384141943`, pull_request `37384148492`). Suite complète, artefacts, recettes et revue de ce nouveau diff encore à exécuter.
- **Retour sur les outils** : `senior-code-basics`, PowerShell, rg, Git, apply_patch, uv, pytest, Ruff ; HTTPX MockTransport et FakeGoogle vérifient les contrats sans appel Google réel. Documentation officielle consultée le 2026-10-06 : [push et notification initiale](https://developers.google.com/workspace/calendar/api/guides/push), [events.watch et TTL](https://developers.google.com/workspace/calendar/api/v3/reference/events/watch), [channels.stop](https://developers.google.com/workspace/calendar/api/v3/reference/channels/stop). L'identité stable ne fournit pas une garantie d'idempotence de création ; sans resource ID connu, l'arrêt n'est pas disponible, d'où l'expiration bornée. Réutilisation des outils justifiée par les régressions observables.
- **Suite** : terminer les vérifications avec les nouveaux artefacts et la revue indépendante, publier sur la branche existante. Google/Titan/S3 Vectors et IAM réels restent non qualifiés. Préserver les travaux voisins JRN-012/JRN-014 et le rappel Devpost.

### Point de contrôle — durée effective du canal

La première suite complète passe avec **168 tests**, dont 16 intégrations DynamoDB Local. La revue indépendante confirme un P2 complémentaire : Google peut limiter la durée du canal à moins de deux heures ; le seuil fixe d'une heure recréait alors des canaux à chaque passage, et la notification initiale ne récupérait pas son expiration effective. Trois régressions échouent avant correction (réponse normale, perdue, tardive). L'admission conserve maintenant son instant de création et un `renewAfter` calculé selon la durée effective ; les échéances de réponse et notification sont cumulées par minimum, sans prolongation ni glissement du seuil. Les **55 tests mémoire/calendrier** passent ensuite, Ruff et format également. La première recette socle est PASS, mais les artefacts et preuves seront reconstruits après ce dernier changement avant publication.

### Reprise pour intégration des étapes 2 et 3

La demande du 2026-10-06 autorise la réunion et le push des deux branches. Les corrections locales de cette entrée sont conservées dans un commit dédié avant fusion ; leur validation cumulative et publication seront consignées dans l'entrée d'intégration à la fin du journal. La PR #2 est déjà fusionnée dans `main` au contrôle GitHub. Les résultats précédents restent historiques et ne prouvent pas encore le comportement du code réuni.

## JRN-018 — 2026-10-06 — Troisième partie : coordination autonome et apprentissage

*Correction d’identifiant lors de l’intégration : cette entrée portait JRN-015 dans le worktree isolé. JRN-015 désigne déjà la publication de l’étape 2 ; le contenu historique ci-dessous est conservé sous JRN-018.*

- **Objectif et état** : terminé pour l'implémentation, la qualification locale et la préparation AWS des six blocs de l'étape 3 ; code écrit par l'agent principal seul dans un worktree isolé. Revue finale indépendante **PASS, 9,2/10**, seuil demandé atteint après deux séries de corrections. Qualification distante **NOT_RUN**, faute d'identifiants AWS.
- **Réalisations** : branche `gus-rlin/koyori-etape3`, worktree géré `koyori-etape3/Koyori`, base `fb5f310` conservant les 51 fichiers de l'étape 2 initiale. Plans typés, adaptateur Strands/Nova, objectifs durables, coordination bornée, routines/réveils, amendement/pause/reprise/annulation, apprentissage sourcé et notifications dans `src/koyori/`, avec routes et workers. CDK, Compose, scripts de qualification et tests ajoutés/adaptés. Contrats dans [docs/stage3.md](docs/stage3.md), API, exploitation, manifeste, README et note de concept actualisés ; [preuves](docs/verification/stage3.md) et [trois revues](docs/verification/stage3-review.md) conservées. Fournisseurs commerciaux simulés ; aucun appel réel Nova, Google ou achat. Aucun fichier ni état Git du checkout d'origine modifié par cette tâche.
- **Choix et raisons** : réutiliser magasins transactionnels, identités, devis, budgets, actions et reçus de l'étape 2. Plans bornés dans `Domain`, modèle proposant un contrat strict sans autorité fournisseur, quotas durables avant chaque appel, sources contrôlées avant checkpoint/réserve/dispatch. Fermer chaque tentative après une attente durable ; rapprochement des actions indépendant. Strands retenu conformément au TDD, modes réel et simulation explicites ; décisions détaillées dans les points de contrôle ci-dessous.
- **Difficultés et résolution** : base locale de l'étape 2 copiée et snapshotée ; téléchargements pip tronqués contournés par le runtime Linux verrouillé avec uv ; fixtures, ports des helpers et recette répétable corrigés. Confidentialité d'un warning SDK corrigée et testée. Huit défauts reproduits par les deux premières revues corrigés avec 19 régressions. Nova/AWS demeure bloqué par l'absence d'identifiants ; aucune validation distante inventée. Symptômes, tentatives et limites sont conservés ci-dessous.
- **Ce qui a bien fonctionné** : isolation du checkout et des volumes/ports, contrôles transactionnels existants, crash d'un processus vivant après checkpoint, tests de courses et sources révoquées. La revue indépendante a identifié des défauts absents des recettes nominales ; leurs régressions échouent avant correction puis passent. Les empreintes relient les sources à l'image, au bundle et aux preuves.
- **Vérifications** : **205 tests réussis, zéro échec/erreur/exclusion**, incluant DynamoDB Local, en 88,47 s ; Ruff et format de 74 fichiers réussis, contrôle du diff réussi. Image et bundle reconstruits, synthèse CDK et neuf assertions d'infrastructure réussies ; trois recettes Docker finales **PASS**. Audit runtime : 52 composants, aucune vulnérabilité connue signalée. Reviewer : 66 tests ciblés et deux courses supplémentaires réussis, 37 modules du bundle identiques aux sources, empreintes et preuves contrôlées. [artifact-evidence.json](docs/verification/artifact-evidence.json) conserve les résultats ; qualification Nova [NOT_RUN](docs/verification/nova-qualification.json), IAM distant/Cognito/Google et workflow GitHub non exécutés.
- **Retour sur les outils** : Git, PowerShell, rg, apply_patch et worktrees Codex ont permis une implémentation et une reprise isolées. uv 0.11.28/Python 3.12.13, Docker client 29.8.2/Compose 5.5.1 : construction verrouillée et reprises locales observées ; approche à réutiliser. Strands 1.57.2 et Botocore/Boto3 1.43.108 exécutés avec transport Converse intercepté : contrat et quota vérifiés, warning privé isolé ; réutilisation réelle conditionnée à la qualification Nova. CDK 2.272.0 utile pour préparer Standard/Scheduler/IAM, sans déploiement. pytest 9.1.1, Ruff 0.16.10 et pip-audit 2.10.1 donnent des contrôles reproductibles ; module Python contournant le launcher Windows refusé. Documentations officielles consultées le 2026-10-06. Aucun coût AWS mesuré ni ressource AWS créée. Apache-2.0 conservée ; aucune contribution Open Source complémentaire publiée ou fusionnée par cette tâche.
- **Suite** : qualifier Nova/AWS et Google avec accès autorisé, puis préparer l'étape 4 voix/MCP. Comparer les corrections concurrentes de l'étape 2 avant intégration ; résoudre alors la collision de numérotation du journal (cette branche part de JRN-014, le checkout d'origine possède désormais ses propres JRN-015 à JRN-017). La stack locale `koyori-stage3` et ses volumes restent disponibles ; aucune ressource distante active créée par cette tâche.

### Point de contrôle — contrats, exécution et recettes ciblées

Plans stricts et graphe validé, Strands 1.57.2 avec quotas durables avant chaque requête Converse et retries SDK désactivés, objectifs sous baux/générations, devis et actions liés à l'époque de l'objectif, routines civiles versionnées, propositions d'apprentissage et notifications groupées implémentés. Step Functions Standard, Scheduler et séparation des credentials du lecteur d'agenda préparés dans le CDK. Plans bornés conservés dans des lignes `PLAN` de `Domain` ; cette décision évite un second magasin S3 pour moins de 24 Ko par plan et conserve validation/promotion/historique dans la transaction. Elle précise la proposition du TDD, sans annoncer une exécution AWS.

**30 tests ciblés réussis**, dont Strands/Botocore réellement exécutés avec transport HTTP intercepté, doublons et reprise des adaptateurs Step Functions/Scheduler. **4 recettes DynamoDB Local réussies** sur une nouvelle stack Compose isolée (`koyori-stage3`, ports 8890/9334, volumes distincts) : progression/replanification/annulation, course pause-dispatch avec rollback, occurrence unique et budget commun à deux objectifs. Les premiers échecs étaient des fixtures incompatibles avec les contrats existants (clé d'idempotence non UUID, comparaison du texte d'exception au lieu du code, contexte household périmé après création d'une routine) ; fixtures corrigées, sans assouplir les contrôles produit. Une reprise après pause obtient désormais un nouveau devis tout en conservant l'intention commercialement non exécutée ; seul l'état canonique `BLOCKED`/`REJECTED`, sans opération ni dépense fournisseur, permet cette reprise.

La construction du bundle Linux échoue sur `InvalidChunkLength` pendant le téléchargement pip, malgré la chaîne TLS publique déjà utilisée en JRN-013. Gravité : construction bloquée, sources intactes. Le build Docker avec uv est en cours ; le problème réseau/cache pip n'est pas attribué à Strands. Prochaine action : réessayer puis utiliser le runtime verrouillé de l'image si nécessaire, avec vérification de ses sources. Aucune recette Docker finale ni revue indépendante exécutée à ce point.

### Point de contrôle — qualification locale et limites distantes

Le builder pip reproduit trois téléchargements tronqués (`InvalidChunkLength`), y compris après essai sans cache. L'option explicite `scripts/build_lambda.py --runtime-image koyori-stage3:local` utilise uv 0.11.28 dans l'image Linux verrouillée, avec export du lock, hash obligatoires et chaîne TLS publique ; le bundle est construit. La cause réseau/proxy reste une hypothèse. Suggestion : rendre les téléchargements tronqués récupérables avec un diagnostic indiquant le paquet et un retry borné. Le certificat additionnel est monté sans clé privée et n'entre pas dans l'image. `uv sync --system-certs` résout aussi le refus local `UnknownIssuer` lors du rebuild editable ; aucune vérification TLS désactivée.

Les recettes Docker des étapes 1 et 2 passent sur la stack distincte. Une première reprise pointait le helper hôte vers les ports du checkout initial ; `worker_environment()` aligne désormais ports hôte et Compose, et les nouveaux workers sont inclus dans les arrêts/reprises. La recette étape 3 découvre le refus de l'ETag initial `"0"` par la route de politique de notifications ; correction alignée sur le budget existant et test de non-régression API. Une exécution suivante confirme plan/reprise/pause/commande puis subit `RemoteProtocolError` sur un GET ; conteneur API vérifié vivant, sain, sans OOM. La cause réseau/keep-alive n'est pas confirmée ; seuls les GET de qualification sont repris au maximum trois fois, sans relancer une mutation ni masquer un échec d'état.

Une première suite complète donne **180 tests réussis, aucun skip**, émulateurs et template inclus. Les ajouts suivants couvrent création initiale de politique, apprentissage/activité privée, débordement des notifications, deux lectures simultanées, réutilisation du quota de routines et retrait de l'autorité d'une routine. Contrôle ciblé : 10 tests limites/routines réussis. Les groupes de seize débordent désormais dans un groupe supplémentaire au lieu de perdre des objets ; les historiques de routines annulées ne consomment plus le quota actif.

La lecture du chemin de synchronisation confirme que la révision de connexion ne représente pas un changement des événements. `CALVERSION` et des dépendances typées séparent contenu et droits ; les mises à jour visibles invalident le plan et bloquent une ancienne action avant dispatch, sans nouvelle révision de connexion. Une sync sans changement ne provoque pas de raisonnement, et un état partiel ne constitue pas un agenda vide. Les tests avec fournisseur Google fictif, dont changement matériel/no-op/sync partielle, passent ; aucune qualification Google réelle déduite de ces fixtures. Un conflit d'invalidation est désormais repris avec relecture canonique et signalé au consommateur s'il persiste.

Le script opt-in `scripts/qualify_planner.py --live` réalise son contrôle préalable avec IMDS désactivé sur le poste : **NOT_RUN, aws_credentials_unavailable**, zéro cas exécuté et aucun appel Nova. Huit fixtures FR/EN, comptes absents/capacité inconnue/sources hostiles, sont disponibles pour un accès autorisé futur ; jusqu'à seize requêtes facturables, aucune action fournisseur. Aucun coût AWS mesuré, aucune ressource distante créée. Les contrats, limites de région US/consentement, manifestes, API, exploitation et note de concept sont actualisés. La validation cumulative finale et la revue indépendante restent à terminer.

### Point de contrôle — recette complète avant revue

La recette étape 3 est **PASS** avec processus réel tué après plan commité, redémarrage stockage/API, idempotence, séparation propriétaire, attente sans raisonnement supplémentaire, pause/reprise, préférence acceptée, modification du même achat pour quatre, annulation avec reçu, occurrence unique et notifications. Un précédent essai répétait la clé fixe de préférence et produisait `MEMORY_KEY_EXISTS` après l'essai interrompu ; les fixtures utilisent désormais une clé distincte par exécution, sans modifier le contrat de mémoire.

La lecture de Strands 1.57.2 montre qu'un warning de parsing peut inclure les 200 premiers caractères de `raw_input`. Le test de transport injecte un warning privé synthétique et révèle sa présence avec la configuration initiale ; les namespaces SDK sont désormais isolés par handler nul, sans propagation, et le test passe. Les logs applicatifs conservent les codes d'état expurgés. Suggestion importante pour le SDK : remplacer ce texte de warning par taille/classe d'erreur et réserver toute inspection explicite à un canal autorisé.

L'audit runtime via pip-audit 2.10.1 retourne **No known vulnerabilities found**. Le launcher Windows `pip-audit` est refusé par le contrôle d'application (`os error 4551`) ; l'invocation du module par l'interpréteur Python existant réussit. Deux warnings de désérialisation de cache sont ignorés par l'outil ; l'audit se termine normalement. Les empreintes seront relevées dans le rapport de livraison.

La suite cumulative complète atteint **186 réussites, zéro échec/erreur/exclusion** (JUnit `artifacts/all-tests.xml`), incluant DynamoDB Local et les assertions CDK. Ruff, format et `git diff --check` réussissent. Le sous-agent `stage3_review` commence une revue indépendante en lecture seule de la totalité du diff depuis `fb5f310` ; aucun score anticipé. L'image et le bundle seront remis en concordance avec le dernier correctif de confidentialité des logs SDK, puis avec les corrections de revue éventuelles.

### Revue indépendante et corrections — premier passage

Le sous-agent `stage3_review` rend **FAIL, 7,3/10** sur le premier diff staged (SHA-256 `dd98fd99c3b490b9c5c8c28e8a4245e3d405b02a05103d89415e6c7abba4345a`) après 47 tests ciblés réussis. Cinq défauts sont reproduits : source découverte par un lecteur non persistée dans les dépendances, permettant un achat après effacement ; quota de routine en pause jamais libéré après perte d'autorité ; objectif d'un membre réadmis conservant l'ancien quota ; compte actif masqué par plus de cent connexions historiques ; fuseau inconnu renvoyant 503 plutôt que 422. Aucun autre défaut confirmé annoncé à ce passage ; le seuil demandé n'est pas atteint.

L'agent principal corrige seul les cinq chemins. Les références des lecteurs rejoignent atomiquement le contexte et `PLANDEP`, avec contrôle de toutes les révisions, plafond de 24 références et de cent clés de transaction. Les routines disposent d'une intention de contrôle des droits/horizon indépendante du réveil ; les quotas sont libérés de façon conditionnelle, y compris après pause. Une époque d'accès ancienne terminalise l'objectif même après réadmission, tout en laissant le rapprochement des actions fonctionner indépendamment. La découverte parcourt jusqu'à cinq pages de cent connexions, conserve huit comptes de l'époque actuelle et signale toute recherche incomplète. Les fuseaux inconnus deviennent des erreurs de saisie.

Huit régressions échouent avant corrections après ajustement de deux fixtures : réserver demandait une passe supplémentaire après le devis, et le helper de retrait utilisait un nom de méthode inexistant. Ces erreurs de tests sont corrigées avant de valider les défauts ; aucune règle produit assouplie. Après ajout de correction/effacement, pagination bornée et débordement des sources parallèles, **14 régressions passent** ; **31 tests ciblés** lecteurs/reprise/adaptateurs avaient également réussi avant le dernier contrôle de borne. Ruff réussit. La suite cumulative, les artefacts et la seconde revue restent à exécuter. [Rapport de revue](docs/verification/stage3-review.md).

### Revue indépendante et corrections — deuxième passage

La seconde revue donne **FAIL, 8,1/10** sur le diff `c45439cd3c5af727e448476ba6f95b207fed3fa320c5cd7e002763d006337b0d` : cinq constats initiaux corrigés, 36 tests ciblés rejoués réussis, mais trois nouveaux défauts confirmés. Une référence déclarée au troisième agenda, hors des deux instantanés du prompt, n'était pas ajoutée au contexte durable ; le contrôle de règle expirée supprimait le dernier réveil persisté après une panne jusqu'au lendemain ; le filtre d'époque ignorait un compte simulé neuf parce que sa création ne conservait pas `memberEpoch`. Deux sont des régressions du premier correctif, explicitement conservées dans l'historique. Le seuil n'est pas atteint.

Correction seule par l'agent principal : union de toutes les références acceptées, sans changement silencieux de révision et avec les mêmes plafonds/gardes ; livraison du dernier réveil existant par le chemin canonique avant libération du quota, uniquement si la règle reste active, non suspendue et autorisée ; génération d'accès persistée sur le nouveau compte simulé, compatibilité historique 1 et exclusion du compte antérieur à la révocation. Cinq régressions échouent avant correction : troisième agenda avec/sans événement, retard au lendemain avec/sans course contrôle/livraison et nouveau compte après réadmission. Les 200 tests complets du second état ont passé sans exclusion ; ce résultat n'est pas attribué au troisième état. La dernière série ciblée routines/objectifs/actions compte 50 réussites avant ajout des deux scénarios du troisième agenda. Troisième revue et validations cumulatives finales à poursuivre.

### Point de contrôle — troisième état et isolation

Les 37 tests ciblés lecteurs/agenda/reprise/SDK passent après les trois dernières corrections. La suite complète du troisième état donne **205 réussites, aucun échec/erreur/exclusion**, en 88,47 secondes ; Ruff, format (74 fichiers) et contrôle du diff réussissent. Le reviewer rejoue indépendamment 66 tests étape 3 (19 régressions, IAM, SDK, routines, sources, notifications et reprises), tous réussis, puis poursuit des courses ciblées. Aucun score final anticipé. Image reconstruite, bundle Linux et nouvelles recettes en cours.

Un contrôle en lecture seule du checkout d'origine détecte son évolution pendant cette tâche : HEAD `f823a82`, commits de publication/revue mémoire `2c75427`/`ecf9669`, neuf fichiers encore modifiés au moment du contrôle. Il ne correspond donc plus aux 51 fichiers initiaux copiés dans `fb5f310`. Aucun changement ni rollback de ce checkout n'est effectué par cette tâche ; l'isolation conserve la base documentée plutôt que d'importer silencieusement les modifications concurrentes. Avant intégration de la branche étape 3, comparer/fusionner ces corrections de l'étape 2. Ce contrôle ne démontre pas que le checkout d'origine est resté inchangé.

### Clôture — preuves renouvelées et revue à 9,2/10

La troisième revue indépendante rend **PASS, 9,2/10**, sans constat matériel ouvert, sur le diff staged SHA-256 `dc52a1d8da966d402e25081f3b481d384c6b4b58c35f796e2207952eb3f6d0d6`. Répartition : correction 2,9/3 ; validation 1,8/2 ; sécurité 2,7/3 ; effets/compatibilité 0,9/1 ; maintenabilité 0,9/1. Les 66 tests ciblés et deux courses forcées (révocation avant réveil tardif, correction avant lecture de mémoire) passent. Ce score évalue le code et les preuves locales/préparation AWS ; il ne mesure pas la qualité d'un modèle réel.

Les trois recettes de reprise Docker sont réexécutées après reconstruction et donnent **PASS**. La recette étape 3 contrôle le processus tué après plan, le redémarrage stockage/API, le rejeu idempotent, l'isolation du propriétaire, l'attente sans appel modèle, la pause/reprise avec nouveau plan, la préférence acceptée, le même achat amendé pour quatre, l'annulation avec reçu et l'occurrence unique avec notifications groupées. Le bundle Linux verrouillé contient 52 dépendances ; l'audit final ne rapporte ni vulnérabilité connue ni warning de cache. La synthèse CDK et les neuf assertions d'infrastructure passent. Le reviewer confirme les 205 tests JUnit sans exclusion, les trois rapports et les 37 modules du bundle identiques aux sources.

Les empreintes finales sont enregistrées le 2026-10-06 dans [artifact-evidence.json](docs/verification/artifact-evidence.json) : sources `e3ee48b93f552dd6500a87ab0b0ffd6b7be980eb8318122bb1548adde4d967d1`, bundle `6abf9c428826f8af8b404362398f5cd52f68c8d185a0a3eb31505d855bc2ac22`, template `48d2ab0450f5db8e4c700edb4e6abe7db3936acc66cbde24c4892a8c3ac7b77e`. L'identifiant réel de l'image inspectée est `sha256:46bc5fecbcff75d372512350fe7f6c14140c8586ff2731b866d900af6b22486d` ; le digest de configuration affiché pendant le build n'est pas utilisé comme preuve de cet identifiant. Après verdict, seuls les documents de livraison et cette entrée sont complétés ; aucun changement de code supplémentaire. Le dernier contrôle recalcule la même empreinte source, confirme les 37 modules identiques au bundle et vérifie 62 références Markdown locales sans cible manquante. Les artefacts locaux bruts restent ignorés dans `artifacts/`, et le commit de livraison reste local à la branche isolée.

Limites finales : qualification distante toujours **NOT_RUN**, aucun coût ni service AWS distant créé, commerces simulés, Google et IAM distribué non qualifiés. La stack Compose isolée reste disponible aux ports API 8098, DynamoDB 8890 et SQS 9334. Aucune publication, pull request ni fusion effectuée par cette tâche. Comparaison des corrections concurrentes et renumérotation du journal requises avant intégration ; aucune modification du checkout d'origine pour les résoudre ici.

## JRN-019 — 2026-10-06 — Réunion et publication des étapes 2 et 3

- **Objectif et état** : terminé ; les deux branches sont réunies, validées et publiées au même commit, avec deux checkouts propres, conformément à la demande de l’utilisateur.
- **Réalisations** : corrections locales de l’étape 2 conservées dans `b80d5b1`, fusion avec `8f44fcd` dans `b1c896d`, puis intégration du `main` publié dans `dd9210c`. Les entrées JRN-012/JRN-014 et le rappel Devpost sont conservés. L’entrée de l’étape 3 devient JRN-018 pour éviter le doublon JRN-015. Les preuves sont renouvelées sur le code réuni.
- **Choix et raisons** : fusion sans réécriture de l’historique ; référence de contenu `fb5f310`, snapshot initial de l’étape 2 dont l’étape 3 est issue. La base Git commune réelle précède ces fichiers, ce qui produit des conflits add/add artificiels. Une fusion à trois contenus depuis le snapshot conserve les correctifs de l’étape 2 et les ajouts de l’étape 3. Le générateur de preuves conserve la normalisation LF/tri POSIX et le contrôle `--check-source`, avec les trois recettes et le périmètre de l’étape 3.
- **Difficultés et résolution** : 35 fichiers signalés en conflit par la fusion Git ; la fusion avec le snapshot ne laisse qu’un conflit de code dans le périmètre/empreinte du rapport, résolu en combinant les deux comportements. Journal réuni explicitement, preuve JSON à régénérer après validation. `uv run` ne démarre pas pendant le conflit TOML ; utilisation temporaire de l’interpréteur existant `.venv/Scripts/python.exe` pour résoudre les contenus, sans installer de dépendance.
- **Ce qui a bien fonctionné** : sauvegarde ignorée des changements, de l’index et des deux journaux avant toute fusion ; conservation de chaque série de modifications dans l’historique.
- **Vérifications** : 241 tests réussis sans exclusion, trois recettes Docker PASS, Ruff/format et CDK réussis, audit des 52 composants sans vulnérabilité connue. Les 37 modules du bundle et les 83 blobs Git correspondent aux sources/proof. Les deux références GitHub sont relues au même commit ; détails et incidents ci-dessous. Aucun résultat ancien ni score de revue attribué automatiquement au résultat réuni.
- **Retour sur les outils** : `senior-code-basics`, Git, GitHub CLI, PowerShell, Python et apply_patch utilisés. Les outils de lecture des chats confirment que les deux tâches précédentes sont inactives. Aucun appel fournisseur ni déploiement AWS effectué.
- **Suite** : observer la CI distante et ouvrir une PR de l’ensemble vers `main` lorsque souhaité ; la demande présente porte sur les deux branches, publiées sans fusion distante supplémentaire. AWS/Nova/Google réels restent à qualifier. Les stacks locales sont conservées ; les artefacts bruts et sauvegardes de fusion restent ignorés.

### Point de contrôle — contenus réunis et certificat du builder

Les 66 fichiers modifiés comparables correspondent exactement à l’union calculée depuis `fb5f310` ; les quatre exceptions relues explicitement sont le journal, le générateur de preuves, sa preuve à renouveler et la référence du rapport de revue. Ruff et format passent sur les 74 fichiers Python. Le premier `docker compose up -d --build` échoue pendant le téléchargement PyPI (`UnknownIssuer`) ; aucun nouveau conteneur n’est démarré par cet essai. Le contournement déjà validé dans JRN-013/JRN-018 sera réutilisé : certificat public local approuvé monté par secret BuildKit, TLS conservé, puis démarrage sans rebuild implicite.

L’image fusionnée et son démarrage réussissent avec ce certificat. Les 117 tests ciblés mémoire/agenda/coordination/reprise passent ; les recettes étapes 1 et 2 donnent PASS. Le builder Lambda installe les 52 dépendances puis échoue en supprimant l’ancien bundle `artifacts/lambda.previous` après activation (`PermissionError` du montage Windows, Docker/Python 3.12). La commande complète ne sera pas déclarée réussie. Avant de poursuivre, vérifier le bundle actif contre les sources, puis nettoyer uniquement ce répertoire de build avec PowerShell et des chemins absolus contrôlés. La cause précise du refus Linux/NTFS reste non confirmée ; suggestion : documenter le diagnostic et prévoir une reprise de nettoyage après activation.

Le bundle activé contient les 37 modules Koyori, tous identiques aux sources, ainsi que Strands ; l’audit runtime ne trouve aucune vulnérabilité connue. La commande combinant vérification et suppression native est refusée par la politique d’exécution avant lancement. Après vérification séparée des chemins absolus, `Move-Item -LiteralPath` conserve l’ancien bundle dans `.local/merge-stage2-stage3/lambda-previous` plutôt que de le supprimer ; cette reprise réussit. Aucun fichier utilisateur ni certificat n’est retiré. La synthèse CDK est ensuite lancée sur le bundle actif vérifié.

### Validation cumulative du code réuni

`KOYORI_INTEGRATION=1 uv run --no-sync pytest -q --junitxml=artifacts/all-tests.xml` : **241 réussites, zéro échec/erreur/exclusion**, en 85,88 secondes. Les trois recettes Docker `verify_local.py`, `verify_stage2.py`, `verify_stage3.py` sont PASS sur l’image fusionnée. Ruff, format des 74 fichiers Python, contrôle du diff et recherche des marqueurs de conflit passent ; les 69 références Markdown locales contrôlées existent. La synthèse CDK réussit, avec ses assertions vérifiées par la suite complète. L’audit du bundle Linux porte sur 52 composants, sans vulnérabilité connue ; 37 modules Koyori identiques aux sources. Les 12 services locaux sont actifs et l’API est healthy.

[artifact-evidence.json](docs/verification/artifact-evidence.json) est régénéré après ces contrôles, puis `record_evidence.py --check-source` confirme l’empreinte portable. Les rapports étapes 2 et 3 distinguent leurs anciens compteurs et scores de cette nouvelle validation. Aucune nouvelle revue indépendante ni nouveau score n’est attribué à la fusion. Les limites AWS/Nova/Google réels restent celles des étapes précédentes ; aucun déploiement ni coût AWS nouveau. Commits et publication des deux références restent à vérifier avant clôture.

### Commits et premier essai de publication

La fusion `b1c896d` conserve `b80d5b1` et `8f44fcd`. Le commit `dd9210c` intègre ensuite `origin/main` (`79dd519`) sans changement de fichier ; l’empreinte reste `5f340a8147daca1567cf8761ba64857cedfc1b1dae9c0cab5542524854b176ee`. Les 83 blobs de sources staged correspondent à la preuve normalisée. Le worktree étape 3 avance par fast-forward au même commit ; les deux checkouts sont propres à ce contrôle.

`git push --atomic --set-upstream origin gus-rlin/koyori-etape2 gus-rlin/koyori-etape3` est refusé par GitHub avec `Internal Server Error` pour les deux références. Il ne s’agit pas d’un conflit ni d’un rejet de permissions annoncé. Aucun succès distant n’est déduit ; relire les références distantes puis retenter de manière bornée, sans force-push. La publication reste à clore.

La lecture distante confirme l’étape 2 toujours à `f823a82` et l’étape 3 absente. Un second push atomique est aussi refusé avec l’erreur serveur. L’atomicité du transport était un choix d’exécution, pas une exigence de la demande : tenter chaque référence séparément vers le même commit, sans modifier l’historique, permettra de déterminer si l’erreur dépend du push groupé. Conserver la réalité d’une publication partielle si un seul envoi réussit.

### Clôture — publication confirmée

Le push individuel de l’étape 3 avec les paramètres initiaux échoue aussi en erreur serveur. L’API GitHub confirme les droits `push` du dépôt ; la [page d’état officielle](https://www.githubstatus.com/) indique les services opérationnels au contrôle du 2026-10-06, ce qui ne confirme pas la cause des rejets observés. Le push de chaque branche avec `git -c http.version=HTTP/1.1 push --set-upstream` réussit. Ce succès est observé ; aucune cause HTTP/2 ou incident global n’est affirmé. Suggestion d’amélioration : le rejet distant devrait préciser la couche en échec plutôt qu’un simple `Internal Server Error`.

`git ls-remote --heads` confirme `gus-rlin/koyori-etape2` et `gus-rlin/koyori-etape3` toutes deux à `a7eefaa53ffa39bec68d24599017481f6ee08047`. Les branches locales ont les mêmes sources et avancent par fast-forward, sans force-push ; l’historique des deux étapes et celui de `main` sont conservés. La dernière mise à jour de ce journal sera synchronisée de la même manière sur les deux références. Aucun test applicatif répété pour ces seuls ajouts documentaires. Aucun run GitHub étape 3 n’est encore retourné au premier contrôle ; aucune réussite CI distante déclarée.

## JRN-020 — 2026-10-06 — Publication de la PR des étapes réunies

- **Objectif et état** : terminé ; créer la pull request de l’ensemble à la demande de l’utilisateur, après réunion et push des deux branches dans JRN-019.
- **Réalisations** : [PR #3](https://github.com/gus-rlin/Koyori/pull/3) ouverte, non draft, de `gus-rlin/koyori-etape3` vers `main`, titre `feat: add durable goal coordination and stage-two fixes`. Description en anglais : coordination persistante, routines, apprentissage sourcé, notifications et corrections restantes de l’étape 2 ; validations et limites réelles explicites. PR attachée à cette conversation. Correction documentaire : la note de concept renvoie maintenant à JRN-018 pour l’étape 3, conformément à la renumérotation réalisée en JRN-019 ; aucun changement produit ou code.
- **Choix et raisons** : une PR unique depuis l’étape 3, car les deux branches partagent le même contenu et la PR #2 est déjà fusionnée. Aucun doublon ouvert au contrôle initial. Conserver les deux références synchronisées par fast-forward et push atomique ; utiliser HTTP/1.1 par commande, contournement réussi en JRN-019. Les scores historiques de revue ne sont pas attribués à la nouvelle fusion.
- **Difficultés et résolution** : aucun problème observé lors de la création et de l’attachement. Une référence JRN-015 devenue obsolète dans la note de concept est corrigée après relecture. Les incidents de publication précédents restent documentés dans JRN-019.
- **Ce qui a bien fonctionné** : inspection des PR avant création, base explicite `main`, description passée par fichier ignoré `--body-file`, puis attachement immédiat de l’URL créée. Aucun changement de code pour cette publication.
- **Vérifications** : checkout propre au démarrage, `git fetch origin`, diff de PR inspecté, `git diff --check` et `record_evidence.py --check-source` réussis. Les preuves de JRN-019 restent celles du code publié : 241 tests sans exclusion, trois recettes Docker PASS, Ruff/format/CDK et audit des 52 composants. Aucun test applicatif répété pour les seules retouches documentaires. CI push encore en cours au contrôle ; aucune réussite distante anticipée. Métadonnées finales de la PR et égalité/propreté des deux branches à relire après publication de cette entrée.
- **Retour sur les outils** : skill `senior-code-basics`, PowerShell, Git, GitHub CLI et `attach_artifact` utilisés ; `gh pr create --body-file` et attachement réussissent. Aucun appel fournisseur, déploiement ni coût AWS nouveau.
- **Suite** : suivre les checks et retours de revue de la PR #3 avant fusion. AWS/Nova/Google réels et voix/MCP conservent les limites des étapes précédentes ; ouverture de PR distincte d’une fusion.

## JRN-021 — 2026-10-06 — Quatrième partie : canaux et qualification cumulative

- **Objectif et état** : terminé pour l'implémentation et la qualification locale ; étape 4 codée seule dans un worktree isolé, revue indépendante **9/10** après corrections. Les critères exigeant un backend déployé, des modèles et un agenda réels restent non acquis ; aucun déploiement ni qualification distante annoncé.
- **Réalisations** : worktree géré `koyori-etape4-complete/Koyori`, branche `gus-rlin/koyori-etape4`, base `f81df40` des étapes réunies. Contrats de session, admissions/tickets/délégations, registre commun MCP/voix, SDK MCP Streamable HTTP, transport WebSocket, adaptateurs Nova/Polly, signaux AppSync avec rattrapage durable, export personnel, effacement des souvenirs par lots et restauration en quarantaine. Infrastructure et images verrouillées, manifeste compatible, procédures et rapports français/anglais ajoutés. Transcriptions, planificateur et commerce des recettes restent simulés. Contribution Open Source complémentaire préparée comme proposition, sans extraction indépendante ni publication.
- **Choix et raisons** : réutiliser le domaine et ses transactions. MCP 2025-11-25 négocié explicitement ; aucune approbation ni permission accordée par outil. Mode partagé limité aux lectures partagées. Toute parole générative du modèle est supprimée ; annonces contrôlées via Polly afin d'éviter un faux succès financier avant reconnaissance d'un appel d'outil. Cette mesure réduit la conversation libre, compromis à qualifier avec la voix réelle.
- **Difficultés et résolution** : lecture PowerShell de noms avec apostrophe typographique échouée, puis réussie avec guillemets doubles. Le précédent checkout d'amorce `koyori-etape4/Koyori` a disparu entre deux contrôles ; cause non confirmée, branche intacte. Nouveau worktree créé depuis la même base, sans toucher le checkout principal. SDK `aws-sdk-bedrock-runtime` 0.11.0 : transport par défaut aiohttp sans duplex ; transport `smithy-http[awscrt]` 0.5.0 sélectionné avec HTTP/2 obligatoire. Launcher pytest Windows refusé (`os error 4551`) ; invocation du module Python utilisée, conforme au contournement historique.
- **Ce qui a bien fonctionné** : installation verrouillée uv avec certificats système, inspection directe des SDK installés, primitives de droits et de conditionnement transactionnel réutilisées ; courses DynamoDB Local, vérification HTTP sur TCP réel et revue indépendante ont révélé des défauts absents des fixtures initiales. Après correction : 297 tests et quatre recettes réussis, sans réduire les contrôles.
- **Vérifications** : suite cumulative finale **297 réussites, zéro échec/erreur/exclusion**, 101,90 s, sur les émulateurs explicitement isolés ; un warning de dépréciation Starlette/httpx. Quatre recettes Docker **PASS** sur l'image finale ; Ruff/format des 100 fichiers Python et diff réussis. Synthèse CDK, audit de 72 dépendances sans vulnérabilité connue, correspondance des 47 modules Lambda et runtime AMD64, construction/inspection ARM64 sans exécution native. Revue finale 9/10, 75 tests ciblés indépendants réussis. Preuves dans [rapport](docs/verification/stage4.md), [empreintes](docs/verification/artifact-evidence.json) et [manifeste](docs/verification/deployment-manifest.json). Contrôles distants et workflow GitHub non exécutés.
- **Retour sur les outils** : `senior-code-basics`, PowerShell, rg, Git, worktrees Codex, apply_patch et uv 0.11.28 ; MCP 1.30.0, AgentCore SDK 1.24.0, SDK Bedrock natif 0.11.0 et CRT 0.32.2 ajoutés pour les protocoles réels, usage distant à qualifier. Sources officielles consultées le 2026-10-06 : [MCP](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), [AgentCore WebSocket](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-websocket.html), [serveur MCP](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html), [Nova Sonic](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-getting-started.html), [AppSync](https://docs.aws.amazon.com/appsync/latest/eventapi/configure-event-api-auth.html). Aucun coût mesuré ni service distant créé.
- **Suite** : qualifier ARM64 natif, Cognito/PKCE, IAM, Nova/Polly, AppSync, Google et PITR AWS avec fixtures synthétiques, puis les trois parcours déployés et leur latence/coût audio mesurés. Extraire et valider la contribution complémentaire avant choix du dépôt et publication. Code conservé localement sur la branche isolée ; aucun push ni PR demandé.

### Point de contrôle — défaut concurrent et frontières de lecture

La première suite complète donne 272 réussites et un échec (90,24 s). Deux finalisations concurrentes perdent une condition de révision dans `Sessions.check(activity=True)` avant la transaction du tour. Cause confirmée par DynamoDB Local : écriture d'activité sans retry. Correction : recharger les droits et la session dans six tentatives maximum, et écrire au plus une fois par seconde. Les neuf tests ciblés sessions/concurrence passent ensuite, dont ticket consommé une seule fois et tour produisant une seule mémoire, tâche et réservation.

Le fence d'effacement lie désormais admissions et délégations à une génération de confidentialité ; les grants antérieurs restent refusés après fin de l'effacement. La lecture sonore revalide sources/révisions avant et pendant diffusion et propage les erreurs de la tâche de playback. Le test d'une correction par un autre membre pendant une lecture partagée passe. Restauration : une intention de retrait des vecteurs est recréée même si l'ancienne intention était terminée ou absente ; l'index et le nombre de shards sont préservés. Export : un souvenir expiré/inaccessible ne bloque plus une page entière.

Le contexte des canaux réutilise le lecteur d'agenda de l'étape 2, au plus deux comptes et six engagements. Le runtime ne reçoit toujours aucun credential Google. Tests de contrat : agenda personnel disponible, absent du mode partagé, refus lors de révocation fournisseur. Ce lecteur peut bloquer l'ouverture vocale si un agenda lié est indisponible ; aucune fraîcheur fournisseur fictive n'est annoncée.

SDK natif Smithy : l'inspection du resolver SigV4 révèle qu'une configuration construite directement ne fournit pas de chaîne de credentials par défaut. Un resolver refreshable utilise la chaîne boto3 existante, sans valeurs en logs ; son test de renouvellement passe. Le test du stream utilise les vraies classes d'événement, avec client intercepté ; Nova réel reste non exécuté. Les permissions de logs AgentCore sont corrigées vers le préfixe documenté des runtimes, et `/ping` vocal indique `HealthyBusy` pendant une connexion. Sources officielles IAM et Cognito resource binding relues le 2026-10-06.

Les 21 tests ciblés voix/mémoire/effacement/récupération/agendas, puis les six tests parole/SDK et les deux tests de rotation locale passent ; ces séries se recouvrent et ne constituent pas un nouveau compteur cumulatif. Ruff/format passent. Le warning Starlette/httpx reste observé. Documentation ajoutée dans `docs/stage4.md`, procédures actualisées, manifeste et concept corrigés ; proposition Open Source complémentaire préparée, sans publication. Image locale construite avec le certificat public par secret BuildKit, sans désactivation TLS ; artefacts finaux et revue restent à renouveler après les derniers ajouts.

### Point de contrôle — artefacts et qualification cumulative

La suite suivante passe : 281 tests, zéro échec/erreur/exclusion, en 91,78 s. Les 47 modules Lambda correspondent exactement aux sources ; les 47 modules installés dans l'image runtime AMD64 correspondent après normalisation LF. Le bundle Linux contient 72 dépendances auditées, sans vulnérabilité connue. Le premier audit échoue en validation du certificat PyPI ; `REQUESTS_CA_BUNDLE` vers le même bundle public approuvé permet l'audit avec TLS conservé. Il ne s'agit pas d'un audit réussi avant ce contournement.

La construction ARM64 échoue d'abord parce que `.dockerignore` exclut `start_runtime.py`, puis sur `/bin/sh` (`exec format error`, émulation indisponible ici). Correction du contexte et builder `BUILDPLATFORM` qui installe les roues de `TARGETARCH` : image ARM64 construite sans émulation. Premier essai du builder réutilise par erreur un binaire uv ARM64 dans le builder AMD64 ; stage uv fixé à `BUILDPLATFORM`, puis construction réussie. L'image est inspectée `arm64`, la variante AMD64 réussit ses imports voix/MCP/SDK/CRT. L'exécution native ARM64 reste non qualifiée ; aucun déploiement ECR/AWS. Suggestion réutilisable : séparer architecture du builder, roues de la cible et preuve d'exécution, et inclure cette construction dans la CI.

Les recettes Docker étapes 1 et 2 donnent PASS. Une relecture supplémentaire du contexte découvre que la date par défaut employait le fuseau du foyer au lieu de celui du profil ; corrigé et couvert par une fixture Tokyo/Paris de part et d'autre de minuit (les six tests MCP passent). Sources/artefacts et suite cumulative seront renouvelés après ce correctif. L'encodage du fichier de comparaison de modules était supposé UTF-16 à tort ; lecture UTF-8 réussie, aucun défaut d'image associé. Précontrôle distant : `NOT_RUN`, credentials AWS indisponibles, zéro appel facturable. Les rapports ne lui attribuent aucune qualification.

### Point de contrôle — HTTP MCP sur le réseau réel

La recette étape 3 est PASS. Le premier essai étape 4 échoue lors d'`initialize` : HTTP 200 puis `RemoteProtocolError` côté client Windows. Les tests TestClient avaient tous réussi. Le nouveau test TCP reproduit la panne. Diagnostic sans contenu personnel : le SDK et Uvicorn émettent `Content-Length: 180` avec 180 octets JSON ; le client socket reçoit `Transfer-Encoding: chunked` sans le cadrage correspondant. Le même appel sur le réseau Docker Linux réussit avec les 180 octets. L'hypothèse initiale d'un corps absent dans le SDK est donc corrigée ; une transformation extérieure est observée, sa couche exacte reste inconnue. `trust_env=False`, conversion du statut en entier et `Cache-Control: no-transform` ne résolvent pas la panne et ne sont pas conservés.

Contournement retenu : les réponses MCP laissent leur cadrage à l'hôte ASGI, sans `Content-Length` ; Uvicorn produit alors les chunks valides. Initialisation, découverte et refus d'authentification passent sur une vraie connexion TCP, ainsi que les six tests MCP précédents. Pas de contournement d'authentification, de retries masquant la panne ni de changement du SDK. Le test TCP désactive uniquement le lifespan, extérieur au comportement HTTP étudié. Friction importante pour la recette locale : le diagnostic réseau devrait indiquer une transformation de cadrage au lieu d'une simple fermeture. Images et preuves cumulatives à renouveler avant la revue.

### Première revue indépendante — 7,5/10 et corrections

Le sous-agent de revue demandé intervient après l'implémentation réalisée seul. Score provisoire **7,5/10**, seuil non atteint ; 33 tests ciblés exécutés par le reviewer, trois contre-vérifications locales et exemples d'annonces. Cinq défauts confirmés : huit Lambdas sans variables HTTPS exigées par `Settings` (P1), absence de lecture du fence Sessions pour les workers et des délégations pour le lecteur Google (P1), divulgation partagée/export non conditionnés au fence du propriétaire (P2), ledger ignorant une demande d'effacement acceptée avant ses premiers lots (P1), annonces de succès de lecture sur erreurs et omission de l'approbation en présence d'une action proposée (P2).

Corrections : configuration commune des onze Lambdas historiques ; `GetItem` limité à `RESTORE_FENCE` pour leurs workers, et `GetItem`/`ConditionCheckItem` limités à `CHANNELGRANT#*`/`VOICE#*` pour le lecteur ; assertions sur chaque environnement et rôle synthétisés. `Memory.read_checks` protège souvenir et fence du propriétaire, y compris absence, dans les canaux, playback, export, lectures REST et validation des sources du plan. Le ledger refuse de se créer tant qu'un effacement est `ERASING` ; la procédure exige de finir ces lots dans la source. Test DynamoDB Local : snapshot antérieur, ledger refusé pendant l'effacement, puis restauration avec texte supprimé et cible bloquée. Narration : erreurs explicitement non confirmées ou interdites, attente d'approbation prioritaire en FR/EN, sans preuve canonique inventée.

Les 36 tests ciblés confidentialité/recovery/parole/MCP/voix passent. Une invocation comportant deux noms de fichiers de test inexistants ne lance aucun test ; reprise avec les noms obtenus par `rg --files`. La série suivante donne 64 réussites et un échec de fixture : le resolver de template représentait l'issuer Cognito par une chaîne générique ; correction de cette fixture, puis les quatre contrôles d'infrastructure passent. Ce n'était pas un nouveau défaut de l'issuer déployé. La précédente suite de 283 réussites employait les endpoints de test par défaut (8800/9324), les variables opérationnelles fixées ne remplaçant pas `KOYORI_TEST_*` ; ses tables dédiées n'étaient pas la stack de cette recette. La suite finale sera exécutée explicitement sur les émulateurs isolés 8900/9344. Le cleanup du test de restauration couvre maintenant aussi sa quatrième table `Connections`.

Points solides relevés par la revue : domaine commun, autorité opaque recontrôlée, pas d'outil d'auto-approbation, absence de parole générative, budgets bornés, reçus durables et limites réelles explicites. Les lacunes trouvées montrent qu'une synthèse CDK réussie et une suite locale verte ne suffisent pas à vérifier les contrats de démarrage/IAM ni les fenêtres d'effacement. Aucun score final anticipé ; preuves cumulatives et seconde revue restent à renouveler.

### Seconde revue indépendante — seuil de 9/10 atteint

Le même reviewer relit les corrections, exécute indépendamment 75 tests ciblés en deux séries sans exclusion et donne **9/10**, sans constat matériel restant. Correction/autorité, confidentialité, robustesse, préparation du déploiement et tests obtiennent chacun 9/10 dans cette évaluation. Toutes les modifications sont réalisées par l'agent principal ; le reviewer travaille en lecture seule. Le score reste celui de l'implémentation et des preuves locales, pas de la qualité de voix, de l'IAM exécuté ou d'une qualification AWS réelle.

La suite finale sur les variables `KOYORI_TEST_DDB_ENDPOINT=http://127.0.0.1:8900` et `KOYORI_TEST_SQS_ENDPOINT=http://127.0.0.1:9344` donne **297 réussites, zéro échec/erreur/exclusion**, en 101,90 secondes. Un avertissement Starlette/httpx de dépréciation reste visible. Images locale, runtime ARM64 et AMD64 puis bundle Lambda reconstruits sur ce dernier état. Les 47 modules Lambda sont identiques aux sources, les 47 empreintes normalisées du runtime AMD64 aussi ; imports voix/MCP/SDK natif/CRT réussis. ARM64 inspectée comme telle, sans exécution native. Audit des 72 dépendances Linux : aucune vulnérabilité connue ; nouvelle synthèse CDK réussie. Les quatre recettes sur l'image finale et l'enregistrement des preuves restent à terminer avant clôture.

### Clôture — preuves finales et limites conservées

Les **quatre recettes Docker cumulatives donnent PASS**, réexécutées après les cinq corrections de revue. L'étape 4 vérifie initialisation MCP officielle, même objectif voix/MCP/REST, tâche poursuivie après fermeture, conversation retrouvée après redémarrage, rappel canonique FR/EN, rattrapage sans signal et rafale de quatre lecteurs. Les conteneurs API et voix embarquent les mêmes 47 modules que les sources finales. Sur 17 observations mixtes localhost MCP/session synthétique : p50 **58,64 ms**, p95 **197,11 ms** ; ces chiffres ne mesurent pas la voix réelle. Zéro appel à un modèle dans la recette vocale ; coût AWS non mesuré, aucun service distant créé.

Les [empreintes](docs/verification/artifact-evidence.json) sont renouvelées : source normalisée `6fc13bd4747d25cf439ddb1d6e4e31dc7f676fec992c9507877c71ae88fe0925`, image locale `sha256:039e26853d86954fe604a89cacc3c3a93b972beb7016d139442cb55a2eff5933`, bundle et template liés. `record_evidence.py --check-source` confirme la correspondance ; les 110 blobs de source staged correspondent aussi à cette empreinte. Le [manifeste](docs/verification/deployment-manifest.json) est `PREPARED_NOT_DEPLOYED`, images ECR non publiées et architecture native non qualifiée. Le précontrôle `qualify_channels.py --live` reste `NOT_RUN` faute de credentials ; il ne contient pas de driver complet de recette cloud. Aucun score de modèle, coût réel ou réussite de parcours déployé n'est inventé.

Ruff, format des 100 fichiers, diff et recherche des marqueurs de conflit/secrets passent ; 111 références Markdown locales existent dans les 21 documents contrôlés. Le checkout original est relu : branche `gus-rlin/koyori-etape2`, HEAD `f81df40f7b955209c6828eb8a34502aeeec3249d`, propre, identique à l'état initial. Les 14 conteneurs du projet `koyori-stage4` restent actifs, API healthy, et ses cinq volumes sont conservés (`dynamodb-data`, `elasticmq-data`, `issuer-keys`, `provider-key`, `public-keys`). Ports localhost : API 8108, voix 8109, DynamoDB 8900, SQS 9344 ; subnet `10.253.44.0/24`. Aucun volume ni ressource d'un autre projet supprimé. Arrêt de cette stack dans PowerShell : fixer `$env:COMPOSE_PROJECT_NAME='koyori-stage4'`, puis lancer `docker compose stop` avec les variables de la recette ; ne pas supprimer ses volumes si la reprise doit être démontrée.

Retour réutilisable : le domaine commun, les reçus canoniques et les contraintes transactionnelles fonctionnent sur redémarrage/concurrence ; les frontières HTTP, la configuration de chaque Lambda et les fences du propriétaire demandent des tests observables spécifiques. Les frictions, essais infructueux et corrections sont conservés dans les points de contrôle plutôt que masqués par la réussite finale. Les dernières retouches portent sur les documents et preuves ; aucune implémentation nouvelle après le verdict 9/10. Contributions et dossier de concours restent une préparation locale, distincte d'une publication ou d'une admissibilité.

## JRN-022 — 2026-10-06 — Publication de la quatrième partie

- **Objectif et état** : terminé ; branche `gus-rlin/koyori-etape4` poussée et [PR #4](https://github.com/gus-rlin/Koyori/pull/4) ouverte à la demande de l'utilisateur.
- **Réalisations** : commit `5531157` de l'étape 4 publié avec son journal dans le worktree isolé. PR non draft vers `main`, titre `feat: add MCP and voice channels with durable sessions`, attachée à cette conversation. Description en anglais : MCP et voix sur le domaine commun, sessions durables, annonces sourcées, activité, confidentialité et récupération ; preuves locales et qualifications réelles restantes explicites.
- **Choix et raisons** : base `main`, car la PR #3 des étapes précédentes est fusionnée et son HEAD `f81df40` est la base commune. `origin/main` est maintenant `4654b30`, sans différence de fichier avec cette base ; aucun rebase ou merge local nécessaire. PR prête pour revue, non draft ; conserver les limites réelles dans sa description. HTTP/1.1 par commande Git reprend le contournement observé en JRN-019, sans modifier la configuration globale.
- **Difficultés et résolution** : aucun problème observé lors du push, de la création ou de l'attachement ; incidents historiques référencés dans JRN-019 et JRN-021.
- **Ce qui a bien fonctionné** : contrôler la base distante et l'absence de PR existante avant création évite une PR empilée ou un doublon. Push HTTP/1.1 et `gh pr create --body-file` réussissent ; l'attachement immédiat rend la PR accessible dans la conversation. Les sources normalisées correspondent toujours aux preuves de JRN-021.
- **Vérifications** : checkout propre au démarrage, fetch, base commune, diff de PR et `git diff --check` contrôlés ; `record_evidence.py --check-source` réussi avant et après publication. `gh pr view` confirme PR ouverte, non draft, base `main`, branche exacte ; `git ls-remote` et HEAD de PR correspondent à `4a22fa3` au premier contrôle. Validations applicatives réutilisées sans les réexécuter pour cette publication documentaire : 297 tests, quatre recettes Docker PASS, revue indépendante 9/10, Ruff/format/CDK et audit de 72 composants (JRN-021). Deux checks GitHub `verify` en cours au contrôle ; aucune réussite CI distante anticipée. Dernière clôture documentaire à pousser puis égalité/propreté à relire.
- **Retour sur les outils** : `senior-code-basics`, PowerShell, Git, GitHub CLI, worktree Codex et `attach_artifact` utilisés ; publication et attachement réussis. Aucun appel fournisseur, déploiement ou coût AWS nouveau.
- **Suite** : suivre les checks et retours de revue de la PR #4 avant fusion. Qualifications AWS/Nova/Google réelles inchangées ; aucune fusion demandée. L'ouverture de cette PR du dépôt principal ne constitue pas la publication de la contribution Open Source complémentaire.

## JRN-023 — 2026-10-06 — Clarification de l'état de l'étape 4

- **Objectif et état** : terminé ; expliquer le décalage entre une lecture annonçant seulement les étapes 1–3 et la livraison de code de JRN-021. Correction de formulation : l'étape 4 est codée et validée localement, mais sa preuve de fin complète exige encore qualification et parcours déployés.
- **Réalisations** : contrôle des deux checkouts, des fichiers des canaux, du plan, du rapport de qualification et de la PR. Le checkout original reste sur `gus-rlin/koyori-etape2`, HEAD `f81df40`, README « parties 1, 2 et 3 ». Le worktree isolé est sur `gus-rlin/koyori-etape4`, HEAD publié `2b171bf`, README « parties 1 à 4 » ; MCP, voix, sessions, parole, activité et confidentialité y sont présents. PR #4 encore ouverte, non fusionnée.
- **Choix et raisons** : distinguer code implémenté, preuves locales/CI, publication de branche et qualification réelle. Le seuil de revue 9/10 porte sur l'implémentation locale ; il ne valide pas la preuve de fin déployée décrite par le plan. Le terme « étape terminée » employé sans cette portée serait excessif.
- **Difficultés et résolution** : le checkout visible conserve le README antérieur et son journal comporte une modification concurrente. Les deux branches portent désormais des entrées JRN-021 différentes, celle du checkout original étant encore non commitée au contrôle ; préserver les deux observations et résoudre les identifiants lors d'une intégration de ce travail parallèle. La lecture de chaque branche séparément explique le décalage documentaire sans déduire une absence du code dans la PR.
- **Ce qui a bien fonctionné** : recouper branche/HEAD, README, modules, critères du plan et état GitHub donne une réponse vérifiable ; une suite verte est séparée de l'accès réel aux services.
- **Vérifications** : `record_evidence.py --check-source` réussi ; contrôle des fichiers et critères d'étape 4. La PR #4 cible `main`, HEAD `2b171bf`, état `OPEN`, `mergedAt=null`. Deux checks `verify` sont `SUCCESS` ; le [run de branche](https://github.com/gus-rlin/Koyori/actions/runs/37402942652) est terminé avec succès sur ce même HEAD. Aucun test applicatif ou appel fournisseur répété pour cette clarification. `channel-qualification.json` reste `NOT_RUN / aws_credentials_unavailable` ; modèles, IAM, agenda, ARM64 natif et parcours déployés non qualifiés.
- **Retour sur les outils** : routine `senior-code-basics`, PowerShell, Git, `rg`, uv et GitHub CLI pour contrôle ciblé ; aucune nouvelle intégration ou ressource distante. La CI GitHub exécutée est désormais une réussite observée, distincte de la préparation documentée avant publication dans JRN-021/JRN-022.
- **Suite** : revue puis décision de fusion de PR #4 ; qualification réelle du backend et trois parcours du concept ensuite. La candidature et la contribution complémentaire conservent leurs limites documentées. Aucun déploiement ni fusion effectué par cette clarification.

## JRN-024 — 2026-10-06 — Corrections des contrats AgentCore de la PR #4

- **Objectif et état** : terminé pour les trois remarques fournies ; correctif `6f45c3b` publié sur `gus-rlin/koyori-etape4`, description de la PR #4 actualisée et trois discussions résolues. Diff limité aux deux modules, leurs tests, l'empreinte CI et cette entrée.
- **Réalisations** : `src/koyori/voice.py` expose `POST /invocations` avec une réponse fixe indiquant `/ws`, sans consommer un ticket ni exécuter un tour. `src/koyori/mcp_server.py` transmet `Mcp-Session-Id` à AgentCore et restitue la session, la version MCP, le statut HTTP, le type de contenu, `WWW-Authenticate` et `Retry-After`. Les autres en-têtes distants ne sont pas copiés. Deux régressions ajoutées aux tests existants ; aucune dépendance ni modification d'infrastructure.
- **Choix et raisons** : conserver le protocole HTTP du runtime vocal et son admission WebSocket ; corriger le proxy existant sans nouveau transport. Sources AWS relues le 2026-10-06 : [contrat HTTP](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html), [contrat MCP](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp-protocol-contract.html), [InvokeAgentRuntime](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-agentcore/client/invoke_agent_runtime.html). L'empreinte source dans `docs/verification/artifact-evidence.json` est actualisée pour le contrôle CI ; un complément distingue les 34 tests actuels des 297 tests et artefacts historiques de JRN-021, non reconstruits ici. Aucun changement de décision produit nécessitant une modification du concept.
- **Difficultés et résolution** : le test vocal reproduit le 404 initial. La première fixture du proxy utilise une configuration déployée incompatible avec l'identité locale ; elle est remplacée par des paramètres de test isolés, sans assouplir `Settings`. Le SDK intercepté vérifie les paramètres d'appel, y compris l'absence de session au premier appel puis sa réutilisation. Le warning de dépréciation Starlette/httpx déjà observé demeure, sans échec. Changements du journal du checkout principal préservés ; travail dans le checkout propre de la PR. `gh pr edit --body-file` refuse l'édition faute de scope `read:project` ; le PATCH REST de la PR réussit avec les permissions existantes, sans renouveler l'authentification. Impact limité à la commande d'édition ; suggestion : éviter la lecture des projets pour une édition du seul corps.
- **Ce qui a bien fonctionné** : `Stubber` de Botocore contrôle le contrat réel du SDK sans réseau AWS ; le scénario initialise une session puis conserve une réponse 401 et ses en-têtes, sans exposer l'en-tête `Authorization` distant. Le test HTTP confirme que le ticket vocal reste utilisable sur son chemin normal.
- **Vérifications** : `.venv/Scripts/python.exe -m pytest -q tests/test_stage4_mcp.py tests/test_stage4_mcp_tcp.py tests/test_stage4_voice.py tests/test_stage4_sessions.py tests/test_stage4_speech.py --junitxml=artifacts/pr4-protocol-tests.xml` : **34 réussites, zéro échec/erreur/exclusion**. Ruff check et format sur les 100 fichiers Python réussis ; diff relu et `git diff --check` réussi. Pas de suite cumulative, de reconstruction d'image/bundle ni de recette distante supplémentaire pour ce correctif ; la CI les exécutera sur la nouvelle révision.
- **Retour sur les outils** : `senior-code-basics`, PowerShell, Git, GitHub CLI, apply_patch, Python, pytest, Ruff et Botocore/Boto3 1.43.108 utilisés. Le modèle installé expose les champs MCP et `statusCode` documentés ; leur validation interceptée est réutilisable. Retours AWS réels inchangés depuis JRN-021, aucun coût ni ressource distante créé.
- **Suite** : HEAD local, référence distante et PR relus à `6f45c3b`, checkout propre ; deux checks CI encore en cours au contrôle, aucune réussite anticipée. Une quatrième remarque CORS apparue pendant la tâche reste ouverte, hors des trois remarques fournies. Qualification AWS réelle, reconstruction des artefacts et fusion restent distinctes de ces tests ciblés. Cette clôture documentaire sera publiée sans nouveau changement applicatif.

## JRN-025 — 2026-10-06 — État des manques et priorités du projet

*Correction de numérotation lors de la réunion : cette observation portait JRN-021 dans le checkout principal. JRN-021 désigne maintenant la quatrième partie ; son contenu historique est conservé sous JRN-025. Cette revue porte sur les étapes 1 à 3 alors visibles et précède la réunion de la quatrième partie et de la démonstration web.*

- **Objectif et état** : terminé ; répondre à « Qu'est-ce qui manque au projet ? » en comparant la vision, le plan des quatre étapes, le manifeste, les preuves et les chemins de code concernés. Revue ciblée, sans audit exhaustif ni modification applicative.
- **Réalisations** : distinction entre mécanismes locaux des étapes 1 à 3, adaptateurs externes préparés et expérience produit encore à construire. Manques identifiés : interface utilisateur et conversation vocale continue ; serveur MCP et transports voix/activité ; qualification Nova, Google Calendar et Titan/S3 Vectors ; qualification du déploiement, de l'identité distante et de la récupération ; mesures de qualité/latence/coût et essais utilisateurs ; dossier de démonstration et contribution Open Source complémentaire. Les achats demeurent simulés et l'agenda est en lecture seule ; les autres domaines de la vision ne disposent pas de connecteurs opérationnels dans le manifeste.
- **Choix et raisons** : recommandation, sans nouvelle décision d'architecture : qualifier tôt le modèle et un agenda de recette, puis relier une interface vocale minimale au domaine existant pour démontrer les trois parcours de la note de concept. Conserver le commerce simulé explicitement pour cette démonstration ; les transactions marchandes réelles constituent un élargissement ultérieur. Distinguer la fin du backend prévu en étape 4 des exigences minimales de candidature. La [FAQ officielle](https://amazonappdev2026.devpost.com/details/faqs), relue le 2026-10-06, autorise une expérience Alexa+ simulée sans appareil et indique qu'un dépôt public exécutable localement avec vidéo suffit, sans hébergement obligatoire. Le déploiement distant reste une qualification prévue par le projet, pas une condition supplémentaire imposée à la candidature par cette revue.
- **Difficultés et résolution** : aucun blocage de revue. La qualification Nova enregistrée reste `NOT_RUN / aws_credentials_unavailable` ; cette tâche n'a ni recherché ni configuré d'identifiants. Le statut `DELIVERED` de `src/koyori/notifications.py` rend un groupe consultable dans le flux HTTP ; aucun envoi audio ou push externe n'est constaté dans ce chemin. Cette distinction évite d'assimiler le flux local à une notification effectivement entendue.
- **Ce qui a bien fonctionné** : recouper `README.md`, `docs/delivery-manifest.md`, `docs/stage2.md`, `docs/stage3.md`, le plan de construction et les rapports JSON avec `src/koyori/planner.py`, `src/koyori/notifications.py` et les routes HTTP permet de séparer code existant, simulation et validation distante. Le journal JRN-019 fournit les dernières validations cumulatives du code réuni.
- **Vérifications** : `uv run --no-sync python scripts/record_evidence.py --check-source` réussi : empreinte enregistrée identique au checkout. `git diff --check` réussi avant ajout de cette entrée. Les preuves existantes rapportent 241 tests réussis, sans échec ni exclusion, et trois recettes Docker PASS ; ces tests et recettes ne sont pas réexécutés pendant cette revue. Inspection Compose : API healthy et services locaux actifs. Aucun appel de modèle, consentement Google, déploiement AWS, coût mesuré, essai utilisateur ni contrôle du statut GitHub distant réalisé ici. [Preuve cumulative](docs/verification/artifact-evidence.json), [qualification Nova](docs/verification/nova-qualification.json).
- **Retour sur les outils** : skill `senior-code-basics`, PowerShell, `rg`, Git, Docker Compose, uv et navigateur de recherche utilisés pour lecture et contrôle ciblés ; aucun nouveau SDK ni service intégré. Le [règlement officiel](https://amazonappdev2026.devpost.com/rules), relu le 2026-10-06, confirme vidéo publique de moins de trois minutes, retours sur les outils, documentation des usages AWS et références de contribution complémentaire Open Source. Aucun document de candidature final ni contribution complémentaire publiée identifié dans les fichiers inspectés ; cela ne prouve pas l'absence de supports extérieurs au dépôt.
- **Suite** : choisir le premier parcours vocal démontrable et obtenir une preuve de planification réelle sur données synthétiques, puis qualifier agenda/mémoire et interruptions de session. Mesurer le comportement observable avant d'élargir les connecteurs. Compléter ensuite récupération, exploitation et dossier selon le périmètre retenu. Priorités proposées à l'utilisateur, sans engagement de mise en œuvre dans cette tâche.

## JRN-026 — 2026-10-06 — Interface compagnon dans un worktree isolé

*Correction de numérotation lors de la réunion : cette entrée portait JRN-021 sur la branche interface. Son contenu historique est conservé sous JRN-026 ; JRN-021 désigne la quatrième partie.*

- **Objectif et état** : terminé pour la démonstration et ses validations ; créer l’interface de Koyori dans un nouveau worktree propre à la demande de l’utilisateur.
- **Réalisations** : worktree géré `koyori-interface/Koyori`, branche `gus-rlin/koyori-interface`, base `f81df40`. Application réalisée dans `apps/web` ; aucun changement dans le checkout d’origine.
- **Choix et raisons** : React/TypeScript/Vite conformément au TDD ; CSS natif à tokens, dialogues HTML natifs plutôt qu’une bibliothèque de composants lourde. Direction sobre argent/sauge, typographie Manrope auto-hébergée, Phosphor pour une seule famille d’icônes. Les prescriptions marketing du skill design sont adaptées à une application compagnon. Démonstration interactive en mémoire, explicitement distincte du backend, sans faux accès Alexa ni microphone activé.
- **Difficultés et résolution** : aucun frontend existant ; les contrats vocaux de l’étape 4 ne sont pas disponibles. L’interface montre les parcours via des fixtures synthétiques sans inventer une intégration distante.
- **Ce qui a bien fonctionné** : lecture du concept, du TDD et des entrées récentes avant création du worktree depuis le HEAD réunissant les étapes 2 et 3.
- **Vérifications** : checkout d’origine propre au démarrage ; validations frontend à exécuter après implémentation.
- **Retour sur les outils** : skills `design-taste-frontend`, `senior-code-basics` et `imagegen`, Git, worktrees Codex, PowerShell, npm. Documentation officielle React, Vite et Phosphor consultée le 2026-10-06. Génération d’une photographie d’intérieur via l’outil intégré en cours. Aucun appel ou coût AWS, aucun achat, aucune publication Open Source complémentaire.
- **Suite** : réaliser les vues, tester les parcours, les deux thèmes et le responsive, puis compléter cette entrée avec les résultats réels.

### Point de contrôle — interface et vérifications

Les sept vues sont réalisées dans `apps/web` : accueil, demandes, mémoire, routines, services, activité et réglages. Les demandes se créent, se filtrent, se mettent en pause, reprennent et s’annulent ; le panier se valide explicitement dans la simulation, sans inventer une confirmation commerçant. Refuser puis reprendre une demande permet de revoir le panier. Les préférences se recherchent, se corrigent et se suppriment avec confirmation. Les routines disposent d’interrupteurs sans exécution planifiée. Navigation par fragments, formulaires validés, dialogues natifs, retour du focus, états vides, thèmes clair/sombre et mouvement réduit sont en place. Aucun appel métier réseau, jeton, stockage persistant ou accès microphone.

**Friction npm 11.16.0 / Node 24.18.0** : `npm install` sur ce poste échoue ou réessaie longtemps avec `UNABLE_TO_VERIFY_LEAF_SIGNATURE` pour registry.npmjs.org. Attendu : résolution des dépendances ; observé : installation initiale d’environ six minutes et audit indisponible à cette tentative. Gravité : installation ralentie/bloquée. Contournement réussi : `NODE_USE_SYSTEM_CA=1` pour la commande, avec vérification TLS conservée ; installation des dépendances de développement et audit réussis en 19 secondes. Suggestion : remonter dès le premier échec TLS le recours aux certificats système approuvés. Aucun certificat ni secret copié dans le dépôt. Une tentative d’import Fontsource `latin.css` révèle que cet export n’existe pas dans ce paquet variable ; retour à son point d’entrée documenté présent sur disque, puis build réussi. Aucun résultat de test issu du build interrompu n’est retenu.

La première série fonctionnelle passe 14 tests, les deux contrôles Axe échouant sur le contraste clair et la racine sombre. Tokens corrigés ; l’analyse est stabilisée avec mouvement réduit pour ne pas mesurer une opacité d’animation transitoire. Les captures ont aussi révélé un libellé de navigation coupé et un espace manquant autour d’un saut de ligne mobile : corrigés. Première mesure Lighthouse 96/100/96, favicon manquant et image surdimensionnée. Favicon rendu depuis Phosphor, image WebP responsive et préchargement corrigent ces points : mesure finale **99/100/100**, LCP **2,1 s**, CLS **0**, TBT **0 ms**. Mesures locales, pas des garanties terrain.

`npm run build` réussit. `npm test -- --workers=2` contre le build de production : **16 tests réussis en 13,1 s**, ordinateur Chrome et mobile Chromium émulé. Aucun débordement horizontal des sept vues à 320 px. Axe ne signale aucune violation dans les vues testées clair/sombre ; douze analyses complémentaires couvrent les six autres vues sur ordinateur. Les captures des deux thèmes et formats sont inspectées. Rapports bruts dans `artifacts/` et `apps/web/test-results/` ignorés ; synthèse durable dans [docs/verification/interface.md](docs/verification/interface.md). Les tests Python/Docker ne sont pas relancés car le runtime backend n’est pas modifié.

**Outils réellement utilisés** : React 19.3.0, TypeScript 7.0.2, Vite 8.3.2, Phosphor 2.1.10, Fontsource Manrope 5.3.0 ; runtime CSS/React léger sans bibliothèque d’animation ou d’état globale. Playwright 1.63.0 et Axe 4.13.0 ont permis des régressions observables ; Lighthouse 13.5.0 a identifié les coûts d’image et le favicon ; Sharp 0.35.5 a optimisé les assets, Prettier 3.9.9 a formaté les fichiers. npm audit : 149 paquets, aucune vulnérabilité connue signalée. Le visuel généré avec `image_gen` est inspecté et conservé en deux tailles WebP dans le worktree ; prompt exact et origine dans le README frontend. Outil utile pour une identité visuelle propre sans photographie d’un foyer réel, à réutiliser pour de nouveaux assets contextualisés. Les outils de capture headless et `view_image` ont permis de relire le rendu ; `open_in_codex` a accepté la demande d’aperçu local (retour `queued`). Aucun accès AWS utilisé, aucun coût AWS ni ressource distante créée.

### Clôture

- **Objectif et état** : terminé pour l’interface interactive de démonstration, ses validations et sa documentation. Raccordement réel explicitement hors de cette livraison.
- **Choix et raisons** : état local React, données synthétiques séparées, composants communs et vue du jour distincts ; HTML natif préféré à une bibliothèque de dialogues, CSS à tokens préféré à une seconde abstraction de styles. Aucune modification des sources Python ou du déploiement AWS. Documentation du concept actualisée pour distinguer la démonstration de la vision vocale.
- **Ce qui a bien fonctionné** : développement et serveur séparés dans le worktree, régressions utilisateur sur deux formats, correction des vrais défauts révélés par Axe/Lighthouse, assets servis localement sans dépendance à un CDN.
- **Suite** : relier l’interface aux contrats d’identité/API puis à la voix de l’étape 4 ; ajouter à ce moment les états de chargement/erreur réseau et les contrôles serveur adaptés. Tester Safari, lecteurs d’écran et appareils physiques avant une qualification produit. Le serveur Vite local est conservé sur 5178 pour consultation. Travail local sous Apache-2.0 ; aucune PR, publication ou contribution Open Source complémentaire réalisée.

Derniers contrôles : `npm audit` réexécuté sans vulnérabilité connue ; Prettier vérifie tous les fichiers frontend sans différence. Le checkout d’origine est relu propre, sans changement de HEAD ni de fichier par cette tâche. Les sources, images et documents de cette livraison sont conservés dans un commit local de `gus-rlin/koyori-interface`, sans push ni fusion. Le serveur de preview de qualification est arrêté ; seul le serveur de consultation sur 5178 est conservé.

## JRN-027 — 2026-10-06 — Réunion de tous les changements dans le checkout principal

- **Objectif et état** : terminé ; rendre le checkout principal propre sur une branche contenant les changements récents, y compris la quatrième partie, son correctif de protocole, l’interface et la revue locale encore non commitée.
- **Réalisations** : branche `gus-rlin/koyori-integration-complete` créée dans le checkout principal. L’entrée locale de revue est préservée par `ccb0a11`. Fusion de `origin/main` à `e692694`, comprenant l’étape 4 et `f7e8d55`, enregistrée dans `0d5f40a`. Réunion de la branche interface `2ab1e83` avec son historique. Les entrées concurrentes JRN-021 de la revue et de l’interface deviennent JRN-025 et JRN-026 avec notes explicites ; le concept conserve les deux descriptions et le rapport interface renvoie au bon identifiant.
- **Choix et raisons** : nouvelle branche commune, fusions préservant les historiques et les branches sources ; aucun rebase ni suppression de fichier. Les anciens worktrees sont propres et leurs chats inactifs au contrôle. Le backend et le frontend sont réunis dans Git ; cette opération ne réalise pas leur raccordement fonctionnel. Les fichiers ignorés de dépendances, builds et données locales sont conservés. Aucun changement applicatif ajouté.
- **Difficultés et résolution** : conflits documentaires dans le journal et le concept, résolus en conservant les deux contenus. Deux scripts PowerShell de résolution sont refusés avant exécution par le parseur, qui interprète les apostrophes typographiques françaises dans les chaînes entre apostrophes ; chaînes concernées passées entre guillemets doubles, résolution réussie. Le premier contrôle d’infrastructure lit le template CDK antérieur : 11 Lambdas observées au lieu des 13 attendues. Cause confirmée : artefact local ignoré resté à l’étape 3, pas une divergence du code fusionné. Synthèse renouvelée et les 10 contrôles d’infrastructure passent. Aucun code modifié pour contourner ce résultat ; générer les artefacts adaptés au checkout avant les contrôles qui les lisent.
- **Ce qui a bien fonctionné** : fetch avant réunion : la PR #4 est déjà intégrée à `main`, permettant de reprendre son dernier correctif sans modifier sa branche. Comparaison Git de l’index : tous les fichiers backend sont identiques à `origin/main`, tous les fichiers `apps/web` sont identiques à la branche interface. Les contournements TLS documentés permettent de synchroniser les dépendances sans désactiver la vérification.
- **Vérifications** : `uv sync --frozen --group infra --system-certs` et `npm ci --no-audit --no-fund` avec `NODE_USE_SYSTEM_CA=1` réussis. Empreinte backend `record_evidence.py --check-source`, Ruff check et format des 100 fichiers réussis. Build TypeScript/Vite réussi ; **16 tests Playwright réussis en 20,5 s**, sur serveur Vite local, Chrome ordinateur et mobile émulé. Suite pytest avec intégrations DynamoDB Local/ElasticMQ sur 8900/9344 : **298 réussites, un échec d’infrastructure, aucune exclusion**, en 101,92 s ; après synthèse CDK, `tests/test_infrastructure.py` et `tests/test_stage4_infrastructure.py` : **10 réussites**. Rapports locaux ignorés : `artifacts/integration-complete-tests.xml` et `artifacts/integration-complete-infrastructure-tests.xml`. Warning de dépréciation Starlette/httpx déjà connu, sans autre problème observé. Suite complète non répétée après cette correction d’artefact ; les dix contrôles concernés sont revérifiés. Diff et absence de conflits contrôlés ; 27 identifiants de journal distincts. Images/bundle et recettes Docker non reconstruits ou répétés : code backend strictement identique au dernier `main`, artefacts historiques conservés avec leurs limites de JRN-024.
- **Retour sur les outils** : `senior-code-basics`, Git, PowerShell, `rg`, apply_patch, uv, npm, pytest, Playwright, Ruff et CDK utilisés ; `list_threads` confirme les chats concernés inactifs sans leur envoyer de message. Comparaison des blobs Git utile pour prouver la préservation exacte du code. Aucun appel fournisseur, coût AWS, déploiement ni contribution Open Source complémentaire.
- **Suite** : branche de réunion locale, aucune nouvelle PR ni publication distante demandée ou effectuée. Raccordement frontend/backend et qualifications réelles restent ceux des livraisons précédentes. Le bundle Lambda ignoré du checkout principal reste historique : le reconstruire avant toute préparation de déploiement ; la synthèse CDK seule ne le qualifie pas. Les autres worktrees et services locaux sont conservés.

## JRN-028 — 2026-10-06 — Mémoire durable, recherche et apprentissage inspirés de Hermes

- **Objectif et état** : terminé pour l'implémentation et la qualification locale du plan validé, dans le worktree isolé `koyori-memory-hermes/Koyori`, branche `gus-rlin/koyori-memory-hermes`, base `e0f967b`. Qualifications distantes explicitement restantes.
- **Réalisations** : contexte durable, recherche lexicale des archives, outil MCP/voix commun et propositions d'apprentissage automatiques avec acceptation explicite ; confidentialité et registre de restauration 2.0 couvrant ces chemins. Fichiers principaux : `memory.py`, `lexical.py`, `auto_learning.py`, `learning.py`, `goals.py`, `privacy.py`, `backup.py`, workers, canaux et infrastructure. Documentation dans [le contrat mémoire](docs/memory-hermes.md), [le rapport final](docs/verification/memory-hermes.md), la note de concept et les documents d'exploitation/livraison. Le checkout principal reste propre ; aucun frontend connecté ou fournisseur réel ajouté.
- **Choix et raisons** : séparer mémoire durable et archives ; utiliser DynamoDB existant pour l'index lexical ; produire automatiquement des propositions privées, avec acceptation explicite. Validation locale synthétique et contrats SDK interceptés demandés par l'utilisateur. Référence [Hermes au commit 4787e4d](https://github.com/NousResearch/hermes-agent/tree/4787e4d56fc8d9265d4c7d3c0fe5accee86b4078), consultée le 2026-10-06 : mémoire compacte, recherche historique et boucle d'apprentissage ; adaptation indépendante sans copie de code. Trois revues du plan : 8,3/10 puis 9/10, puis 9/10 après précision du registre de suppressions. Ces notes ne valident pas le code futur.
- **Difficultés et résolution** : la revue a corrigé le déclencheur `SUCCEEDED`, les plafonds SDK, la distinction `coreItems/items`, les budgets combinés et les curseurs multi-partitions. La lecture de `backup.py` a révélé que le registre actuel ne couvre pas les générations de confidentialité et les propositions : extension prévue en version 2.0, annulation des jobs importés et reconstruction lexicale sous quarantaine. Aucun problème de création du worktree observé.
- **Ce qui a bien fonctionné** : exploration en lecture seule et revue indépendante avant implémentation ; vérification des ports réellement libres et choix d'un environnement Compose distinct.
- **Vérifications** : état initial : 40 tests ciblés mémoire/apprentissage/contexte/confidentialité réussis en 12,11 s. Suite finale : **344 réussites, aucune exclusion, zéro échec/erreur**, 143,81 s, avec DynamoDB Local et ElasticMQ ; warning Starlette/httpx préexistant uniquement. Les **cinq recettes Docker passent** sur l'image finale, Ruff check/format des 108 fichiers Python, synthèse CDK/IAM, audit runtime et correspondance des 50 sources applicatives réussis. Sources/lock/bundle/template/image et résultats dans [artifact-evidence.json](docs/verification/artifact-evidence.json) ; contrôle d'empreinte et préparation du manifeste réussis. Revue finale **9/10**, maintenue après lecture complémentaire des scripts. Détails et limites des séries dans les points de contrôle ci-dessous.
- **Retour sur les outils** : skill `senior-code-basics`, Git, PowerShell, rg, GitHub/API publique, outils worktree Codex, uv et pytest utilisés. Le sous-agent reviewer a relu le plan sans modification. Aucun appel Nova/Google ni coût AWS observé, aucune publication ou contribution complémentaire effectuée.
- **Suite** : qualifier dans un environnement dédié l'exécution ARM64, IAM/GSI/PITR et Nova réel, sa qualité linguistique, sa région/consentement et ses coûts, avant activation AWS. Le frontend reste autonome. Travail conservé par commit local propre ; aucun push, PR ou déploiement demandé ou exécuté.

### Implémentation et première revue du code

Mémoire durable issue des clés canoniques, contexte `coreItems` séparé, index lexical transactionnel par références/révisions, recherche paginée et outil commun MCP/voix ajoutés. Le worker d'apprentissage distinct conserve ses intentions, baux et réservations SDK ; ses sorties deviennent des propositions `LEARNING` privées. L'acceptation conserve partage et expiration d'une correction. Les phases d'effacement couvrent propositions, jobs et déduplication ; registre 2.0 et reconstruction lexicale sous quarantaine ajoutés à la restauration des snapshots 1.0. Aucune dépendance ajoutée.

Première revue du code : **7,5/10 provisoire**, sur des fichiers encore en évolution. Défauts trouvés : fence absent traité comme `None` dans la projection ; états d'action `CONFIRMED` confondus avec `SUCCEEDED` ; compteur lexical absent pendant effacement d'anciennes données ; révisions source/cible non vérifiées dans la lecture d'une proposition ; cible résolue après appel modèle. Corrigés avec tests observables et gardes des données effectivement fournies au modèle. La note du plan n'est pas assimilée à cette revue de code.

Contrôles intermédiaires : **48 tests ciblés réussis** (nouvelle mémoire, apprentissage, apprentissage existant et confidentialité) en 10,01 s ; **6 intégrations DynamoDB Local réussies** (nouveaux index/apprentissage/restauration et canaux existants) en 13,75 s. Les nouveaux tests utilisent Strands/Botocore réels avec transport HTTP intercepté : une requête sur sortie valide, plafonnement à deux y compris réparation/reprise, sans retry SDK caché ni fuite des fragments privés simulés dans les logs. Ces résultats ne qualifient pas Nova distant. Des erreurs de fixture initiales (clé contenant un point interdit par le contrat existant, signature de helper, contexte devenu ancien après création d'un objectif) sont corrigées sans assouplir les contrats.

Docker 29.8.0 / Compose 5.5.1 : premier lancement refusé pour chevauchement du sous-réseau `10.253.43.0/24`, déjà utilisé par l'étape 3. Inventaire des réseaux effectué, remplacement par `10.253.45.0/24` libre : environnement démarré. Impact limité au lancement, aucun service existant modifié. Amélioration réutilisable : vérifier les sous-réseaux en plus des ports avant une recette isolée. Image `koyori-memory-hermes:local` reconstruite avec lock et autorité publique approuvée via secret BuildKit ; TLS conservé et certificats hors image. Les données/volumes et tables `KoyoriMemoryHermes*` sont dédiés. Suite cumulative, artefacts finaux, documentation et revue finale restent à renouveler après les derniers correctifs.

### Deuxième revue et suite cumulative

Deuxième revue du code : **8,5/10**. Deux défauts concrets restaient : un effacement débutant juste avant le checkpoint final pouvait empêcher un objectif aux actions déjà confirmées de devenir `SUCCEEDED` ; le texte d'une proposition refusée restait lisible après modification ou suppression de sa cible. Corrigés : checkpoint autorisé sous garde du fence sans création d'apprentissage, revalidation des cibles aussi pour les refus. Les régressions correspondantes passent. Le quota quotidien est explicitement commun aux foyers d'une même personne, avec test de concurrence de consommation entre deux foyers.

Première suite cumulative : **334 réussites et trois échecs** en 117,48 s. Les échecs ont révélé une assertion ancienne de timeout du nouveau worker, un contexte de foyer vide marqué à tort incomplet et la perte du contrat historique des échanges explicitement désignés par `memoryKeys` dans la planification. Assertion adaptée au worker de 60 s ; index vierge reconnu complet en l'absence de souvenirs ; récupération des clés explicites et repli récent rétablis avec classement et budgets globaux. Les contrôles historiques du nombre de sources restent inchangés. **61 tests ciblés passent** après ces corrections, puis la suite cumulative complète avec DynamoDB Local/ElasticMQ passe : **340 réussites, aucune exclusion, aucun échec**, en 112,62 s. Ruff check et format passent sur les 108 fichiers Python ; seul le warning Starlette/httpx préexistant reste signalé.

La première recette mémoire avait validé contexte durable, recherche ancienne, outil MCP et acceptation, puis refusait le step-up d'effacement : le helper signait un corps sans le `schemaVersion` ajouté par le contrat. Correction du corps synthétique signé, aucune protection serveur assouplie. Les cinq recettes et les empreintes finales restent à terminer. Une troisième revue de l'implémentation est lancée après les 340 réussites ; son résultat n'est pas encore acquis.

### Troisième revue et préparation des artefacts

Troisième revue : **8,8/10**, avec 40 contrôles indépendants réussis et aucun nouveau défaut de confidentialité ou de reprise trouvé. Deux écarts de contrat restent relevés et sont corrigés : calcul des clés manquantes pendant chaque réduction du payload avant la mesure finale des 20 000 octets ; acceptation du contexte CDK explicite `true` transmis sous forme de chaîne par la CLI, en plus du booléen. Régression multioctets calibrée à la frontière du budget ajoutée ; synthèses de configuration booléenne/CLI et valeur ambiguë ajoutées sans accès AWS.

Le test de synthèse a d'abord échoué sur le chemin d'import du paquet infrastructure, corrigé dans la fixture. Sa tentative suivante a rencontré une copie de fichier manquant pendant l'activation atomique du nouveau bundle Lambda, qui se déroulait en parallèle : deux cas passent et un échoue. Cause confirmée par les chemins et l'activation concomitante, pas par une permission AWS. Les validations qui lisent un bundle doivent suivre la fin de sa construction. La synthèse séparée renouvelée après construction passe ; tous les fichiers applicatifs du bundle sont identiques au checkout. Audit `pip_audit` du runtime reconstruit : aucune vulnérabilité connue signalée. Recettes mémoire et reprise étape 1 réussies sur l'image reconstruite ; elles seront renouvelées avec les autres recettes après le dernier correctif de budget. Une quatrième revue sera demandée sur l'état corrigé.

### Quatrième revue du code

Les quatre nouveaux contrôles passent en 32,67 s après stabilisation du bundle. Quatrième revue : **9/10**, sans défaut bloquant ni constat matériel restant. Le reviewer a exécuté personnellement `git diff --check` et la régression du budget, en complément de ses 40 contrôles indépendants précédents ; il a relu les synthèses CDK paramétrées exécutées par l'agent principal. Son verdict distingue explicitement le code local des qualifications AWS, linguistiques et frontend. La suite cumulative de 344 cas et les cinq recettes sont en cours de confirmation ; la livraison n'est pas encore déclarée terminée.

Images finale locale et AgentCore AMD64/ARM64 reconstruites avec le lock. Les 50 modules applicatifs des deux variantes AMD64 correspondent exactement au checkout (`8d31edd3a8b164a0f1de965efe365d30554f5750ab127d82e459ec150835b0eb`) ; imports voix/MCP/SDK/CRT réussis sans appel fournisseur. Image ARM64 inspectée comme telle ; l'essai d'import `docker run --rm --platform linux/arm64 --entrypoint python koyori-memory-hermes-agentcore:arm64 ...` est refusé avant lancement Python par `exec format error`, limite d'exécution déjà observée en JRN-024 sur ce poste. Impact : construction vérifiée, exécution ARM64 non qualifiée. Aucun contournement de plateforme ou installation d'émulateur ajouté à ce chantier. Prochaine qualification : répéter les imports et recettes sur un hôte ARM64 ou un runner avec émulation disponible avant déploiement ; les manifestes conservent ce statut non qualifié.

Suite finale confirmée : **344 tests réussis** en 143,81 s, aucune exclusion. Recettes Docker étapes 1 et 2 renouvelées sur l'image finale : **PASS**. La recette étape 3 échoue sur le statut attendu lors d'un accès de Sam à une proposition privée ; investigation en cours sur le choix du foyer par les scripts, qui prennent le premier de la liste après création d'un foyer supplémentaire pour la recette mémoire. Aucun statut serveur ni assertion de confidentialité assoupli à ce stade.

Correction factuelle du point précédent : le contrôle concerne un **objectif privé**, et non une proposition. L'API confirme que le premier foyer est celui de qualification mémoire, sans Sam : contexte Sam refusé en 403, contexte Sam du foyer synthétique A autorisé en 200. Cause confirmée : hypothèse historique des quatre recettes sur l'ordre des foyers. Un helper commun sélectionne désormais l'unique fixture nommée par le bootstrap, avec erreur explicite si absente ou ambiguë. Les contrôles d'accès restent inchangés ; aucun droit rétabli. Priorité importante pour la reproductibilité des recettes après création de plusieurs foyers. Les quatre recettes sont renouvelées après ce correctif de scripts, sans changement de runtime.

Cinquième lecture, limitée à ce complément de scripts : **9/10 maintenu**, aucun nouveau défaut matériel ; `git diff --check` exécuté personnellement par le reviewer. Les recettes elles-mêmes restent exécutées par l'agent principal. Ruff check/format passent à nouveau, et les recettes étapes 1/2 passent avec la sélection déterministe de la fixture.

### Clôture locale

- **Objectif et état** : terminé ; tous les éléments du plan sont implémentés, la revue requise atteint 9/10 sans défaut bloquant et les validations locales finales sont acquises.
- **Réalisations** : cinq recettes renouvelées séquentiellement sur `koyori-memory-hermes:local`, toutes **PASS**. La recette étape 3 vérifie reprise du plan, isolation du propriétaire, attente sans nouveau modèle, pause/reprise, préférence utilisée, modification du même achat simulé, annulation avec reçu, occurrence unique et notifications groupées. L'étape 4 vérifie MCP/REST/voix, reconnexion, poursuite après fermeture et rattrapage durable. La nouvelle mémoire vérifie core, archive ancienne, accents, recherche MCP, acceptation et effacement des propositions. Rapports de métadonnées conservés dans [artifact-evidence.json](docs/verification/artifact-evidence.json), manifeste `PREPARED_NOT_DEPLOYED` renouvelé.
- **Choix et raisons** : conserver l'autorité des données canoniques et les composants existants ; index sans texte et crédits réservés avant SDK, procédures déclaratives et acceptation manuelle. Priorité importante : mieux rappeler les préférences anciennes et proposer les apprentissages sans les imposer. Aucune nouvelle dépendance. La séparation mémoire compacte/historique/apprentissage de Hermes sert de référence ; aucun code Hermes copié ni mémoire importée.
- **Difficultés et résolution** : défauts des revues et échecs de tests/fixtures décrits ci-dessus, tous corrigés localement. Le filtre durable FR/EN est volontairement conservateur et peut manquer certaines formulations ; la proposition manuelle reste disponible. Exécution ARM64 non qualifiée sur ce poste faute d'exécution compatible ; la construction seule n'est pas assimilée à un runtime validé. Aucun autre problème observé lors des derniers contrôles.
- **Ce qui a bien fonctionné** : transactions et relectures canoniques couvrent concurrence, crash/reprise et effacement ; vérification du SDK réel avec HTTP intercepté démontre les plafonds sans appel facturable. Les revues ont produit des régressions observables plutôt qu'un changement de note sans correction. La recette multiple-foyers a révélé une hypothèse de fixture jusque-là invisible.
- **Vérifications** : 344 tests finaux, cinq recettes, Ruff, synthèse et audit réussis ; `record_evidence.py --check-source` confirme l'empreinte `c41d70cc4bbbf41d1b27eb74d57d96cbfc6c297ddb65bc8541abe5caa442a6f4`. Les quatre tests de preuve passent après génération des nouveaux rapports ; Ruff est également renouvelé. Références locales relues et absence de différence du checkout principal contrôlée. Le dernier correctif touche uniquement les scripts de sélection de fixture, validés par les recettes et la cinquième lecture ; les tests/runtime n'ont pas changé après la suite cumulative. Contrôles natifs/distants et workflow GitHub non exécutés. Pas de qualification frontend supplémentaire : ses fichiers n'ont pas changé.
- **Retour sur les outils** : Python 3.12.13, uv 0.11.28, Docker 29.8.0/Compose 5.5.1, Strands 1.57.2 et Boto3/Botocore 1.43.108, CDK 2.272.0, Ruff 0.16.10 et pip-audit 2.10.1 effectivement utilisés. Strands permet les sorties typées ; l'interception Botocore vérifie les requêtes réellement réservées et les logs privés, approche à réutiliser. DynamoDB Local/ElasticMQ utiles pour les transactions et reprises, à conserver avant essais distants ; IAM/GSI AWS restent à qualifier. Les frictions Docker, certificats et CDK sont décrites ci-dessus avec contournements et limites. Aucun appel fournisseur, coût AWS observé ni ressource AWS créée ; services et volumes locaux dédiés conservés pour reprise.
- **Suite** : qualification distante explicite sur fixtures, mesure de la pertinence linguistique et raccordement frontend selon les chantiers suivants. Source locale sous Apache-2.0 dans ce dépôt le 2026-10-06 ; aucune contribution Open Source complémentaire, URL de PR, publication ou fusion créée. Les qualifications du hackathon ne sont pas déduites de ces validations locales.
