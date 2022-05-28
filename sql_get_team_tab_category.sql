SELECT
    tp.team_id,
    sum(tp.score) as team_score,
    sp.rating_change AS rating_change,
    s1.first_name AS s1_first_name,
    s2.first_name AS s2_first_name,
    s1.last_name AS s1_last_name,
    s2.last_name AS s2_last_name,
    s1.id AS s1_id,
    s2.id AS s2_id,
    s1c.category_id
FROM
   team_performances tp
LEFT JOIN teams t ON
    tp.team_id = t.id
LEFT JOIN debates d ON
    tp.debate_id = d.id
LEFT JOIN rounds r ON
    d.round_id = r.id
LEFT JOIN speakers AS s1 ON
    t.speaker_one_id = s1.id
LEFT JOIN speakers AS s2 ON
    t.speaker_two_id = s2.id
LEFT JOIN speakers_in_categories AS s1c ON
    t.speaker_one_id = s1c.speaker_id
LEFT JOIN speakers_in_categories AS s2c ON
    t.speaker_two_id = s2c.speaker_id
INNER JOIN
    (
        SELECT sum(rating_change) AS rating_change, speaker_id
        FROM speeches
        WHERE tournament_id = xxxxxx
        GROUP BY speaker_id
    )
    sp ON
    t.speaker_one_id = sp.speaker_id
WHERE
    tp.tournament_id = xxxxxx
AND
    r.stage != 'E'
AND
    s1c.category_id = yyyyyy
AND
    s2c.category_id = yyyyyy
GROUP BY
    tp.team_id, t.speaker_one_id, s1.first_name, s2.first_name, s1.last_name, s2.last_name, s1.id, s2.id, s1c.category_id
ORDER BY
    team_score DESC;