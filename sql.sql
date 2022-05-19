-- INSERT INTO speakers (first_name, last_name, middle_name) VALUES ("Свинг", "Свингов", "Свингович");
-- ALTER TABLE speakers ADD internal_id INTEGER NOT NULL DEFAULT 0;
-- DROP TABLE team_performances;
-- DELETE FROM speakers;

SELECT
   *
FROM
   team_performances
INNER JOIN teams ON
    team_performances.team_id = teams.id
WHERE
    team_performances.debate_id = 1;