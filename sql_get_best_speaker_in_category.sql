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