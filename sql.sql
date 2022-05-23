-- INSERT INTO speakers (first_name, last_name, middle_name) VALUES ("Артем", "Самарский", "Сергеевич");
-- INSERT INTO speakers (first_name, last_name, middle_name) VALUES ("Свинг", "Свингов", "Свингович");
-- ALTER TABLE speakers ADD internal_id INTEGER NOT NULL DEFAULT 0;
-- DROP TABLE team_performances;
-- DELETE FROM speakers;

SELECT speaker_id, avg(score)
FROM speeches
WHERE
    score =
        (
            SELECT avg(score)
            FROM speeches
            GROUP BY speaker_id
            ORDER BY avg(score) DESC
            LIMIT 1
        )
GROUP BY speaker_id
ORDER BY avg(score) DESC;