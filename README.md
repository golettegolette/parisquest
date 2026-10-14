# Parisquest

Collectionnez Paris, lieu par lieu. Parisquest transforme près de 18 000 lieux réels de la capitale (arbres remarquables, fontaines, plaques commémoratives, monuments, stations, passages couverts, cafés historiques…) en cartes à collectionner. Pour capturer une carte, il faut se rendre sur place : le téléphone vérifie que vous êtes à portée grâce au GPS.

## Jouer

Ouvrez le site sur votre téléphone, autorisez la localisation, puis marchez. Sur iPhone (Safari) ou Android (Chrome), « Ajouter à l'écran d'accueil » installe le jeu comme une application.

Pour essayer sans se déplacer, ajoutez `?test` à l'adresse : un mode test apparaît, qui permet de se placer n'importe où en touchant la carte et de faire passer les jours.

## Règles

- **Paquets** : un paquet de 5 cartes toutes les 5 minutes, jusqu'à 10 en réserve (5 offerts au départ). Le compteur s'arrête quand la réserve est pleine.
- **Rareté** : chaque carte tirée a 60 % de chances d'être Commune, 25 % Peu commune, 10 % Rare, 4 % Épique, 1 % Légendaire. Le palier d'un lieu est fixé par centiles à l'intérieur de son type : un lieu célèbre (nombre d'éditions Wikipédia qui en parlent) est plus prestigieux, une station très fréquentée (validations Île-de-France Mobilités) est plus rare.
- **Doublons** : un lieu déjà possédé ajoute un exemplaire (×2, ×3…).
- **Visites** : aller sur place valide une carte possédée. Première visite : sceau « Visité ». Ensuite, une visite par jour fait monter la carte d'un niveau, jusqu'au niveau 5.
- **Collections** : 38 séries thématiques (Passages couverts, Stations fantômes, Ponts de Paris…), bonus de 50 écus à la complétion.
- **Écus** : calculés à partir de la collection (rareté, doublons, visites, collections complètes).

Tant que le serveur n'est pas branché, le jeu tourne en démo locale : la progression et le compteur restent dans le navigateur et ne sont pas protégés. Avec le serveur (dossier `supabase/`), les paquets, le tirage et la collection sont gérés côté serveur et impossibles à tromper. La position du joueur n'est jamais enregistrée.

## Contenu du dépôt

| Chemin | Rôle |
|---|---|
| `index.html` | le jeu complet (une seule page) |
| `data/places.json` | les 17 919 lieux, familles, types et collections |
| `data/map.json` | contours des parcs, arrondissements, Seine et biens UNESCO |
| `data/streets.json` | emprises des voies (plan de secours si le fond de carte ne charge pas) |
| `manifest.webmanifest`, `sw.js`, `icons/` | installation sur l'écran d'accueil et usage hors ligne |
| `supabase/` | serveur : schéma SQL sécurisé, référentiel des lieux, guide d'installation |
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
