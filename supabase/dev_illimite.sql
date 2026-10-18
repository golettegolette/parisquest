-- =====================================================================
-- Parisquest : règle TEMPORAIRE de développement (19/10/2026)
-- Les comptes listés dans dev_accounts ont des paquets illimités : à chaque action, le serveur
-- remet leur réserve à 10 paquets, au moins 3 Packs PariGo et au moins 1 Pack de chaque arrondissement.
-- Les autres joueurs ne sont pas concernés. Le compte est reconnu par le serveur (e-mail vérifié),
-- jamais par ce que dit le téléphone.
-- Pour arrêter : exécuter dev_illimite_off.sql (vide la liste ; la règle ne s'applique plus à personne).
-- À exécuter après quetes.sql et boutique_arr.sql. Peut être relancé sans risque.
-- =====================================================================

create table if not exists public.dev_accounts (
  user_id  uuid primary key references auth.users (id) on delete cascade,
  note     text,
  added_at timestamptz not null default now()
);
alter table public.dev_accounts enable row level security;     -- aucune lecture ni écriture depuis le jeu
revoke all on public.dev_accounts from anon, authenticated;

-- Compte du développeur (e-mail de connexion)
insert into public.dev_accounts (user_id, note)
  select id, 'développeur (paquets illimités, temporaire)' from auth.users where lower(email) = 'tim@goletto.net'
on conflict (user_id) do nothing;

-- Charge (et verrouille) la ligne du joueur connecté, après mise à jour du compteur ; recharge les comptes de développement
create or replace function public._pq_player()
returns public.players language plpgsql security definer set search_path = public as $$
declare uid uuid := auth.uid(); p public.players;
begin
  if uid is null then raise exception 'non connecté' using errcode = '28000'; end if;
  insert into public.players (user_id) values (uid) on conflict (user_id) do nothing;
  select * into p from public.players where user_id = uid for update;
  p := public._pq_accrue(p);
  if exists (select 1 from public.dev_accounts d where d.user_id = uid) then
    p.packs := 10; p.anchor := now();
    p.parigo_packs := greatest(p.parigo_packs, 3);
    p.arr_packs := coalesce(p.arr_packs, '{}'::jsonb) || (
      select jsonb_object_agg(a::text, greatest(coalesce((p.arr_packs ->> a::text)::integer, 0), 1)) from generate_series(1, 20) a);
    update public.players set packs = p.packs, anchor = p.anchor, parigo_packs = p.parigo_packs, arr_packs = p.arr_packs where user_id = uid;
  else
    update public.players set packs = p.packs, anchor = p.anchor where user_id = uid;
  end if;
  return p;
end $$;
revoke execute on function public._pq_player() from public, anon, authenticated;

-- Vérification : le compte reconnu
select u.email, coalesce(pr.pseudo, '(pas de pseudo)') as pseudo, d.note
from public.dev_accounts d join auth.users u on u.id = d.user_id left join public.profiles pr on pr.user_id = d.user_id;
