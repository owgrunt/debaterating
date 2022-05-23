SELECT *
    -- speeches.speaker_id, avg(score) AS average_score
FROM speeches
INNER JOIN
    speakers_in_categories ON speeches.speaker_id = speakers_in_categories.speaker_id
WHERE
    speeches.tournament_id = 1
AND
    speakers_in_categories.category_id = 1
GROUP BY speeches.speaker_id
-- HAVING average_score IN
--     (
--         SELECT avg(score) AS average_score
--         FROM speeches
        -- WHERE
        --     speeches.tournament_id = 1
--         GROUP BY speaker_id
--         ORDER BY average_score DESC
--         LIMIT 1
--     )
;