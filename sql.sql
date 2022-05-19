-- INSERT INTO speakers (first_name, last_name, middle_name) VALUES ("Свинг", "Свингов", "Свингович");
-- ALTER TABLE speakers ADD internal_id INTEGER NOT NULL DEFAULT 0;
-- DROP TABLE team_performances;
-- DELETE FROM speakers;

SELECT
   team_performances.team_id,
   team_performances.score,
   speaker_one.rating + speaker_two.rating AS sum
FROM
   team_performances
INNER JOIN teams ON
    team_performances.team_id = teams.id
INNER JOIN speakers AS speaker_one ON
    teams.speaker_one_id = speaker_one.id
INNER JOIN speakers AS speaker_two ON
    teams.speaker_two_id = speaker_two.id
WHERE
    team_performances.debate_id = 1
ORDER BY
    team_performances.score DESC;