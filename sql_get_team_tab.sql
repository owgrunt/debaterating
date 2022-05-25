SELECT
   tp.team_id,
   sum(tp.score) as team_score,
   (
        SELECT sum(rating_change)
        FROM speeches sp
        WHERE t.speaker_one_id = sp.speaker_id
        AND tp.tournament_id = 1
   ),
   s1.first_name AS s1_first_name,
   s2.first_name AS s2_first_name,
   s1.last_name AS s1_last_name,
   s2.last_name AS s2_last_name,
   s1.id AS s1_id,
   s2.id AS s2_id
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
WHERE
    tp.tournament_id = 1
AND
    r.stage != "E"
GROUP BY
    tp.team_id
ORDER BY
    team_score DESC;