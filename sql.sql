-- INSERT INTO speakers (first_name, last_name, middle_name) VALUES ("Свинг", "Свингов", "Свингович");
-- ALTER TABLE speakers ADD internal_id INTEGER NOT NULL DEFAULT 0;
-- DROP TABLE team_performances;
-- DELETE FROM speakers;

SELECT
   *
FROM
   team_performances l
INNER JOIN teams r ON
    l.team_id = r.id;