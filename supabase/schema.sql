-- =====================================================================
-- Parisquest : serveur (Supabase / PostgreSQL)
-- À exécuter une fois dans Supabase : SQL Editor → New query → coller → Run.
--
-- Principe : le téléphone n'écrit jamais directement dans la base.
-- Tout passe par trois fonctions exécutées sur le serveur :
--   pack_state()   état de la réserve de paquets (horloge du serveur)
--   open_pack()    ouvre un paquet : décompte + tirage des 5 cartes côté serveur
--   visit_place()  valide une visite sur place (distance + une fois par jour)
-- Les tables sont en lecture seule pour les joueurs (Row Level Security).
-- =====================================================================

-- ---------- Lieux (référentiel, rempli par places.csv) ----------
create table if not exists public.places (
  id       text primary key,
  kind     text not null,
  tier     smallint not null check (tier between 0 and 4),   -- 0 Commune … 4 Légendaire
  lat      double precision not null,
  lon      double precision not null,
  reach_m  real not null                                     -- rayon de visite (m), emprise comprise
);
create index if not exists places_tier_idx on public.places (tier);

-- ---------- Joueurs : réserve de paquets ----------
-- packs  : paquets en réserve au moment « anchor »
-- anchor : instant à partir duquel court le paquet suivant
create table if not exists public.players (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  packs      smallint not null default 5 check (packs between 0 and 10),
  anchor     timestamptz not null default now(),
  created_at timestamptz not null default now()
);

-- ---------- Collection ----------
create table if not exists public.user_cards (
  user_id    uuid not null references auth.users (id) on delete cascade,
  place_id   text not null references public.places (id),
  copies     integer not null default 1,
  level      smallint not null default 1,
  visits     integer not null default 0,
  first_at   timestamptz not null default now(),
  last_visit date,
  primary key (user_id, place_id)
);

-- ---------- Journal des paquets ouverts (contrôle, statistiques) ----------
create table if not exists public.pack_log (
  id        bigserial primary key,
  user_id   uuid not null references auth.users (id) on delete cascade,
  opened_at timestamptz not null default now(),
  cards     jsonb not null
);
create index if not exists pack_log_user_idx on public.pack_log (user_id, opened_at desc);

-- ---------- Sécurité : lecture seule, et seulement ses propres lignes ----------
alter table public.places     enable row level security;
alter table public.players    enable row level security;
alter table public.user_cards enable row level security;
alter table public.pack_log   enable row level security;

drop policy if exists "lieux lisibles par tous" on public.places;
create policy "lieux lisibles par tous" on public.places for select using (true);
drop policy if exists "ma réserve" on public.players;
create policy "ma réserve" on public.players for select using (auth.uid() = user_id);
drop policy if exists "mes cartes" on public.user_cards;
create policy "mes cartes" on public.user_cards for select using (auth.uid() = user_id);
drop policy if exists "mes paquets" on public.pack_log;
create policy "mes paquets" on public.pack_log for select using (auth.uid() = user_id);

revoke insert, update, delete, truncate on public.places, public.players, public.user_cards, public.pack_log from anon, authenticated;

-- ---------- Règles des paquets ----------
-- Un paquet toutes les 300 s, 10 au maximum, 5 offerts à l'inscription.
-- Le compteur ne tourne pas quand la réserve est pleine : il repart de zéro au premier paquet ouvert.
create or replace function public._pq_accrue(p public.players)
returns public.players language plpgsql as $$
declare k integer;
begin
  if p.packs >= 10 then
    p.anchor := now();
    return p;
  end if;
  k := floor(extract(epoch from (now() - p.anchor)) / 300)::integer;
  if k > 0 then
    p.packs := least(10, p.packs + k);
    if p.packs >= 10 then p.anchor := now();
    else p.anchor := p.anchor + make_interval(secs => k * 300);
    end if;
  end if;
  return p;
end $$;

-- Charge (et verrouille) la ligne du joueur connecté, après mise à jour du compteur.
-- Le verrou empêche deux ouvertures simultanées de consommer le même paquet.
create or replace function public._pq_player()
returns public.players language plpgsql security definer set search_path = public as $$
declare uid uuid := auth.uid(); p public.players;
begin
  if uid is null then raise exception 'non connecté' using errcode = '28000'; end if;
  insert into public.players (user_id) values (uid) on conflict (user_id) do nothing;
  select * into p from public.players where user_id = uid for update;
  p := public._pq_accrue(p);
  update public.players set packs = p.packs, anchor = p.anchor where user_id = uid;
  return p;
end $$;

create or replace function public._pq_state_json(p public.players)
returns jsonb language sql stable as $$
  select jsonb_build_object(
    'packs', p.packs, 'cap', 10,
    'next_at', case when p.packs >= 10 then null else p.anchor + interval '300 seconds' end,
    'server_now', now())
$$;

create or replace function public.pack_state()
returns jsonb language plpgsql security definer set search_path = public as $$
declare p public.players;
begin
  p := public._pq_player();
  return public._pq_state_json(p);
end $$;

-- Ouvre un paquet. Chances par carte : Légendaire 1 %, Épique 4 %, Rare 10 %, Peu commune 25 %, Commune 60 %.
create or replace function public.open_pack()
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  p public.players; r double precision; t smallint; pid text; is_new boolean; drawn jsonb := '[]'::jsonb; i integer;
begin
  p := public._pq_player();
  if p.packs < 1 then raise exception 'aucun paquet disponible' using errcode = 'P0001'; end if;
  if p.packs >= 10 then p.anchor := now(); end if;
  p.packs := p.packs - 1;
  update public.players set packs = p.packs, anchor = p.anchor where user_id = p.user_id;

  for i in 1..5 loop
    r := random();
    t := case when r < 0.01 then 4 when r < 0.05 then 3 when r < 0.15 then 2 when r < 0.40 then 1 else 0 end;
    select id into pid from public.places where tier = t order by random() limit 1;
    insert into public.user_cards (user_id, place_id) values (p.user_id, pid)
      on conflict (user_id, place_id) do update set copies = public.user_cards.copies + 1
      returning (xmax = 0) into is_new;
    drawn := drawn || jsonb_build_object('id', pid, 'tier', t, 'new', is_new);
  end loop;

  insert into public.pack_log (user_id, cards) values (p.user_id, drawn);
  return public._pq_state_json(p) || jsonb_build_object('cards', drawn);
end $$;

-- Visite sur place d'une carte possédée : distance vérifiée par le serveur, une visite par jour (heure de Paris).
-- Première visite : sceau « Visité ». Visites suivantes : +1 niveau, jusqu'au niveau 5.
create or replace function public.visit_place(p_id text, p_lat double precision, p_lon double precision, p_acc real default null)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  uid uuid := auth.uid(); pl public.places; c public.user_cards; d double precision;
  today date := (now() at time zone 'Europe/Paris')::date;
begin
  if uid is null then raise exception 'non connecté' using errcode = '28000'; end if;
  select * into pl from public.places where id = p_id;
  if not found then raise exception 'lieu inconnu'; end if;
  select * into c from public.user_cards where user_id = uid and place_id = p_id for update;
  if not found then raise exception 'cette carte n''est pas dans votre collection'; end if;
  d := 2 * 6371000 * asin(sqrt(power(sin(radians(p_lat - pl.lat) / 2), 2)
       + cos(radians(pl.lat)) * cos(radians(p_lat)) * power(sin(radians(p_lon - pl.lon) / 2), 2)));
  if d > pl.reach_m + least(greatest(coalesce(p_acc, 0), 0), 25) then
    raise exception 'trop loin du lieu (% m)', round(d);
  end if;
  if c.last_visit = today then raise exception 'déjà visitée aujourd''hui'; end if;
  if c.visits > 0 and c.level >= 5 then raise exception 'niveau maximum atteint'; end if;
  update public.user_cards
     set visits = visits + 1,
         level = case when visits = 0 then level else least(5, level + 1) end,
         last_visit = today
   where user_id = uid and place_id = p_id
   returning * into c;
  return jsonb_build_object('level', c.level, 'visits', c.visits, 'last_visit', c.last_visit);
end $$;

-- Seules les trois fonctions publiques sont appelables par les joueurs connectés.
revoke execute on function public._pq_accrue(public.players), public._pq_player(), public._pq_state_json(public.players) from public, anon, authenticated;
revoke execute on function public.pack_state(), public.open_pack(), public.visit_place(text, double precision, double precision, real) from public, anon;
grant execute on function public.pack_state(), public.open_pack(), public.visit_place(text, double precision, double precision, real) to authenticated;
