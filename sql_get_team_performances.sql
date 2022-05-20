SELECT
   team_performances.team_id,
   team_performances.score,
   team_performances.debate_id,
   teams.swing,
   teams.speaker_one_id AS speaker_one,
   teams.speaker_two_id AS speaker_two,
   speaker_one.rating AS speaker_one_rating,
   speaker_two.rating AS speaker_two_rating
FROM
   team_performances
INNER JOIN teams ON
    team_performances.team_id = teams.id
INNER JOIN speakers AS speaker_one ON
    teams.speaker_one_id = speaker_one.id
INNER JOIN speakers AS speaker_two ON
    teams.speaker_two_id = speaker_two.id
INNER JOIN debates ON
    team_performances.debate_id = debates.id
WHERE
    team_performances.tournament_id = xxxxxx
AND
    team_performances.debate_id = 1
AND
    debates.round_id = yyyyyy
ORDER BY
    team_performances.debate_id ASC;