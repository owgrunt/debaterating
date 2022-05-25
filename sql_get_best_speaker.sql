SELECT speaker_id, avg(score) AS average_score
FROM speeches
WHERE tournament_id = xxxxxx
GROUP BY speaker_id
HAVING average_score IN
    (
        SELECT avg(score) AS average_score
        FROM speeches
        WHERE tournament_id = xxxxxx
        GROUP BY speaker_id
        ORDER BY average_score DESC
        LIMIT 1
    );

SELECT speeches.speaker_id, avg(speeches.score) AS average_score, speakers.first_name, speakers.last_name
FROM speeches
INNER JOIN speakers ON speeches.speaker_id = speakers.id
WHERE tournament_id = {id}
GROUP BY speaker_id