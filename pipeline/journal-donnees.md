# Parisquest : journal des données et des choix

Ce journal recense tout ce que Parisquest fait aux données publiques qu'il utilise : ce qui est repris tel quel, ce qui est transformé, ce qui est retiré, et pourquoi. Il sert à justifier les choix auprès des fournisseurs (Ville de Paris, Île-de-France Mobilités, Wikimedia) ou de partenaires. Il est tenu à jour à chaque modification de la chaîne de données.

État au 18/10/2026 : **17 037 lieux**, 46 types, 8 familles, 38 séries, 164 quêtes.

## 1. Sources et licences

| Fournisseur | Jeu de données | Licence | Fichier |
|---|---|---|---|
| Ville de Paris (opendata.paris.fr) | Arbres remarquables | ODbL | arbresremarquablesparis.json |
| | Arbres à abattre pour raisons sanitaires | ODbL | arbres-a-abattre-…json |
| | Espaces verts et assimilés | ODbL | espaces_verts.geojson |
| | Jardins partagés ; jardins relais | ODbL | jardins-partages.json ; jardins-relais.json |
| | Fontaines à boire | ODbL | fontaines-a-boire.json |
| | Dénominations et emprises des voies actuelles | ODbL | denominations-emprises-voies-actuelles.json |
| | Voies en escalier (plan de voirie) | ODbL | plan-de-voirie-voies-en-escalier.json |
| | Plaques commémoratives | ODbL | plaques_commemoratives.json |
| | Femmes illustres à Paris (portraits) | ODbL | femmes-illustres-a-paris-portraits.json |
| | Référentiel archéologique de Paris | ODbL | referentiel-archeologique-de-paris.json |
| | PLU, biens inscrits au patrimoine mondial | ODbL | plu-annexes-biens-inscrits-au-patrimoine-mondial.json |
| | Lieux municipaux | ODbL | lieux-municipaux.json |
| | Marchés découverts | ODbL | marches-decouverts.json |
| | Kiosques de presse | ODbL | kiosques-de-presse.json |
| | Paris autrement, balades (POI) | ODbL | paris-autrement-…-poi.json |
| | Arrondissements ; voies d'eau | ODbL | arrondissements.geojson ; voies-deau.geojson |
| Île-de-France Mobilités (data.iledefrance-mobilites.fr) | Référentiel des arrêts | Licence Ouverte (Etalab) | arrets.json |
| | Validations sur le réseau ferré (fréquentation) | Licence Ouverte | validations.json |
| | Arrêts et lignes associées | Licence Ouverte | idfm-arrets-lignes.csv |
| | Référentiel des lignes (couleurs officielles) | Licence Ouverte | idfm-referentiel-des-lignes.csv |
| Wikimedia | Wikidata (requête SPARQL sur Paris, 4 quadrants) | CC0 | data/src/wikidata/sparql_*.json |
| | Wikipédia (liens d'articles en français) | lien seulement | |
| | Wikimedia Commons (photos) | licence de chaque photo, crédit affiché | |

Fond de carte du jeu : OpenFreeMap (données OpenStreetMap, ODbL), affiché par MapLibre.

## 2. Chaîne de construction

Fichiers bruts → `build2.py` (+ `wikidata.py`, `ridership.py`) → `ponts.py` → `vestiges.py` → `acces.py` → `lines.py` → `quests.py` → `build_server.py` (référentiel du serveur) et `build_site.py` (site). Tous les scripts sont publiés dans `site/pipeline/`.

## 3. Ville de Paris : ce qui est repris, transformé ou écarté

**Arbres remarquables** : tous repris. Rareté calculée sur l'âge (plantés avant 1900 : plus rare), la rareté du genre botanique dans Paris, la hauteur et le label « remarquable ». Les arbres des bois ont un rayon de capture de 100 m.

**Arbres à abattre** : repris comme « arbres en sursis » (440).

**Espaces verts** : seules les catégories Square, Jardin, Parc, Promenade, Bois, Arboretum, Île, Archipel, Forêt urbaine, Esplanade et Mail deviennent des cartes ; les cimetières servent au fond de carte. Jardins d'immeubles, talus, jardinières et autres catégories techniques écartés. Rareté : taille, catégorie et ancienneté.

**Jardins partagés et jardins relais** : repris.

**Fontaines à boire** : reprises (1 370) ; Wallace, pétillantes, albien et Millénaire forment des séries.

**Voies** :
- Toutes les voies nommées sont reprises (6 624), avec longueur, largeur, siècle de dénomination et historique. Rareté : ancienneté du nom, rareté du type de voie (belvédère, hameau, sente…), voies très courtes.
- Escaliers : retirés le 14/10/2026 (cartes isolées, peu lisibles).
- Ponts : pour les 49 ponts présents à la fois comme voie de la Ville et comme fiche Wikidata, c'est la voie qui est gardée (décision du 18/10/2026, voir § 5).
- 803 voies privées « non inscrites à la liste des voies privées ouvertes à la circulation publique » (villas, cours, cités, squares) restent dans le jeu, mais leur point est placé à leur entrée et elles se capturent depuis l'espace public (18/10/2026, voir § 6).

**Plaques commémoratives** : reprises (2 330). Classées par objet (résistants, écrivains, artistes, scientifiques, politiques, militaires, événements, victimes civiles de guerre, victimes du terrorisme). Les plaques des victimes sont gardées pour l'instant (décision du 18/10/2026, à revoir).

**Femmes illustres** : reprises (77), doublons entre onglets retirés.

**Référentiel archéologique** (décisions du 18/10/2026) :
- Constat : le jeu de données recense des opérations de fouille, pas des vestiges visibles ; presque tout est enfoui, détruit ou conservé au musée.
- Les fiches n'ayant pas de nom, `vestiges.py` lit la synthèse de chaque fiche et en tire un titre (« Sarcophages mérovingiens », « Voie romaine », « Temple antique »…), accordé avec l'époque citée près de la découverte, et une illustration. Le titre d'origine (« Vestiges antiques ») est conservé dans les données (`x.n0`).
- Sélection : seuls sont gardés les vestiges visibles (5 fiches relues à la main : crypte archéologique du parvis Notre-Dame (3), tour de la Liberté de la Bastille, chapelle de la Vierge de Saint-Germain-des-Prés) et ceux dont la synthèse décrit clairement une découverte. **833 fiches retirées** : sondages négatifs, provenance contestée, synthèses floues, découvertes trop vagues (« fondations », « habitat », « céramiques »). 978 fiches gardées, plus 3 fiches Wikidata (arènes de Lutèce, thermes de Cluny, Lutèce).
- Les vestiges de la Bastille et de la chapelle, remontés ailleurs, sont placés là où on les voit aujourd'hui (squares Henri-Galli et Laurent-Prache).
- Type renommé « Sous vos pieds » ; mention « Visible sur place » ou « Enfoui ou disparu ».
- Les titres sont produits automatiquement : quelques erreurs restent possibles.

**Patrimoine mondial** : 4 biens (rives de la Seine, tour Saint-Jacques, immeuble Molitor de Le Corbusier) ; capture n'importe où dans le périmètre. Le tracé en pointillés a été retiré de la carte le 18/10/2026.

**Lieux municipaux** : seules ces catégories sont reprises : musées municipaux, lieux de culte remarquables, bibliothèques, théâtres soutenus, conservatoires, ateliers Beaux-Arts, lieux de découverte, cimetières, mairies, bains-douches, piscines, baignades estivales, marchés spécialisés, skate parks, stades, terrains de boules.

**Marchés découverts**, **kiosques**, **Paris autrement** (lieux insolites) : repris.

**Arrondissements** : contours utilisés pour le fond de carte et, depuis le 18/10/2026, pour corriger l'arrondissement d'un lieu (voir § 5).

## 4. Île-de-France Mobilités

**Référentiel des arrêts** : stations de métro, RER, train, tramway et funiculaire situées dans Paris (code INSEE 751xx). Les quais d'un même nom distants de plus de 500 m sont séparés en deux stations. 352 stations (247 métro, 60 tram, 44 RER et train, 1 funiculaire).

**Validations** : la fréquentation fixe la rareté : plus une station est fréquentée, plus sa carte est commune ; les stations à un seul quai par sens gagnent un cran. Sans données : Peu commune.

**Lignes** (`lines.py`, 18/10/2026) :
- Chaque station est rattachée à ses lignes par l'identifiant d'arrêt, sinon par le nom à moins de 350 m et le même mode.
- Couleurs et noms officiels tirés du référentiel des lignes.
- Correctif manuel : gares de Bercy rattachées aux lignes 6 et 14.
- Vérifié contre Wikipédia (lignes 1, 4, 11, 14, 3bis, RER A à E).
- Gare Vaugirard (trains de Normandie) et ancien funiculaire de Belleville sans ligne.
- Pour les quêtes, une seule station par arrêt et par ligne (gare et station RER homonymes regroupées à moins de 600 m).

## 5. Wikimedia (Wikidata, Wikipédia, Commons)

- **Enrichissement** : une fiche Wikidata qui correspond à une carte existante (même type, nom proche, faible distance) lui ajoute le lien Wikipédia, la description, la photo Commons et la notoriété (nombre de langues de l'article). 9 536 cartes ont un article, 9 806 une photo (crédit affiché).
- **Nouvelles cartes** : 2 859 cartes viennent uniquement de Wikidata (édifices, hôtels particuliers, parcs, Paris disparu, œuvres, lieux de culte, théâtres, musées, cafés, enceintes, monuments, cinémas…).
- **Fiches écartées** : écoles et petite enfance, établissements de santé, prisons, police, armée, représentations diplomatiques ; organisations et événements qui ne sont pas des lieux. Voies, stations, plaques, arbres, voies privées et passages : enrichissement seulement, jamais de nouvelle carte.
- **Rareté** : log2(1 + langues) + ancienneté.
- **Ponts en double** (18/10/2026) : 49 ponts présents à la fois comme fiche Wikidata et comme voie de la Ville ; la voie est gardée et récupère la photo et l'article. Les viaducs du métro, les ponts du canal sans voie et les ponts disparus restent des fiches Wikidata. Série « Ponts de Paris » : 94 lieux.
- **Arrondissement corrigé d'après la position** (18/10/2026) : quand l'arrondissement d'une fiche ne correspond pas aux contours officiels, la position l'emporte (148 lieux, par exemple le Café de Flore, noté dans le 5e, passé au 6e), sauf à moins de 40 m d'une limite (l'Arc de triomphe reste dans le 8e).

## 6. Accès public et sécurité des joueurs (18/10/2026)

- **Lieux exclus** : écoles, crèches, hôpitaux, EHPAD, prisons, sites militaires et diplomatiques, propriétés privées.
- **Espace public** : calculé sur une grille de 2 m à partir des emprises des voies (publiques et privées ouvertes à la circulation) et des parcs, bois et cimetières.
- **Voies privées fermées** : 803 voies placées à leur entrée et capturables depuis l'entrée (40 m ou plus), sans y entrer.
- **Lieux loin de la rue** (gares, fonds de cour, œuvres dans des enceintes) : 621 lieux ont un rayon de capture allongé jusqu'à l'espace public (distance + 20 m, 150 m au plus). Une mention s'affiche sur la fiche du lieu.
- **Limite connue** : les grands jardins d'État (Luxembourg, Jardin des plantes, Tuileries, Villette) manquent aux données de la Ville. Leurs lieux sont donc capturables depuis la rue voisine.
- **Vie privée** : aucune position de joueur n'est enregistrée ; le serveur ne garde que le dernier lieu visité et son heure, pour le contrôle de vitesse.

## 7. Rareté (toutes sources)

Par type de lieu : 35 % Commune, 25 % Peu commune, 20 % Rare, 13 % Épique, 7 % Légendaire, d'après les scores décrits ci-dessus. Répartition actuelle : 6 834 / 3 617 / 4 012 / 1 490 / 1 084.

## 8. Séries et quêtes

**Séries** : 38 séries construites à partir des attributs des sources, par exemple :
- arbres plantés avant 1900 ;
- fontaines Wallace ;
- voies nommées avant le XVIᵉ siècle ;
- plaques d'Ancien Régime ;
- stations à un seul quai par sens ;
- ponts.

**Quêtes** (`quests.py`, 18/10/2026) : 164 quêtes en 14 catégories :
- Arrondissements et quartiers ;
- Lignes de métro ;
- RER, tram et funiculaire ;
- Stations et gares ;
- Personnalités ;
- Histoire et mémoire ;
- Sous vos pieds : vestiges archéologiques ;
- Patrimoine ;
- Nature ;
- Eau et ponts ;
- Culture ;
- Vie de quartier ;
- Rues et voies ;
- Grands défis.

Les arrondissements et les lignes sont rangés dans l'ordre croissant. Chaque quête a une description, son contenu calculé et jusqu'à 3 lieux phares.

**Récompenses** : 15 × √n PQ par palier, arrondi à 5, au moins 20.

## 9. Lieux retirés du jeu (historique)

| Date | Quoi | Nombre | Raison | Joueurs |
|---|---|---|---|---|
| 14/10/2026 | Escaliers | tous | cartes isolées dans la famille Rues | avant le serveur |
| 18/10/2026 | Ponts Wikidata en double | 49 | doublons de la voie de la Ville | cartes reportées sur la voie (ponts_doublons.sql) |
| 18/10/2026 | Fiches archéologiques sans découverte claire | 833 | rien à voir ni à raconter | 10 PQ par exemplaire (vestiges_retires.sql) |

## 10. Chronologie des décisions

- **14/10/2026** : base de 17 919 lieux, 38 collections ; escaliers retirés ; fiches Wikidata de voies privées jamais transformées en cartes ; serveur Supabase branché.
- **18/10/2026** :
  - concept paquets, capture sur place et quêtes ;
  - lignes de transport et couleurs IDFM ;
  - ponts dédoublonnés ;
  - capture selon l'accès public ;
  - arrondissements corrigés d'après la position ;
  - vestiges renommés puis triés (« Sous vos pieds ») ;
  - quêtes classées et décrites.
