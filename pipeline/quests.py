"""Quêtes de Parisquest : définitions pour le jeu (site/data/quests.json) et pour le serveur (site/supabase/quests_data.sql).

Une quête = un ensemble de lieux et des paliers. Règles de comptage (identiques dans le jeu et sur le serveur) :
  arr <n>      lieux de l'arrondissement n            fam <f>   lieux de la famille f
  rive <g|d>   rive gauche (5, 6, 7, 13, 14, 15) ou droite (autres arrondissements)
  kind <k>     lieux du type k                         tier <t>  lieux de la rareté t
  tag <id>     liste explicite de lieux (séries, lignes, thèmes) : table place_tags
  all          toutes les cartes        arrs   arrondissements représentés (sur 20)
  kinds        types représentés        series séries terminées (sur 38)
Toutes les cartes comptent, qu'elles viennent d'un paquet, d'un achat, d'un échange ou d'une capture.

Récompense d'un palier de n lieux : R(n) = 15 × √n PQ, arrondie à 5 (au moins 20 PQ).
Pour rester cohérent avec la Boutique (500 PQ = 0,99 €) : une petite quête vaut quelques centimes, une ligne de métro
environ 0,15 €, un arrondissement complet environ 1 € (paliers cumulés environ 3 €). Tout finir (les 17 919 cartes)
rapporterait environ 165 € de PQ, ce qui est hors de portée en pratique.
Les quêtes ne se refont pas : impossible de « fabriquer » des PQ en boucle."""
import json, math, re, pathlib, collections, unicodedata
ROOT = pathlib.Path(__file__).parent
pl = json.load(open(ROOT / "site" / "data" / "places.json"))
I = pl["items"]; K = pl["kinds"]; F = pl["families"]; COLS = pl["collections"]; LINES = pl.get("lines", {})
fam = lambda it: K[it["k"]]["f"]
LEFT = {5, 6, 7, 13, 14, 15}
ar = lambda it: int(it["r"]) if it.get("r") and str(it["r"]).isdigit() else None
def r5(x): return max(20, int(round(x / 5.0)) * 5)
R = lambda n: r5(15 * math.sqrt(n))
def tiers_for(n):
    if n >= 200: return [0.10, 0.25, 0.50, 1.0]
    if n >= 60: return [0.25, 0.50, 1.0]
    return [1.0]
def hav(a1, o1, a2, o2):
    r = math.radians
    return 2 * 6371000 * math.asin(math.sqrt(math.sin(r(a2 - a1) / 2) ** 2 + math.cos(r(a1)) * math.cos(r(a2)) * math.sin(r(o2 - o1) / 2) ** 2))

Q, TAGS = [], {}
def quest(cat, qid, name, title, desc, rule, val, members=None, total=None, tiers=None, steps=None):
    if members is not None:
        members = sorted(set(members)); total = len(members)
        if rule == "tag": TAGS[val] = members
    if not total: return
    if steps is None: steps = sorted({max(1, math.ceil(total * p)) for p in (tiers or tiers_for(total))})
    Q.append({"id": qid, "cat": cat, "name": name, "title": title, "desc": desc, "rule": rule, "val": val, "total": total,
              "steps": steps, "rewards": [R(s) for s in steps]})
ITEMS_BY = lambda pred: [it["i"] for it in I if pred(it)]

# ---------- Territoires ----------
for a in range(1, 21):
    o = "1er" if a == 1 else f"{a}e"
    quest("Territoires", f"arr-{a}", f"Le {o} arrondissement", f"Seigneur du {o}", f"Les lieux du {o} arrondissement.", "arr", str(a), ITEMS_BY(lambda it, a=a: ar(it) == a))
quest("Territoires", "rive-d", "La rive droite", "Boss de la rive droite", "Les lieux des arrondissements de la rive droite.", "rive", "d", ITEMS_BY(lambda it: ar(it) and ar(it) not in LEFT))
quest("Territoires", "rive-g", "La rive gauche", "Boss de la rive gauche", "Les lieux des arrondissements de la rive gauche.", "rive", "g", ITEMS_BY(lambda it: ar(it) in LEFT))
quest("Territoires", "montmartre", "Montmartre", "Gamin de la Butte", "Les lieux de la Butte Montmartre.", "tag", "zone:montmartre",
      ITEMS_BY(lambda it: ar(it) == 18 and 48.8825 < it["a"] < 48.8895 and 2.3345 < it["o"] < 2.3460))
quest("Territoires", "bois", "Les Bois de Paris", "Garde forestier", "Boulogne et Vincennes.", "tag", "zone:bois", ITEMS_BY(lambda it: "Bois de" in (it.get("site") or "")))
quest("Territoires", "tour", "Tour de Paris", "Globe-trotteur parisien", "Au moins une carte dans chacun des 20 arrondissements.", "arrs", "", total=20, steps=[5, 10, 20])

# ---------- Familles ----------
FT = {"nature": ("Amoureux du vert", "Toute la nature de Paris."), "eau": ("Porteur d'eau", "Fontaines, ponts, bains et baignades."),
      "rues": ("Arpenteur", "Les voies de Paris."), "memoire": ("Gardien de la mémoire", "Plaques, femmes illustres et tombes."),
      "patrimoine": ("Gardien du patrimoine", "Vestiges, édifices, hôtels, lieux de culte."), "culture": ("Rat de culture", "Musées, théâtres, cinémas, œuvres."),
      "quartier": ("Titi parisien", "Kiosques, marchés, cafés, Paris insolite."), "transport": ("Roi du métro", "Stations et gares.")}
for f, (t, dsc) in FT.items():
    quest("Familles", f"fam-{f}", F[f]["name"], t, dsc, "fam", f, ITEMS_BY(lambda it, f=f: fam(it) == f))

# ---------- Transports : lignes (une station par arrêt, sans doublon entre gare et station RER) ----------
def norm(s):
    s = unicodedata.normalize("NFD", s.lower()); s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s.replace("gare de", "").replace("gare d", "").replace("gare", "").replace("bienvenue", "").replace("paris", ""))
st = [it for it in I if it["k"] == "station"]
per_line = collections.defaultdict(list)
for it in st:
    for c in it.get("ln", []): per_line[c].append(it)
def dedupe(L):
    keep = []
    for it in sorted(L, key=lambda it: (len(it["n"]), it["n"])):
        a = norm(it["n"])
        if any(hav(it["a"], it["o"], k["a"], k["o"]) < 600 and (a in norm(k["n"]) or norm(k["n"]) in a) for k in keep): continue
        keep.append(it)
    return keep
ORDER = sorted(per_line, key=lambda c: ({"metro": 0, "rer": 1, "tram": 2, "train": 3, "funi": 4}[LINES[c]["m"]], len(LINES[c]["l"]), LINES[c]["l"]))
for c in ORDER:
    m = LINES[c]["m"]; L = dedupe(per_line[c])
    if m == "train" or len(L) < 3: continue           # Transilien : 2 ou 3 gares par ligne, regroupées plus bas
    lab = LINES[c]["n"]
    title = {"metro": f"Pilote du {LINES[c]['l']}", "rer": f"As du RER {LINES[c]['l']}", "tram": f"Conducteur du {LINES[c]['l']}", "funi": "Funambule"}[m]
    quest("Transports", f"ligne-{c}", lab, title, f"Toutes les stations de la ligne dans Paris.", "tag", f"ligne:{c}", [it["i"] for it in L], tiers=[1.0])
quest("Transports", "funiculaire", "Funiculaire de Montmartre", "Funambule", "La gare basse et la gare haute.", "tag", "ligne:FUN", [it["i"] for it in per_line.get("FUN", [])], tiers=[1.0])
quest("Transports", "stations", "Toutes les stations", "Roi du sous-sol", "Métro, RER, tramway et gares dans Paris.", "kind", "station", [it["i"] for it in st])
nlines = {it["i"]: len([c for c in it.get("ln", []) if LINES[c]["m"] in ("metro", "rer")]) for it in st}
hubs = dedupe([it for it in st if nlines[it["i"]] >= 4])
quest("Transports", "hubs", "Les grandes correspondances", "Maître des correspondances", "Les stations où se croisent au moins 4 lignes de métro ou de RER.", "tag", "theme:hubs", [it["i"] for it in hubs], tiers=[1.0])
busy = sorted(dedupe([it for it in st if (it.get("x") or {}).get("valid")]), key=lambda it: -it["x"]["valid"])[:10]
quest("Transports", "busy", "Les 10 plus fréquentées", "Heure de pointe", "Les stations aux plus fortes validations.", "tag", "theme:busy", [it["i"] for it in busy], tiers=[1.0])

# ---------- Séries (les 38 collections du jeu) ----------
for ci, (f, name, sub, idxs) in enumerate(COLS):
    quest("Séries", f"serie-{ci}", name, f"Collectionneur : {name}", sub, "tag", f"serie:{ci}", [I[i]["i"] for i in idxs])

# ---------- Thèmes ----------
def by(k, pred=lambda it: True): return ITEMS_BY(lambda it: it["k"] == k and pred(it))
sub = lambda s: (lambda it: (it.get("s") or "") == s)
THEMES = [
    # Eau
    ("Eau", "fontaines-monu", "Fontaines monumentales", "Esthète des fontaines", "Les grandes fontaines de Paris.", by("fontaine", lambda it: (it.get("x") or {}).get("ft") == "MONUMENTALE")),
    ("Eau", "piscines", "Piscines", "Nageur de Paris", "Les piscines de la ville.", by("piscine")),
    ("Eau", "fontaines", "Toutes les fontaines", "Source vive", "Toutes les fontaines de Paris.", by("fontaine")),
    # Nature
    ("Nature", "arbres", "Arbres remarquables", "Ami des arbres", "Les arbres classés remarquables.", by("arbre")),
    ("Nature", "platanes", "Platanes remarquables", "Ombre des platanes", "Les platanes remarquables.", by("arbre", lambda it: (it.get("x") or {}).get("g") == "Platanus")),
    ("Nature", "jpart", "Jardins partagés", "Main verte", "Les jardins cultivés par les habitants.", by("jpart")),
    ("Nature", "squares", "Les squares", "Roi des squares", "Les squares de Paris.", by("parc", sub("Square"))),
    ("Nature", "sursis", "Arbres en sursis", "Sauveur d'arbres", "Les arbres menacés d'abattage.", by("sursis")),
    ("Nature", "parcs", "Parcs et jardins", "Promeneur", "Tous les parcs, jardins et promenades.", by("parc")),
    # Mémoire
    *[("Mémoire", f"plaque-{i}", n, t, d, by("plaque", sub(s))) for i, (s, n, t, d) in enumerate([
        ("Résistants", "Les résistants", "Mémoire de la Résistance", "Les plaques des résistants."),
        ("Écrivains et intellectuels", "Écrivains et intellectuels", "Homme de lettres", "Là où ils ont vécu ou écrit."),
        ("Artistes (beaux-arts)", "Peintres et sculpteurs", "Œil d'artiste", "Les artistes des beaux-arts."),
        ("Artistes (musique et danse)", "Musique et danse", "Mélomane", "Musiciens, compositeurs, danseurs."),
        ("Artistes (théâtre et cinéma)", "Théâtre et cinéma", "Cinéphile", "Acteurs, metteurs en scène, cinéastes."),
        ("Médecins et scientifiques", "Médecins et scientifiques", "Savant de Paris", "Les grands noms de la science."),
        ("Politiques", "Les politiques", "Homme d'État", "Personnalités politiques."),
        ("Évènements et faits historiques", "Les grands événements", "Témoin de l'histoire", "Là où l'histoire s'est jouée."),
        ("Militaires", "Les militaires", "Stratège", "Officiers et soldats."),
        ("Victimes civiles de guerre", "Victimes civiles de guerre", "Devoir de mémoire", "En mémoire des victimes civiles."),
        ("Victimes du terrorisme", "Victimes du terrorisme", "Veilleur", "En mémoire des victimes du terrorisme."),
    ])],
    ("Mémoire", "femmes", "Femmes illustres", "Ambassadrice des femmes illustres", "Les plaques des femmes illustres.", by("femme")),
    ("Mémoire", "tombes", "Tombes célèbres", "Pèlerin", "Les tombes des personnalités.", by("tombe")),
    ("Mémoire", "plaques", "Toutes les plaques", "Gardien des plaques", "Toutes les plaques commémoratives.", by("plaque")),
    # Patrimoine
    ("Patrimoine", "antiquite", "Lutèce antique", "Archéologue de Lutèce", "Les vestiges de l'Antiquité.", by("vestige", lambda it: "antiquite" in (it.get("x") or {}).get("per", []))),
    ("Patrimoine", "moyenage", "Paris médiéval", "Chevalier de Paris", "Les vestiges du Moyen Âge.", by("vestige", lambda it: "moyen_age" in (it.get("x") or {}).get("per", []))),
    ("Patrimoine", "modernes", "Temps modernes", "Historien", "Les vestiges des XVIᵉ au XVIIIᵉ siècles.", by("vestige", lambda it: "temps_modernes" in (it.get("x") or {}).get("per", []))),
    ("Patrimoine", "hotels", "Hôtels particuliers", "Marquis", "Tous les hôtels particuliers.", by("hotelpart")),
    ("Patrimoine", "culte", "Lieux de culte", "Pèlerin de Paris", "Églises, temples, synagogues, mosquées.", by("culte")),
    ("Patrimoine", "synagogues", "Synagogues", "Gardien des synagogues", "Les synagogues de Paris.", by("culte", lambda it: (it.get("s") or "").startswith("Synagogue"))),
    ("Patrimoine", "cathedrales", "Cathédrales", "Bâtisseur de cathédrales", "Les cathédrales de Paris.", by("culte", lambda it: (it.get("s") or "").startswith("Cathédrale"))),
    ("Patrimoine", "abbayes", "Abbayes et couvents", "Moine copiste", "Abbayes, couvents et prieurés.", by("abbaye")),
    ("Patrimoine", "monuments", "Monuments", "Guide de Paris", "Les monuments de Paris.", by("monument")),
    ("Patrimoine", "edifices", "Édifices", "Architecte", "Les édifices remarquables.", by("edifice")),
    # Culture
    ("Culture", "theatres", "Théâtres et salles", "Roi de la scène", "Théâtres et salles de spectacle.", by("theatre")),
    ("Culture", "cinemas", "Cinémas", "Cinéphile averti", "Les cinémas de Paris.", by("cinema")),
    ("Culture", "biblios", "Bibliothèques", "Rat de bibliothèque", "Les bibliothèques de Paris.", by("biblio")),
    ("Culture", "oeuvres", "Œuvres d'art et street art", "Chasseur d'œuvres", "Œuvres dans l'espace public.", by("oeuvre")),
    ("Culture", "galeries", "Galeries", "Collectionneur d'art", "Les galeries d'art.", by("galerie")),
    ("Culture", "ateliers", "Ateliers d'artistes", "Bohème", "Les ateliers d'artistes.", by("atelier")),
    ("Culture", "lieuxculture", "Lieux culturels", "Noctambule", "Les lieux culturels.", by("lieuculture")),
    # Quartier
    ("Quartier", "kiosques", "Kiosques à journaux", "Crieur de journaux", "Les kiosques de Paris.", by("kiosque")),
    ("Quartier", "marches", "Marchés", "Roi du marché", "Les marchés alimentaires.", by("marche")),
    ("Quartier", "commerces", "Commerces", "Chineur", "Les commerces remarquables.", by("magasin")),
    ("Quartier", "insolite", "Paris insolite", "Curieux de Paris", "Les lieux étonnants.", by("insolite")),
    ("Quartier", "boules", "Terrains de boules", "Pointeur", "Les terrains de pétanque.", by("sport", sub("Terrains de boules"))),
    # Rues
    *[("Rues", f"rue-{s.lower()}", n, t, d, by("rue", sub(s))) for s, n, t, d in [
        ("Villa", "Les villas", "Villégiateur", "Les villas, voies privées ouvertes au public."),
        ("Impasse", "Les impasses", "Explorateur d'impasses", "Au bout de chaque impasse."),
        ("Cité", "Les cités", "Citadin", "Les cités de Paris."),
        ("Passage", "Les passages", "Passe-muraille", "Les passages de Paris."),
        ("Quai", "Les quais", "Bouquiniste", "Les quais de Paris."),
        ("Boulevard", "Les boulevards", "Boulevardier", "Les boulevards de Paris."),
        ("Avenue", "Les avenues", "Flâneur", "Les avenues de Paris."),
        ("Place", "Les places", "Maître des places", "Les places de Paris."),
    ]],
]
for cat, qid, name, title, desc, members in THEMES:
    quest(cat, qid, name, title, desc, "tag", f"theme:{qid}", members)

# ---------- Rareté et prestige ----------
def langs(it):
    for v in it.get("f") or []:
        if isinstance(v, str):
            m = re.match(r"(\d+) langues?$", v)
            if m: return int(m.group(1))
    return 0
quest("Prestige", "legend", "Chasseur de Légendaires", "Chasseur de Légendaires", "Les cartes Légendaires.", "tier", "4", ITEMS_BY(lambda it: it["t"] == 4), steps=[10, 50, 100, 500, 1128])
quest("Prestige", "epic", "Chasseur d'Épiques", "Chasseur d'Épiques", "Les cartes Épiques.", "tier", "3", ITEMS_BY(lambda it: it["t"] == 3), steps=[10, 50, 250, 1000, 1598])
quest("Prestige", "icones", "Les icônes de Paris", "Ambassadeur de Paris", "Les lieux connus dans plus de 30 langues.", "tag", "theme:icones", ITEMS_BY(lambda it: langs(it) >= 30))
quest("Prestige", "merveilles", "Les merveilles", "Merveille de Paris", "Les lieux connus dans plus de 60 langues.", "tag", "theme:merveilles", ITEMS_BY(lambda it: langs(it) >= 60))
quest("Prestige", "touche", "Touche-à-tout", "Touche-à-tout", "Une carte de chaque type de lieu.", "kinds", "", total=len(K), steps=[10, 25, len(K)])
quest("Prestige", "collection", "Collectionneur", "Encyclopédie vivante", "Toutes les cartes de Paris.", "all", "", total=len(I), steps=[100, 1000, 5000, len(I)])
quest("Prestige", "series", "Séries complètes", "Maître des séries", "Terminer les séries.", "series", "", total=len(COLS), steps=[5, 15, len(COLS)])

# ---------- Sorties ----------
ids = [q["id"] for q in Q]; assert len(ids) == len(set(ids)), "identifiants en double"
out = {"quests": Q, "tags": TAGS, "left": sorted(LEFT)}
(ROOT / "site" / "data" / "quests.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
lit = lambda s: "'" + str(s).replace("'", "''") + "'"
sql = ["-- Parisquest : définitions des quêtes (généré par pipeline/quests.py). À exécuter après quetes.sql. Peut être relancé.",
       "delete from public.place_tags;"]
for q in Q:
    sql.append(f"insert into public.quests (id, cat, name, title, rule, val, total, steps, rewards) values ({lit(q['id'])}, {lit(q['cat'])}, {lit(q['name'])}, {lit(q['title'])}, {lit(q['rule'])}, {lit(q['val'])}, {q['total']}, '{{{','.join(map(str, q['steps']))}}}', '{{{','.join(map(str, q['rewards']))}}}') on conflict (id) do update set cat = excluded.cat, name = excluded.name, title = excluded.title, rule = excluded.rule, val = excluded.val, total = excluded.total, steps = excluded.steps, rewards = excluded.rewards;")
for tag, mem in TAGS.items():
    arr = ",".join('"' + i + '"' for i in mem)
    sql.append(f"insert into public.place_tags (place_id, tag) select unnest('{{{arr}}}'::text[]), {lit(tag)} on conflict do nothing;")
sql.append("select count(*) as quetes from public.quests; select count(*) as etiquettes from public.place_tags;")
(ROOT / "site" / "supabase" / "quests_data.sql").write_text("\n".join(sql) + "\n")
tot = sum(sum(q["rewards"]) for q in Q)
cats = collections.Counter(q["cat"] for q in Q)
print(len(Q), "quêtes", dict(cats), "| paliers :", sum(len(q["steps"]) for q in Q), "| total des récompenses :", tot, "PQ ≈", round(tot / 500 * 0.99, 1), "€")
print("taille quests_data.sql :", round((ROOT / "site" / "supabase" / "quests_data.sql").stat().st_size / 1e3), "Ko ; quests.json :", round((ROOT / "site" / "data" / "quests.json").stat().st_size / 1e3), "Ko")
