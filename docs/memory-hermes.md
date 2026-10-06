# Mémoire durable, archives et apprentissage

Contrats actualisés le 2026-10-06. Ce chantier réutilise `MEMORY`, `MEMKEY`, `LEARNING` et les autorisations existantes. Les données canoniques constituent l'autorité ; aucun fichier de prompt n'est une seconde mémoire. Implémentation indépendante sous Apache-2.0, sans code importé de Hermes.

## Contexte et recherche

`POST /v1/context` conserve `includeCore=false` par défaut. Avec `true`, `coreItems` contient au plus huit préférences/procédures accessibles, découvertes par leurs clés, indépendamment des 500 derniers échanges. `items` conserve les filtres d'archive, notamment le jour civil dans le fuseau de la personne. `coreTruncated` indique un contexte durable incomplet ; `truncated` couvre aussi les archives et index. Le budget `maxCharacters` compte la représentation JSON des souvenirs, core compris. Une clé explicitement demandée est cherchée directement, même si la découverte des autres clés atteint 500 slots.

Pour la planification, les clés explicitement demandées précèdent pertinence lexicale, préférences personnelles et informations partagées. Au plus 14 souvenirs, dont huit durables, 8 000 caractères de souvenirs et 20 000 octets UTF-8 de payload complet. Le plan ne référence que la sélection finale ; `missingMemoryKeys` exige une clarification. Les révisions, sources et générations sont gardées avant chaque requête SDK et à la promotion.

`POST /v1/memories/search` accepte `query`, `day`, `kinds`, `key`, `limit` (1–8), `maxCharacters` (256–12 000) et `cursor`. `includeCore` reste `false` pour cette recherche. Normalisation Unicode NFKD, casse, accents et mots-outils FR/EN ; intersection de 1–8 termes significatifs. Le terme le plus long sert d'ancre, avec les autres termes vérifiés sur le texte canonique. Ce choix est déterministe, sans prétendre estimer la fréquence des termes.

Deux partitions accessibles au maximum : privée de la personne et partagée du foyer. Le curseur opaque chiffré lie acteur, foyer, paramètres et positions effectivement consommées, sans perdre la fin des buffers préchargés. Une page examine au plus 500 candidats ; une page vide avec `nextCursor` demande de continuer. Les filtres de journée suivent les frontières civiles, y compris les changements d'heure. Les résultats sont chronologiques dans la recherche paginée. Le contexte non paginé combine rappel lexical et sémantique disponible, avec pertinence avant récence ; les refus de quota et résultats incomplets sont annoncés.

`search_memories` est inscrit dans le registre commun MCP/voix. Une délégation personnelle recherche sa mémoire et le partage ; un appareil partagé ne lit que le partage. Les résultats, y compris `coreItems`, sont revérifiés avant restitution et pendant la lecture vocale. La recherche n'autorise aucune action ou partage.

## Index dérivé et migration

Les postings `LEX#scope#hash` ne contiennent que référence, révision, génération de confidentialité et scope. `LEXDOC#foyer#id` référence les postings à purger ; aucun texte n'est copié dans l'index. Les intentions `LEXRUN` remplacent les anciens termes par lots de 32, avec suppression conditionnelle, reprise et gardes canoniques. Elles sont indépendantes des quotas d'embedding et d'apprentissage. Une correction rend immédiatement les postings anciens inutilisables ; le worker les supprime ensuite. L'expiration détectée à la recherche programme une purge sans appeler de modèle.

`indexIncomplete` reste vrai tant que le backfill n'est pas achevé ou qu'une projection est en attente. Avant ouverture d'un namespace existant, arrêter les writers et exécuter l'outil opérateur local :

```powershell
uv run python -m koyori.backup reindex --writers-stopped
```

Configurer `KOYORI_TABLE_PREFIX` et les endpoints de la cible avant la commande. La reconstruction parcourt les mémoires canoniques et termine chaque intention par lecture cohérente ; elle ne dépend pas du délai du GSI. Elle est répétable et ne lance aucun apprentissage rétroactif. Cette commande locale n'est pas exposée au modèle ; pour AWS, appliquer la même primitive sous contrôle opérateur, avec permissions de scan et quarantaine, puis qualifier sur compte isolé.

## Propositions automatiques

Une transaction enregistrant un échange personnel admissible, ou la transition d'un objectif personnel `coordination.goal` vers `SUCCEEDED`, crée son intention `LEARNRUN`. Les échecs, annulations, acceptations de propositions et réindexations ne créent pas d'intention. Le worker `learning` est distinct du coordinateur, du connecteur et de la projection ; bail de 120 s, générations et reprise durable. Sur AWS un sweep est prévu chaque minute, une tentative finie à la fois dans la fenêtre Lambda. Aucune garantie de délai d'une minute n'est déduite de ce programme.

Strands/Nova reçoit une source autorisée et un petit contexte, sans outils d'exécution ; sortie typée de zéro à trois propositions. Les préférences exigent aussi un marqueur explicite durable FR/EN côté serveur ; les déclarations ponctuelles datées sont exclues. Ce filtre conservateur peut manquer une préférence formulée autrement ou dans une autre langue : la proposition manuelle reste disponible. Un achat confirmé seul ne produit pas une préférence, même si le modèle en propose une. Les procédures nécessitent instructions réutilisables ou étapes observées avec reçus `CONFIRMED` ; elles restent déclaratives et ne modifient aucune permission. La qualité linguistique du modèle distant reste à qualifier.

Chaque requête `Converse` réserve durablement un crédit avant HTTP : **deux sur toute la vie de l'intention**, réparations de schéma et reprises incluses, et **20 par jour UTC par personne**, tous ses foyers confondus. Le plafond peut être abaissé. Aucun retry Botocore caché. Un crash conserve les crédits réservés, même si la requête n'a pas atteint le fournisseur. Une erreur avec crédit restant réessaie après 30 s ; le quota quotidien reporte au lendemain, dans une fenêtre d'éligibilité de sept jours. Les messages fournisseur ne sont pas journalisés ; seuls code fixe, état, compteurs et usages sont persistés.

Publication atomique via `LEARNING`, notification privée groupée et déduplication durable des propositions identiques, y compris refusées. Le texte normalisé, la clé, les étapes et la révision cible participent au fingerprint. Les cibles d'une correction sont épinglées avant l'appel ; une clé apparue pendant l'appel ne devient pas sa cible. L'acceptation explicite vérifie sources et cible, puis crée/corrige le souvenir. Une correction conserve visibilité et expiration ; elle n'accroît pas budget ou autorisations. Lecture/export masquent une proposition dont la source/cible a changé.

Modes : `disabled` par défaut dans Settings et CDK ; `simulated` dans Compose local (fixture FR/EN limitée) ; `aws` seulement par configuration explicite. Pour la synthèse CDK, le contexte `learningEnabled=true` active le mode AWS. Il faut auparavant confirmer région/consentement pour le profil Nova US, accès modèle, coûts et logs dans un compte de qualification. Le transport intercepté teste le véritable SDK ; il ne prouve pas un appel AWS réel.

## Effacement et récupération

Le fence `PRIVACY` invalide immédiatement les anciens jobs, propositions et disclosures. L'effacement résumable parcourt mémoires, textes/étapes des propositions, jobs et fingerprints. Les postings/vecteurs se purgent par intentions indépendantes ; les lecteurs relisent le canon avant réponse. L'historique commercial et les textes d'objectif ont la rétention distincte existante.

Le registre de suppressions **2.0** couvre tombstones `MEMORY`/`LEARNING` et générations `PRIVACY`. Il est produit depuis la source actuelle arrêtée, après complétion des effacements. Une restauration conserve le maximum des générations, insère les fences absents de la sauvegarde, supprime tous les anciens jobs d'apprentissage et reconstruit l'index lexical des survivants sous `RESTORE_FENCE`. Un objectif restauré `SUCCEEDED` n'est pas réanalysé. Les snapshots 1.0 restent acceptés avec ce registre actuel 2.0 ; les anciens registres 1.0 doivent être régénérés. La cible reste bloquée après reconstruction jusqu'à la réconciliation opérateur.

## Recette isolée et sources

`local/memory.env` et `compose.memory.yaml` fixent projet `koyori-memory-hermes`, tables `KoyoriMemoryHermes*`, volumes dédiés, ports 8910/9354/8188/8198 et sous-réseau `10.253.45.0/24`. Vérifier leur disponibilité sur un autre poste.

```powershell
docker build -t koyori-memory-hermes:local .
docker compose --env-file local/memory.env -f compose.yaml -f compose.memory.yaml up -d --no-build
$env:KOYORI_MEMORY_ENV = '1'
uv run python scripts/verify_memory.py
```

Les cinq recettes existantes/nouvelle utilisent cet environnement quand `KOYORI_MEMORY_ENV=1`. Sans ce flag elles utilisent leur projet habituel. Les clés et rapports contenant des fixtures restent dans les volumes/répertoires ignorés.

Inspiration consultée le **2026-10-06**, dépôt fixé au commit [4787e4d56fc8d9265d4c7d3c0fe5accee86b4078](https://github.com/NousResearch/hermes-agent/tree/4787e4d56fc8d9265d4c7d3c0fe5accee86b4078) : [mémoire persistante](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory/), [skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/), [memory_tool.py](https://github.com/NousResearch/hermes-agent/blob/4787e4d56fc8d9265d4c7d3c0fe5accee86b4078/tools/memory_tool.py), [session_search_tool.py](https://github.com/NousResearch/hermes-agent/blob/4787e4d56fc8d9265d4c7d3c0fe5accee86b4078/tools/session_search_tool.py). Nous retenons la séparation mémoire compacte / historique / apprentissage. L'acceptation, les révisions, l'isolation du foyer et les quotas restent propres aux exigences de Koyori.

Preuves : [rapport de vérification](verification/memory-hermes.md) et JRN-028 dans [le journal](../JOURNAL.md). Aucun push, déploiement ou contribution complémentaire publié par ce chantier.
