-- Parisquest : fin de la règle temporaire de développement (paquets illimités).
-- Vide la liste des comptes de développement : plus personne n'a de paquets illimités.
-- Les paquets déjà en stock restent ; le compteur normal reprend (1 paquet toutes les 10 minutes).
delete from public.dev_accounts;
select count(*) as comptes_dev_restants from public.dev_accounts;
