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

Q, TAGS, MEM = [], {}, {}
def quest(cat, qid, name, title, desc, rule, val, members=None, total=None, tiers=None, steps=None):
    if members is not None:
        members = sorted(set(members)); total = len(members); MEM[qid] = members
        if rule == "tag": TAGS[val] = members
    if not total: return
    if steps is None: steps = sorted({max(1, math.ceil(total * p)) for p in (tiers or tiers_for(total))})
    Q.append({"id": qid, "cat": cat, "name": name, "title": title, "desc": desc, "rule": rule, "val": val, "total": total,
              "steps": steps, "rewards": [R(s) for s in steps]})
ITEMS_BY = lambda pred: [it["i"] for it in I if pred(it)]

# ---------- Territoires ----------
ARR_DESC = {
    1: "Le cœur royal de Paris, du Louvre aux Tuileries et aux Halles.",
    2: "Le quartier de la Bourse, des passages couverts et de la rue Montorgueil.",
    3: "Le haut Marais, ses hôtels particuliers et ses ateliers.",
    4: "L'île de la Cité, l'île Saint-Louis, le bas Marais et l'Hôtel de Ville.",
    5: "Le Quartier latin : la Sorbonne, le Panthéon et le Jardin des plantes.",
    6: "Saint-Germain-des-Prés, ses cafés littéraires et le jardin du Luxembourg.",
    7: "La tour Eiffel, les Invalides, le musée d'Orsay et les ministères.",
    8: "Les Champs-Élysées, la Madeleine et la place de la Concorde.",
    9: "Les grands boulevards, l'Opéra Garnier et la Nouvelle Athènes.",
    10: "Les gares du Nord et de l'Est, le canal Saint-Martin et ses écluses.",
    11: "Bastille, Oberkampf et les cours d'artisans du faubourg Saint-Antoine.",
    12: "Bercy, la Coulée verte, la gare de Lyon et le bois de Vincennes.",
    13: "La Butte-aux-Cailles, le quartier asiatique et Paris Rive Gauche.",
    14: "Montparnasse, ses ateliers d'artistes, les catacombes et le parc Montsouris.",
    15: "Le plus peuplé de Paris : Vaugirard, Grenelle et le parc André-Citroën.",
    16: "Passy, Auteuil, le Trocadéro et le bois de Boulogne.",
    17: "Les Batignolles, la plaine Monceau et les Épinettes.",
    18: "Montmartre et ses escaliers, la Goutte-d'Or et La Chapelle.",
    19: "Les Buttes-Chaumont, le bassin et le parc de la Villette.",
    20: "Belleville, Ménilmontant et le Père-Lachaise.",
}
for a in range(1, 21):
    o = "1er" if a == 1 else f"{a}e"
    quest("Territoires", f"arr-{a}", f"Le {o} arrondissement", f"Seigneur du {o}", ARR_DESC[a], "arr", str(a), ITEMS_BY(lambda it, a=a: ar(it) == a))
quest("Territoires", "rive-d", "La rive droite", "Boss de la rive droite", "Tous les lieux au nord de la Seine (1er à 4e, 8e à 12e, 16e à 20e).", "rive", "d", ITEMS_BY(lambda it: ar(it) and ar(it) not in LEFT))
quest("Territoires", "rive-g", "La rive gauche", "Boss de la rive gauche", "Tous les lieux au sud de la Seine (5e, 6e, 7e, 13e, 14e, 15e).", "rive", "g", ITEMS_BY(lambda it: ar(it) in LEFT))
quest("Territoires", "montmartre", "Montmartre", "Gamin de la Butte", "Le sommet de la Butte, de la place du Tertre aux vignes.", "tag", "zone:montmartre",
      ITEMS_BY(lambda it: ar(it) == 18 and 48.8825 < it["a"] < 48.8895 and 2.3345 < it["o"] < 2.3460))
quest("Territoires", "bois", "Les Bois de Paris", "Garde forestier", "Les bois de Boulogne et de Vincennes, les deux poumons de Paris.", "tag", "zone:bois", ITEMS_BY(lambda it: "Bois de" in (it.get("site") or "")))
quest("Territoires", "tour", "Tour de Paris", "Globe-trotteur parisien", "Avoir au moins une carte dans chacun des 20 arrondissements.", "arrs", "", total=20, steps=[5, 10, 20])

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
    far = max(((p, q) for p in L for q in L), key=lambda pq: hav(pq[0]["a"], pq[0]["o"], pq[1]["a"], pq[1]["o"]))
    far = sorted(far, key=lambda it: (it["o"], it["a"]))
    quest("Transports", f"ligne-{c}", lab, title, f"Toutes les stations de la ligne dans Paris, de {far[0]['n']} à {far[1]['n']}.", "tag", f"ligne:{c}", [it["i"] for it in L], tiers=[1.0])
quest("Transports", "funiculaire", "Funiculaire de Montmartre", "Funambule", "La gare basse et la gare haute, au pied et au sommet de la Butte.", "tag", "ligne:FUN", [it["i"] for it in per_line.get("FUN", [])], tiers=[1.0])
quest("Transports", "stations", "Toutes les stations", "Roi du sous-sol", "Toutes les stations de métro, de RER, de tramway et les gares dans Paris.", "kind", "station", [it["i"] for it in st])
nlines = {it["i"]: len([c for c in it.get("ln", []) if LINES[c]["m"] in ("metro", "rer")]) for it in st}
hubs = dedupe([it for it in st if nlines[it["i"]] >= 4])
quest("Transports", "hubs", "Les grandes correspondances", "Maître des correspondances", "Les stations où se croisent au moins 4 lignes de métro ou de RER.", "tag", "theme:hubs", [it["i"] for it in hubs], tiers=[1.0])
busy = sorted(dedupe([it for it in st if (it.get("x") or {}).get("valid")]), key=lambda it: -it["x"]["valid"])[:10]
quest("Transports", "busy", "Les 10 plus fréquentées", "Heure de pointe", "Les 10 stations les plus fréquentées de Paris, selon les validations Navigo.", "tag", "theme:busy", [it["i"] for it in busy], tiers=[1.0])

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
    # Sous vos pieds (vestiges archéologiques, enfouis ou visibles)
    ("Sous vos pieds", "vestiges", "Sous vos pieds", "Archéologue", "Tous les vestiges archéologiques : ce que les fouilles ont trouvé sous les rues de Paris.", by("vestige")),
    ("Sous vos pieds", "visibles", "Encore visibles", "Œil de l'archéologue", "Les vestiges qu'on peut encore voir sur place.", by("vestige", lambda it: (it.get("x") or {}).get("vis"))),
    ("Sous vos pieds", "lutece-monuments", "Les monuments de Lutèce", "Citoyen de Lutèce", "Thermes, forum, arènes, théâtre, temples, aqueduc et voies de la ville romaine.",
     by("vestige", lambda it: it["n"].startswith(("Thermes", "Forum de Lutèce", "Arènes", "Théâtre antique", "Temple antique", "Aqueduc gallo", "Voie romaine")) or it["i"] in ("vestige:Q641548", "vestige:Q2669368"))),
    ("Sous vos pieds", "necropoles", "Nécropoles et sarcophages", "Gardien des tombeaux", "Sarcophages, sépultures et anciens cimetières retrouvés sous la ville.",
     by("vestige", lambda it: (it.get("x") or {}).get("ic") in ("sarcophagus", "stele"))),
    ("Sous vos pieds", "enceintes-enfouies", "Les enceintes enfouies", "Bâtisseur de remparts", "Les tronçons des murailles successives de Paris retrouvés en fouille.",
     by("vestige", lambda it: (it.get("x") or {}).get("ic") == "rampart")),
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


# ---------- Classement, descriptions et contenu (affichage) ----------
CATS = ["Arrondissements et quartiers", "Lignes de métro", "RER, tram et funiculaire", "Stations et gares", "Personnalités",
        "Histoire et mémoire", "Sous vos pieds : vestiges archéologiques", "Patrimoine", "Nature", "Eau et ponts", "Culture", "Vie de quartier", "Rues et voies", "Grands défis"]
SERIE_CAT = {0: "Nature", 1: "Nature", 2: "Nature", 3: "Nature", 4: "Nature", 5: "Eau et ponts", 6: "Eau et ponts", 7: "Eau et ponts",
             8: "Eau et ponts", 9: "Eau et ponts", 10: "Rues et voies", 11: "Rues et voies", 12: "Personnalités", 13: "Personnalités",
             14: "Personnalités", 15: "Personnalités", 16: "Personnalités", 17: "Personnalités", 18: "Histoire et mémoire",
             19: "Patrimoine", 20: "Histoire et mémoire", 21: "Patrimoine", 22: "Patrimoine", 23: "Culture", 24: "Culture",
             25: "Vie de quartier", 26: "Vie de quartier", 27: "Vie de quartier", 28: "Histoire et mémoire", 29: "Histoire et mémoire",
             30: "Patrimoine", 31: "Eau et ponts", 32: "Rues et voies", 33: "Vie de quartier", 34: "Stations et gares",
             35: "Stations et gares", 36: "RER, tram et funiculaire", 37: "Stations et gares"}
PERSO = ["femmes", "serie-12", "serie-13", "serie-14", "serie-15", "plaque-1", "plaque-2", "plaque-3", "plaque-4", "plaque-5",
         "serie-16", "serie-17", "plaque-0", "plaque-6", "plaque-8", "tombes"]
SOUS = ["vestiges", "visibles", "lutece-monuments", "antiquite", "serie-20", "moyenage", "modernes", "necropoles", "enceintes-enfouies"]
HIST = ["serie-18", "serie-29", "serie-28", "plaque-7", "plaque-9", "plaque-10", "plaques"]
DESC = {
    "fontaines-monu": "Les fontaines sculptées des places et des jardins.",
    "piscines": "Les piscines de la Ville, des bassins Art déco aux plus récentes.",
    "fontaines": "Toutes les fontaines : Wallace, à boire, pétillantes et monumentales.",
    "arbres": "Les arbres classés remarquables pour leur âge, leur taille ou leur histoire.",
    "platanes": "Les platanes remarquables, l'arbre des boulevards parisiens.",
    "jpart": "Les jardins cultivés par les habitants, souvent cachés entre deux immeubles.",
    "squares": "Les squares de quartier, ces petits jardins publics à la parisienne.",
    "sursis": "Les arbres malades ou dangereux promis à l'abattage : à voir avant qu'ils ne disparaissent.",
    "parcs": "Tous les parcs, jardins, squares et promenades.",
    "plaque-0": "Les plaques posées là où des résistants ont vécu, combattu ou sont tombés.",
    "plaque-1": "Les maisons où ont vécu ou écrit les écrivains et les penseurs.",
    "plaque-2": "Peintres, sculpteurs et graveurs : les plaques de leurs maisons et ateliers.",
    "plaque-3": "Compositeurs, musiciens, chanteurs et danseurs.",
    "plaque-4": "Acteurs, metteurs en scène et cinéastes.",
    "plaque-5": "Médecins, chimistes, physiciens : là où ils ont vécu ou travaillé.",
    "plaque-6": "Les plaques des femmes et hommes politiques.",
    "plaque-7": "Les plaques qui marquent un événement : révolutions, Libération, premières mondiales.",
    "plaque-8": "Les plaques des officiers et des soldats.",
    "plaque-9": "Les plaques à la mémoire des civils tués pendant les guerres.",
    "plaque-10": "Les plaques à la mémoire des victimes des attentats.",
    "femmes": "Les femmes illustres liées à un lieu de Paris.",
    "tombes": "Les tombes de personnalités dans les cimetières parisiens.",
    "plaques": "Toutes les plaques commémoratives de la Ville.",
    "antiquite": "Tout ce que les fouilles ont retrouvé de la Lutèce gallo-romaine.",
    "moyenage": "Les vestiges du Moyen Âge retrouvés sous la ville : églises, cimetières, enceintes, caves.",
    "modernes": "Les vestiges des XVIᵉ, XVIIᵉ et XVIIIᵉ siècles retrouvés en fouille.",
    "serie-20": "Les traces de la Lutèce d'avant Rome.",
    "hotels": "Les hôtels particuliers, demeures de l'aristocratie et de la grande bourgeoisie.",
    "culte": "Églises, temples, synagogues, mosquées et pagodes.",
    "cathedrales": "Les cathédrales de toutes les confessions.",
    "abbayes": "Abbayes, couvents et prieurés, dont il reste parfois un cloître ou une chapelle.",
    "monuments": "Arcs, colonnes, statues et mémoriaux.",
    "edifices": "Les édifices remarquables : palais, halles, bâtiments publics.",
    "theatres": "Théâtres, cabarets et salles de spectacle.",
    "cinemas": "Les cinémas, des salles d'art et essai aux grands écrans.",
    "biblios": "Les bibliothèques de la Ville et les grandes bibliothèques.",
    "oeuvres": "Statues, sculptures, fresques et street art dans l'espace public.",
    "ateliers": "Les ateliers et cités d'artistes.",
    "lieuxculture": "Centres culturels, tiers-lieux et salles de concert.",
    "kiosques": "Les kiosques à journaux, petites rotondes vertes et dorées.",
    "marches": "Les marchés alimentaires découverts.",
    "commerces": "Vieilles boutiques et enseignes remarquables.",
    "insolite": "Les lieux étonnants et secrets de Paris.",
    "boules": "Les terrains de pétanque.",
    "rue-villa": "Les villas, ruelles verdoyantes souvent privées : elles se capturent depuis leur entrée.",
    "rue-impasse": "Jusqu'au bout de chaque impasse.",
    "rue-cité": "Les cités, groupes de maisons ou d'ateliers autour d'une voie.",
    "rue-passage": "Les passages, couverts ou à ciel ouvert, qui relient deux rues.",
    "rue-quai": "Les quais de la Seine et des canaux.",
    "rue-boulevard": "Des Grands Boulevards aux boulevards des Maréchaux.",
    "rue-avenue": "Les avenues de Paris.",
    "rue-place": "Des grandes places royales aux plus petites placettes.",
    "legend": "Les cartes Légendaires, les plus rares du jeu.",
    "epic": "Les cartes Épiques, juste en dessous des Légendaires.",
    "icones": "Les lieux qui ont un article Wikipédia dans plus de 30 langues.",
    "merveilles": "Les lieux connus dans le monde entier : article Wikipédia dans plus de 60 langues.",
    "touche": "Avoir au moins une carte de chaque type de lieu.",
    "collection": "Toutes les cartes de Paris. Bon courage.",
    "series": "Terminer les séries de la Collection.",
    "serie-12": "Les femmes scientifiques parmi les femmes illustres.", "serie-13": "Les écrivaines parmi les femmes illustres.",
    "serie-14": "Les championnes parmi les femmes illustres.", "serie-15": "Les artistes parmi les femmes illustres.",
    "serie-16": "Les plaques des inventeurs et des ingénieurs.", "serie-17": "Les plaques des aviateurs et des explorateurs.",
    "serie-21": "Les mairies d'arrondissement et l'Hôtel de Ville.", "serie-23": "Les musées de Paris, des plus grands aux musées de quartier.",
    "serie-36": "Toutes les stations de tramway dans Paris.",
    "fam-nature": "Toute la famille Nature.", "fam-eau": "Toute la famille Eau.", "fam-rues": "Toute la famille Rues.",
    "fam-memoire": "Toute la famille Mémoire.", "fam-patrimoine": "Toute la famille Patrimoine.", "fam-culture": "Toute la famille Culture.",
    "fam-quartier": "Toute la famille Quartier.", "fam-transport": "Toute la famille Transports.",
}
PLUR = {"arbre": "arbres remarquables", "parc": "parcs et jardins", "jpart": "jardins partagés", "jrel": "jardins relais", "sursis": "arbres en sursis",
        "fontaine": "fontaines", "piscine": "piscines", "baignade": "baignades", "bains": "bains-douches", "rue": "voies", "plaque": "plaques",
        "femme": "femmes illustres", "vestige": "vestiges", "monde": "sites du patrimoine mondial", "culte": "lieux de culte", "mairie": "mairies",
        "cimetiere": "cimetières", "musee": "musées", "biblio": "bibliothèques", "theatre": "théâtres", "conserv": "conservatoires",
        "atelier": "ateliers", "decouverte": "découvertes", "marche": "marchés", "marchesp": "marchés spécialisés", "kiosque": "kiosques",
        "insolite": "lieux insolites", "sport": "lieux de sport", "station": "stations", "hotelpart": "hôtels particuliers",
        "abbaye": "abbayes et couvents", "monument": "monuments", "enceinte": "vestiges d'enceintes", "edifice": "édifices",
        "disparu": "lieux disparus", "oeuvre": "œuvres d'art", "galerie": "galeries", "lieuculture": "lieux culturels", "cinema": "cinémas",
        "pont": "ponts", "eaulieu": "lieux d'eau", "tombe": "tombes", "cafe": "cafés et restaurants", "magasin": "commerces",
        "loisir": "lieux de loisirs", "fantome": "stations fantômes"}
SING = {"arbre": "arbre remarquable", "parc": "parc", "jpart": "jardin partagé", "jrel": "jardin relais", "sursis": "arbre en sursis",
        "fontaine": "fontaine", "piscine": "piscine", "baignade": "baignade", "bains": "bains-douches", "rue": "voie", "plaque": "plaque",
        "femme": "femme illustre", "vestige": "vestige", "monde": "site du patrimoine mondial", "culte": "lieu de culte", "mairie": "mairie",
        "cimetiere": "cimetière", "musee": "musée", "biblio": "bibliothèque", "theatre": "théâtre", "conserv": "conservatoire",
        "atelier": "atelier", "decouverte": "découverte", "marche": "marché", "marchesp": "marché spécialisé", "kiosque": "kiosque",
        "insolite": "lieu insolite", "sport": "lieu de sport", "station": "station", "hotelpart": "hôtel particulier",
        "abbaye": "abbaye", "monument": "monument", "enceinte": "vestige d'enceinte", "edifice": "édifice",
        "disparu": "lieu disparu", "oeuvre": "œuvre d'art", "galerie": "galerie", "lieuculture": "lieu culturel", "cinema": "cinéma",
        "pont": "pont", "eaulieu": "lieu d'eau", "tombe": "tombe", "cafe": "café", "magasin": "commerce", "loisir": "lieu de loisirs",
        "fantome": "station fantôme"}
nfr = lambda n: f"{n:,}".replace(",", " ")
lab = lambda k, n: f"{nfr(n)} {SING[k] if n == 1 else PLUR[k]}"
BYI = {it["i"]: it for it in I}
def contenu(q):
    m = MEM.get(q["id"])
    if q["rule"] == "arrs": return "20 arrondissements"
    if q["rule"] == "kinds": return f"{len(K)} types de lieux"
    if q["rule"] == "series": return f"{len(COLS)} séries"
    if q["rule"] == "all": return f"{nfr(len(I))} cartes"
    if not m: return ""
    c = collections.Counter(BYI[i]["k"] for i in m).most_common()
    if len(c) == 1: return lab(*c[0])
    top = c[:3]; rest = sum(n for _, n in c[3:])
    parts = [lab(k, n) for k, n in top] + ([f"{nfr(rest)} autre{'s' if rest > 1 else ''}"] if rest else [])
    return f"{nfr(len(m))} lieux : " + ", ".join(parts[:-1]) + " et " + parts[-1]
EX = {"serie-31": ["Pont Neuf", "Pont Alexandre III", "Pont des Arts"]}   # les ponts « rue » n'ont pas de notoriété Wikidata
INSTIT = re.compile(r"^(Université|École|Institut|Académie|Conservatoire|Collège|Lycée|Alliance|Centre national|SUPINFO|ESCP|La Fémis|Le Cordon)", re.I)
def a_voir(q):
    m = MEM.get(q["id"])
    if q["id"] in EX: return EX[q["id"]]
    if not m or len(m) <= 3 or q["rule"] in ("arrs", "kinds", "series", "arr", "rive"): return []
    L = [BYI[i] for i in m]
    kinds = {it["k"] for it in L}
    if kinds <= {"station", "fantome"}:
        L = sorted((it for it in L if (it.get("x") or {}).get("valid")), key=lambda it: -it["x"]["valid"])
    else:
        L = sorted((it for it in L if langs(it) >= 3 and not INSTIT.match(it["n"]) and (it["k"] != "magasin" or kinds == {"magasin"})),
                   key=lambda it: (-langs(it), it["n"]))
    out, pos = [], []
    for it in L:
        n = it["n"][0].upper() + it["n"][1:]
        if n in out or any(hav(it["a"], it["o"], a, o) < 300 for a, o in pos): continue
        out.append(n); pos.append((it["a"], it["o"]))
        if len(out) == 3: break
    return out if len(out) >= 2 else []
for q in Q:
    i = q["id"]
    if q["cat"] == "Territoires": q["cat"] = "Arrondissements et quartiers"
    elif i.startswith("ligne-"): q["cat"] = "Lignes de métro" if LINES[i[6:]]["m"] == "metro" else "RER, tram et funiculaire"
    elif i == "funiculaire": q["cat"] = "RER, tram et funiculaire"
    elif q["cat"] == "Transports": q["cat"] = "Stations et gares"
    elif i in SOUS: q["cat"] = "Sous vos pieds : vestiges archéologiques"
    elif i.startswith("serie-"): q["cat"] = SERIE_CAT[int(i[6:])]
    elif i in SOUS: q["cat"] = "Sous vos pieds : vestiges archéologiques"
    elif i in PERSO: q["cat"] = "Personnalités"
    elif i in HIST: q["cat"] = "Histoire et mémoire"
    elif q["cat"] in ("Familles", "Prestige"): q["cat"] = "Grands défis"
    elif q["cat"] in ("Eau",): q["cat"] = "Eau et ponts"
    elif q["cat"] == "Quartier": q["cat"] = "Vie de quartier"
    elif q["cat"] == "Rues": q["cat"] = "Rues et voies"
    elif q["cat"] == "Mémoire": q["cat"] = "Histoire et mémoire"
    assert q["cat"] in CATS, (i, q["cat"])
    if i in DESC: q["desc"] = DESC[i]
    if q["desc"] and q["desc"][-1] not in ".!?": q["desc"] += "."
    q["what"] = contenu(q); q["ex"] = a_voir(q)
# ordre : par catégorie, puis lignes et arrondissements dans l'ordre croissant, sinon ordre de création
def lnum(c):
    m = re.match(r"([A-Z]+)(\d*)(.*)", c); return (m.group(1), int(m.group(2) or 0), m.group(3))
FIRST = {"Personnalités": PERSO, "Histoire et mémoire": HIST, "Sous vos pieds : vestiges archéologiques": SOUS}
def key(iq):
    k, q = iq; i = q["id"]
    if i.startswith("arr-"): sub = (0, int(i[4:]))
    elif i.startswith("ligne-"): sub = (0, lnum(i[6:]))
    elif q["cat"] in FIRST and i in FIRST[q["cat"]]: sub = (0, FIRST[q["cat"]].index(i))
    else: sub = (1, k)
    return (CATS.index(q["cat"]), sub)
Q = [q for _, q in sorted(enumerate(Q), key=lambda iq: (key(iq)[0], str(key(iq)[1][0]), key(iq)[1][1] if isinstance(key(iq)[1][1], tuple) else (key(iq)[1][1],)))]
for n, q in enumerate(Q): q["ord"] = n

# ---------- Sorties ----------
ids = [q["id"] for q in Q]; assert len(ids) == len(set(ids)), "identifiants en double"
out = {"quests": Q, "cats": CATS, "tags": TAGS, "left": sorted(LEFT)}
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
