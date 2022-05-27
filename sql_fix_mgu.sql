-- UPDATE tournament_participants SET role = "adjudicator" WHERE role = "ca" AND tournament_id = 1;
-- UPDATE tournament_participants SET role = "ca" WHERE internal_name = "Артем Посвежинский" AND tournament_id = 1;
-- UPDATE tournament_participants SET role = "ca" WHERE internal_name = "Роман Игнатенко" AND tournament_id = 1;
-- UPDATE tournament_participants SET role = "ca" WHERE internal_name = "Глеб Игнатьев" AND tournament_id = 1;
INSERT INTO achievements (tournament_id, speaker_id, type, name) VALUES (1, 91, "adjudicator", "лучший судья");
INSERT INTO achievements (tournament_id, speaker_id, type, name) VALUES (1, 92, "adjudicator", "лучший судья");
INSERT INTO achievements (tournament_id, speaker_id, type, name) VALUES (1, 90, "adjudicator", "лучший судья");