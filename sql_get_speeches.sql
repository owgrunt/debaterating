SELECT
    speeches.id,
    speeches.tournament_id,
    speeches.debate_id,
    speeches.score,
    speeches.rating_change,
    speeches.position,
    team_performances.score AS team_score
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
WHERE
    speeches.speaker_id = 66
ORDER BY
    speeches.id ASC;