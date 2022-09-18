SELECT speaker_id, avg(score) AS average_score
FROM speeches
WHERE tournament_id = xxxxxx
GROUP BY speaker_id
HAVING avg(score) IN
    (
        SELECT avg(score)
        FROM speeches
        WHERE tournament_id = xxxxxx
        GROUP BY speaker_id
        ORDER BY avg(score) DESC
        LIMIT 1
    );