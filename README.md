# Parisquest

Collectionnez Paris, lieu par lieu. Parisquest transforme près de 18 000 lieux réels de la capitale (arbres remarquables, fontaines, plaques commémoratives, monuments, stations, passages couverts, cafés historiques…) en cartes à collectionner. Pour capturer une carte, il faut se rendre sur place : le téléphone vérifie que vous êtes à portée grâce au GPS.

## Jouer

Ouvrez le site sur votre téléphone, autorisez la localisation, puis marchez. Sur iPhone (Safari) ou Android (Chrome), « Ajouter à l'écran d'accueil » installe le jeu comme une application.

Pour essayer sans se déplacer, ajoutez `?test` à l'adresse : un mode test apparaît, qui permet de se placer n'importe où en touchant la carte et de faire passer les jours.

## Règles

- **Le principe** : collectionnez Paris en le parcourant. Chaque lieu réel est une carte, et on la gagne en y allant.
- **Capture** : sur place, n'importe quel lieu se capture (le téléphone vérifie que vous êtes à portée, le serveur aussi). La carte entre dans la collection déjà visitée. Ensuite, une visite par jour la fait monter d'un niveau, jusqu'au niveau 5.
- **Paquet du jour** : un paquet gratuit par jour (3 en réserve au plus), avec 5 lieux tirés près de vous. Ces cartes sont « à découvrir » : elles apparaissent sur la carte et deviennent à vous quand vous allez les capturer.
- **Rareté** : 60 % Commune, 25 % Peu commune, 10 % Rare, 4 % Épique, 1 % Légendaire dans les paquets. Le palier d'un lieu est fixé par centiles dans son type (notoriété Wikipédia, fréquentation des stations). Sur la carte, les lieux Rares et mieux à moins de 400 m sont entourés de leur couleur.
- **Score** : Commune 1 point, Peu commune 2, Rare 5, Épique 15, Légendaire 50, doublés si la carte a été visitée sur place.
- **Classements** : Paris, par arrondissement et entre amis. Le premier collectionneur d'un arrondissement en est le Maître.
- **Séries** : 38 collections thématiques. **Succès** : objectifs à paliers.
- **Garde-fous** : 60 visites par jour au maximum, visite refusée si le déplacement depuis la précédente suppose plus de 50 km/h. La position sert à vérifier la portée et à tirer les lieux proches ; elle n'est jamais enregistrée.

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
