"""Vestiges archéologiques : un titre précis et une illustration pour chaque carte (décision de Timothée, 18/10/2026).

Les 1 811 fiches du référentiel archéologique de la Ville n'ont pas de nom, seulement une époque (« Vestiges antiques »)
et une synthèse de la découverte. On lit la synthèse pour en tirer ce qui a été trouvé (sarcophages, puits, voie romaine,
enceinte de Philippe Auguste, église Saint-Benoît…), on l'accorde avec l'époque (« Sépultures mérovingiennes »,
« Puits médiéval ») et on choisit une illustration (x.ic). Le sous-titre reste l'adresse.
À lancer après build2.py (avant ou après ponts.py). Peut être relancé : on repart toujours de la fiche source."""
import json, re, pathlib, collections, unicodedata
ROOT = pathlib.Path(__file__).parent
PL = ROOT / "site" / "data" / "places.json"
pl = json.load(open(PL))
SRC = {r["id"]: r for r in json.load(open(ROOT / "data" / "src" / "referentiel-archeologique-de-paris.json"))}

# époque → adjectif accordé (masc. sing., fém. sing., masc. plur., fém. plur.)
ADJ = {
    "prehistoire": ("préhistorique", "préhistorique", "préhistoriques", "préhistoriques"),
    "protohistoire": ("gaulois", "gauloise", "gaulois", "gauloises"),
    "antiquite": ("gallo-romain", "gallo-romaine", "gallo-romains", "gallo-romaines"),
    "merovingien": ("mérovingien", "mérovingienne", "mérovingiens", "mérovingiennes"),
    "moyen_age": ("médiéval", "médiévale", "médiévaux", "médiévales"),
    "temps_modernes": ("moderne", "moderne", "modernes", "modernes"),
    "epoque_contemporaine": ("du XIXᵉ siècle", "du XIXᵉ siècle", "du XIXᵉ siècle", "du XIXᵉ siècle"),
}
G = {"ms": 0, "fs": 1, "mp": 2, "fp": 3}
SAINT = r"((?:Saint|Sainte|Saints)[-\s][A-ZÉÈ][\w'\-]+(?:[-\s](?:des?|du|de la|l')?\s?[A-ZÉÈ][\w'\-]+)*|Notre-Dame(?:[-\s](?:des?|du|de la)[-\s][A-ZÉÈ][\w'\-]+(?:[-\s][A-ZÉÈ][\w'\-]+)*)?)"

# (motif, titre, genre, illustration, accorder l'époque)
RULES = [
    (r"arènes", "Arènes de Lutèce", "fp", "arena", False),
    (r"thermes", "Thermes", "mp", "column", True),
    (r"\bforum\b", "Forum de Lutèce", "ms", "column", False),
    (r"\b(?:un|le) temple\b(?! protestant)|temple (?:gallo|antique|romain|de mercure|dédié)", "Temple antique", "ms", "column", False),
    (r"théâtre antique|théâtre gallo", "Théâtre antique", "ms", "arena", False),
    (r"aqueduc", "Aqueduc", "ms", "aqueduct", True),
    (r"pirogue|embarcation|barque", "Pirogues", "fp", "boat", True),
    (r"néolithique|mésolithique|paléolithique|préhistori|silex|hache polie", "Outils préhistoriques", "mp", "flint", False),
    (r"trésor", "Trésor", "ms", "coin", True),
    (r"philippe[\s-]auguste", "Enceinte de Philippe Auguste", "fs", "rampart", False),
    (r"charles v\b|enceinte de charles", "Enceinte de Charles V", "fs", "rampart", False),
    (r"fossés? jaunes|enceinte de louis xiii", "Enceinte de Louis XIII", "fs", "rampart", False),
    (r"enceinte de thiers|fortifications de thiers|\bthiers\b", "Enceinte de Thiers", "fs", "rampart", False),
    (r"bastide", "Enceinte de Charles V", "fs", "rampart", False),
    (r"fermiers[\s-]généraux", "Mur des Fermiers généraux", "ms", "rampart", False),
    (r"enceinte|rempart|courtine|bastion", "Enceinte", "fs", "rampart", True),
    (r"cardo|decuman|voie romaine|voie antique|chaussées? antiques?|chaussées? (?:d'époque )?romaines?", "Voie romaine", "fs", "road", False),
    (r"nécropole", "Nécropole", "fs", "sarcophagus", True),
    (r"sarcophage", "Sarcophages", "mp", "sarcophagus", True),
    (r"cimetière", "Ancien cimetière", "ms", "stele", False),
    (r"stèle|épitaphe|inscription funéraire", "Stèle funéraire", "fs", "stele", True),
    (r"sépulture|inhum|ossements|squelette|pierres? tombale|\btombes?\b", "Sépultures", "fp", "stele", True),
    (r"(?:église|chapelle|abbaye|prieuré|couvent|cloître|crypte)", "Édifice religieux", "ms", "church", True),
    (r"vestiges? du palais|fondations du palais|ancien palais", "Palais disparu", "ms", "mansion", False),
    (r"four à chaux", "Four à chaux", "ms", "kiln", False),
    (r"\bfours?\b|atelier de potier", "Four", "ms", "kiln", True),
    (r"\bpuits\b", "Puits", "ms", "well", True),
    (r"\bcaves?\b|cellier|souterrain|galerie", "Caves", "fp", "vault", True),
    (r"carrière", "Ancienne carrière", "fs", "vault", False),
    (r"égout|canalisation|conduit", "Ancienne canalisation", "fs", "vault", True),
    (r"\bquai\b|\bberges?\b|\bport\b", "Ancienne berge", "fs", "boat", True),
    (r"\bfossé", "Fossé", "ms", "road", True),
    (r"statue|statuette|sculpt|chapiteau|relief|colonne|pilier", "Sculpture", "fs", "column", True),
    (r"fibule|bague|bijou|perle|épingle", "Bijoux", "mp", "coin", True),
    (r"monnaie|monnayage|deniers?\b", "Monnaies", "fp", "coin", True),
    (r"habitat|maison|bâtiment|construction|trou de poteau|foyer", "Habitat", "ms", "facade", True),
    (r"\bmur\b|\bmurs\b|maçonnerie|fondation", "Fondations", "fp", "facade", True),
    (r"céramique|poterie|tesson|amphore|vaisselle|tasse|verrerie", "Céramiques", "fp", "amphora", True),
    (r"fosse|dépotoir", "Fosses", "fp", "amphora", True),
    (r"mobilier|objets", "Objets anciens", "mp", "amphora", True),
]
# lieu nommé dans la synthèse, pour préciser le titre : « Sarcophages de Saint-Marcel », « Hôtel Lambert »
NAMED = re.compile(r"(?:[ée]glise|[ÉE]glise|chapelle|abbaye|prieuré|couvent|cloître|paroisse|bourg)\s+(?:de\s+|du\s+)?" + SAINT)
HOTEL = re.compile(r"(?:[hH]ôtel)\s+((?:de\s+(?:la\s+)?|du\s+|des\s+|d')?(?:[A-ZÉ][a-zéèêëàâîïôûç'\-]+)(?:[\s-](?:de\s+|du\s+)?[A-ZÉ][a-zéèêëàâîïôûç'\-]+)?)")
# mots qui décrivent les travaux plutôt que la découverte (« lors de la construction de l'égout »)
CONTEXTE = re.compile(r"lors d|occasion d|en creusant|pour réparer|raccordement|percement|établissement d|travaux|construction d|projet d|dans le cadre|emprise d|creusement d|aménagement d|agrandissement d|réseau d")
MAJEUR = {"Arènes de Lutèce", "Thermes", "Forum de Lutèce", "Temple antique", "Théâtre antique", "Pirogues", "Trésor", "Aqueduc"}
NEG = re.compile(r"aucune? [\w\s'-]{0,40}n'(?:a|ont) été (?:découvert|observ|mis|retrouv|identifi|repéré)|n'a (?:révélé|livré|permis de découvrir) aucun|n'a pas (?:permis|mis en évidence|livré|révélé)|pas mis en évidence de niveau|négati|aucun vestige|aucune trace|aucun niveau|aucune structure|stérile|n'a (?:livré|révélé) aucun", re.I)

def periods(r):
    p = [k for k in ("prehistoire", "protohistoire", "antiquite", "moyen_age", "temps_modernes", "epoque_contemporaine") if r.get(k) == "Oui"]
    t = (r.get("synthese") or "").lower()
    if "moyen_age" in p and re.search(r"mérovingien|carolingien|haut moyen", t): p = ["merovingien" if x == "moyen_age" else x for x in p]
    return p

# plusieurs époques sur un même site : on prend celle qui est citée près de la découverte, sinon aucune
MOTS = {"prehistoire": r"préhist|néolith|silex", "protohistoire": r"gaulois|la tène|protohist", "antiquite": r"antique|romain|gallo|ier siècle|iie siècle|iiie siècle|ive siècle|haut-empire|bas-empire",
        "merovingien": r"mérovingien|carolingien|haut moyen", "moyen_age": r"médiév|moyen âge|gothique|xiie|xiiie|xive|xve",
        "temps_modernes": r"moderne|xvie|xviie|xviiie", "epoque_contemporaine": r"xixe|contemporain"}
def proche(tl, pat, p):
    for m in re.finditer(pat, tl):
        zone = tl[max(0, m.start() - 90):m.end() + 90]
        hits = [k for k in p if re.search(MOTS[k], zone)]
        if len(hits) == 1: return hits[0]
    return None

def titre(r):
    t = r.get("synthese") or ""; tl = t.lower(); p = periods(r)
    if not t or t == "None" or NEG.search(t[:180]) or re.search(r"provenance (?:est |fut |reste )?(?:contestée|incertaine)", tl) or len(t) < 25: return None, "trowel"
    named = NAMED.search(t); hotel = HOTEL.search(t)
    # on retient ce qui est cité en premier dans la synthèse (le sujet de la découverte), hors description des travaux ;
    # les découvertes majeures (arènes, thermes, forum…) l'emportent où qu'elles soient citées
    cands = []
    for k, (pat, title, g, ic, accord) in enumerate(RULES):
        pos = [m.start() for m in re.finditer(pat, tl) if not CONTEXTE.search(tl[max(0, m.start() - 50):m.start()])]
        if pos: cands.append((0 if title in MAJEUR else min(pos), k))
    for _, k in sorted(cands):
        pat, title, g, ic, accord = RULES[k]
        if title == "Édifice religieux" and named:
            mot = re.match(r"\w+", named.group(0)).group(0).lower()
            return f"{'Église' if mot in ('église', 'paroisse', 'bourg') else mot.capitalize()} {named.group(1)}"[:40], ic
        if ic in ("stele", "sarcophagus", "vault", "well", "facade", "column") and named and len(title) + len(named.group(1)) < 34:
            return f"{title} de {named.group(1)}", ic
        if ic == "facade" and named and named.group(0)[:1].lower() in "ée":
            return f"Église {named.group(1)}"[:40], "church"
        if ic in ("facade",) and hotel and re.sub(r"^(de |du |des |d')", "", hotel.group(1)) not in ("Ville", "Dieu"):
            return f"Hôtel {hotel.group(1)}"[:40], "mansion"
        if title == "Enceinte":
            for pat2, title2, _, _, _ in RULES:
                if title2 and title2.startswith(("Enceinte de", "Mur des")) and re.search(pat2, tl): return title2, ic
        if accord and p:
            per = p[0] if len(p) == 1 else proche(tl, pat, p)
            if per: title += " " + ADJ[per][G[g]]
        return title, ic
    if hotel and re.sub(r"^(de |du |des |d')", "", hotel.group(1)) not in ("Ville", "Dieu"): return f"Hôtel {hotel.group(1)}"[:40], "mansion"
    return None, "trowel"

def norm(s):
    s = unicodedata.normalize("NFD", s); return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()

stats = collections.Counter(); ex = collections.defaultdict(list); n = 0
for it in pl["items"]:
    if it["k"] != "vestige" or not it["i"].startswith("vestige:"): continue
    r = SRC.get(it["i"].split(":", 1)[1])
    if not r: continue
    x = it.setdefault("x", {}) if isinstance(it.get("x"), dict) else it.setdefault("x", {})
    x.setdefault("n0", it["n"])                          # titre d'origine (« Vestiges antiques »)
    t, ic = titre(r)
    if t is None:                                       # rien d'identifiable : on garde l'époque, plus le type d'opération
        t = x["n0"] if x["n0"] != "Site archéologique" else ("Fouille archéologique" if (r.get("nature_operation") or "") in ("Fouille", "Sauvetage urgent") else "Site archéologique")
    it["n"] = t[0].upper() + t[1:]; x["ic"] = ic; n += 1
    stats[re.sub(r" (gallo-romaine?s?|médiéva\w+|modernes?|gauloise?s?|préhistoriques?|mérovingien\w*|du XIXᵉ siècle)$", "", it["n"])] += 1
    if len(ex[ic]) < 3: ex[ic].append(it["n"])
# ---------- « Sous vos pieds » : on ne garde que le visible ou le clairement décrit ----------
# Vestiges encore visibles depuis l'espace public (relu à la main dans les synthèses)
VISIBLES = {"24", "1971", "524", "576", "1796"}
# titre, illustration et, si les vestiges ont été déplacés, l'endroit où on les voit aujourd'hui
MANUEL = {
    "24": ("Tour de la Liberté de la Bastille", "rampart", (48.85132, 2.36178)),     # remontée au square Henri-Galli
    "1971": ("Chapelle de la Vierge de Saint-Germain-des-Prés", "church", (48.85426, 2.33394)),   # square Laurent-Prache
    "524": ("Crypte archéologique du parvis Notre-Dame", "vault", None),
    "576": ("Rempart du Bas-Empire", "rampart", None),
    "1796": ("Enceinte gallo-romaine de la Cité", "rampart", None),
}
EXCLU = {"2216"}     # synthèse trompeuse (parcelle hors de l'enceinte, rien de notable)
VIS_WD = {"vestige:Q641548", "vestige:Q2669368"}          # arènes de Lutèce, thermes de Cluny
VAGUE = ("Fondations", "Habitat", "Fosses", "Objets anciens", "Céramiques", "Fossé", "Ancienne canalisation",
         "Vestiges", "Site archéologique", "Fouille archéologique")
def garder(it):
    if it["k"] != "vestige": return True
    if not it["i"].startswith("vestige:") or not it["i"][8:].isdigit(): return True
    sid = it["i"][8:]; r = SRC.get(sid) or {}
    if sid in EXCLU: return False
    if sid in VISIBLES: return True
    syn = r.get("synthese") or ""
    flou = re.search(r"indéterminée?s?|incertaine?s?|n'est pas précisé|non précisé|aucun contexte|difficile de se prononcer|aurait", syn) and len(syn) < 220
    return (it.get("x") or {}).get("ic", "trowel") != "trowel" and len(syn) >= 70 and not flou and \
        not any(it["n"] == v or it["n"].startswith(v + " ") for v in VAGUE)
for it in pl["items"]:
    if it["k"] == "vestige" and it["i"][8:] in MANUEL:
        t, ic, pos = MANUEL[it["i"][8:]]
        it["n"] = t; it["x"]["ic"] = ic
        if pos: it["a"], it["o"] = pos; it["site"] = {"24": "Square Henri-Galli", "1971": "Square Laurent-Prache"}[it["i"][8:]]
retires = [it["i"] for it in pl["items"] if not garder(it)]
for it in pl["items"]:
    if it["k"] == "vestige":
        vis = it["i"] in VIS_WD or it["i"][8:] in VISIBLES
        it.setdefault("x", {})["vis"] = 1 if vis else 0
        it["s"] = "Visible sur place" if vis else "Enfoui ou disparu"
pl["kinds"]["vestige"]["l"] = "Sous vos pieds"
old_ids = [it["i"] for it in pl["items"]]
gone = set(retires)
keep = [it for it in pl["items"] if it["i"] not in gone]
new_index = {it["i"]: k for k, it in enumerate(keep)}
for c in pl["collections"]:
    c[3] = sorted(new_index[old_ids[i]] for i in c[3] if old_ids[i] in new_index)
pl["items"] = keep
pl["removed"] = sorted(set(pl.get("removed", [])) | gone)
json.dump(pl, open(PL, "w"), ensure_ascii=False, separators=(",", ":"))

lit = lambda v: "'" + v.replace("'", "''") + "'"
REFUND = 10   # PQ rendus par exemplaire retiré (1 paquet de 5 cartes ≈ 50 PQ en Boutique)
sql = f"""-- Parisquest : « Sous vos pieds », vestiges archéologiques (généré par pipeline/vestiges.py).
-- On ne garde que les vestiges visibles ou clairement décrits. Les cartes retirées sont remboursées
-- ({REFUND} PQ par exemplaire, mises en vente comprises), les échanges en cours qui les contiennent sont annulés.
-- À exécuter une fois dans Supabase (SQL Editor), puis relancer quests_data.sql. Peut être relancé sans risque.
drop table if exists pg_temp.retire;
create temporary table retire (id text primary key);
insert into retire select unnest(array[{",".join(lit(i) for i in pl["removed"])}]) on conflict do nothing;
delete from retire r where not exists (select 1 from public.places p where p.id = r.id);
-- remboursement des cartes possédées
update public.players p set ecus = p.ecus + {REFUND} * x.n
  from (select c.user_id, sum(c.copies) n from public.user_cards c join retire r on r.id = c.place_id group by c.user_id) x
  where p.user_id = x.user_id;
-- ventes au Marché : l'enchérisseur récupère sa mise, le vendeur est remboursé de sa carte
update public.players p set ecus = p.ecus + x.n
  from (select bidder, sum(current_bid) n from public.listings l join retire r on r.id = l.place_id
        where l.status = 'open' and l.bidder is not null group by bidder) x where p.user_id = x.bidder;
update public.players p set ecus = p.ecus + {REFUND} * x.n
  from (select seller, count(*) n from public.listings l join retire r on r.id = l.place_id where l.status = 'open' group by seller) x
  where p.user_id = x.seller;
delete from public.listings l using retire r where l.place_id = r.id;
update public.trades t set status = 'cancelled', decided_at = now()
  where t.status = 'open' and (t.give && (select array_agg(id) from retire) or t.want && (select array_agg(id) from retire));
update public.profiles p set showcase = (select coalesce(array_agg(x), '{{}}') from unnest(p.showcase) x where x not in (select id from retire))
  where p.showcase && (select array_agg(id) from retire);
delete from public.defense_decks d where d.cards && (select array_agg(id) from retire);
update public.messages m set place_id = null from retire r where m.place_id = r.id;
update public.players p set last_visit_place = null from retire r where p.last_visit_place = r.id;
delete from public.visit_log v using retire r where v.place_id = r.id;
delete from public.user_cards c using retire r where c.place_id = r.id;
delete from public.place_tags t using retire r where t.place_id = r.id;
delete from public.places p using retire r where p.id = r.id;
-- vestiges remontés ailleurs : la carte se capture là où on les voit aujourd'hui
""" + "".join(f"update public.places set lat = {pos[0]}, lon = {pos[1]} where id = 'vestige:{k}';\n" for k, (_, _, pos) in MANUEL.items() if pos) + """select count(*) as vestiges_retires from retire;
"""
(ROOT / "site" / "supabase" / "vestiges_retires.sql").write_text(sql)
print(len(retires), "vestiges retirés ;", sum(1 for it in keep if it["k"] == "vestige"), "gardés dont",
      sum(1 for it in keep if it["k"] == "vestige" and it["x"].get("vis")), "visibles")
print(n, "vestiges renommés ;", len(stats), "titres différents")
for k, v in stats.most_common(12): print(f"  {v:4}  {k}")
