SELECT
   tp.team_id,
   sum(tp.score) as team_score,
   s1.first_name AS s1_first_name,
   s2.first_name AS s2_first_name,
   s1.last_name AS s1_last_name,
   s2.last_name AS s2_last_name
FROM
   team_performances tp
INNER JOIN teams t ON
    tp.team_id = t.id
INNER JOIN speakers AS s1 ON
    t.speaker_one_id = s1.id
INNER JOIN speakers AS s2 ON
    t.speaker_two_id = s2.id
INNER JOIN debates ON
    team_performances.debate_id = debates.id
WHERE
    team_performances.tournament_id = 1
ORDER BY
    team_score DESC;