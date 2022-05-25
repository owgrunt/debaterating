SELECT
   team_performances.team_id,
   sum(tp.score) as team_score,
   team_performances.debate_id,
   teams.swing,
   teams.speaker_one_id AS speaker_one,
   teams.speaker_two_id AS speaker_two,
   speaker_one.rating AS speaker_one_rating,
   speaker_two.rating AS speaker_two_rating
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