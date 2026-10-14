"""Intégration des lieux de Paris présents sur Wikidata (articles Wikipédia en français).

- Les fiches qui correspondent à une carte existante (même type, nom proche, à faible distance)
  enrichissent cette carte : lien Wikipédia, notoriété, description, photo.
- Les autres deviennent de nouvelles cartes, dans des types dédiés (hôtel particulier, pont, café...).
- Les fiches qui ne sont pas des lieux (organisations, événements) ou qui sont sensibles
  (écoles, hôpitaux, prisons, casernes, ambassades) sont écartées.
"""
import collections
import glob
import json
import math
import re
import unicodedata

# ---------- types Wikidata (P31) -> type de carte ----------
T = {
    # voies : servent à enrichir les rues existantes
    "voie": "Q79007 Q174782 Q7543083 Q13634881 Q3558430 Q12731 Q207934 Q54114 Q34442 Q15070223 Q3840711 Q828909 Q325358 "
            "Q17383262 Q16544740 Q285783 Q1529 Q283977 Q1251403 Q5004679 Q628179 Q62685721 Q21000333 Q1304276 Q83620 Q445741 Q3950",
    "voieprivee": "Q703941",
    "passage": "Q2900244 Q97495053",
    "escalier": "Q12511 Q16634966",
    "station": "Q928830 Q22808403 Q22808404 Q1793804 Q2175765 Q55488 Q55485 Q11606300 Q20202072 Q108667555 Q55491 Q11670533 Q13433889",
    "fantome": "Q168565",
    "funiculaire": "Q142031",
    "parc": "Q22746 Q55177716 Q2026833 Q22698 Q1107656 Q16645058 Q22652 Q167346 Q6553474 Q12783 Q291177 Q1470855 Q56478984 Q1759852 Q3108101 Q1429180 Q787113 Q88372",
    "jpart": "Q251958",
    "culte": "Q16970 Q2977 Q56242215 Q56242225 Q56242250 Q108325 Q120560 Q34627 Q32815 Q56242063 Q2031836 Q44539 Q5393308 Q317557 Q1088552 Q334383 Q199451 Q446828 Q693842 Q192619 Q96371632 Q133747929",
    "abbaye": "Q44613 Q1128397 Q160742 Q138313683 Q817056 Q2750108 Q15823129 Q76529788 Q18648725 Q97824060 Q15823107 Q56315868 Q3024331 Q174981 Q1701174",
    "musee": "Q33506 Q207694 Q17431399 Q3196771 Q16735822 Q2772772 Q866133 Q588140 Q614316 Q108860927 Q2087181 Q10624527 Q1865249 Q26945165 "
             "Q3329412 Q3330843 Q2516357 Q2398990 Q1970365 Q17438516 Q14928320 Q787934 Q1415133 Q2106220 Q3330083 Q12104174 Q962734 Q4306024 "
             "Q7209480 Q122973294 Q135641693 Q26958661 Q26958726 Q10333872 Q62098611 Q5436782 Q1191610 Q667018 Q110498831 Q17000324 Q24699794 "
             "Q740437 Q957433 Q3329663 Q24906026 Q19979289",
    "galerie": "Q1007870 Q56856618 Q2945053 Q18123390 Q15206795 Q2094773",
    "lieuculture": "Q1329623 Q98792435 Q2190251 Q5061188 Q3152824 Q18674739 Q3540209 Q117531692 Q2945285 Q1352795",
    "theatre": "Q24354 Q153562 Q1060829 Q8719053 Q112688641 Q1763828 Q57660343 Q3469910 Q3476585 Q478679 Q769713 Q131183 Q16889960 Q61525088 "
               "Q17149955 Q1684522 Q622425 Q1228895 Q1188223 Q805353 Q114727401 Q51167626",
    "cinema": "Q41253 Q1153108 Q2990473",
    "biblio": "Q7075 Q2326815 Q2901570 Q671735 Q28564 Q385994 Q856234 Q1622062 Q22806 Q2208411 Q1769139 Q18628369 Q2061246 Q6150991 Q21716051 Q1438040",
    "conserv": "Q17487523 Q66742023",
    "hotelpart": "Q1365179 Q15848826 Q16560 Q53536964 Q751876 Q23413 Q1436181 Q1802963 Q5383482 Q481289",
    "monument": "Q4989906 Q575759 Q5003624 Q143912 Q170980 Q4817 Q1930585 Q12277 Q321053 Q162875 Q23929227 Q135645306 Q1541043 Q12516 Q18351990 "
                "Q492255 Q2984296 Q329477 Q19826646 Q3401774 Q80793 Q236279 Q376 Q853854 Q3003415 Q2309609 Q17172602 Q371752 Q3643463 Q12518 "
                "Q11166728 Q1440300 Q1440476 Q202570 Q1256453 Q2921357 Q172896 Q156849 Q12146012 Q503958 Q151511",
    "enceinte": "Q82117 Q16748868 Q57346 Q81851 Q90754 Q23418 Q81917 Q91165 Q1785071",
    "oeuvre": "Q860861 Q179700 Q3476533 Q659396 Q838948 Q241045 Q2293362 Q2520013 Q29857932 Q245117 Q5784272 Q219423 Q22669139 Q133067 Q19479037 Q787116 Q4390114 Q6642845",
    "fontaine": "Q483453 Q829304 Q1630622",
    "pont": "Q12280 Q158438 Q537127 Q1068842 Q3771516 Q1210334 Q3397526 Q12042110 Q4291972 Q18615527 Q3397516 Q14276458 Q5592057 Q6636777 "
            "Q428759 Q950431 Q1898246 Q158218 Q158555 Q1055465 Q3397551 Q2502622 Q181348 Q39486269 Q7197275 Q863454",
    "eaulieu": "Q105731 Q44782 Q25516778 Q124282 Q12284 Q23442 Q162602 Q13691 Q863974 Q131681 Q3215290 Q1047832 Q2551525 Q6501028 Q474 Q1328914 Q1690211",
    "piscine": "Q1501 Q357380 Q200023",
    "bains": "Q785952",
    "cimetiere": "Q39614 Q2972684 Q846659 Q2404995 Q107684101 Q109239160 Q675824",
    "tombe": "Q173387 Q381885 Q56055312 Q1424583",
    "mairie": "Q25550691 Q543654",
    "cafe": "Q30022 Q11707 Q1581509 Q187456 Q866742 Q3427914 Q154250 Q256020 Q654772 Q801712 Q274393 Q861651 Q5307737 Q1043639 Q30324198 Q6433096",
    "magasin": "Q216107 Q213441 Q11315 Q31374404 Q39658032 Q2922223 Q200764 Q46843593 Q61696039 Q30315715 Q1123813 Q1426795 Q1941779 Q2090555 "
               "Q3267025 Q9209474 Q124535592 Q1341287 Q11691 Q2080521",
    "marchesp": "Q132510 Q37654 Q28142754 Q385870 Q18658261 Q130702973",
    "sport": "Q483110 Q1076486 Q641226 Q27951514 Q1049757 Q1154710 Q830528 Q11822917 Q1282870 Q14092 Q741118 Q13380226 Q7579839 Q909906 Q1867518",
    "loisir": "Q194195 Q2416723 Q15982170 Q43501 Q1401536 Q2281788",
    "vestige": "Q839954 Q21752084 Q14752696 Q6581615 Q24933318 Q7362268 Q2202509 Q220659",
    "plaque": "Q721747",
    "arbre": "Q811534",
    "edifice": "Q41176 Q11755959 Q13402009 Q1577547 Q1202402 Q3947 Q1307276 Q18142 Q11303 Q2304397 Q118896406 Q1021645 Q2519340 Q1220959 Q294422 "
               "Q35112127 Q811979 Q1497375 Q18247357 Q276173 Q102421356 Q1797122 Q746628 Q2072285 Q1378975 Q3364296 Q1137809 Q7138926 Q109568071 "
               "Q1662011 Q83405 Q380342 Q63969188 Q97669839 Q3067776 Q1495738 Q385557 Q181623 Q896586 Q38720 Q44494 Q185187 Q131596 Q489357 "
               "Q3068953 Q165044 Q1135180 Q62832 Q1254933 Q148319 Q623525 Q185600 Q657100 Q180174 Q1011110 Q130485312 Q2064236 Q797108 Q805248 "
               "Q11142797 Q488444 Q35054 Q1139917 Q277760 Q607241 Q455403 Q27686 Q259618 Q3918 Q875538 Q902104 Q3551775 Q847027 Q38723 "
               "Q1542938 Q3578166 Q135436 Q414147 Q2822246 Q162633 Q1966910 Q120116792 Q209465 Q16889960 Q1570262",
}
DISPARU = set("Q19860854 Q56556915 Q15893266 Q55097207 Q107311481 Q96354572 Q123124127 Q64578911 Q4663385 Q11486300 Q64654999 "
              "Q21751045 Q19899465 Q125547334 Q52103661 Q27067659".split())
EXCLUDE = set((
    # enseignement primaire et secondaire, petite enfance
    "Q3914 Q9842 Q2511322 Q16463 Q1459186 Q189004 Q126807 Q20860083 Q1244442 Q423208 Q1080794 Q1138671 Q48747650 Q108037689 "
    "Q3591580 Q2983855 Q107286953 Q30313902 Q48409379 Q3807410 Q269770 Q2307291 Q28936014 "
    # santé
    "Q16917 Q180370 Q1774898 Q30103124 Q39364723 Q2945729 Q1059324 Q4284971 Q210999 Q958822 Q569500 Q22908 Q16685822 Q1774587 Q111082601 "
    # prisons, police, armée, sécurité
    "Q40357 Q56670380 Q683992 Q18331255 Q97366313 Q124936806 Q131263 Q917182 Q1935049 Q21028475 Q2387974 Q861951 Q28648855 Q47913 "
    "Q125577386 Q214183 Q2101516 Q1825410 Q1195942 "
    # représentations diplomatiques
    "Q3917681 Q5244910 Q372690 Q2737008 Q213283 Q579581 Q431071 Q114104178"
).split())
KIND_OF = {}
PRIORITY = ["fantome", "funiculaire", "passage", "station", "musee", "culte", "abbaye", "cimetiere", "tombe", "mairie", "biblio", "conserv",
            "theatre", "cinema", "galerie", "lieuculture", "piscine", "bains", "fontaine", "pont", "eaulieu", "enceinte", "monument", "oeuvre",
            "vestige", "plaque", "arbre", "hotelpart", "cafe", "magasin", "marchesp", "sport", "loisir", "parc", "jpart", "escalier",
            "voieprivee", "edifice", "voie"]
for kind, qs in T.items():
    for q in qs.split():
        KIND_OF.setdefault(q, kind)

# types de carte existants auxquels une fiche peut être rattachée
MATCH = {
    "voie": ["rue"], "voieprivee": ["rue"], "passage": ["rue"], "escalier": ["escalier", "rue"], "station": ["station"],
    "parc": ["parc", "jpart"], "jpart": ["jpart"], "culte": ["culte"], "musee": ["musee"], "biblio": ["biblio"], "conserv": ["conserv"],
    "theatre": ["theatre"], "cimetiere": ["cimetiere"], "mairie": ["mairie"], "fontaine": ["fontaine"], "piscine": ["piscine", "baignade"],
    "bains": ["bains"], "sport": ["sport"], "marchesp": ["marche", "marchesp"], "plaque": ["plaque"], "arbre": ["arbre"],
    "lieuculture": ["decouverte", "theatre"], "monument": ["monde"], "edifice": ["monde"],
}
# types qui ne créent pas de carte s'ils ne trouvent pas de correspondance
ENRICH_ONLY = {"voie", "station", "escalier", "plaque", "arbre", "voieprivee", "passage"}  # voies privées et passages : jamais de nouvelle carte

NEW_KINDS = {
    # code : (famille, libellé, illustration, rayon de capture)
    "hotelpart": ("patrimoine", "Hôtel particulier", "mansion", 40),
    "abbaye": ("patrimoine", "Abbaye et couvent", "church", 50),
    "monument": ("patrimoine", "Monument", "obelisk", 40),
    "enceinte": ("patrimoine", "Enceinte de Paris", "rampart", 50),
    "edifice": ("patrimoine", "Édifice", "facade", 40),
    "disparu": ("patrimoine", "Paris disparu", "ghost", 50),
    "oeuvre": ("culture", "Œuvre d'art", "statue", 25),
    "galerie": ("culture", "Galerie", "palette", 40),
    "lieuculture": ("culture", "Lieu culturel", "compass", 50),
    "cinema": ("culture", "Cinéma", "cinema", 40),
    "pont": ("eau", "Pont", "bridge", 40),
    "eaulieu": ("eau", "Lieu d'eau", "pool", 80),
    "tombe": ("memoire", "Tombe", "stele", 15),
    "cafe": ("quartier", "Café et restaurant", "cafe", 25),
    "magasin": ("quartier", "Commerce", "awning", 40),
    "loisir": ("quartier", "Loisirs", "ball", 80),
    "fantome": ("transport", "Station fantôme", "station", 60),
}
# type Wikidata -> type de carte existant quand aucune correspondance n'est trouvée
CREATE_AS = {"parc": "parc", "jpart": "jpart", "culte": "culte", "musee": "musee", "biblio": "biblio", "conserv": "conserv",
             "theatre": "theatre", "cimetiere": "cimetiere", "mairie": "mairie", "fontaine": "fontaine", "piscine": "piscine",
             "bains": "bains", "sport": "sport", "marchesp": "marchesp", "vestige": "vestige",
             "funiculaire": "station"}

STOP = set("le la les l de du des d et a au aux en sur sous saint sainte st ste paris parisien parisienne".split())
GENERIC = set(("rue avenue boulevard place passage villa impasse allee square jardin parc eglise chapelle musee station gare metro "
               "theatre cinema fontaine pont cimetiere mairie bibliotheque mediatheque salle cite quai cour route voie hotel maison "
               "immeuble temple synagogue mosquee basilique cathedrale de cafe restaurant marche porte").split())


def norm(s, drop_generic=True):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\([^)]*\)", " ", s)
    toks = [t for t in re.split(r"[^a-z0-9]+", s) if t and t not in STOP]
    if drop_generic:
        toks = [t for t in toks if t not in GENERIC]
    return toks


def similar(a, b):
    ta, tb = set(norm(a)), set(norm(b))
    if not ta or not tb:
        return norm(a, False) == norm(b, False)
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return small <= big or len(ta & tb) / len(ta | tb) >= 0.5


def point_in_rings(rings, lon, lat):
    inside = False
    for r in rings:
        for i in range(len(r)):
            x1, y1 = r[i - 1]
            x2, y2 = r[i]
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                inside = not inside
    return inside


def load_items(src_dir):
    items = {}
    for f in sorted(glob.glob(f"{src_dir}/wikidata/*.json")):
        for b in json.load(open(f, encoding="utf-8"))["results"]["bindings"]:
            q = b["item"]["value"].rsplit("/", 1)[1]
            it = items.setdefault(q, {"q": q, "types": set()})
            for k in ("nom", "description", "coord", "article", "liens", "image", "creation"):
                if k in b and k not in it:
                    it[k] = b[k]["value"]
            if "type" in b:
                it["types"].add(b["type"]["value"].rsplit("/", 1)[1])
    return list(items.values())


def classify(types):
    if types & EXCLUDE:
        return None
    if types & DISPARU:
        return "disparu"
    kinds = {KIND_OF[t] for t in types if t in KIND_OF}
    for k in PRIORITY:
        if k in kinds:
            return k
    return None


def integrate(src_dir, items, add, KINDS, percentile_tiers, clip, cap1):
    """Ajoute ou rattache les lieux Wikidata. Renvoie des statistiques."""
    for k, v in NEW_KINDS.items():
        KINDS.setdefault(k, v)
    arr_rings = []
    for f in json.load(open(f"{src_dir}/arrondissements.geojson", encoding="utf-8"))["features"]:
        arr_rings.append([[(p[0], p[1]) for p in ring] for ring in f["geometry"]["coordinates"]])

    # grille des cartes existantes
    grid = collections.defaultdict(list)
    for it in items:
        grid[(int(it["a"] / 0.002), int(it["o"] / 0.003))].append(it)

    def near(lat, lon, kinds, radius_m):
        out = []
        cx, cy = int(lat / 0.002), int(lon / 0.003)
        span = max(1, math.ceil(radius_m / 220))
        for dx in range(-span, span + 1):
            for dy in range(-span, span + 1):
                for it in grid.get((cx + dx, cy + dy), []):
                    if it["k"] not in kinds:
                        continue
                    d = math.hypot((it["a"] - lat) * 111195, (it["o"] - lon) * 111195 * 0.6577)
                    if d <= radius_m:
                        out.append((d, it))
        return sorted(out, key=lambda x: x[0])

    stats = collections.Counter()
    created = collections.defaultdict(list)
    THIS_YEAR = 2026
    for w in load_items(src_dir):
        m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", w.get("coord", ""))
        if not m:
            continue
        lon, lat = float(m.group(1)), float(m.group(2))
        if not any(point_in_rings(r, lon, lat) for r in arr_rings):
            stats["hors Paris"] += 1
            continue
        kind = classify(w["types"])
        if not kind:
            stats["écartés (non-lieux ou sensibles)"] += 1
            continue
        name = w.get("nom") or ""
        langs = int(w.get("liens") or 0)
        wp = w.get("article")
        img = (w.get("image") or "").replace("http://", "https://")
        desc = cap1(w.get("description") or "")
        year = None
        if w.get("creation"):
            m2 = re.match(r"^-?(\d{1,4})", w["creation"])
            year = int(m2.group(1)) if m2 else None

        # 1. rattachement à une carte existante
        match = None
        if kind in MATCH:
            radius = 450 if kind in ("voie", "voieprivee", "passage") else 300 if kind in ("station", "parc", "cimetiere") else 150
            for d, it in near(lat, lon, MATCH[kind], radius):
                if kind == "voie" and norm(it["n"], False) == norm(name, False):
                    match = it
                    break
                if kind != "voie" and similar(it["n"], name):
                    match = it
                    break
        if match:
            match.setdefault("wd", w["q"])
            match.setdefault("wp", wp)
            match["nt"] = max(match.get("nt", 0), langs)
            if desc and not match.get("w"):
                match["w"] = desc
            if img and not match.get("p"):
                match["p"] = img
                match.setdefault("c", "Wikimedia Commons")
            if kind == "passage":
                match.setdefault("x", {})["couvert"] = 1
            stats["rattachés à une carte existante"] += 1
            continue
        if kind in ENRICH_ONLY:
            stats["sans correspondance (ignorés)"] += 1
            continue

        # 2. nouvelle carte
        ck = CREATE_AS.get(kind, kind)
        if ck not in KINDS:
            stats["type non géré"] += 1
            continue
        facts = [["Notoriété", f"{langs} langue{'s' if langs > 1 else ''}"], ["Création", str(year) if year else "?"]]
        x = {"wdt": sorted(w["types"])[:6]}
        if kind == "passage":
            x["couvert"] = 1
        if ck == "fontaine":
            x["ft"] = "MONUMENTALE"
        if ck == "station":
            x["mode"] = "funiculaire"
        it = add(ck, w["q"], name, lat, lon, s=clip(desc, 70), w=desc, p=img, c="Wikimedia Commons" if img else "",
                 f=facts, x=x)
        if it:
            it["wd"], it["wp"], it["nt"] = w["q"], wp, langs
            age = (THIS_YEAR - year) if year else None
            # un lieu célèbre est une carte prestigieuse ; l'ancienneté ajoute un peu de prestige
            it["_s"] = math.log2(1 + langs) + (1 if age and age > 300 else 0.5 if age and age > 120 else 0)
            created[ck].append(it)
            stats["nouvelles cartes"] += 1
    for ck, group in created.items():
        percentile_tiers(group, lambda it: it["_s"])
    # plancher de prestige pour toute carte connue sur Wikipédia (nouvelle ou enrichie)
    for it in items:
        if it["k"] == "station":  # presque toutes les stations ont un article traduit : critère non discriminant
            continue
        nt = it.get("nt") or 0
        floor = 4 if nt >= 60 else 3 if nt >= 30 else 2 if nt >= 15 else 1 if nt >= 8 else 0
        if floor > it.get("t", 0):
            it["t"] = floor
            stats["cartes rehaussées par leur notoriété"] += 1
    return stats, created
