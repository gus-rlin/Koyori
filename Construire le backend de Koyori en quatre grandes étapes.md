# Construire le backend de Koyori en quatre grandes étapes

**Construire le backend en quatre étapes successives, avec un résultat utilisable et une preuve de fin pour chacune.** Valider une étape avant de commencer les fonctionnalités de la suivante. Le résultat visé est un agent personnel qui conserve les demandes du foyer, retrouve le bon contexte, coordonne des actions autorisées et poursuit son travail après la conversation.

Ce document propose un ordre de réalisation à partir de la note de concept et du TDD de Koyori. Au 4 octobre 2026, le dépôt contient des documents ; aucune application ni intégration n'y est implémentée. Les travaux et cases de validation ci-dessous restent à réaliser. Le découpage ne vaut pas validation de toutes les propositions techniques du TDD.

## Les quatre étapes et leur résultat

| Ordre | Étape | Résultat qui permet de passer à la suite |
| --- | --- | --- |
| 1 | Socle durable et autorisations du foyer | Une demande authentifiée est enregistrée, exécutée et reprise après interruption sans perdre son état ni exposer les données d'une autre personne. |
| 2 | Mémoire, contexte et connecteurs contrôlés | Une commande explicite utilise un contexte sourcé et réalise une action vérifiable, avec droits, budget et traitement des résultats incertains. |
| 3 | Coordination autonome et apprentissage | Une demande naturelle devient un plan borné, poursuit ses étapes dans le temps et s'adapte aux corrections sans recommencer les actions déjà engagées. |
| 4 | Accès vocal, MCP et qualification complète | Les mêmes capacités fonctionnent par les canaux prévus, sur un backend déployé et qualifié, avec des résultats, limites et coûts documentés. |

Ces quatre étapes organisent la construction. Elles ne correspondent pas à quatre microservices. Le TDD propose un code partagé et des exécutables séparés selon leurs responsabilités et leurs droits. Le parallélisme du produit sera ajouté en étape 3 pour les opérations réellement indépendantes.

## Le périmètre du backend

Le plan couvre les API, l'identité, les autorisations, la persistance, les tâches, la mémoire, les connecteurs, les modèles, la coordination, les échéances, les notifications, le serveur MCP, le transport vocal côté serveur et l'exploitation. Les premières recettes utilisent un client HTTP et des scripts ; la dernière ajoute un client MCP et un client audio de recette.

Le design de l'application, les écrans React, la capture et la lecture audio dans le navigateur constituent le chantier d'interface. Leurs contrats serveur figurent ici : admission de session, messages audio, cartes de résultat, approbations, correction des souvenirs et rattrapage de l'activité. La fluidité complète de l'expérience vocale devra aussi être vérifiée avec le client réel.

**Au début de l'étape 1, établir un manifeste de livraison.** Pour chaque capacité, indiquer son étape, ses dépendances, son contrat, son critère d'acceptation et son statut prévu : réelle, simulée ou différée. Les parcours de la note de concept servent de base : organiser la journée, retrouver une demande passée et adapter un plan en cours. La liste des services accessibles reste à confirmer.

Le TDD propose notamment Python, Pydantic, AWS CDK, DynamoDB, des traitements AWS durables, Bedrock et Strands. Ce plan conserve cette base de travail sans reprendre la pile Rust/PostgreSQL de l'exemple Kyro. Les versions, accès, régions, capacités de modèles et intégrations proposées sont à qualifier dans l'étape qui les utilise.

La démonstration de référence décrite par le TDD associe un backend réel, un serveur MCP réel, un agenda connecté et un fournisseur de commerce simulé. Le canal vocal dédié représente l'expérience Alexa+ visée. Une intégration native Alexa+ ou un achat réel ne peuvent être annoncés qu'après obtention des accès nécessaires et validation de leur propre contrat. Les transports, réservations de services et équipements domestiques conservent leur place dans le registre de capacités ; leur disponibilité dépend des connecteurs livrés.

## La règle pour terminer une étape

Une étape est terminée lorsque ses contrats sont documentés et versionnés, son scénario nominal fonctionne, ses cas de refus et de panne passent, et les recettes précédentes restent valides. Pour chaque recette, conserver le commit ou l'empreinte de l'artefact, les versions et la configuration utilisées, le résultat observé et le caractère réel ou simulé des dépendances.

Les tests locaux vérifient la logique et permettent de provoquer des pannes. Ils ne prouvent pas le comportement des services AWS, des modèles ou d'un fournisseur réel retenu dans la livraison. Une simulation de commerce peut être acceptée comme telle dans le manifeste ; elle ne démontre aucun achat réel. Une réponse du modèle annonçant un succès ne constitue jamais une preuve d'exécution.

Les droits, l'observation et les contrôles de coût commencent avec les premiers composants concernés. La quatrième étape rassemble les preuves de l'ensemble ; elle ne reporte pas ces contrôles à la fin.

## Étape 1 — Construire le socle durable et les autorisations du foyer

**Objectif :** disposer d'un serveur fiable, indépendant de la voix et du raisonnement des agents. Une première opération déterministe suffit à valider le parcours de persistance et de reprise.

### Travail à réaliser dans cet ordre

1. Fixer le manifeste de livraison et préparer le dépôt applicatif : contrats, logique de domaine, API de contrôle, workers, infrastructure et recettes. Verrouiller les dépendances et définir les configurations locales et AWS de développement, avec données synthétiques et références de secrets.

2. Mettre en place l'authentification, les foyers, les membres, les délégations et les droits par objet. Construire le contexte d'identité côté serveur. Distinguer données privées et partagées ainsi que canal personnel et canal domestique partagé ; l'appartenance au foyer ne donne pas accès à tous les comptes ou souvenirs.

3. Persister commandes, tâches, révisions, décisions de politique et événements de domaine. Une demande n'est acceptée qu'après son enregistrement durable avec l'événement qui permettra son traitement. Prévoir les conflits de révision, la déduplication des commandes et les transitions autorisées de tâche.

4. Construire l'outbox transactionnelle, sa publication et sa réparation, les files et leur traitement des messages en échec, puis la déduplication des consommateurs. Ajouter les baux et générations d'exécution qui empêchent un ancien worker d'enregistrer un résultat obsolète. Conserver un réveil reçu pendant une exécution pour qu'il ne soit pas perdu.

5. Exposer les premières commandes et lectures HTTP, les politiques d'autonomie et le journal d'activité autorisé. Documenter les erreurs stables, les clés d'idempotence et les préconditions de révision. Distinguer dès l'API demande acceptée, attente, échec et résultat confirmé.

6. Déployer les composants nécessaires à cette première recette par infrastructure versionnée. Installer journaux expurgés, traces, contrôles de santé, limites de traitement et sauvegardes. Vérifier les transactions et reprises avec les services AWS réellement retenus ; préparer une restauration d'essai sans déclencher d'action externe.

**Contrats livrés :** contexte d'identité, foyer et délégation, commande, tâche versionnée, politique, événement de domaine, intention de travail durable et flux d'activité. Les futures fonctions de mémoire et d'exécution utiliseront ces contrats.

### Preuve de fin de l'étape 1

- [ ] Deux foyers ne peuvent lire ni modifier leurs ressources respectives. Dans un même foyer, un membre ne peut lire une ressource privée sans partage ou délégation explicite.
- [ ] Une demande acceptée avant l'arrêt du worker retrouve la même tâche après reprise ; une livraison répétée ne crée pas une deuxième mutation interne.
- [ ] Une publication d'événement interrompue est réparée ; un réveil reçu pendant un traitement n'est pas perdu et un ancien worker ne peut écraser un état plus récent.
- [ ] Une même clé d'idempotence et un même contenu retrouvent le résultat initial ; un contenu différent ou une ancienne révision produit un conflit explicite.
- [ ] Un accès expiré ou révoqué est refusé, même si son enregistrement reste présent. Les erreurs et journaux ne révèlent ni secret ni contenu privé inutile.
- [ ] Un redémarrage et une restauration d'essai retrouvent des tâches, droits et travaux en attente cohérents. Les résultats locaux et AWS sont identifiés séparément.

**Passage à l'étape 2 :** le backend conserve et traite une commande contrôlée. La mémoire, les connecteurs et les agents n'auront pas à reconstruire l'identité, les droits ou la reprise du travail.

## Étape 2 — Construire la mémoire et les connecteurs contrôlés

**Objectif :** retrouver un contexte fiable et exécuter une action explicite par API. Aucun plan produit par un modèle n'est nécessaire pour prouver que les outils savent fonctionner correctement.

### Travail à réaliser dans cet ordre

1. Implémenter les quatre représentations de mémoire : échanges finalisés, préférences versionnées, engagements issus des tâches et reçus, procédures déclaratives révisables. Enregistrer origine, auteur ou attribution de canal, date, visibilité et durée de validité. Une envie ponctuelle conserve son contexte temporel.

2. Construire la lecture chronologique, la recherche par clé et l'assemblage d'un contexte borné. « Hier » utilise le fuseau de la personne ou du foyer. Ajouter la recherche sémantique proposée dans le TDD, avec embeddings et index dérivé, puis relire les enregistrements actuels pour vérifier droits, révision, expiration et suppression. Exposer correction et effacement des souvenirs.

3. Créer le registre des capacités et les contrats des connecteurs : lecture ou écriture, propriétaire du compte, mode simulé ou réel, autorisations, preuve attendue, délais et règles de reprise. Livrer l'agenda OAuth retenu et le simulateur persistant de courses et repas. Une capacité sans fournisseur configuré renvoie une indisponibilité ou un passage de relais explicite.

4. Construire le moteur déterministe d'autorisation des actions : conditions exactes du devis, politique actuelle, approbation liée à ces conditions et réservation atomique du budget. Représenter les montants en unités monétaires entières. Une préférence ou une réponse de modèle ne peut augmenter les droits ni approuver une dépense.

5. Ajouter le registre des actions externes et leur exécution durable : intention commerciale stable, opération précise, clé d'idempotence fournisseur, reçu et état observé. Après un délai dépassé, conserver le résultat inconnu et la réservation puis rechercher l'opération chez le fournisseur. Une modification ou annulation possède sa propre opération et ses propres preuves.

6. Relier notifications fournisseur et synchronisation d'agenda aux événements du socle. Vérifier leur authenticité selon le contrat du fournisseur, traiter doublons et événements désordonnés, gérer renouvellement et révocation OAuth. Autoriser un connecteur commercial réel seulement après qualification de ses garanties d'idempotence, de rapprochement et de respect des conditions autorisées.

**Contrats livrés :** mémoire sourcée, contexte autorisé, capacité versionnée, connexion fournisseur, devis, approbation, réservation de budget, action externe et reçu. Entrée : commande structurée et contexte authentifié. Sortie : résultat établi, attente ou incertitude explicite.

### Preuve de fin de l'étape 2

- [ ] Une lecture de « ce que j'ai demandé hier » retrouve les échanges de la bonne journée locale et l'état actuel des tâches liées. Une source absente reste signalée comme absente.
- [ ] Une correction ou suppression gagne contre un ancien index, cache ou événement rejoué ; la recherche ne révèle pas la mémoire privée d'un autre membre.
- [ ] Le connecteur d'agenda lit les calendriers réellement autorisés ; retrait d'accès et notifications répétées ou désordonnées produisent un état cohérent. Les essais commerciaux portent un marquage de simulation conservé jusqu'aux reçus.
- [ ] Deux actions concurrentes ne réservent pas plus que le budget disponible ; un changement de prix ou de conditions invalide une approbation devenue inadéquate.
- [ ] Le simulateur crée une commande puis coupe la réponse : Koyori conserve un résultat inconnu, rapproche l'opération et retrouve une seule commande fournisseur, sans libérer prématurément le budget.
- [ ] Une révocation bloque les nouveaux envois ; une requête déjà partie reste suivie explicitement. Une annulation annoncée comme confirmée possède sa preuve fournisseur.
- [ ] Les appels réels d'embedding et d'indexation retenus sont qualifiés. Une tentative du client ou du modèle de passer du mode simulé au mode réel est refusée.

**Passage à l'étape 3 :** Koyori possède déjà une mémoire exploitable et des outils éprouvés. La coordination automatique pourra utiliser ces mécanismes sans confier au modèle l'autorité d'exécuter ou de déclarer un résultat.

## Étape 3 — Ajouter la coordination autonome et l'apprentissage

**Objectif :** transformer une intention naturelle en travail persistant, avec dépendances, échéances, adaptation et retours d'expérience.

### Travail à réaliser dans cet ordre

1. Définir le plan versionné et ses étapes : objectif, références de contexte, capacités, arguments, dépendances, preuves attendues et limites. Valider par code le graphe, les comptes concernés, les dates, les schémas et le périmètre des outils. Les devis viennent des connecteurs ; le modèle ne fournit pas un prix faisant autorité.

2. Qualifier le modèle de planification et brancher le coordinateur Strands proposé dans le TDD. Ajouter seulement les spécialistes nécessaires aux capacités du manifeste. Borner appels, contexte, parallélisme et réparation des sorties invalides ; les spécialistes produisent des résultats structurés et utilisent le même état de référence.

3. Relier le plan validé aux exécutions durables de l'étape 1 et aux connecteurs de l'étape 2. Avancer les étapes prêtes, vérifier leurs résultats et enregistrer l'attente suivante. Une tâche qui attend demain, une décision ou un fournisseur termine son exécution courante ; elle ne maintient pas une boucle de modèle active.

4. Ajouter échéances et routines récurrentes : registre durable des réveils, programmation, réparation des échéances manquées et identifiants d'occurrence. Traiter fuseaux, changements d'heure, versions de règles et annulations. Un ancien réveil ne réactive pas une routine remplacée.

5. Traiter modification, pause, reprise et annulation d'un objectif. Avant de remplacer une action, retrouver les opérations engagées et leur état fournisseur. Conserver l'intention commerciale lors d'une replanification ; demander une nouvelle décision lorsque les conditions changent au-delà du cadre confié.

6. Ajouter l'apprentissage des préférences et procédures à partir de retours sourcés, avec révisions et possibilité de correction. Une procédure reste déclarative et limitée aux capacités admises. Une inférence ne transforme pas une préférence en permission. Relier les changements utiles au journal d'activité et aux règles de notification, avec regroupement et horaires de calme.

**Contrats livrés :** plan validé, résultat de spécialiste, point de reprise, condition d'attente, règle de réveil, proposition d'apprentissage et intention de notification. Entrée : demande naturelle et contexte autorisé. Sortie : progression vérifiable ou décision précise à obtenir.

### Preuve de fin de l'étape 3

- [ ] Avec le modèle réel, une demande couverte relie agenda, préférences et actions puis produit les reçus attendus. Une demande hors capacités reste explicitement limitée.
- [ ] Des recherches indépendantes avancent dans les limites prévues ; les opérations qui partagent un budget, une commande ou un autre invariant sont contrôlées par les mêmes règles déterministes.
- [ ] Une tâche acceptée puis interrompue reprend après redémarrage ; une attente prolongée ne déclenche pas d'appels de raisonnement sans événement utile.
- [ ] « Nous serons quatre ce soir » retrouve la commande prévue pour deux, rapproche son état et utilise une modification ou une décision explicite. Aucune commande de remplacement silencieuse n'est créée.
- [ ] Une échéance répétée, un changement d'heure ou un réveil ancien ne crée pas deux intentions pour la même occurrence ; une pause empêche les nouveaux envois tout en conservant le rapprochement des opérations en cours.
- [ ] Un retour sur le goût ou la procédure modifie les prochaines propositions sans augmenter dépenses autorisées, partage ou accès aux comptes.
- [ ] Une instruction hostile dans l'agenda, un faux succès d'outil, un plan invalide ou une panne de modèle n'accorde aucun droit et ne déclenche pas une reprise sans borne. Le plafond de raisonnement conserve une capacité distincte pour résoudre les actions incertaines.

**Passage à l'étape 4 :** le cœur agentique fonctionne déjà par API et continue sans conversation ouverte. Les canaux vocaux et MCP donneront accès à ce même état et à ces mêmes contrôles.

## Étape 4 — Relier les canaux et qualifier le backend complet

**Objectif :** rendre le système accessible par la voix et MCP, puis démontrer son fonctionnement déployé avec des preuves cumulatives.

### Travail à réaliser dans cet ordre

1. Exposer les lectures et commandes du domaine à travers le serveur MCP versionné proposé dans le TDD. Vérifier authentification OAuth, portée des jetons et délégations internes. Les métadonnées fournies par un client ne choisissent pas son identité effective ; les outils n'offrent pas au modèle une approbation de ses propres actions.

2. Construire le transport vocal serveur et qualifier le couple AgentCore/Nova proposé. Ajouter admission, ticket à usage unique, contexte personnel ou partagé, formats audio négociés, interruptions, renouvellement de flux et reconnexion. Conserver les tours finalisés dans la mémoire et retrouver les tâches après fermeture de session.

3. Produire les annonces transactionnelles depuis l'état et les preuves, avec formulations contrôlées et synthèse Polly proposée dans le TDD. Distinguer demande reçue, attente d'approbation, résultat inconnu, commande confirmée et livraison effective. L'interruption du son ne constitue pas une annulation commerciale.

4. Brancher les signaux d'activité temps réel proposés via AppSync sur le journal durable par utilisateur. Vérifier autorisation des abonnements, reconnexion et rattrapage des événements manqués. Les notifications utilisent les canaux disponibles et autorisés ; leur livraison ne présume pas un accès à la parole proactive d'Alexa.

5. Finaliser la livraison de l'environnement de démonstration : artefacts immuables, configuration de région et de modèles, droits séparés, déploiement reproductible et compatibilité des tâches en cours. Qualifier export, effacement, restauration avec application des suppressions, rotation des secrets et retour à une version compatible. Un retour du code ne prétend pas annuler les effets fournisseur.

6. Exécuter les parcours complets et les essais de panne, charge et récupération. Mesurer latence, qualité de mémoire en français et en anglais, réussite des tâches, refus appropriés, consommation et coût observé. Préparer les preuves AWS Builder et la contribution Open Source complémentaire retenue, avec licence, dates, dépôt et validations ; distinguer préparation locale, publication, pull request et fusion.

**Contrats livrés :** outils MCP, session et transport vocal, résultat vocal sourcé, abonnement d'activité, export et effacement, manifeste de déploiement, procédures de récupération et rapport de qualification.

### Preuve de fin de l'étape 4

- [ ] Un client MCP et un client vocal soumettent et consultent les mêmes tâches. L'authentification, l'isolation des foyers et le mode partagé restent appliqués sur ces deux chemins.
- [ ] Fermer la voix immédiatement après acceptation laisse la tâche continuer ou attendre correctement ; la reconnexion retrouve son état. Un ticket expiré, réutilisé ou attribué à une autre session est refusé.
- [ ] Les annonces et résultats exposés correspondent aux preuves enregistrées. Un délai fournisseur dépassé n'est pas annoncé comme une commande ou une annulation réussie.
- [ ] Après perte des signaux temps réel, le rattrapage restitue l'activité autorisée sans exposer celle d'un autre membre.
- [ ] Les trois parcours de la note de concept passent sur le backend déployé : journée réorganisée, demande passée retrouvée et exécutée au moment prévu, plan adapté en cours. Agenda réel, modèles réels, commerce simulé et canal représentant Alexa sont identifiés séparément.
- [ ] Une restauration ou un déploiement interrompu ne rejoue pas aveuglément les actions externes, ne rétablit pas des données effacées et ne change pas le sens d'une approbation existante.
- [ ] Le rapport identifie résultats obtenus, objectifs non atteints, configurations, coûts observés et ressources encore actives. Il relie chaque usage AWS et contribution complémentaire effectivement réalisés à leurs fichiers et preuves.

**Backend terminé pour le manifeste retenu :** les capacités annoncées possèdent leurs preuves et les limites sont visibles. La candidature, la vidéo et la qualification de l'interface complète restent des travaux distincts. La fin de cette étape ne démontre pas à elle seule une intégration native Alexa+, tous les domaines de la vision ou l'admissibilité aux mini-défis.

## Où se range chaque chantier du TDD

| Chantier | Étape responsable |
| --- | --- |
| Périmètre, registre des décisions et manifeste de livraison — sections 1, 2 et 21 | 1 ; actualisation et preuves à chaque étape |
| Code partagé, configuration et infrastructure — sections 3, 4 et 18 | 1 pour le socle ; déploiement des composants avec leur étape ; livraison complète en 4 |
| Identité, droits, secrets et séparation privé/partagé — sections 11, 13 et 14 | 1 ; application aux souvenirs et comptes en 2, aux canaux en 4 |
| Commandes, tâches, outbox, files et reprise — sections 7, 11 et 12 | 1 ; plans et attentes métier en 3 |
| Mémoire, provenance, correction et recherche — sections 10 et 11 | 2 ; adaptation des préférences et procédures en 3 |
| Connecteurs, agenda et commerce simulé — section 9 | 2 ; réutilisation par les plans en 3 |
| Autorisations d'action, budgets, approbations et rapprochement — section 8 | 2 ; réapplication lors des changements de plan en 3 |
| Coordinateur, spécialistes et routage des modèles — section 6 | Embeddings en 2 ; planification en 3 ; parole en 4 |
| Routines, échéances et notifications — sections 7 et 15 | 3 ; transport des notifications et rattrapage en 4 |
| API de contrôle et contrats de domaine — section 12 | Dès 1, enrichissement avec chaque capacité |
| MCP, sessions et transport vocal serveur — sections 5, 12 et 13 | 4, sur les commandes et droits existants |
| Activité temps réel, caches et performance — section 15 | Journal durable en 1 ; caches avec leur usage ; diffusion et qualification globale en 4 |
| Résilience, observation, limites et coûts — sections 16, 17 et 19 | Dès 1 ; cas fournisseur en 2, limites de modèles en 3, exercices complets en 4 |
| Export, effacement et restauration — sections 11, 14 et 16 | Sauvegardes du socle en 1 ; suppression des souvenirs en 2 ; parcours complet en 4 |
| Vérifications et preuves — sections 20 et 22 | Recettes cumulatives à chaque étape ; rapport complet en 4 |
| Interface, audio navigateur et parcours visuels — section 5 | Chantier d'interface ; contrats serveur en 4 et validation conjointe du parcours vocal |

Un chantier présent dans plusieurs étapes enrichit un contrat existant. Les contrôles livrés restent actifs pendant les étapes suivantes ; un défaut découvert ensuite se corrige avec une vérification adaptée.

## Commencer par l'étape 1

Le premier résultat à rechercher est : **authentifier un membre, créer une tâche par API, interrompre son traitement puis retrouver la même tâche et un état cohérent après reprise, sans accès possible depuis un autre foyer.** Fixer cette recette et le manifeste avant de construire le socle. Elle ne nécessite ni interface complète, ni planification par modèle, ni connecteur marchand.

## Références du projet

- [Note de concept de Koyori](<Koyori — L’agent personnel de la maison.md>) : vision, mémoire, autonomie, parcours et stratégie du concours.
- [Technical Design Document](Koyori_Technical_Design_Document.md) : architecture proposée, contrats et critères techniques.
- [Journal de développement](JOURNAL.md) : décisions, état réel, difficultés et vérifications.
- [Règles du concours fournies](DEVDAY_REGLES.md) : texte conservé dans le dépôt ; exigences à recontrôler avant candidature.
- [Construire le backend de Kyro en cinq parties](<../Kyro_v2/docs/nvidia-hackathon/Construire le backend de Kyro en cinq parties.md>) : exemple de structure, d'ordre de construction et de preuves de fin.

Plan rédigé le 4 octobre 2026 à partir du concept, des sections pertinentes du TDD, du journal et de l'exemple fourni. Le document Kyro sert de référence de présentation ; ses consignes, sa pile technique et son périmètre ne deviennent pas des décisions pour Koyori. Aucune nouvelle qualification externe des API ou des conditions du concours n'est réalisée par ce découpage.
