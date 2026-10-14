-- Requêtes utiles sur parisquest.sqlite
-- Ouvrir : sqlite3 parisquest.sqlite   (ou DB Browser for SQLite)

-- 1. Répartition des raretés par famille (contrôle de l'équilibre du jeu)
SELECT * FROM v_rarity_by_family;

-- 2. Les cartes légendaires d'un arrondissement
SELECT family, kind, name, address
FROM v_places
WHERE arrondissement = 18 AND rarity_level = 4
ORDER BY family, name;

-- 3. Nombre de cartes par arrondissement (densité de jeu)
SELECT arrondissement, COUNT(*) AS cartes, SUM(rarity >= 3) AS epiques_ou_plus
FROM places WHERE arrondissement IS NOT NULL
GROUP BY arrondissement ORDER BY cartes DESC;

-- 4. Lieux dans un rayon de ~300 m autour d'un point (ici Notre-Dame), du plus proche au plus loin
--    Distance approchée en mètres, suffisante à l'échelle de Paris
WITH c AS (SELECT 48.8530 AS lat, 2.3499 AS lon)
SELECT v.family, v.kind, v.name,
       ROUND(111195 * sqrt((v.lat - c.lat) * (v.lat - c.lat) + ((v.lon - c.lon) * 0.6577) * ((v.lon - c.lon) * 0.6577))) AS distance_m
FROM v_places v, c
WHERE v.lat BETWEEN c.lat - 0.003 AND c.lat + 0.003
  AND v.lon BETWEEN c.lon - 0.0045 AND c.lon + 0.0045
ORDER BY distance_m;

-- 5. Taille et avancement type de chaque collection
SELECT f.name AS famille, c.name AS collection, COUNT(cp.place_id) AS lieux
FROM collections c JOIN families f ON f.id = c.family_id
JOIN collection_places cp ON cp.collection_id = c.id
GROUP BY c.id ORDER BY famille, lieux;

-- 6. Fiche complète d'une carte avec ses caractéristiques
SELECT p.name, p.subtitle, p.highlight, pf.label, pf.value
FROM places p LEFT JOIN place_facts pf ON pf.place_id = p.id
WHERE p.id = 'arbre:2002352'
ORDER BY pf.position;

-- 7. Marchés ouverts le dimanche, avec leurs horaires
SELECT p.name, p.address, mh.opens, mh.closes
FROM market_hours mh JOIN places p ON p.id = mh.place_id
WHERE mh.day = 6 ORDER BY mh.opens;

-- 8. Lire un attribut propre à un type (ici : les fontaines Wallace par arrondissement)
SELECT arrondissement, COUNT(*) AS wallace
FROM places
WHERE kind_id = 'fontaine' AND json_extract(attributes, '$.ft') = 'FONTNE_WALLACE'
GROUP BY arrondissement ORDER BY wallace DESC;

-- 9. Ajuster une règle de rareté : passer toutes les fontaines pétillantes en Légendaire
--    (puis relancer l'export : python3 -c "import db; db.export('parisquest.sqlite', 'site/data')")
-- UPDATE places SET rarity = 4 WHERE kind_id = 'fontaine' AND json_extract(attributes, '$.ft') = 'FTNE_PETILLANTE';

-- 10. Stations les plus rares (petites stations, peu de quais)
SELECT name, subtitle AS mode, arrondissement, rarity
FROM places WHERE kind_id = 'station' AND rarity = 4 ORDER BY name;
