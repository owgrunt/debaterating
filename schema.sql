-- CREATE TABLE users (
--     id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
--     username TEXT NOT NULL,
--     hash TEXT NOT NULL);
-- CREATE UNIQUE INDEX username ON users (username);

CREATE TABLE speakers (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    middle_name TEXT,
    society_id INTEGER,
    speaker_score NUMERIC NOT NULL DEFAULT 70,
    rating INTEGER NOT NULL DEFAULT 1500,
    shown INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (society_id) REFERENCES societies(id)
);
CREATE UNIQUE INDEX speaker_id ON speakers (id);
CREATE INDEX speaker_by_first_name ON speakers (first_name);
CREATE INDEX speaker_by_last_name ON speakers (last_name);
CREATE INDEX speaker_by_middle_name ON speakers (middle_name);

CREATE TABLE societies (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    name TEXT NOT NULL,
    short_name TEXT NOT NULL,
    city TEXT NOT NULL
);
CREATE UNIQUE INDEX society_id ON societies (id);

CREATE TABLE tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    name TEXT NOT NULL,
    short_name TEXT NOT NULL,
    internal_id INTEGER,
    slug TEXT,
    domain TEXT,
    date TEXT NOT NULL,
    type TEXT NOT NULL
);
CREATE UNIQUE INDEX tournament_id ON tournaments (id);

CREATE TABLE teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    tournament_id INTEGER NOT NULL,
    internal_id INTEGER,
    name TEXT NOT NULL,
    swing INTEGER NOT NULL DEFAULT 0,
    speaker_one_id INTEGER NOT NULL,
    speaker_two_id INTEGER NOT NULL,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id),
    FOREIGN KEY(speaker_one_id) REFERENCES speakers(id),
    FOREIGN KEY(speaker_two_id) REFERENCES speakers(id)
);
CREATE UNIQUE INDEX team_id ON teams (id);
CREATE INDEX team_internal_id ON teams (internal_id);
CREATE INDEX speaker_one_id ON teams (speaker_one_id);
CREATE INDEX speaker_two_id ON teams (speaker_two_id);

CREATE TABLE rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    tournament_id INTEGER NOT NULL,
    internal_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    short_name TEXT NOT NULL,
    seq INTEGER NOT NULL,
    break_category INTEGER,
    stage TEXT NOT NULL,
    motion TEXT,
    info_slide TEXT,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id),
    FOREIGN KEY(break_category) REFERENCES break_categories(id)
);
CREATE UNIQUE INDEX round_id ON rounds (id);
CREATE INDEX round_by_tournament ON rounds (tournament_id);

CREATE TABLE break_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    tournament_id INTEGER NOT NULL,
    internal_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    general INTEGER DEFAULT 1,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id)
);
CREATE UNIQUE INDEX break_category_id ON break_categories (id);
CREATE INDEX break_categories_by_tournament ON break_categories (tournament_id);

CREATE TABLE debates (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    tournament_id INTEGER NOT NULL,
    round_id INTEGER NOT NULL,
    internal_id INTEGER NOT NULL,
    average_rating INTEGER,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id),
    FOREIGN KEY(round_id) REFERENCES rounds(id)
);
CREATE UNIQUE INDEX debate_id ON debates (id);
CREATE INDEX debate_by_round ON debates (round_id);

CREATE TABLE speeches (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    tournament_id INTEGER NOT NULL,
    speaker_id INTEGER NOT NULL,
    debate_id INTEGER NOT NULL,
    score INTEGER,
    rating_change INTEGER,
    position INTEGER NOT NULL,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id),
    FOREIGN KEY(speaker_id) REFERENCES speakers(id),
    FOREIGN KEY(debate_id) REFERENCES debates(id)
);
CREATE UNIQUE INDEX speech_id ON speeches (id);
CREATE INDEX speech_by_speaker ON speeches (speaker_id);
CREATE INDEX speech_by_debate ON speeches (debate_id);

CREATE TABLE team_performances (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    tournament_id INTEGER NOT NULL,
    debate_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    side TEXT NOT NULL,
    score INTEGER NOT NULL,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id),
    FOREIGN KEY(debate_id) REFERENCES debates(id),
    FOREIGN KEY(team_id) REFERENCES teams(id)
);
CREATE INDEX team_performance_debate ON team_performances (debate_id);

CREATE TABLE tournament_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    tournament_id INTEGER NOT NULL,
    speaker_id INTEGER,
    speaker_internal_id INTEGER NOT NULL,
    internal_name TEXT NOT NULL,
    adjudicator INTEGER NOT NULL DEFAULT 0,
    ca INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id),
    FOREIGN KEY(speaker_id) REFERENCES speakers(id)
);
CREATE INDEX tournament_participants_internal_id ON tournament_participants (speaker_internal_id);
CREATE INDEX tournament_participants_by_tournament ON tournament_participants (tournament_id);

CREATE TABLE adjudications (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    tournament_id INTEGER NOT NULL,
    speaker_id INTEGER NOT NULL,
    debate_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id),
    FOREIGN KEY(speaker_id) REFERENCES speakers(id),
    FOREIGN KEY(debate_id) REFERENCES debates(id)
);
CREATE UNIQUE INDEX adjudication_id ON adjudications (id);
CREATE INDEX adjudication_by_adjudicator ON adjudications (speaker_id);
CREATE INDEX adjudication_by_debate ON adjudications (debate_id);

CREATE TABLE achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    tournament_id INTEGER NOT NULL,
    speaker_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    name TEXT,
    break_category INTEGER,
    debate_id INTEGER,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(id),
    FOREIGN KEY(speaker_id) REFERENCES speakers(id),
    FOREIGN KEY(break_category) REFERENCES break_categories(id),
    FOREIGN KEY(debate_id) REFERENCES debates(id)
);
CREATE UNIQUE INDEX achievement_id ON achievements (id);
CREATE INDEX achievement_by_speaker ON achievements (speaker_id);
CREATE INDEX achievement_by_tournament ON achievements (tournament_id);