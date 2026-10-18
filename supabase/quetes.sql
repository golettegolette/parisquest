-- =====================================================================
-- Parisquest : concept du 18/10/2026 (paquets + capture sur place + quêtes)
-- À exécuter APRÈS schema.sql, social.sql, direction_a.sql et places_arr.sql, puis exécuter quests_data.sql.
-- Peut être relancé sans risque.
--
--   * Paquets : un toutes les 10 minutes (2 minutes avec le Pass PariGo), 10 en réserve ; achats et Pack PariGo comme avant.
--   * Capture : n'importe quel lieu se capture sur place (visit_place de direction_a.sql, inchangée).
--   * Le paquet du jour « à découvrir » est retiré : les cartes à découvrir deviennent de vraies cartes.
--   * PQ : la monnaie du jeu (colonne players.ecus) ; gagnée avec les quêtes, achetée en Boutique, dépensée au Marché.
--   * Quêtes : claim_quest(id, palier) vérifie la progression sur le serveur et crédite les PQ une seule fois ;
--     quest_board() donne mes paliers, le nombre de joueurs par palier et le premier à avoir fini chaque quête ;
--     quest_leaders() classe les joueurs par paliers obtenus.
-- =====================================================================

-- ---------- Paquets : 10 minutes ----------
create or replace function public._pq_accrue(p public.players)
returns public.players language plpgsql as $$
declare k integer; per integer := case when p.pass_until > now() then 120 else 600 end;
begin
  if p.packs >= 10 then
    p.anchor := now();
    return p;
  end if;
  k := floor(extract(epoch from (now() - p.anchor)) / per)::integer;
  if k > 0 then
    p.packs := least(10, p.packs + k);
    if p.packs >= 10 then p.anchor := now();
    else p.anchor := p.anchor + make_interval(secs => k * per);
    end if;
  end if;
  return p;
end $$;

create or replace function public._pq_state_json(p public.players)
returns jsonb language sql stable security definer set search_path = public as $$
  select jsonb_build_object(
    'packs', p.packs, 'cap', 10,
    'next_at', case when p.packs >= 10 then null else p.anchor + make_interval(secs => case when p.pass_until > now() then 120 else 600 end) end,
    'ecus', p.ecus, 'pass_until', p.pass_until,
    'bonus_packs', p.bonus_packs, 'parigo_packs', p.parigo_packs,
    'parigo_free', (p.pass_until > now() and p.parigo_free_on is distinct from (now() at time zone 'Europe/Paris')::date),
    'score', public._pq_score(p.user_id),
    'server_now', now())
$$;

-- Les cartes « à découvrir » du paquet du jour deviennent de vraies cartes ; le paquet du jour est retiré.
update public.user_cards set pending = false where pending;
revoke execute on function public.open_daily_pack(double precision, double precision) from public, anon, authenticated;
grant execute on function public.open_pack(), public.open_parigo_pack(), public.pack_state() to authenticated;

-- ---------- Quêtes ----------
create table if not exists public.quests (
  id      text primary key,
  cat     text not null,
  name    text not null,
  title   text not null,
  rule    text not null check (rule in ('arr', 'rive', 'fam', 'kind', 'tier', 'tag', 'all', 'arrs', 'kinds', 'series')),
  val     text not null default '',
  total   integer not null,
  steps   integer[] not null,       -- seuils des paliers (nombre de cartes)
  rewards integer[] not null        -- PQ par palier
);
create table if not exists public.place_tags (
  place_id text not null references public.places (id) on delete cascade,
  tag      text not null,
  primary key (tag, place_id)
);
create index if not exists place_tags_place_idx on public.place_tags (place_id);
create table if not exists public.quest_claims (
  user_id    uuid not null references auth.users (id) on delete cascade,
  quest_id   text not null references public.quests (id) on delete cascade,
  step       smallint not null,     -- 1 = premier palier
  reward     integer not null,
  claimed_at timestamptz not null default now(),
  primary key (user_id, quest_id, step)
);
create index if not exists quest_claims_q_idx on public.quest_claims (quest_id, step, claimed_at);

alter table public.quests enable row level security;
alter table public.place_tags enable row level security;
alter table public.quest_claims enable row level security;
drop policy if exists "quêtes publiques" on public.quests;          create policy "quêtes publiques" on public.quests for select using (true);
drop policy if exists "étiquettes publiques" on public.place_tags;  create policy "étiquettes publiques" on public.place_tags for select using (true);
drop policy if exists "mes quêtes" on public.quest_claims;          create policy "mes quêtes" on public.quest_claims for select using (auth.uid() = user_id);
revoke insert, update, delete, truncate on public.quests, public.place_tags, public.quest_claims from anon, authenticated;
grant select on public.quests, public.place_tags, public.quest_claims to anon, authenticated;

-- Progression d'un joueur dans une quête (toutes les cartes comptent, quelle que soit leur origine)
create or replace function public._quest_progress(u uuid, q public.quests)
returns integer language plpgsql stable as $$
declare n integer;
begin
  if q.rule = 'arrs' then
    select count(distinct pl.arr) into n from public.user_cards c join public.places pl on pl.id = c.place_id where c.user_id = u and not c.pending and pl.arr is not null;
  elsif q.rule = 'kinds' then
    select count(distinct pl.kind) into n from public.user_cards c join public.places pl on pl.id = c.place_id where c.user_id = u and not c.pending;
  elsif q.rule = 'series' then
    select count(*) into n from (
      select t.tag from public.place_tags t left join public.user_cards c on c.place_id = t.place_id and c.user_id = u and not c.pending
      where t.tag like 'serie:%' group by t.tag having count(*) = count(c.place_id)) s;
  elsif q.rule = 'tag' then
    select count(*) into n from public.place_tags t join public.user_cards c on c.place_id = t.place_id and c.user_id = u and not c.pending where t.tag = q.val;
  else
    select count(*) into n from public.user_cards c join public.places pl on pl.id = c.place_id
    where c.user_id = u and not c.pending and (
      q.rule = 'all'
      or (q.rule = 'arr' and pl.arr = q.val::smallint)
      or (q.rule = 'rive' and pl.arr is not null and (pl.arr = any(array[5, 6, 7, 13, 14, 15]::smallint[])) = (q.val = 'g'))
      or (q.rule = 'fam' and pl.family = q.val)
      or (q.rule = 'kind' and pl.kind = q.val)
      or (q.rule = 'tier' and pl.tier = q.val::smallint));
  end if;
  return coalesce(n, 0);
end $$;

-- Récupère la récompense d'un palier (une seule fois). Vérification complète sur le serveur.
create or replace function public.claim_quest(p_quest text, p_step integer)
returns jsonb language plpgsql security definer set search_path = public as $$
declare uid uuid := public._me(); q public.quests; have integer; ok boolean; s integer; got integer := 0;
begin
  perform public._ensure_player(uid);
  perform 1 from public.players where user_id = uid for update;          -- une réclamation à la fois par joueur
  select * into q from public.quests where id = p_quest;
  if not found then raise exception 'quête inconnue' using errcode = 'P0001'; end if;
  if p_step < 1 or p_step > cardinality(q.steps) then raise exception 'palier inconnu' using errcode = 'P0001'; end if;
  have := public._quest_progress(uid, q);
  if have < q.steps[p_step] then raise exception 'pas encore : % sur %', have, q.steps[p_step] using errcode = 'P0001'; end if;
  -- les paliers précédents sont accordés en même temps s'ils n'ont pas été réclamés
  for s in 1..p_step loop
    insert into public.quest_claims (user_id, quest_id, step, reward) values (uid, q.id, s, q.rewards[s])
      on conflict do nothing returning true into ok;
    if ok then got := got + q.rewards[s]; end if;
    ok := null;
  end loop;
  if got > 0 then update public.players set ecus = ecus + got where user_id = uid; end if;
  return jsonb_build_object('quest', q.id, 'step', p_step, 'reward', got, 'ecus', (select ecus from public.players where user_id = uid),
                            'first', p_step = cardinality(q.steps) and (select count(*) from public.quest_claims where quest_id = q.id and step = p_step) = 1);
end $$;

-- Tableau des quêtes : mes paliers, nombre de joueurs par palier, premier à avoir terminé chaque quête
create or replace function public.quest_board()
returns jsonb language plpgsql security definer set search_path = public stable as $$
declare uid uuid := public._me();
begin
  return jsonb_build_object(
    'mine', coalesce((select jsonb_object_agg(quest_id, s) from (select quest_id, max(step) s from public.quest_claims where user_id = uid group by quest_id) m), '{}'),
    'counts', coalesce((select jsonb_object_agg(quest_id, cs) from (
                select quest_id, jsonb_agg(n order by step) cs from (select quest_id, step, count(*) n from public.quest_claims group by quest_id, step) a group by quest_id) b), '{}'),
    'first', coalesce((select jsonb_object_agg(x.quest_id, p.pseudo) from (
                select distinct on (c.quest_id) c.quest_id, c.user_id from public.quest_claims c join public.quests q on q.id = c.quest_id
                where c.step = cardinality(q.steps) order by c.quest_id, c.claimed_at) x join public.profiles p on p.user_id = x.user_id), '{}'),
    'players', (select count(*) from public.profiles));
end $$;

-- Titres d'un joueur : les quêtes terminées (dernier palier)
create or replace function public.my_titles()
returns jsonb language sql security definer set search_path = public stable as $$
  select coalesce(jsonb_agg(jsonb_build_object('quest', q.id, 'title', q.title, 'at', c.claimed_at,
           'first', c.claimed_at = (select min(c2.claimed_at) from public.quest_claims c2 where c2.quest_id = q.id and c2.step = c.step)) order by c.claimed_at), '[]')
  from public.quest_claims c join public.quests q on q.id = c.quest_id
  where c.user_id = auth.uid() and c.step = cardinality(q.steps)
$$;

-- Classement des quêtes : paliers obtenus, puis quêtes terminées
create or replace function public.quest_leaders()
returns jsonb language plpgsql security definer set search_path = public stable as $$
declare uid uuid := public._me();
begin
  return (with s as (
      select c.user_id, count(*) steps, count(*) filter (where c.step = cardinality(q.steps)) done
      from public.quest_claims c join public.quests q on q.id = c.quest_id group by c.user_id),
    r as (select s.*, p.pseudo, rank() over (order by s.steps desc, s.done desc) rk from s join public.profiles p on p.user_id = s.user_id)
    select jsonb_build_object(
      'top', coalesce((select jsonb_agg(jsonb_build_object('rank', rk, 'pseudo', pseudo, 'steps', steps, 'done', done, 'me', user_id = uid) order by rk, lower(pseudo)) from (select * from r order by rk limit 100) t), '[]'),
      'me', (select jsonb_build_object('rank', rk, 'steps', steps, 'done', done) from r where user_id = uid),
      'players', (select count(*) from r)));
end $$;

revoke execute on function public._quest_progress(uuid, public.quests) from public, anon, authenticated;
do $$
declare f text;
begin
  foreach f in array array['claim_quest(text, integer)', 'quest_board()', 'my_titles()', 'quest_leaders()'] loop
    execute format('revoke execute on function public.%s from public, anon', f);
    execute format('grant execute on function public.%s to authenticated', f);
  end loop;
end $$;
