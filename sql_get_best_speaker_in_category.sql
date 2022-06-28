SELECT
    speeches.speaker_id, avg(score) AS average_score
FROM speeches
INNER JOIN
    speakers_in_categories ON speeches.speaker_id = speakers_in_categories.speaker_id
WHERE
    speeches.tournament_id = xxxxxx
AND
    speakers_in_categories.category_id = yyyyyy
GROUP BY speeches.speaker_id
HAVING speeches.speaker_id IN
    (
        SELECT speeches.speaker_id
        FROM speeches
        INNER JOIN
            speakers_in_categories ON speeches.speaker_id = speakers_in_categories.speaker_id
        WHERE
            speeches.tournament_id = xxxxxx
        AND
            speakers_in_categories.category_id = yyyyyy
        GROUP BY speeches.speaker_id
        ORDER BY avg(score) DESC
        LIMIT 1
    )
;