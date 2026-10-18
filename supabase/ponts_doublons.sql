-- Parisquest : ponts en double (généré par pipeline/ponts.py). On garde la version « rue » de chaque pont.
-- Les cartes déjà possédées en version « pont » sont reportées sur la version « rue », puis la version « pont » est retirée.
-- À exécuter une fois dans Supabase (SQL Editor), puis relancer quests_data.sql. Peut être relancé sans risque.
drop table if exists pg_temp.pont_map;
create temporary table pont_map (old_id text primary key, new_id text not null);
insert into pont_map values
  ('pont:Q1061959', 'rue:12506'),
  ('pont:Q1073098', 'rue:11358'),
  ('pont:Q1140060', 'rue:13628'),
  ('pont:Q1196667', 'rue:11933'),
  ('pont:Q1196676', 'rue:9761'),
  ('pont:Q1196688', 'rue:13534'),
  ('pont:Q1323635', 'rue:15082'),
  ('pont:Q1327827', 'rue:9719'),
  ('pont:Q1329076', 'rue:13648'),
  ('pont:Q1329141', 'rue:9076'),
  ('pont:Q1418458', 'rue:9033'),
  ('pont:Q1469250', 'rue:10339'),
  ('pont:Q1513866', 'rue:9284'),
  ('pont:Q1621256', 'rue:8902'),
  ('pont:Q1758497', 'rue:13339'),
  ('pont:Q1853517', 'rue:14952'),
  ('pont:Q18575822', 'rue:10619'),
  ('pont:Q2073308', 'rue:9030'),
  ('pont:Q2273701', 'rue:11121'),
  ('pont:Q2274186', 'rue:10189'),
  ('pont:Q2307670', 'rue:13832'),
  ('pont:Q2307685', 'rue:12438'),
  ('pont:Q2307722', 'rue:9128'),
  ('pont:Q2339845', 'rue:10619'),
  ('pont:Q2426843', 'rue:10896'),
  ('pont:Q290355', 'rue:9341'),
  ('pont:Q291093', 'rue:12263'),
  ('pont:Q30741087', 'rue:15187'),
  ('pont:Q335277', 'rue:12454'),
  ('pont:Q3368264', 'rue:15714'),
  ('pont:Q3368265', 'rue:15382'),
  ('pont:Q3368266', 'rue:15669'),
  ('pont:Q3368275', 'rue:15455'),
  ('pont:Q3368276', 'rue:15691'),
  ('pont:Q3368301', 'rue:15454'),
  ('pont:Q3368313', 'rue:15734'),
  ('pont:Q3390136', 'rue:14876'),
  ('pont:Q3396524', 'rue:15456'),
  ('pont:Q3396657', 'rue:12375'),
  ('pont:Q3397319', 'rue:15671'),
  ('pont:Q3397654', 'rue:15670'),
  ('pont:Q3397655', 'rue:15718'),
  ('pont:Q390418', 'rue:8871'),
  ('pont:Q513655', 'rue:13855'),
  ('pont:Q540781', 'rue:11334'),
  ('pont:Q589000', 'rue:9637'),
  ('pont:Q605912', 'rue:14969'),
  ('pont:Q644398', 'rue:10004'),
  ('pont:Q963509', 'rue:12089');
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
