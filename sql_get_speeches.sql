SELECT
    speeches.id,
    speeches.tournament_id,
    speeches.debate_id,
    speeches.score,
    speeches.rating_change,
    speeches.position,
    team_performances.score AS team_score,
    team_performances.side,
    debates.average_rating
FROM
   speeches
INNER JOIN team_performances
    ON speeches.debate_id = team_performances.debate_id
    AND team_performances.team_id IN
        (
            SELECT
                id
            FROM
                teams
            WHERE
                speeches.speaker_id = teams.speaker_one_id
            OR
                speeches.speaker_id = teams.speaker_two_id
        )
INNER JOIN debates
    ON speeches.debate_id = debates.id
WHERE
    speeches.speaker_id = xxxxxx
ORDER BY
    speeches.id DESC;