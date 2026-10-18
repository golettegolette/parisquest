"""Ponts en double : la même structure existait deux fois, comme voie (famille Rues, Ville de Paris) et comme pont
(famille Eau, Wikidata). Décision de Timothée (18/10/2026) : on garde la version « rue ».

Ce script retire les ponts Wikidata qui ont leur équivalent parmi les voies (même nom à moins de 250 m),
garde les autres (ponts du canal, viaducs, ponts disparus), et refait la série « Ponts de Paris »
avec toutes les voies-ponts et les ponts restants. Il écrit aussi site/supabase/ponts_doublons.sql
pour reporter les cartes déjà possédées sur la version rue côté serveur.
À lancer après build2.py, avant lines.py et quests.py."""
import json, math, re, unicodedata, pathlib
ROOT = pathlib.Path(__file__).parent
PL = ROOT / "site" / "data" / "places.json"
pl = json.load(open(PL)); I = pl["items"]

def norm(s):
    s = unicodedata.normalize("NFD", s.lower()); s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\b(pont|passerelle|de|du|des|la|le|l|d|viaduc)\b", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)
def hav(a1, o1, a2, o2):
    r = math.radians
    return 2 * 6371000 * math.asin(math.sqrt(math.sin(r(a2 - a1) / 2) ** 2 + math.cos(r(a1)) * math.cos(r(a2)) * math.sin(r(o2 - o1) / 2) ** 2))
is_rue_pont = lambda it: it["k"] == "rue" and (it.get("s") in ("Pont", "Passerelle", "Viaduc") or re.match(r"(Petit )?(Pont|Passerelle|Viaduc)\b", it["n"]))

rues = [it for it in I if is_rue_pont(it)]
voies = [it for it in I if it["k"] == "rue"]
# le pont de l'Europe est la place de l'Europe (dalle au-dessus des voies de Saint-Lazare)
MANUEL = {"pont de l'Europe": "Place de l'Europe-Simone Veil"}
pairs = {}
for p in (it for it in I if it["k"] == "pont"):
    a = norm(p["n"])
    if re.search(r"viaduc|métro", p["n"], re.I): continue   # viaducs du métro : ouvrages distincts du pont voisin
    near = sorted(((hav(p["a"], p["o"], r["a"], r["o"]), r) for r in rues), key=lambda x: x[0])
    best = next((r for d, r in near if d < 250 and a and norm(r["n"]) and (a == norm(r["n"]) or a in norm(r["n"]) or norm(r["n"]) in a)), None)
    if not best and (p["n"] in MANUEL or not re.match(r"(pont|passerelle|viaduc)\b", p["n"], re.I)):   # pont Wikidata qui est en fait une place (dalle sur le canal ou sur les voies)
        best = next((r for r in voies if (norm(r["n"]) == a or r["n"] == MANUEL.get(p["n"])) and hav(p["a"], p["o"], r["a"], r["o"]) < 60), None)
    if best:
        pairs[p["i"]] = best["i"]
        # la version rue récupère la photo et l'article Wikipédia de la version pont
        for k in ("p", "c", "wp"):
            if p.get(k) and not best.get(k): best[k] = p[k]

old_ids = [it["i"] for it in I]
keep = [it for it in I if it["i"] not in pairs]
new_index = {it["i"]: n for n, it in enumerate(keep)}
for c in pl["collections"]:
    ids = [old_ids[i] for i in c[3]]
    if c[1] == "Ponts de Paris":
        ids = [it["i"] for it in keep if it["k"] == "pont" or is_rue_pont(it) or it["i"] in pairs.values()]
        c[2] = "Tous les ponts, passerelles et viaducs"
    c[3] = sorted({new_index[pairs.get(i, i)] for i in ids if pairs.get(i, i) in new_index})
pl["items"] = keep
# anciens identifiants → nouveaux, pour reporter les cartes des sauvegardes locales
pl["moved"] = {**pl.get("moved", {}), **pairs}
json.dump(pl, open(PL, "w"), ensure_ascii=False, separators=(",", ":"))

lit = lambda s: "'" + s.replace("'", "''") + "'"
vals = ",\n  ".join(f"({lit(a)}, {lit(b)})" for a, b in sorted(pairs.items()))
sql = f"""-- Parisquest : ponts en double (généré par pipeline/ponts.py). On garde la version « rue » de chaque pont.
-- Les cartes déjà possédées en version « pont » sont reportées sur la version « rue », puis la version « pont » est retirée.
-- À exécuter une fois dans Supabase (SQL Editor), puis relancer quests_data.sql. Peut être relancé sans risque.
drop table if exists pg_temp.pont_map;
create temporary table pont_map (old_id text primary key, new_id text not null);
insert into pont_map values
  {vals};
-- cartes : on ajoute les exemplaires à la version rue (en gardant le meilleur niveau et les visites)
insert into public.user_cards (user_id, place_id, copies, level, visits, first_at, last_visit, pending)
  select c.user_id, m.new_id, sum(c.copies), max(c.level), sum(c.visits), min(c.first_at), max(c.last_visit), bool_and(c.pending)
  from public.user_cards c join pont_map m on m.old_id = c.place_id group by c.user_id, m.new_id
on conflict (user_id, place_id) do update set
  copies = public.user_cards.copies + excluded.copies,
  level = greatest(public.user_cards.level, excluded.level),
  visits = public.user_cards.visits + excluded.visits,
  first_at = least(public.user_cards.first_at, excluded.first_at),
  last_visit = greatest(public.user_cards.last_visit, excluded.last_visit),
  pending = public.user_cards.pending and excluded.pending;
delete from public.user_cards c using pont_map m where c.place_id = m.old_id;
insert into public.visit_log (user_id, place_id, day)
  select distinct v.user_id, m.new_id, v.day from public.visit_log v join pont_map m on m.old_id = v.place_id
on conflict do nothing;
delete from public.visit_log v using pont_map m where v.place_id = m.old_id;
update public.listings l set place_id = m.new_id from pont_map m where l.place_id = m.old_id;
update public.profiles p set showcase = (select array_agg(coalesce(m.new_id, x)) from unnest(p.showcase) x left join pont_map m on m.old_id = x)
  where p.showcase && (select array_agg(old_id) from pont_map);
update public.trades t set give = (select array_agg(coalesce(m.new_id, x)) from unnest(t.give) x left join pont_map m on m.old_id = x),
                           want = (select array_agg(coalesce(m.new_id, x)) from unnest(t.want) x left join pont_map m on m.old_id = x)
  where t.give && (select array_agg(old_id) from pont_map) or t.want && (select array_agg(old_id) from pont_map);
update public.players p set last_visit_place = m.new_id from pont_map m where p.last_visit_place = m.old_id;
update public.messages x set place_id = m.new_id from pont_map m where x.place_id = m.old_id;
update public.defense_decks d set cards = (select array_agg(coalesce(m.new_id, x) order by o) from unnest(d.cards) with ordinality u(x, o) left join pont_map m on m.old_id = x)
  where d.cards && (select array_agg(old_id) from pont_map);
delete from public.place_tags t using pont_map m where t.place_id = m.old_id;
delete from public.places p using pont_map m where p.id = m.old_id;
select count(*) as ponts_retires from pont_map;
"""
(ROOT / "site" / "supabase" / "ponts_doublons.sql").write_text(sql)
print(len(pairs), "ponts en double retirés ;", len(keep), "lieux ; série Ponts de Paris :",
      next(len(c[3]) for c in pl["collections"] if c[1] == "Ponts de Paris"), "lieux")
