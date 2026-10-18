-- =====================================================================
-- Parisquest : Pack Arrondissement (19/10/2026)
-- 15 cartes tirées au hasard dans l'arrondissement choisi, avec les chances d'un paquet normal
-- (Commune 60 %, Peu commune 25 %, Rare 10 %, Épique 4 %, Légendaire 1 %) ; si une rareté manque dans
-- l'arrondissement, la plus proche. Vendu 2,49 € (crédité par le webhook de paiement, clé service_role).
-- À exécuter après quetes.sql. Peut être relancé sans risque.
-- =====================================================================

alter table public.players add column if not exists arr_packs jsonb not null default '{}'::jsonb;   -- {"5": 2} = 2 packs du 5e
alter table public.purchases add column if not exists arr smallint;

-- État du joueur renvoyé au jeu : on ajoute les packs d'arrondissement en stock
create or replace function public._pq_state_json(p public.players)
returns jsonb language sql stable security definer set search_path = public as $$
  select jsonb_build_object(
    'packs', p.packs, 'cap', 10,
    'next_at', case when p.packs >= 10 then null else p.anchor + make_interval(secs => case when p.pass_until > now() then 120 else 600 end) end,
    'ecus', p.ecus, 'pass_until', p.pass_until,
    'bonus_packs', p.bonus_packs, 'parigo_packs', p.parigo_packs,
    'parigo_free', (p.pass_until > now() and p.parigo_free_on is distinct from (now() at time zone 'Europe/Paris')::date),
    'arr_packs', coalesce(p.arr_packs, '{}'::jsonb),
    'score', public._pq_score(p.user_id),
    'server_now', now())
$$;

-- Ouvre un Pack Arrondissement en stock
create or replace function public.open_arr_pack(p_arr integer)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  p public.players; n integer; r double precision; t smallint; pid text; is_new boolean; drawn jsonb := '[]'::jsonb; i integer;
begin
  if p_arr is null or p_arr < 1 or p_arr > 20 then raise exception 'arrondissement inconnu' using errcode = 'P0001'; end if;
  p := public._pq_player();                                       -- joueur connecté, ligne verrouillée
  n := coalesce((p.arr_packs ->> p_arr::text)::integer, 0);
  if n < 1 then raise exception 'aucun pack de cet arrondissement' using errcode = 'P0001'; end if;
  p.arr_packs := case when n = 1 then p.arr_packs - p_arr::text else jsonb_set(p.arr_packs, array[p_arr::text], to_jsonb(n - 1)) end;

  for i in 1..15 loop
    r := random();
    t := case when r < 0.01 then 4 when r < 0.05 then 3 when r < 0.15 then 2 when r < 0.40 then 1 else 0 end;
    -- un lieu de l'arrondissement, de la rareté tirée ou, à défaut, de la plus proche
    select id, tier into pid, t from public.places where arr = p_arr order by abs(tier - t), random() limit 1;
    insert into public.user_cards (user_id, place_id) values (p.user_id, pid)
      on conflict (user_id, place_id) do update set copies = public.user_cards.copies + 1
      returning (xmax = 0) into is_new;
    drawn := drawn || jsonb_build_object('id', pid, 'tier', t, 'new', is_new);
    if not is_new then p.ecus := p.ecus + 5; end if;               -- doublon : +5 PQ
  end loop;

  update public.players set ecus = p.ecus, arr_packs = p.arr_packs where user_id = p.user_id;
  insert into public.pack_log (user_id, cards) values (p.user_id, jsonb_build_object('arr', p_arr, 'cards', drawn));
  return public._pq_state_json(p) || jsonb_build_object('cards', drawn);
end $$;

-- Crédit d'un achat (webhook de paiement uniquement). Idempotent : un même paiement ne crédite qu'une fois.
create or replace function public.credit_arr_pack(p_user uuid, p_ref text, p_arr integer, p_n integer default 1)
returns boolean language plpgsql security definer set search_path = public as $$
declare inserted boolean;
begin
  if p_arr is null or p_arr < 1 or p_arr > 20 or coalesce(p_n, 0) < 1 then raise exception 'achat invalide' using errcode = 'P0001'; end if;
  insert into public.purchases (ref, user_id, arr, packs) values (p_ref, p_user, p_arr, 0)
    on conflict (ref) do nothing returning true into inserted;
  if inserted is null then return false; end if;
  insert into public.players (user_id) values (p_user) on conflict (user_id) do nothing;
  update public.players
     set arr_packs = jsonb_set(coalesce(arr_packs, '{}'::jsonb), array[p_arr::text], to_jsonb(coalesce((arr_packs ->> p_arr::text)::integer, 0) + p_n))
   where user_id = p_user;
  return true;
end $$;

revoke execute on function public._pq_state_json(public.players) from public, anon, authenticated;
revoke execute on function public.open_arr_pack(integer) from public, anon;
grant execute on function public.open_arr_pack(integer) to authenticated;
revoke execute on function public.credit_arr_pack(uuid, text, integer, integer) from public, anon, authenticated;
grant execute on function public.credit_arr_pack(uuid, text, integer, integer) to service_role;
select 'pack arrondissement prêt' as ok;
