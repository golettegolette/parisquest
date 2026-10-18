# Parisquest

Collectionnez Paris, lieu par lieu. Parisquest transforme près de 18 000 lieux réels de la capitale (arbres remarquables, fontaines, plaques commémoratives, monuments, stations, passages couverts, cafés historiques…) en cartes à collectionner. Pour capturer une carte, il faut se rendre sur place : le téléphone vérifie que vous êtes à portée grâce au GPS.

## Jouer

Ouvrez le site sur votre téléphone, autorisez la localisation, puis marchez. Sur iPhone (Safari) ou Android (Chrome), « Ajouter à l'écran d'accueil » installe le jeu comme une application.

Pour essayer sans se déplacer, ajoutez `?test` à l'adresse : un mode test apparaît, qui permet de se placer n'importe où en touchant la carte et de faire passer les jours.

## Règles

- **Paquets** : un paquet de 5 cartes toutes les 10 minutes (2 minutes avec le Pass PariGo), jusqu'à 10 en réserve, 5 offerts au départ. Chances par carte : 60 % Commune, 25 % Peu commune, 10 % Rare, 4 % Épique, 1 % Légendaire.
- **Capture sur place** : n'importe quel lieu se capture en y allant (portée vérifiée par le serveur). Une carte visitée porte le sceau « Visité » ; une visite par jour la fait monter d'un niveau, jusqu'au niveau 5.
- **Quêtes** : 159 quêtes (arrondissements, rives, lignes de métro, RER et tramway, familles, séries, thèmes, raretés), souvent en paliers. Toutes les cartes comptent, quelle que soit leur origine. Chaque palier rapporte des PQ, une seule fois ; le dernier donne un titre. Toucher une quête montre ses lieux sur la carte.
- **PQ** : la monnaie du jeu. Gagnés avec les quêtes, achetés en Boutique (500 PQ pour 0,99 € et plus), dépensés au Marché aux enchères. Jamais reconvertibles en argent.
- **Boutique** : 10 paquets pour 0,99 € ; Pass PariGo à 3,99 € par mois ; Pack PariGo à 1,49 € (20 cartes, une Épique ou mieux garantie) ; Pack Arrondissement à 2,49 € (15 cartes d'un arrondissement choisi).
- **Classements** : collectionneurs de Paris, par arrondissement (le premier est Maître de l'arrondissement), entre amis, et classement des quêtes.
- **Stations** : chaque station affiche les pastilles de ses lignes, aux couleurs officielles d'Île-de-France Mobilités.
- La position du joueur sert à vérifier la portée ; elle n'est jamais enregistrée.

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
- **Île-de-France Mobilités**, [data.iledefrance-mobilites.fr](https://data.iledefrance-mobilites.fr) : arrêts, validations sur le réseau ferré, arrêts et lignes associées, référentiel des lignes (couleurs). Licence Ouverte v2.0.
- **Wikidata**, [wikidata.org](https://www.wikidata.org) : lieux et monuments, notoriété, dates. CC0.
- **Photos** : Wikimedia Commons (licence propre à chaque image, voir le lien « Photo » au dos de la carte) et Ville de Paris (crédit indiqué sur la carte).
- **Fond de carte** : [OpenFreeMap](https://openfreemap.org), données © [contributeurs OpenStreetMap](https://www.openstreetmap.org/copyright) (ODbL), schéma OpenMapTiles.
- **Bibliothèque** : [MapLibre GL JS](https://maplibre.org) (BSD-3-Clause). Polices Barlow, Barlow Condensed et Literata (SIL Open Font License) via Google Fonts.

Lieux volontairement exclus : propriétés privées, écoles et crèches, établissements de santé, sites militaires, prisons, commissariats et ambassades.
