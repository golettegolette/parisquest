-- =====================================================================
-- Parisquest : fonctions sociales (à exécuter APRÈS schema.sql)
-- Profils et pseudos, amis, messages, échanges, Marché aux enchères,
-- classement, guildes, batailles entre amis, signalements.
--
-- Même principe que pour les paquets : les tables sont en lecture seule
-- pour les joueurs, toute écriture passe par une fonction du serveur qui
-- vérifie les règles et déplace cartes et écus en une seule opération.
--
-- Règles validées par Timothée (14/10/2026) :
--   * une carte cédée (échange ou vente) repart au niveau 1, sans sceau « Visité », chez le nouveau propriétaire ;
--   * toutes les cartes sont échangeables et vendables, même un exemplaire unique ;
--   * pseudo obligatoire et unique pour accéder aux fonctions sociales.
-- =====================================================================

-- ---------- Outils internes ----------
create or replace function public._me() returns uuid language plpgsql stable as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'non connecté' using errcode = '28000'; end if;
  return uid;
end $$;

create or replace function public._ensure_player(u uuid) returns void language sql as $$
  insert into public.players (user_id) values (u) on conflict (user_id) do nothing;
$$;

-- Retire un exemplaire d'une carte (erreur si le joueur ne l'a pas). Le dernier exemplaire supprime la carte,
-- son niveau et son sceau ; elle quitte aussi la vitrine.
create or replace function public._take_card(u uuid, pid text) returns void language plpgsql as $$
declare c public.user_cards;
begin
  select * into c from public.user_cards where user_id = u and place_id = pid for update;
  if not found or c.copies < 1 then raise exception 'carte non disponible : %', pid using errcode = 'P0001'; end if;
  if c.copies > 1 then
    update public.user_cards set copies = copies - 1 where user_id = u and place_id = pid;
  else
    delete from public.user_cards where user_id = u and place_id = pid;
    update public.profiles set showcase = array_remove(showcase, pid) where user_id = u;
  end if;
end $$;

-- Donne un exemplaire : nouvelle carte au niveau 1 sans visite, ou un exemplaire de plus si déjà possédée.
create or replace function public._give_card(u uuid, pid text) returns void language sql as $$
  insert into public.user_cards (user_id, place_id) values (u, pid)
  on conflict (user_id, place_id) do update set copies = public.user_cards.copies + 1;
$$;

-- Verrouille les comptes de plusieurs joueurs, toujours dans le même ordre (évite les interblocages).
create or replace function public._lock_players(us uuid[]) returns void language plpgsql as $$
declare u uuid;
begin
  foreach u in array us loop if u is not null then perform public._ensure_player(u); end if; end loop;
  perform 1 from public.players where user_id = any(us) order by user_id for update;
end $$;

-- ---------- Profils ----------
create table if not exists public.profiles (
  user_id     uuid primary key references auth.users (id) on delete cascade,
  pseudo      text not null check (pseudo ~ '^[A-Za-z0-9À-ÖØ-öø-ÿ_.-]{3,20}$'),
  friend_code text not null unique,
  showcase    text[] not null default '{}',
  created_at  timestamptz not null default now()
);
create unique index if not exists profiles_pseudo_uq on public.profiles (lower(pseudo));

create or replace function public._pseudo(u uuid) returns text language sql stable as $$
  select pseudo from public.profiles where user_id = u
$$;
create or replace function public._need_pseudo() returns uuid language plpgsql stable as $$
declare uid uuid := public._me();
begin
  if not exists (select 1 from public.profiles where user_id = uid) then
    raise exception 'choisissez d''abord un pseudo' using errcode = 'P0001';
  end if;
  return uid;
end $$;

create or replace function public.set_pseudo(p_pseudo text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._me(); p text := btrim(p_pseudo); code text;
begin
  if p !~ '^[A-Za-z0-9À-ÖØ-öø-ÿ_.-]{3,20}$' then
    raise exception 'pseudo invalide : 3 à 20 lettres, chiffres, point, tiret ou souligné' using errcode = 'P0001';
  end if;
  if lower(p) ~ '(admin|moderat|parisquest|support|staff|officiel)' then
    raise exception 'ce pseudo est réservé' using errcode = 'P0001';
  end if;
  if exists (select 1 from public.profiles where lower(pseudo) = lower(p) and user_id <> uid) then
    raise exception 'ce pseudo est déjà pris' using errcode = 'P0001';
  end if;
  if exists (select 1 from public.profiles where user_id = uid) then
    update public.profiles set pseudo = p where user_id = uid;
  else
    loop
      code := upper(substr(md5(random()::text || uid::text || clock_timestamp()::text), 1, 6));
      exit when not exists (select 1 from public.profiles where friend_code = code);
    end loop;
    insert into public.profiles (user_id, pseudo, friend_code) values (uid, p, code);
  end if;
  perform public._ensure_player(uid);
  return public.my_profile();
end $$;

create or replace function public.set_showcase(p_ids text[]) returns jsonb
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo(); ids text[];
begin
  select coalesce(array_agg(x), '{}') into ids from (select distinct unnest(p_ids) x) s;
  if cardinality(ids) > 3 then raise exception '3 cartes au maximum' using errcode = 'P0001'; end if;
  if exists (select 1 from unnest(ids) x where not exists (select 1 from public.user_cards where user_id = uid and place_id = x)) then
    raise exception 'la vitrine ne peut montrer que vos cartes' using errcode = 'P0001';
  end if;
  update public.profiles set showcase = ids where user_id = uid;
  return public.my_profile();
end $$;

create or replace function public.my_profile() returns jsonb
language sql security definer set search_path = public stable as $$
  select coalesce((select jsonb_build_object('pseudo', pseudo, 'friend_code', friend_code, 'showcase', showcase, 'since', created_at)
                   from public.profiles where user_id = auth.uid()), '{}'::jsonb)
$$;

-- ---------- Amis et blocages ----------
create table if not exists public.friends (
  user_a       uuid not null references auth.users (id) on delete cascade,
  user_b       uuid not null references auth.users (id) on delete cascade,
  status       text not null check (status in ('pending', 'accepted')),
  requested_by uuid not null,
  created_at   timestamptz not null default now(),
  primary key (user_a, user_b),
  check (user_a < user_b)
);
create table if not exists public.blocks (
  blocker    uuid not null references auth.users (id) on delete cascade,
  blocked    uuid not null references auth.users (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (blocker, blocked)
);
create or replace function public._are_friends(a uuid, b uuid) returns boolean language sql stable as $$
  select exists (select 1 from public.friends where user_a = least(a, b) and user_b = greatest(a, b) and status = 'accepted')
$$;
create or replace function public._blocked(a uuid, b uuid) returns boolean language sql stable as $$
  select exists (select 1 from public.blocks where (blocker = a and blocked = b) or (blocker = b and blocked = a))
$$;
create or replace function public._find_user(p_who text) returns uuid language sql stable as $$
  select user_id from public.profiles where lower(pseudo) = lower(btrim(p_who)) or friend_code = upper(btrim(p_who)) limit 1
$$;

create or replace function public.friend_request(p_who text) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo(); other uuid := public._find_user(p_who); f public.friends;
begin
  if other is null then raise exception 'aucun joueur avec ce pseudo ou ce code' using errcode = 'P0001'; end if;
  if other = uid then raise exception 'c''est vous' using errcode = 'P0001'; end if;
  if public._blocked(uid, other) then raise exception 'impossible d''ajouter ce joueur' using errcode = 'P0001'; end if;
  if (select count(*) from public.friends where (user_a = uid or user_b = uid) and status = 'accepted') >= 200 then
    raise exception '200 amis au maximum' using errcode = 'P0001';
  end if;
  select * into f from public.friends where user_a = least(uid, other) and user_b = greatest(uid, other) for update;
  if found then
    if f.status = 'accepted' then return 'déjà amis'; end if;
    if f.requested_by = other then
      update public.friends set status = 'accepted' where user_a = f.user_a and user_b = f.user_b;
      return 'accepté';
    end if;
    return 'demande déjà envoyée';
  end if;
  insert into public.friends (user_a, user_b, status, requested_by) values (least(uid, other), greatest(uid, other), 'pending', uid);
  return 'demande envoyée';
end $$;

create or replace function public.friend_respond(p_other uuid, p_accept boolean) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo();
begin
  if p_accept then
    update public.friends set status = 'accepted'
     where user_a = least(uid, p_other) and user_b = greatest(uid, p_other) and status = 'pending' and requested_by = p_other;
    if not found then raise exception 'aucune demande de ce joueur' using errcode = 'P0001'; end if;
    return 'accepté';
  end if;
  delete from public.friends where user_a = least(uid, p_other) and user_b = greatest(uid, p_other) and status = 'pending';
  return 'refusé';
end $$;

create or replace function public.friend_remove(p_other uuid) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._me();
begin
  delete from public.friends where user_a = least(uid, p_other) and user_b = greatest(uid, p_other);
  return 'retiré';
end $$;

create or replace function public.block_user(p_other uuid, p_block boolean default true) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._me();
begin
  if p_other = uid then raise exception 'c''est vous' using errcode = 'P0001'; end if;
  if p_block then
    insert into public.blocks (blocker, blocked) values (uid, p_other) on conflict do nothing;
    delete from public.friends where user_a = least(uid, p_other) and user_b = greatest(uid, p_other);
    update public.trades set status = 'cancelled', decided_at = now()
     where status = 'open' and ((from_user = uid and to_user = p_other) or (from_user = p_other and to_user = uid));
    return 'bloqué';
  end if;
  delete from public.blocks where blocker = uid and blocked = p_other;
  return 'débloqué';
end $$;

-- Liste des amis (avec vitrine), demandes reçues et envoyées, joueurs bloqués
create or replace function public.friends_list() returns jsonb
language plpgsql security definer set search_path = public stable as $$
declare uid uuid := public._me();
begin
  return jsonb_build_object(
    'friends', coalesce((select jsonb_agg(jsonb_build_object('id', p.user_id, 'pseudo', p.pseudo, 'showcase', p.showcase,
                 'cards', (select count(*) from public.user_cards c where c.user_id = p.user_id),
                 'defense', exists (select 1 from public.defense_decks d where d.user_id = p.user_id)) order by lower(p.pseudo))
               from public.friends f join public.profiles p on p.user_id = case when f.user_a = uid then f.user_b else f.user_a end
               where (f.user_a = uid or f.user_b = uid) and f.status = 'accepted'), '[]'),
    'incoming', coalesce((select jsonb_agg(jsonb_build_object('id', p.user_id, 'pseudo', p.pseudo))
               from public.friends f join public.profiles p on p.user_id = f.requested_by
               where (f.user_a = uid or f.user_b = uid) and f.status = 'pending' and f.requested_by <> uid), '[]'),
    'outgoing', coalesce((select jsonb_agg(jsonb_build_object('id', p.user_id, 'pseudo', p.pseudo))
               from public.friends f join public.profiles p on p.user_id = case when f.user_a = uid then f.user_b else f.user_a end
               where (f.user_a = uid or f.user_b = uid) and f.status = 'pending' and f.requested_by = uid), '[]'),
    'blocked', coalesce((select jsonb_agg(jsonb_build_object('id', p.user_id, 'pseudo', p.pseudo))
               from public.blocks b join public.profiles p on p.user_id = b.blocked where b.blocker = uid), '[]'));
end $$;

-- Collection d'un ami (lecture seule)
create or replace function public.friend_cards(p_other uuid) returns jsonb
language plpgsql security definer set search_path = public stable as $$
declare uid uuid := public._me();
begin
  if p_other <> uid and not public._are_friends(uid, p_other) then raise exception 'réservé à vos amis' using errcode = 'P0001'; end if;
  return coalesce((select jsonb_agg(jsonb_build_object('id', place_id, 'copies', copies, 'level', level, 'visits', visits))
                   from public.user_cards where user_id = p_other), '[]');
end $$;

-- ---------- Messages privés (entre amis) ----------
create table if not exists public.messages (
  id         bigserial primary key,
  sender     uuid not null references auth.users (id) on delete cascade,
  recipient  uuid not null references auth.users (id) on delete cascade,
  body       text not null check (char_length(body) between 1 and 500),
  place_id   text references public.places (id),
  created_at timestamptz not null default now(),
  read_at    timestamptz
);
create index if not exists messages_pair_idx on public.messages (least(sender, recipient), greatest(sender, recipient), created_at desc);
create index if not exists messages_rate_idx on public.messages (sender, created_at desc);

create or replace function public.send_message(p_to uuid, p_body text, p_place text default null) returns jsonb
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo(); m public.messages;
begin
  if not public._are_friends(uid, p_to) or public._blocked(uid, p_to) then raise exception 'messages réservés à vos amis' using errcode = 'P0001'; end if;
  if (select count(*) from public.messages where sender = uid and created_at > now() - interval '1 minute') >= 20 then
    raise exception 'trop de messages, patientez une minute' using errcode = 'P0001';
  end if;
  insert into public.messages (sender, recipient, body, place_id) values (uid, p_to, btrim(p_body), p_place) returning * into m;
  return to_jsonb(m);
end $$;

create or replace function public.dm_thread(p_other uuid, p_before bigint default null) returns jsonb
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._me();
begin
  update public.messages set read_at = now() where recipient = uid and sender = p_other and read_at is null;
  return coalesce((select jsonb_agg(to_jsonb(m) order by m.id) from (
    select * from public.messages
     where least(sender, recipient) = least(uid, p_other) and greatest(sender, recipient) = greatest(uid, p_other)
       and (p_before is null or id < p_before)
     order by id desc limit 60) m), '[]');
end $$;

create or replace function public.conversations() returns jsonb
language plpgsql security definer set search_path = public stable as $$
declare uid uuid := public._me();
begin
  return coalesce((select jsonb_agg(x order by x->>'at' desc nulls last) from (
    select jsonb_build_object('id', p.user_id, 'pseudo', p.pseudo,
             'last', (select body from public.messages m where least(m.sender, m.recipient) = least(uid, p.user_id) and greatest(m.sender, m.recipient) = greatest(uid, p.user_id) order by id desc limit 1),
             'at', (select max(created_at) from public.messages m where least(m.sender, m.recipient) = least(uid, p.user_id) and greatest(m.sender, m.recipient) = greatest(uid, p.user_id)),
             'unread', (select count(*) from public.messages m where m.recipient = uid and m.sender = p.user_id and m.read_at is null)) x
      from public.friends f join public.profiles p on p.user_id = case when f.user_a = uid then f.user_b else f.user_a end
     where (f.user_a = uid or f.user_b = uid) and f.status = 'accepted') s), '[]');
end $$;

-- ---------- Échanges (toutes les cartes, entre amis) ----------
create table if not exists public.trades (
  id         bigserial primary key,
  from_user  uuid not null references auth.users (id) on delete cascade,
  to_user    uuid not null references auth.users (id) on delete cascade,
  give       text[] not null default '{}',   -- un élément = un exemplaire
  want       text[] not null default '{}',
  status     text not null default 'open' check (status in ('open', 'accepted', 'declined', 'cancelled')),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default now() + interval '3 days',
  decided_at timestamptz
);
create index if not exists trades_to_idx on public.trades (to_user, status);
create index if not exists trades_from_idx on public.trades (from_user, status);

-- Vérifie qu'un joueur possède assez d'exemplaires pour une liste (doublons compris)
create or replace function public._owns_all(u uuid, ids text[]) returns boolean language sql stable as $$
  select not exists (
    select 1 from (select x, count(*) n from unnest(ids) x group by x) need
    left join public.user_cards c on c.user_id = u and c.place_id = need.x
    where coalesce(c.copies, 0) < need.n)
$$;

create or replace function public.propose_trade(p_to uuid, p_give text[], p_want text[]) returns bigint
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo(); tid bigint;
begin
  if not public._are_friends(uid, p_to) or public._blocked(uid, p_to) then raise exception 'échanges réservés à vos amis' using errcode = 'P0001'; end if;
  if coalesce(cardinality(p_give), 0) + coalesce(cardinality(p_want), 0) = 0 then raise exception 'échange vide' using errcode = 'P0001'; end if;
  if coalesce(cardinality(p_give), 0) > 10 or coalesce(cardinality(p_want), 0) > 10 then raise exception '10 cartes au maximum de chaque côté' using errcode = 'P0001'; end if;
  if not public._owns_all(uid, coalesce(p_give, '{}')) then raise exception 'vous ne possédez pas toutes ces cartes' using errcode = 'P0001'; end if;
  if not public._owns_all(p_to, coalesce(p_want, '{}')) then raise exception 'votre ami ne possède pas toutes ces cartes' using errcode = 'P0001'; end if;
  if (select count(*) from public.trades where from_user = uid and status = 'open' and expires_at > now()) >= 20 then
    raise exception '20 propositions en cours au maximum' using errcode = 'P0001';
  end if;
  insert into public.trades (from_user, to_user, give, want) values (uid, p_to, coalesce(p_give, '{}'), coalesce(p_want, '{}')) returning id into tid;
  return tid;
end $$;

-- Acceptation : toutes les cartes changent de main en une seule opération, ou rien ne bouge.
create or replace function public.respond_trade(p_id bigint, p_accept boolean) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._me(); t public.trades; x text;
begin
  select * into t from public.trades where id = p_id for update;
  if not found or t.to_user <> uid then raise exception 'échange introuvable' using errcode = 'P0001'; end if;
  if t.status <> 'open' or t.expires_at <= now() then raise exception 'cet échange n''est plus ouvert' using errcode = 'P0001'; end if;
  if not p_accept then
    update public.trades set status = 'declined', decided_at = now() where id = p_id;
    return 'refusé';
  end if;
  if public._blocked(t.from_user, t.to_user) then raise exception 'échange impossible' using errcode = 'P0001'; end if;
  perform public._lock_players(array[t.from_user, t.to_user]);
  foreach x in array t.give loop perform public._take_card(t.from_user, x); perform public._give_card(t.to_user, x); end loop;
  foreach x in array t.want loop perform public._take_card(t.to_user, x); perform public._give_card(t.from_user, x); end loop;
  update public.trades set status = 'accepted', decided_at = now() where id = p_id;
  return 'accepté';
end $$;

create or replace function public.cancel_trade(p_id bigint) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._me();
begin
  update public.trades set status = 'cancelled', decided_at = now() where id = p_id and from_user = uid and status = 'open';
  if not found then raise exception 'échange introuvable' using errcode = 'P0001'; end if;
  return 'annulé';
end $$;

create or replace function public.my_trades() returns jsonb
language plpgsql security definer set search_path = public stable as $$
declare uid uuid := public._me();
begin
  return coalesce((select jsonb_agg(jsonb_build_object('id', t.id, 'from', t.from_user, 'to', t.to_user,
             'from_pseudo', public._pseudo(t.from_user), 'to_pseudo', public._pseudo(t.to_user),
             'give', t.give, 'want', t.want,
             'status', case when t.status = 'open' and t.expires_at <= now() then 'expired' else t.status end,
             'created_at', t.created_at, 'expires_at', t.expires_at) order by t.created_at desc)
           from (select * from public.trades where from_user = uid or to_user = uid order by created_at desc limit 60) t), '[]');
end $$;

-- ---------- Marché aux enchères ----------
-- La carte mise en vente quitte la collection du vendeur (séquestre) ; les écus d'une enchère sont débités tout de suite
-- et rendus si quelqu'un surenchérit. Commission de 5 % sur le prix de vente.
create table if not exists public.listings (
  id          bigserial primary key,
  seller      uuid not null references auth.users (id) on delete cascade,
  place_id    text not null references public.places (id),
  start_price integer not null check (start_price between 1 and 1000000),
  buyout      integer check (buyout is null or buyout between 2 and 2000000),
  current_bid integer,
  bidder      uuid references auth.users (id) on delete set null,
  bids        integer not null default 0,
  ends_at     timestamptz not null,
  status      text not null default 'open' check (status in ('open', 'sold', 'unsold', 'cancelled')),
  created_at  timestamptz not null default now(),
  closed_at   timestamptz
);
create index if not exists listings_open_idx on public.listings (status, ends_at);
create index if not exists listings_seller_idx on public.listings (seller, status);
create table if not exists public.listing_bids (
  listing_id bigint not null references public.listings (id) on delete cascade,
  bidder     uuid not null references auth.users (id) on delete cascade,
  amount     integer not null,
  created_at timestamptz not null default now()
);
create index if not exists listing_bids_idx on public.listing_bids (listing_id, created_at desc);

create or replace function public._min_bid(l public.listings) returns integer language sql immutable as $$
  select case when l.current_bid is null then l.start_price else l.current_bid + greatest(1, ceil(l.current_bid * 0.05)::integer) end
$$;

-- Clôture des ventes terminées. Appelée chaque minute par pg_cron, et à chaque consultation du Marché.
create or replace function public.settle_auctions() returns integer
language plpgsql security definer set search_path = public as $$
declare l public.listings; n integer := 0;
begin
  for l in select * from public.listings where status = 'open' and ends_at <= now() order by ends_at for update skip locked loop
    if l.bidder is not null then
      perform public._lock_players(array[l.seller, l.bidder]);
      perform public._give_card(l.bidder, l.place_id);
      update public.players set ecus = ecus + floor(l.current_bid * 0.95)::integer where user_id = l.seller;
      update public.listings set status = 'sold', closed_at = now() where id = l.id;
    else
      perform public._give_card(l.seller, l.place_id);
      update public.listings set status = 'unsold', closed_at = now() where id = l.id;
    end if;
    n := n + 1;
  end loop;
  return n;
end $$;

create or replace function public.create_listing(p_place text, p_start integer, p_buyout integer default null, p_hours integer default 24) returns bigint
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo(); lid bigint;
begin
  if p_hours not in (1, 24, 72) then raise exception 'durée : 1, 24 ou 72 heures' using errcode = 'P0001'; end if;
  if p_start < 1 or p_start > 1000000 then raise exception 'prix de départ entre 1 et 1 000 000 écus' using errcode = 'P0001'; end if;
  if p_buyout is not null and p_buyout <= p_start then raise exception 'l''achat immédiat doit dépasser le prix de départ' using errcode = 'P0001'; end if;
  if (select count(*) from public.listings where seller = uid and status = 'open') >= 20 then
    raise exception '20 ventes en cours au maximum' using errcode = 'P0001';
  end if;
  perform public._lock_players(array[uid]);
  perform public._take_card(uid, p_place);
  insert into public.listings (seller, place_id, start_price, buyout, ends_at)
  values (uid, p_place, p_start, p_buyout, now() + make_interval(hours => p_hours)) returning id into lid;
  return lid;
end $$;

create or replace function public.place_bid(p_id bigint, p_amount integer) returns jsonb
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo(); l public.listings; bal integer; owed integer;
begin
  select * into l from public.listings where id = p_id for update;
  if not found or l.status <> 'open' or l.ends_at <= now() then raise exception 'cette vente est terminée' using errcode = 'P0001'; end if;
  if l.seller = uid then raise exception 'vous ne pouvez pas enchérir sur votre vente' using errcode = 'P0001'; end if;
  if l.bidder = uid then raise exception 'vous êtes déjà le meilleur enchérisseur' using errcode = 'P0001'; end if;
  if p_amount < public._min_bid(l) then raise exception 'enchère minimale : % écus', public._min_bid(l) using errcode = 'P0001'; end if;
  if l.buyout is not null and p_amount >= l.buyout then raise exception 'utilisez l''achat immédiat' using errcode = 'P0001'; end if;
  perform public._lock_players(array[uid, l.bidder]);
  select ecus into bal from public.players where user_id = uid;
  if bal < p_amount then raise exception 'solde insuffisant (% écus)', bal using errcode = 'P0001'; end if;
  update public.players set ecus = ecus - p_amount where user_id = uid;
  if l.bidder is not null then update public.players set ecus = ecus + l.current_bid where user_id = l.bidder; end if;
  update public.listings set current_bid = p_amount, bidder = uid, bids = bids + 1,
         ends_at = greatest(ends_at, now() + interval '2 minutes')        -- anti-dernière seconde
   where id = p_id returning * into l;
  insert into public.listing_bids (listing_id, bidder, amount) values (p_id, uid, p_amount);
  return jsonb_build_object('current_bid', l.current_bid, 'ends_at', l.ends_at, 'ecus', bal - p_amount);
end $$;

create or replace function public.buy_now(p_id bigint) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo(); l public.listings; bal integer;
begin
  select * into l from public.listings where id = p_id for update;
  if not found or l.status <> 'open' or l.ends_at <= now() then raise exception 'cette vente est terminée' using errcode = 'P0001'; end if;
  if l.buyout is null then raise exception 'pas d''achat immédiat sur cette vente' using errcode = 'P0001'; end if;
  if l.seller = uid then raise exception 'c''est votre vente' using errcode = 'P0001'; end if;
  perform public._lock_players(array[uid, l.seller, l.bidder]);
  select ecus into bal from public.players where user_id = uid;
  if l.bidder = uid then bal := bal + l.current_bid; end if;            -- sa propre enchère est déduite
  if bal < l.buyout then raise exception 'solde insuffisant' using errcode = 'P0001'; end if;
  if l.bidder is not null then update public.players set ecus = ecus + l.current_bid where user_id = l.bidder; end if;
  update public.players set ecus = ecus - l.buyout where user_id = uid;
  update public.players set ecus = ecus + floor(l.buyout * 0.95)::integer where user_id = l.seller;
  perform public._give_card(uid, l.place_id);
  update public.listings set status = 'sold', current_bid = l.buyout, bidder = uid, closed_at = now() where id = p_id;
  return 'acheté';
end $$;

create or replace function public.cancel_listing(p_id bigint) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._me(); l public.listings;
begin
  select * into l from public.listings where id = p_id for update;
  if not found or l.seller <> uid or l.status <> 'open' then raise exception 'vente introuvable' using errcode = 'P0001'; end if;
  if l.bidder is not null then raise exception 'impossible d''annuler : il y a déjà une enchère' using errcode = 'P0001'; end if;
  perform public._give_card(uid, l.place_id);
  update public.listings set status = 'cancelled', closed_at = now() where id = p_id;
  return 'annulé';
end $$;

-- Ventes en cours (les 300 qui se terminent le plus tôt) + mes ventes et enchères récentes
create or replace function public.market_list() returns jsonb
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._me();
begin
  perform public.settle_auctions();
  return jsonb_build_object(
    'server_now', now(),
    'ecus', (select ecus from public.players where user_id = uid),
    'open', coalesce((select jsonb_agg(jsonb_build_object('id', l.id, 'place', l.place_id, 'seller', public._pseudo(l.seller), 'mine', l.seller = uid,
               'start', l.start_price, 'buyout', l.buyout, 'bid', l.current_bid, 'leading', l.bidder = uid, 'bids', l.bids,
               'min', public._min_bid(l), 'ends_at', l.ends_at) order by l.ends_at)
             from (select * from public.listings where status = 'open' order by ends_at limit 300) l), '[]'),
    'history', coalesce((select jsonb_agg(jsonb_build_object('id', l.id, 'place', l.place_id, 'status', l.status, 'mine', l.seller = uid,
               'won', l.bidder = uid and l.status = 'sold', 'price', l.current_bid, 'closed_at', l.closed_at) order by l.closed_at desc)
             from (select * from public.listings where status <> 'open' and (seller = uid or bidder = uid) order by closed_at desc limit 40) l), '[]'));
end $$;

-- ---------- Classement ----------
create or replace function public.leaderboard(p_kind text default 'cards') returns jsonb
language plpgsql security definer set search_path = public stable as $$
declare uid uuid := public._me();
begin
  if p_kind not in ('cards', 'legend', 'visits', 'wins') then raise exception 'classement inconnu' using errcode = 'P0001'; end if;
  return (with scores as (
      select p.user_id, p.pseudo,
        case p_kind
          when 'cards'  then (select count(*) from public.user_cards c where c.user_id = p.user_id)
          when 'legend' then (select count(*) from public.user_cards c join public.places pl on pl.id = c.place_id where c.user_id = p.user_id and pl.tier = 4)
          when 'visits' then (select count(*) from public.user_cards c where c.user_id = p.user_id and c.visits > 0)
          else (select count(*) from public.battles b where b.winner = p.user_id)
        end as v
      from public.profiles p),
    ranked as (select user_id, pseudo, v, rank() over (order by v desc) r from scores)
    select jsonb_build_object(
      'top', coalesce((select jsonb_agg(jsonb_build_object('rank', r, 'pseudo', pseudo, 'value', v, 'me', user_id = uid) order by r, lower(pseudo)) from (select * from ranked order by r, lower(pseudo) limit 100) t), '[]'),
      'me', (select jsonb_build_object('rank', r, 'value', v) from ranked where user_id = uid),
      'players', (select count(*) from ranked)));
end $$;

-- ---------- Guildes ----------
create table if not exists public.guilds (
  id          bigserial primary key,
  name        text not null check (char_length(name) between 3 and 30),
  tag         text not null check (tag ~ '^[A-Z0-9]{2,5}$'),
  description text not null default '' check (char_length(description) <= 200),
  created_at  timestamptz not null default now()
);
create unique index if not exists guilds_name_uq on public.guilds (lower(name));
create unique index if not exists guilds_tag_uq on public.guilds (tag);
create table if not exists public.guild_members (
  user_id   uuid primary key references auth.users (id) on delete cascade,   -- une seule guilde par joueur
  guild_id  bigint not null references public.guilds (id) on delete cascade,
  role      text not null default 'membre' check (role in ('chef', 'officier', 'membre')),
  joined_at timestamptz not null default now()
);
create index if not exists guild_members_guild_idx on public.guild_members (guild_id);
create table if not exists public.guild_messages (
  id         bigserial primary key,
  guild_id   bigint not null references public.guilds (id) on delete cascade,
  sender     uuid not null references auth.users (id) on delete cascade,
  body       text not null check (char_length(body) between 1 and 500),
  created_at timestamptz not null default now()
);
create index if not exists guild_messages_idx on public.guild_messages (guild_id, id desc);

create or replace function public._my_guild(u uuid) returns public.guild_members language sql stable as $$
  select * from public.guild_members where user_id = u
$$;

create or replace function public.guild_create(p_name text, p_tag text, p_description text default '') returns bigint
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo(); gid bigint;
begin
  if exists (select 1 from public.guild_members where user_id = uid) then raise exception 'quittez d''abord votre guilde' using errcode = 'P0001'; end if;
  if exists (select 1 from public.guilds where lower(name) = lower(btrim(p_name)) or tag = upper(btrim(p_tag))) then
    raise exception 'nom ou sigle déjà pris' using errcode = 'P0001';
  end if;
  insert into public.guilds (name, tag, description) values (btrim(p_name), upper(btrim(p_tag)), coalesce(p_description, '')) returning id into gid;
  insert into public.guild_members (user_id, guild_id, role) values (uid, gid, 'chef');
  return gid;
end $$;

create or replace function public.guild_join(p_id bigint) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo();
begin
  perform 1 from public.guilds where id = p_id for update;
  if not found then raise exception 'guilde introuvable' using errcode = 'P0001'; end if;
  if exists (select 1 from public.guild_members where user_id = uid) then raise exception 'quittez d''abord votre guilde' using errcode = 'P0001'; end if;
  if (select count(*) from public.guild_members where guild_id = p_id) >= 20 then raise exception 'guilde complète (20 membres)' using errcode = 'P0001'; end if;
  insert into public.guild_members (user_id, guild_id) values (uid, p_id);
  return 'bienvenue';
end $$;

create or replace function public.guild_leave() returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._me(); m public.guild_members; heir uuid;
begin
  select * into m from public.guild_members where user_id = uid for update;
  if not found then raise exception 'vous n''êtes dans aucune guilde' using errcode = 'P0001'; end if;
  delete from public.guild_members where user_id = uid;
  if m.role = 'chef' then
    select user_id into heir from public.guild_members where guild_id = m.guild_id
     order by case role when 'officier' then 0 else 1 end, joined_at limit 1;
    if heir is null then delete from public.guilds where id = m.guild_id; return 'guilde dissoute'; end if;
    update public.guild_members set role = 'chef' where user_id = heir;
  end if;
  return 'guilde quittée';
end $$;

create or replace function public.guild_kick(p_user uuid) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._me(); me public.guild_members := public._my_guild(uid); t public.guild_members := public._my_guild(p_user);
begin
  if me.user_id is null or t.user_id is null or me.guild_id <> t.guild_id or p_user = uid then raise exception 'action impossible' using errcode = 'P0001'; end if;
  if not (me.role = 'chef' or (me.role = 'officier' and t.role = 'membre')) then raise exception 'droits insuffisants' using errcode = 'P0001'; end if;
  delete from public.guild_members where user_id = p_user;
  return 'exclu';
end $$;

create or replace function public.guild_set_role(p_user uuid, p_role text) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._me(); me public.guild_members := public._my_guild(uid); t public.guild_members := public._my_guild(p_user);
begin
  if me.user_id is null or me.role <> 'chef' or t.user_id is null or t.guild_id <> me.guild_id or p_user = uid then raise exception 'réservé au chef' using errcode = 'P0001'; end if;
  if p_role not in ('chef', 'officier', 'membre') then raise exception 'rôle inconnu' using errcode = 'P0001'; end if;
  if p_role = 'chef' then update public.guild_members set role = 'officier' where user_id = uid; end if;
  update public.guild_members set role = p_role where user_id = p_user;
  return 'rôle mis à jour';
end $$;

create or replace function public.guild_send(p_body text) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo(); me public.guild_members := public._my_guild(uid);
begin
  if me.user_id is null then raise exception 'vous n''êtes dans aucune guilde' using errcode = 'P0001'; end if;
  if (select count(*) from public.guild_messages where sender = uid and created_at > now() - interval '1 minute') >= 20 then
    raise exception 'trop de messages, patientez une minute' using errcode = 'P0001';
  end if;
  insert into public.guild_messages (guild_id, sender, body) values (me.guild_id, uid, btrim(p_body));
  return 'envoyé';
end $$;

-- Ma guilde : membres, couverture de Paris, objectif de la semaine (50 visites), discussion
create or replace function public.guild_info() returns jsonb
language plpgsql security definer set search_path = public stable as $$
declare uid uuid := public._me(); me public.guild_members := public._my_guild(uid); g public.guilds; wk date := date_trunc('week', (now() at time zone 'Europe/Paris'))::date;
begin
  if me.user_id is null then return null; end if;
  select * into g from public.guilds where id = me.guild_id;
  return jsonb_build_object(
    'id', g.id, 'name', g.name, 'tag', g.tag, 'description', g.description, 'my_role', me.role,
    'members', (select jsonb_agg(jsonb_build_object('id', m.user_id, 'pseudo', public._pseudo(m.user_id), 'role', m.role,
                   'cards', (select count(*) from public.user_cards c where c.user_id = m.user_id)) order by case m.role when 'chef' then 0 when 'officier' then 1 else 2 end, m.joined_at)
                from public.guild_members m where m.guild_id = g.id),
    'coverage', (select count(distinct c.place_id) from public.user_cards c join public.guild_members m on m.user_id = c.user_id where m.guild_id = g.id),
    'total', (select count(*) from public.places),
    'week_visits', (select count(*) from public.visit_log v join public.guild_members m on m.user_id = v.user_id where m.guild_id = g.id and v.day >= wk),
    'week_goal', 50,
    'messages', coalesce((select jsonb_agg(jsonb_build_object('id', x.id, 'pseudo', public._pseudo(x.sender), 'mine', x.sender = uid, 'body', x.body, 'at', x.created_at) order by x.id)
                 from (select * from public.guild_messages where guild_id = g.id order by id desc limit 60) x), '[]'));
end $$;

create or replace function public.guild_search(p_q text default '') returns jsonb
language sql security definer set search_path = public stable as $$
  select coalesce(jsonb_agg(x), '[]') from (
    select jsonb_build_object('id', g.id, 'name', g.name, 'tag', g.tag, 'description', g.description,
             'members', (select count(*) from public.guild_members m where m.guild_id = g.id)) x
      from public.guilds g
     where p_q = '' or lower(g.name) like '%' || lower(p_q) || '%' or g.tag = upper(p_q)
     order by (select count(*) from public.guild_members m where m.guild_id = g.id) desc, g.created_at
     limit 50) s
$$;

-- ---------- Batailles entre amis ----------
-- Chaque joueur pose un deck de défense de 5 cartes. Un ami l'attaque avec son deck ; le serveur tire 5 terrains,
-- calcule les puissances à partir des collections réelles et enregistre le résultat.
create table if not exists public.defense_decks (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  cards      text[] not null check (cardinality(cards) = 5),
  updated_at timestamptz not null default now()
);
create table if not exists public.battles (
  id           bigserial primary key,
  attacker     uuid not null references auth.users (id) on delete cascade,
  defender     uuid not null references auth.users (id) on delete cascade,
  terrains     text[] not null,
  rounds       jsonb not null,
  attacker_won integer not null,
  winner       uuid,
  created_at   timestamptz not null default now()
);
create index if not exists battles_att_idx on public.battles (attacker, created_at desc);
create index if not exists battles_def_idx on public.battles (defender, created_at desc);
create index if not exists battles_winner_idx on public.battles (winner);

-- Puissance : 10 + 15 par cran de rareté + 6 par niveau au-delà du premier + 8 si visitée + 2 par doublon (4 max), +30 % sur son terrain.
create or replace function public._card_power(u uuid, pid text, terrain text) returns integer language sql stable as $$
  select coalesce((select round((10 + pl.tier * 15 + (c.level - 1) * 6 + case when c.visits > 0 then 8 else 0 end + least(c.copies - 1, 4) * 2)
                         * case when pl.family = terrain then 1.3 else 1 end)::integer
                   from public.user_cards c join public.places pl on pl.id = c.place_id where c.user_id = u and c.place_id = pid), 0)
$$;

create or replace function public._check_deck(u uuid, cards text[]) returns void language plpgsql stable as $$
begin
  if cardinality(cards) <> 5 or (select count(distinct x) from unnest(cards) x) <> 5 then raise exception 'il faut 5 cartes différentes' using errcode = 'P0001'; end if;
  if not public._owns_all(u, cards) then raise exception 'ce deck contient des cartes que vous ne possédez pas' using errcode = 'P0001'; end if;
end $$;

create or replace function public.set_defense(p_cards text[]) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo();
begin
  perform public._check_deck(uid, p_cards);
  insert into public.defense_decks (user_id, cards) values (uid, p_cards)
  on conflict (user_id) do update set cards = excluded.cards, updated_at = now();
  return 'défense enregistrée';
end $$;

create or replace function public.challenge(p_friend uuid, p_cards text[]) returns jsonb
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._need_pseudo(); d public.defense_decks; fams text[]; terr text[] := '{}'; rounds jsonb := '[]';
        i integer; a integer; b integer; won integer := 0; win boolean; bid bigint;
begin
  if not public._are_friends(uid, p_friend) then raise exception 'batailles réservées à vos amis' using errcode = 'P0001'; end if;
  select * into d from public.defense_decks where user_id = p_friend;
  if not found then raise exception 'votre ami n''a pas encore de deck de défense' using errcode = 'P0001'; end if;
  perform public._check_deck(uid, p_cards);
  if (select count(*) from public.battles where attacker = uid and created_at > now() - interval '1 day') >= 30 then
    raise exception '30 batailles par jour au maximum' using errcode = 'P0001';
  end if;
  select array_agg(distinct family) into fams from public.places where family <> '';
  for i in 1..5 loop terr := terr || fams[1 + floor(random() * cardinality(fams))::integer]; end loop;
  for i in 1..5 loop
    a := public._card_power(uid, p_cards[i], terr[i]);
    b := public._card_power(p_friend, d.cards[i], terr[i]);      -- une carte vendue depuis compte pour 0
    win := a > b or (a = b and random() < 0.5);
    if win then won := won + 1; end if;
    rounds := rounds || jsonb_build_object('terrain', terr[i], 'me', p_cards[i], 'op', d.cards[i], 'a', a, 'b', b, 'win', win);
  end loop;
  insert into public.battles (attacker, defender, terrains, rounds, attacker_won, winner)
  values (uid, p_friend, terr, rounds, won, case when won >= 3 then uid else p_friend end) returning id into bid;
  return jsonb_build_object('id', bid, 'rounds', rounds, 'won', won, 'victory', won >= 3, 'opponent', public._pseudo(p_friend));
end $$;

create or replace function public.battle_history() returns jsonb
language plpgsql security definer set search_path = public stable as $$
declare uid uuid := public._me();
begin
  return jsonb_build_object(
    'defense', (select cards from public.defense_decks where user_id = uid),
    'wins', (select count(*) from public.battles where winner = uid),
    'losses', (select count(*) from public.battles where (attacker = uid or defender = uid) and winner <> uid),
    'last', coalesce((select jsonb_agg(jsonb_build_object('id', b.id, 'attack', b.attacker = uid,
               'opponent', public._pseudo(case when b.attacker = uid then b.defender else b.attacker end),
               'victory', b.winner = uid, 'score', case when b.attacker = uid then b.attacker_won else 5 - b.attacker_won end, 'at', b.created_at) order by b.created_at desc)
             from (select * from public.battles where attacker = uid or defender = uid order by created_at desc limit 20) b), '[]'));
end $$;

-- ---------- Signalements ----------
create table if not exists public.reports (
  id          bigserial primary key,
  reporter    uuid not null references auth.users (id) on delete cascade,
  target      uuid not null references auth.users (id) on delete cascade,
  message_id  bigint,
  reason      text not null check (char_length(reason) between 1 and 300),
  created_at  timestamptz not null default now()
);
create or replace function public.report_user(p_target uuid, p_reason text, p_message bigint default null) returns text
language plpgsql security definer set search_path = public as $$
declare uid uuid := public._me();
begin
  if (select count(*) from public.reports where reporter = uid and created_at > now() - interval '1 day') >= 10 then
    raise exception 'trop de signalements aujourd''hui' using errcode = 'P0001';
  end if;
  insert into public.reports (reporter, target, message_id, reason) values (uid, p_target, p_message, btrim(p_reason));
  return 'signalement envoyé';
end $$;

-- ---------- Sécurité ----------
alter table public.profiles       enable row level security;
alter table public.friends        enable row level security;
alter table public.blocks         enable row level security;
alter table public.messages       enable row level security;
alter table public.trades         enable row level security;
alter table public.listings       enable row level security;
alter table public.listing_bids   enable row level security;
alter table public.guilds         enable row level security;
alter table public.guild_members  enable row level security;
alter table public.guild_messages enable row level security;
alter table public.defense_decks  enable row level security;
alter table public.battles        enable row level security;
alter table public.reports        enable row level security;

drop policy if exists "profils publics" on public.profiles;          create policy "profils publics" on public.profiles for select using (true);
drop policy if exists "mes amitiés" on public.friends;               create policy "mes amitiés" on public.friends for select using (auth.uid() in (user_a, user_b));
drop policy if exists "mes blocages" on public.blocks;               create policy "mes blocages" on public.blocks for select using (auth.uid() = blocker);
drop policy if exists "mes messages" on public.messages;             create policy "mes messages" on public.messages for select using (auth.uid() in (sender, recipient));
drop policy if exists "mes échanges" on public.trades;               create policy "mes échanges" on public.trades for select using (auth.uid() in (from_user, to_user));
drop policy if exists "ventes publiques" on public.listings;         create policy "ventes publiques" on public.listings for select using (true);
drop policy if exists "enchères publiques" on public.listing_bids;   create policy "enchères publiques" on public.listing_bids for select using (true);
drop policy if exists "guildes publiques" on public.guilds;          create policy "guildes publiques" on public.guilds for select using (true);
drop policy if exists "membres publics" on public.guild_members;     create policy "membres publics" on public.guild_members for select using (true);
drop policy if exists "discussion de ma guilde" on public.guild_messages;
create policy "discussion de ma guilde" on public.guild_messages for select using (guild_id = (select guild_id from public.guild_members where user_id = auth.uid()));
drop policy if exists "decks publics" on public.defense_decks;       create policy "decks publics" on public.defense_decks for select using (true);
drop policy if exists "mes batailles" on public.battles;             create policy "mes batailles" on public.battles for select using (auth.uid() in (attacker, defender));
-- reports : aucune lecture pour les joueurs

revoke insert, update, delete, truncate on public.profiles, public.friends, public.blocks, public.messages, public.trades, public.listings,
  public.listing_bids, public.guilds, public.guild_members, public.guild_messages, public.defense_decks, public.battles, public.reports
  from anon, authenticated;

-- Fonctions internes : jamais appelables directement
revoke execute on function public._me(), public._ensure_player(uuid), public._take_card(uuid, text), public._give_card(uuid, text),
  public._lock_players(uuid[]), public._pseudo(uuid), public._need_pseudo(), public._are_friends(uuid, uuid), public._blocked(uuid, uuid),
  public._find_user(text), public._owns_all(uuid, text[]), public._min_bid(public.listings), public._my_guild(uuid),
  public._card_power(uuid, text, text), public._check_deck(uuid, text[]) from public, anon, authenticated;

-- Fonctions publiques : réservées aux joueurs connectés
do $$
declare f text;
begin
  foreach f in array array[
    'set_pseudo(text)', 'set_showcase(text[])', 'my_profile()',
    'friend_request(text)', 'friend_respond(uuid, boolean)', 'friend_remove(uuid)', 'block_user(uuid, boolean)', 'friends_list()', 'friend_cards(uuid)',
    'send_message(uuid, text, text)', 'dm_thread(uuid, bigint)', 'conversations()',
    'propose_trade(uuid, text[], text[])', 'respond_trade(bigint, boolean)', 'cancel_trade(bigint)', 'my_trades()',
    'settle_auctions()', 'create_listing(text, integer, integer, integer)', 'place_bid(bigint, integer)', 'buy_now(bigint)', 'cancel_listing(bigint)', 'market_list()',
    'leaderboard(text)',
    'guild_create(text, text, text)', 'guild_join(bigint)', 'guild_leave()', 'guild_kick(uuid)', 'guild_set_role(uuid, text)', 'guild_send(text)', 'guild_info()', 'guild_search(text)',
    'set_defense(text[])', 'challenge(uuid, text[])', 'battle_history()',
    'report_user(uuid, text, bigint)'] loop
    execute format('revoke execute on function public.%s from public, anon', f);
    execute format('grant execute on function public.%s to authenticated', f);
  end loop;
end $$;

-- Messages en direct (Supabase Realtime) et clôture automatique des enchères chaque minute (pg_cron), si disponibles
do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    begin alter publication supabase_realtime add table public.messages; exception when duplicate_object then null; end;
    begin alter publication supabase_realtime add table public.guild_messages; exception when duplicate_object then null; end;
  end if;
  if exists (select 1 from pg_extension where extname = 'pg_cron') then
    perform cron.schedule('parisquest-encheres', '* * * * *', 'select public.settle_auctions()');
  end if;
end $$;
