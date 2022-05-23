-- INSERT INTO speakers (first_name, last_name, middle_name) VALUES ("Артем", "Самарский", "Сергеевич");
-- INSERT INTO speakers (first_name, last_name, middle_name) VALUES ("Свинг", "Свингов", "Свингович");
-- ALTER TABLE speakers ADD internal_id INTEGER NOT NULL DEFAULT 0;
-- DROP TABLE team_performances;
-- DELETE FROM speakers;

SELECT speaker_id, avg(score) AS average_score
FROM speeches
WHERE tournament_id = 1
GROUP BY speaker_id
HAVING average_score IN
    (
        SELECT avg(score) AS average_score
        FROM speeches
        GROUP BY speaker_id
        ORDER BY average_score DESC
        LIMIT 1
    );