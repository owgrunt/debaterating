SELECT
    tp.team_id,
    sum(tp.score) AS team_score,
    sp1.rating_change AS rating_change_one,
    sp2.rating_change AS rating_change_two,
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
INNER JOIN
    (
        SELECT sum(rating_change) AS rating_change, speaker_id
        FROM speeches
        WHERE tournament_id = xxxxxx
        GROUP BY speaker_id
    )
    sp1 ON
    t.speaker_one_id = sp1.speaker_id
INNER JOIN
    (
        SELECT sum(rating_change) AS rating_change, speaker_id
        FROM speeches
        WHERE tournament_id = xxxxxx
        GROUP BY speaker_id
    )
    sp2 ON
    t.speaker_two_id = sp2.speaker_id
WHERE
    tp.tournament_id = xxxxxx
AND
    r.stage != 'E'
GROUP BY
    tp.team_id, t.speaker_one_id, s1.first_name, s2.first_name, s1.last_name, s2.last_name, s1.id, s2.id, sp1.rating_change, sp2.rating_change
ORDER BY
    team_score DESC;