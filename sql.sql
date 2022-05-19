-- INSERT INTO speakers (first_name, last_name, middle_name) VALUES ("Свинг", "Свингов", "Свингович");
-- ALTER TABLE speakers ADD internal_id INTEGER NOT NULL DEFAULT 0;
-- DROP TABLE team_performances;
-- DELETE FROM speakers;

SELECT
   team_performances.team_id,
   speaker_one_id,
   rating
FROM
   team_performances
INNER JOIN teams ON
    team_performances.team_id = teams.id
INNER JOIN speakers ON
    teams.speaker_one_id = speakers.id
INNER JOIN speakers ON
    teams.speaker_two_id = speakers.id
WHERE
    team_performances.debate_id = 1;