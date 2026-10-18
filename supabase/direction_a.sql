-- =====================================================================
-- Parisquest : direction A « Collectionne Paris en le parcourant »
-- À exécuter APRÈS schema.sql et social.sql, puis exécuter places_arr.sql.
-- Peut être relancé sans risque.
--
--   game_state()                    état du joueur : paquet du jour, score, visites du jour (horloge du serveur)
--   open_daily_pack(lat, lon)       paquet du jour : 5 lieux « à découvrir », tirés près du joueur si la position est donnée
--                                   (la position sert au tirage et n'est jamais enregistrée)
--   visit_place(id, lat, lon, acc)  capture sur place : n'importe quel lieu ; une carte à découvrir devient une vraie carte ;
--                                   ensuite une visite par jour fait monter le niveau (max 5)
--   collectors(scope, arr)          classement des collectionneurs : 'paris', 'arr' (un arrondissement) ou 'friends'
--   arr_masters()                   le Maître de chaque arrondissement
--   my_stats()                      score, rang, titres, arrondissements explorés (pour le profil et « Mon Paris »)
--
-- Les anciens paquets (un toutes les 5 minutes, Pack PariGo) sont désactivés : les cartes s'obtiennent sur le terrain.
-- =====================================================================

alter table public.places     add column if not exists arr smallint;                        -- arrondissement (1 à 20), rempli par places_arr.sql
alter table public.user_cards add column if not exists pending boolean not null default false; -- carte « à découvrir » (paquet du jour)
alter table public.players    add column if not exists daily_packs smallint not null default 1;
alter table public.players    add column if not exists daily_on date;
alter table public.players    add column if not exists last_visit_at timestamptz;
alter table public.players    add column if not exists last_visit_place text;
create index if not exists places_arr_idx on public.places (arr);
create index if not exists places_lat_idx on public.places (lat);
do $$ begin
  alter table public.players add constraint players_daily_packs_chk check (daily_packs between 0 and 3);
exception when duplicate_object then null; end $$;

-- ---------- Joueur et paquet du jour ----------
-- Un paquet par jour (heure de Paris), jusqu'à 3 en réserve si l'on ne joue pas pendant quelques jours.
create or replace function public._pq_me()
returns public.players language plpgsql security definer set search_path = public as $$
declare uid uuid := auth.uid(); p public.players; today date := (now() at time zone 'Europe/Paris')::date;
begin
  if uid is null then raise exception 'non connecté' using errcode = '28000'; end if;
  insert into public.players (user_id, daily_on) values (uid, today) on conflict (user_id) do nothing;
  select * into p from public.players where user_id = uid for update;
  if p.daily_on is null then
    p.daily_on := today;
  elsif today > p.daily_on then
    p.daily_packs := least(3, p.daily_packs + (today - p.daily_on));
    p.daily_on := today;
  end if;
  update public.players set daily_packs = p.daily_packs, daily_on = p.daily_on where user_id = uid;
  return p;
end $$;

-- Score de collection : Commune 1, Peu commune 2, Rare 5, Épique 15, Légendaire 50 ; ×2 si visitée sur place.
-- Les cartes « à découvrir » ne comptent pas.
create or replace function public._pq_score(u uuid, a smallint default null)
returns integer language sql stable as $$
  select coalesce(sum((array[1, 2, 5, 15, 50])[pl.tier + 1] * case when c.visits > 0 then 2 else 1 end), 0)::integer
  from public.user_cards c join public.places pl on pl.id = c.place_id
  where c.user_id = u and not c.pending and (a is null or pl.arr = a)
$$;

create or replace function public._pq_state_a(p public.players)
returns jsonb language sql stable security definer set search_path = public as $$
  select jsonb_build_object(
    'daily_packs', p.daily_packs, 'cap', 3,
    'next_at', case when p.daily_packs >= 3 then null
                    else (((now() at time zone 'Europe/Paris')::date + 1)::timestamp at time zone 'Europe/Paris') end,
    'ecus', p.ecus, 'score', public._pq_score(p.user_id),
    'visits_today', (select count(*) from public.visit_log v where v.user_id = p.user_id and v.day = (now() at time zone 'Europe/Paris')::date),
    'server_now', now())
$$;

create or replace function public.game_state()
returns jsonb language plpgsql security definer set search_path = public as $$
declare p public.players;
begin
  p := public._pq_me();
  return public._pq_state_a(p);
end $$;

-- Tire un lieu du palier t que le joueur ne possède pas encore, dans un carré de rad mètres autour de (lat, lon)
-- (partout dans Paris si lat est nul).
drop function if exists public._pq_pick(uuid, smallint, double precision, double precision, double precision, text[]);
create or replace function public._pq_pick(u uuid, t smallint, c_lat double precision, c_lon double precision, rad double precision, excl text[])
returns text language sql volatile as $$
  select pl.id from public.places pl
  where pl.tier = t
    and (c_lat is null or (pl.lat between c_lat - rad / 111320.0 and c_lat + rad / 111320.0
                           and pl.lon between c_lon - rad / (111320.0 * cos(radians(c_lat))) and c_lon + rad / (111320.0 * cos(radians(c_lat)))))
    and not exists (select 1 from public.user_cards c where c.user_id = u and c.place_id = pl.id)
    and pl.id <> all(excl)
  order by random() limit 1
$$;

-- Paquet du jour : 5 lieux à découvrir. Chances par carte : Légendaire 1 %, Épique 4 %, Rare 10 %, Peu commune 25 %, Commune 60 %.
-- Avec la position : d'abord à moins de 1,5 km, puis 4 km, en descendant de palier si besoin, puis partout dans Paris.
create or replace function public.open_daily_pack(p_lat double precision default null, p_lon double precision default null)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  p public.players; r double precision; t smallint; tt smallint; pid text; drawn jsonb := '[]'::jsonb; ids text[] := '{}';
  i integer; rad double precision; lat double precision := p_lat; lon double precision := p_lon;
begin
  p := public._pq_me();
  if p.daily_packs < 1 then raise exception 'plus de paquet aujourd''hui : le prochain arrive à minuit' using errcode = 'P0001'; end if;
  update public.players set daily_packs = daily_packs - 1 where user_id = p.user_id;
  p.daily_packs := p.daily_packs - 1;
  if lat is null or lon is null or lat not between 48.80 and 48.92 or lon not between 2.22 and 2.48 then lat := null; lon := null; end if;

  for i in 1..5 loop
    r := random();
    t := case when r < 0.01 then 4 when r < 0.05 then 3 when r < 0.15 then 2 when r < 0.40 then 1 else 0 end;
    pid := null;
    if lat is not null then
      foreach rad in array array[1500, 4000] loop
        tt := t;
        while pid is null and tt >= 0 loop
          pid := public._pq_pick(p.user_id, tt, lat, lon, rad, ids);
          if pid is null then tt := tt - 1; end if;
        end loop;
        exit when pid is not null;
      end loop;
    end if;
    tt := t;
    while pid is null and tt >= 0 loop
      pid := public._pq_pick(p.user_id, tt, null, null, 0, ids);
      if pid is null then tt := tt - 1; end if;
    end loop;
    exit when pid is null;                                       -- collection complète : plus rien à tirer
    ids := ids || pid;
    insert into public.user_cards (user_id, place_id, pending, visits) values (p.user_id, pid, true, 0) on conflict do nothing;
    drawn := drawn || jsonb_build_object('id', pid, 'tier', (select tier from public.places where id = pid), 'new', true, 'pending', true);
  end loop;

  insert into public.pack_log (user_id, cards) values (p.user_id, jsonb_build_object('daily', true, 'cards', drawn));
  return public._pq_state_a(p) || jsonb_build_object('cards', drawn);
end $$;

-- ---------- Capture sur place ----------
-- Distance vérifiée par le serveur ; une visite par lieu et par jour ; 60 visites par jour au maximum ;
-- refusée si le déplacement depuis la visite précédente suppose plus de 50 km/h.
create or replace function public.visit_place(p_id text, p_lat double precision, p_lon double precision, p_acc real default null)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  uid uuid; p public.players; pl public.places; prev public.places; c public.user_cards; d double precision; dd double precision; dt double precision;
  today date := (now() at time zone 'Europe/Paris')::date; n integer; captured boolean := false; have boolean;
begin
  p := public._pq_me(); uid := p.user_id;                          -- verrouille le compte : une visite à la fois
  select * into pl from public.places where id = p_id;
  if not found then raise exception 'lieu inconnu' using errcode = 'P0001'; end if;
  d := 2 * 6371000 * asin(sqrt(power(sin(radians(p_lat - pl.lat) / 2), 2)
       + cos(radians(pl.lat)) * cos(radians(p_lat)) * power(sin(radians(p_lon - pl.lon) / 2), 2)));
  if d > pl.reach_m + least(greatest(coalesce(p_acc, 0), 0), 25) then
    raise exception 'trop loin du lieu (% m)', round(d) using errcode = 'P0001';
  end if;

  select * into c from public.user_cards where user_id = uid and place_id = p_id for update;
  have := found;
  if have and not c.pending then
    if c.last_visit = today then raise exception 'déjà visitée aujourd''hui' using errcode = 'P0001'; end if;
    if c.visits > 0 and c.level >= 5 then raise exception 'niveau maximum atteint' using errcode = 'P0001'; end if;
  end if;

  select count(*) into n from public.visit_log where user_id = uid and day = today;
  if n >= 60 then raise exception 'limite de 60 visites par jour atteinte' using errcode = 'P0001'; end if;
  if p.last_visit_at is not null and p.last_visit_place is not null and p.last_visit_place <> p_id then
    select * into prev from public.places where id = p.last_visit_place;
    if found then
      dd := 2 * 6371000 * asin(sqrt(power(sin(radians(pl.lat - prev.lat) / 2), 2)
            + cos(radians(prev.lat)) * cos(radians(pl.lat)) * power(sin(radians(pl.lon - prev.lon) / 2), 2)));
      dt := greatest(extract(epoch from (now() - p.last_visit_at)), 1);
      if dd > 300 and dd / dt > 13.9 then
        raise exception 'déplacement trop rapide depuis votre dernière visite' using errcode = 'P0001';
      end if;
    end if;
  end if;

  if not have then
    insert into public.user_cards (user_id, place_id, copies, level, visits, last_visit, pending)
      values (uid, p_id, 1, 1, 1, today, false) returning * into c;
    captured := true;
  elsif c.pending then
    update public.user_cards set pending = false, visits = 1, level = 1, last_visit = today, first_at = now()
     where user_id = uid and place_id = p_id returning * into c;
    captured := true;
  else
    update public.user_cards
       set visits = visits + 1, level = case when visits = 0 then level else least(5, level + 1) end, last_visit = today
     where user_id = uid and place_id = p_id returning * into c;
  end if;

  update public.players set ecus = ecus + 10, last_visit_at = now(), last_visit_place = p_id where user_id = uid;
  insert into public.visit_log (user_id, place_id, day) values (uid, p_id, today) on conflict do nothing;
  return jsonb_build_object('level', c.level, 'visits', c.visits, 'last_visit', c.last_visit, 'captured', captured,
                            'tier', pl.tier, 'arr', pl.arr, 'score', public._pq_score(uid));
end $$;

-- ---------- Classements des collectionneurs ----------
drop function if exists public.collectors(text, smallint);
create or replace function public.collectors(p_scope text default 'paris', p_arr integer default null)
returns jsonb language plpgsql security definer set search_path = public stable as $$
declare uid uuid := public._me();
begin
  if p_scope not in ('paris', 'arr', 'friends') then raise exception 'classement inconnu' using errcode = 'P0001'; end if;
  if p_scope = 'arr' and (p_arr is null or p_arr not between 1 and 20) then raise exception 'arrondissement inconnu' using errcode = 'P0001'; end if;
  return (with s as (
      select c.user_id,
             sum((array[1, 2, 5, 15, 50])[pl.tier + 1] * case when c.visits > 0 then 2 else 1 end)::integer score,
             count(*)::integer cards, (count(*) filter (where c.visits > 0))::integer visited
      from public.user_cards c join public.places pl on pl.id = c.place_id
      where not c.pending and (p_scope <> 'arr' or pl.arr = p_arr::smallint)
      group by c.user_id),
    pool as (
      select pr.user_id, pr.pseudo, coalesce(s.score, 0) score, coalesce(s.cards, 0) cards, coalesce(s.visited, 0) visited
      from public.profiles pr left join s on s.user_id = pr.user_id
      where (p_scope <> 'friends' or pr.user_id = uid or public._are_friends(uid, pr.user_id))
        and (coalesce(s.score, 0) > 0 or pr.user_id = uid)),
    ranked as (select *, rank() over (order by score desc) r from pool)
    select jsonb_build_object(
      'scope', p_scope, 'arr', p_arr,
      'top', coalesce((select jsonb_agg(jsonb_build_object('rank', r, 'pseudo', pseudo, 'score', score, 'cards', cards,
                                         'visited', visited, 'me', user_id = uid) order by r, lower(pseudo))
                       from (select * from ranked order by r, lower(pseudo) limit 100) t), '[]'),
      'me', (select jsonb_build_object('rank', r, 'score', score, 'cards', cards, 'visited', visited) from ranked where user_id = uid),
      'players', (select count(*) from ranked)));
end $$;

create or replace function public.arr_masters()
returns jsonb language plpgsql security definer set search_path = public stable as $$
declare uid uuid := public._me();
begin
  return coalesce((with s as (
      select c.user_id, pl.arr, sum((array[1, 2, 5, 15, 50])[pl.tier + 1] * case when c.visits > 0 then 2 else 1 end)::integer score
      from public.user_cards c join public.places pl on pl.id = c.place_id
      where not c.pending and pl.arr is not null
      group by c.user_id, pl.arr),
    r as (select s.*, pr.pseudo, row_number() over (partition by s.arr order by s.score desc, s.user_id) rn
          from s join public.profiles pr on pr.user_id = s.user_id)
    select jsonb_agg(jsonb_build_object('arr', arr, 'pseudo', pseudo, 'score', score, 'me', user_id = uid) order by arr)
    from r where rn = 1), '[]');
end $$;

-- Mes chiffres : score, rang à Paris, titres de Maître, lieux visités par arrondissement (pour « Mon Paris »)
create or replace function public.my_stats()
returns jsonb language plpgsql security definer set search_path = public stable as $$
declare uid uuid := public._me(); masters jsonb := public.arr_masters();
begin
  return jsonb_build_object(
    'score', public._pq_score(uid),
    'cards', (select count(*) from public.user_cards where user_id = uid and not pending),
    'visited', (select count(*) from public.user_cards where user_id = uid and not pending and visits > 0),
    'pending', (select count(*) from public.user_cards where user_id = uid and pending),
    'rank', (select r from (select pr.user_id, rank() over (order by public._pq_score(pr.user_id) desc) r from public.profiles pr) x where x.user_id = uid),
    'titles', coalesce((select jsonb_agg((m ->> 'arr')::integer) from jsonb_array_elements(masters) m where (m ->> 'me')::boolean), '[]'),
    'by_arr', coalesce((select jsonb_object_agg(arr, n) from (
                 select pl.arr, count(*) n from public.user_cards c join public.places pl on pl.id = c.place_id
                 where c.user_id = uid and not c.pending and c.visits > 0 and pl.arr is not null group by pl.arr) a), '{}'));
end $$;

-- ---------- Les cartes à découvrir ne s'échangent pas, ne se vendent pas et ne s'exposent pas ----------
create or replace function public._take_card(u uuid, pid text) returns void language plpgsql as $$
declare c public.user_cards;
begin
  select * into c from public.user_cards where user_id = u and place_id = pid for update;
  if not found or c.copies < 1 or c.pending then raise exception 'carte non disponible : %', pid using errcode = 'P0001'; end if;
  if c.copies > 1 then
    update public.user_cards set copies = copies - 1 where user_id = u and place_id = pid;
  else
    delete from public.user_cards where user_id = u and place_id = pid;
    update public.profiles set showcase = array_remove(showcase, pid) where user_id = u;
  end if;
end $$;

create or replace function public._owns_all(u uuid, ids text[]) returns boolean language sql stable as $$
  select not exists (
    select 1 from (select x, count(*) n from unnest(ids) x group by x) need
    left join public.user_cards c on c.user_id = u and c.place_id = need.x and not c.pending
    where coalesce(c.copies, 0) < need.n)
$$;

create or replace function public.set_showcase(p_ids text[]) returns jsonb
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo(); ids text[];
begin
  select coalesce(array_agg(x), '{}') into ids from (select distinct unnest(p_ids) x) s;
  if cardinality(ids) > 3 then raise exception '3 cartes au maximum' using errcode = 'P0001'; end if;
  if exists (select 1 from unnest(ids) x where not exists (select 1 from public.user_cards where user_id = uid and place_id = x and not pending)) then
    raise exception 'la vitrine ne peut montrer que vos cartes' using errcode = 'P0001';
  end if;
  update public.profiles set showcase = ids where user_id = uid;
  return public.my_profile();
end $$;

create or replace function public.friend_cards(p_other uuid) returns jsonb
language plpgsql security definer set search_path = public stable as $$
declare uid uuid := public._me();
begin
  if p_other <> uid and not public._are_friends(uid, p_other) then raise exception 'réservé à vos amis' using errcode = 'P0001'; end if;
  return coalesce((select jsonb_agg(jsonb_build_object('id', place_id, 'copies', copies, 'level', level, 'visits', visits))
                   from public.user_cards where user_id = p_other and not pending), '[]');
end $$;

-- ---------- Droits ----------
revoke execute on function public._pq_me(), public._pq_score(uuid, smallint), public._pq_state_a(public.players),
  public._pq_pick(uuid, smallint, double precision, double precision, double precision, text[]) from public, anon, authenticated;
-- anciens paquets désactivés
revoke execute on function public.open_pack(), public.open_parigo_pack() from public, anon, authenticated;
do $$
declare f text;
begin
  foreach f in array array['game_state()', 'open_daily_pack(double precision, double precision)',
    'visit_place(text, double precision, double precision, real)', 'collectors(text, integer)', 'arr_masters()', 'my_stats()'] loop
    execute format('revoke execute on function public.%s from public, anon', f);
    execute format('grant execute on function public.%s to authenticated', f);
  end loop;
end $$;
