SELECT
    tp.team_id,
    sum(tp.score) AS team_score,
    sum(sp.rating_change) AS rating_change,
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
INNER JOIN speeches sp ON
    t.speaker_one_id = sp.speaker_id
WHERE
    tp.tournament_id = xxxxxx
AND
    r.stage != 'E'
AND
    sp.tournament_id = xxxxxx
GROUP BY
    tp.team_id, t.speaker_one_id, s1.first_name, s2.first_name, s1.last_name, s2.last_name, s1.id, s2.id
ORDER BY
    team_score DESC;