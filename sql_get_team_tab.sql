SELECT
   tp.team_id,
   sum(tp.score) as team_score,
   s1.first_name AS s1_first_name,
   s2.first_name AS s2_first_name,
   s1.last_name AS s1_last_name,
   s2.last_name AS s2_last_name,
   s1.id AS s1_id,
   s2.id AS s2_id,
   s1c.category_id
FROM
   team_performances tp
INNER JOIN teams t ON
    tp.team_id = t.id
INNER JOIN debates d ON
    tp.debate_id = d.id
INNER JOIN rounds r ON
    d.round_id = r.id
INNER JOIN speakers AS s1 ON
    t.speaker_one_id = s1.id
INNER JOIN speakers AS s2 ON
    t.speaker_two_id = s2.id
INNER JOIN speakers_in_categories AS s1c ON
    t.speaker_one_id = s1c.id
INNER JOIN speakers_in_categories AS s2c ON
    t.speaker_two_id = s2c.id
WHERE
    tp.tournament_id = 1
AND
    r.stage != "E"
AND
    s1c.category_id = 0
AND
    s2c.category_id = 0
GROUP BY
    tp.team_id
ORDER BY
    team_score DESC;