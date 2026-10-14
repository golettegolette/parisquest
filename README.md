# Parisquest

Collectionnez Paris, lieu par lieu. Parisquest transforme près de 18 000 lieux réels de la capitale (arbres remarquables, fontaines, plaques commémoratives, monuments, stations, passages couverts, cafés historiques…) en cartes à collectionner. Pour capturer une carte, il faut se rendre sur place : le téléphone vérifie que vous êtes à portée grâce au GPS.

## Jouer

Ouvrez le site sur votre téléphone, autorisez la localisation, puis marchez. Sur iPhone (Safari) ou Android (Chrome), « Ajouter à l'écran d'accueil » installe le jeu comme une application.

Pour essayer sans se déplacer, ajoutez `?test` à l'adresse : un mode test apparaît, qui permet de se placer n'importe où en touchant la carte et de faire passer les jours.

## Règles

- **Paquets** : un paquet de 5 cartes toutes les 5 minutes (2 minutes avec le Pass PariGo), jusqu'à 10 en réserve, 5 offerts au départ. Ouverture animée : le paquet se déchire, les cartes apparaissent face cachée de la moins rare à la plus rare ; on les retourne au toucher ou avec les flèches du clavier.
- **Rareté** : chaque carte tirée a 60 % de chances d'être Commune, 25 % Peu commune, 10 % Rare, 4 % Épique, 1 % Légendaire. Le palier d'un lieu est fixé par centiles à l'intérieur de son type : un lieu célèbre (nombre d'éditions Wikipédia qui en parlent) est plus prestigieux, une station très fréquentée (validations Île-de-France Mobilités) est plus rare. Cadre de couleur et étoiles selon la rareté, reflets pour les Épiques, feuille d'or animée pour les Légendaires.
- **Doublons** : un lieu déjà possédé ajoute un exemplaire (×2, ×3…) et rapporte 5 écus.
- **Visites** : aller sur place valide une carte possédée (+10 écus). Première visite : sceau « Visité ». Ensuite, une visite par jour fait monter la carte d'un niveau, jusqu'au niveau 5.
- **Collections** : 38 séries thématiques, 50 écus à la complétion. **Succès** : 13 objectifs à paliers (10, 25, 60, 150 écus).
- **Bataille** : deck de 5 cartes, 5 terrains annoncés, +30 % pour la famille du terrain.
- **Boutique** : 10 paquets pour 0,99 € (ajoutés à la réserve, sans limite) ; Pass PariGo à 4 € par mois (un paquet toutes les 2 minutes et un Pack PariGo offert chaque jour) ; Pack PariGo à 1,49 € (20 cartes, 32 / 28 / 22 / 13 / 5 %, une Épique ou mieux garantie) ; écus de 0,99 € à 9,99 € pour le Marché. Les écus ne sont jamais reconvertibles en argent.
- **Après un paquet** : le paquet suivant s'ouvre directement depuis l'écran d'ouverture, ou s'affiche grisé avec le chrono. Chaque nouvelle carte montre une mini-carte du quartier.

Tant que le serveur n'est pas branché, le jeu tourne en démo locale : la progression et le compteur restent dans le navigateur et ne sont pas protégés. Avec le serveur (dossier `supabase/`), les paquets, le tirage et la collection sont gérés côté serveur et impossibles à tromper. La position du joueur n'est jamais enregistrée.

## Contenu du dépôt

| Chemin | Rôle |
|---|---|
| `index.html` | le jeu complet (une seule page) |
| `data/places.json` | les 17 919 lieux, familles, types et collections |
| `data/map.json` | contours des parcs, arrondissements, Seine et biens UNESCO |
| `data/streets.json` | emprises des voies (plan de secours si le fond de carte ne charge pas) |
| `manifest.webmanifest`, `sw.js`, `icons/` | installation sur l'écran d'accueil et usage hors ligne |
| `supabase/` | serveur : schéma SQL sécurisé, référentiel des lieux, fonctions de paiement Stripe, guide d'installation |
| `pipeline/` | scripts qui produisent les données à partir des sources ouvertes |

## Sources et licences

Les données de jeu (`data/*.json`) sont une base dérivée des sources ci-dessous et sont publiées sous **Open Database License (ODbL)**, comme l'exige la licence des données de la Ville de Paris.

- **Ville de Paris**, [opendata.paris.fr](https://opendata.paris.fr) : arbres remarquables, arbres d'alignement, espaces verts, fontaines, plaques commémoratives, dénominations des voies, marchés, kiosques, colonnes Morris, sanisettes, jardins partagés, emprises des voies, arrondissements, voies d'eau. Licence ODbL.
- **Île-de-France Mobilités**, [data.iledefrance-mobilites.fr](https://data.iledefrance-mobilites.fr) : arrêts et validations sur le réseau ferré. Licence Ouverte v2.0.
- **Wikidata**, [wikidata.org](https://www.wikidata.org) : lieux et monuments, notoriété, dates. CC0.
- **Photos** : Wikimedia Commons (licence propre à chaque image, voir le lien « Photo » au dos de la carte) et Ville de Paris (crédit indiqué sur la carte).
- **Fond de carte** : [OpenFreeMap](https://openfreemap.org), données © [contributeurs OpenStreetMap](https://www.openstreetmap.org/copyright) (ODbL), schéma OpenMapTiles.
- **Bibliothèque** : [MapLibre GL JS](https://maplibre.org) (BSD-3-Clause). Polices Barlow, Barlow Condensed et Literata (SIL Open Font License) via Google Fonts.

Lieux volontairement exclus : propriétés privées, écoles et crèches, établissements de santé, sites militaires, prisons, commissariats et ambassades.
