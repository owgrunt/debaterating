import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from urllib.parse import urlparse

from helpers import apology, login_required, lookup_data, lookup_tournament, lookup_link, add_database_entry, split_name_by_format, has_yo

from datetime import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///debaterating.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
#@login_required
def index():
    return redirect("/import")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


tournament = {}
speakers = []
adjudicators = []
speaker_name_format = ""
adjudicator_name_format = ""
swings = []
teams = []
rounds = []

@app.route("/import", methods=["GET", "POST"])
@login_required
def start_import():
    """Start importing the tournament"""
    return render_template("0-import-tournament.html")


@app.route("/import/tournament", methods=["GET", "POST"])
@login_required
def import_tournament():
    """Process the link"""
    if request.method == "POST":
        # Clear the global variables
        global tournament
        tournament = {}

        # Ensure the address was submitted
        if not request.form.get("address"):
            return apology("must provide an address", 400)

        address = urlparse(request.form.get("address"))

        netloc = address[1]
        path = address[2]

        # Validate the address
        i = 1
        slashes = 0
        for i in range(len(path)):
            if slashes > 1:
                return apology("address format: https://domain.herokuapp.com/tournament/", 400)
            # Try to validate address further
            elif address.path[i] == "?" or address.path[i] == ")" or address.path[i] == "=":
                return apology("address format: https://domain.herokuapp.com/tournament/", 400)
            elif address.path[i] == "/":
                slashes = slashes + 1

        # Remove slashes from the slug
        slug = path.replace("/", "")

        # Get key tournament data
        tournament = lookup_tournament(netloc, slug)

        return redirect("/import/tournament/edit")

    # Can only get here with post
    else:
        return apology("something went wrong", 400)


@app.route("/import/tournament/edit", methods=["GET", "POST"])
@login_required
def edit_tournament():
    """ Get tournament details """
    return render_template("0-import-tournament-edit.html", tournament=tournament)


@app.route("/import/tournament/add", methods=["GET", "POST"])
@login_required
def add_tournament():
    """Add the tournament"""

    if request.method == "POST":
        # Ensure the name was submitted
        if not request.form.get("name"):
            return apology("must provide a tournament name", 400)

        # Update tournament name
        global tournament
        tournament["name"] = request.form.get("name")
        tournament["short_name"] = request.form.get("short_name")

        # Add date and type from form
        tournament["date"] = request.form.get("date")
        tournament["type"] = request.form.get("type")

        # TODO change to use the add_entry()
        # Add the tournament to the db
        # Check that it is not in there already
        candidates = db.execute("SELECT * FROM tournaments WHERE (internal_id = ? OR internal_id IS NULL) AND slug = ? AND domain = ?",
                                tournament["internal_id"], tournament["slug"], tournament["domain"])
        if len(candidates) == 1:
            # Update tournament data
            db.execute("UPDATE tournaments SET name = ?, short_name = ?, date = ?, type = ? WHERE (internal_id = ? OR internal_id IS NULL) AND slug = ? AND domain = ?",
                       tournament["name"], tournament["short_name"], tournament["date"], tournament["type"], tournament["internal_id"], tournament["slug"], tournament["domain"])
        elif len(candidates) == 0:
            # Add a new tournament
            db.execute("INSERT INTO tournaments (name, short_name, date, type, internal_id, slug, domain) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       tournament["name"], tournament["short_name"], tournament["date"], tournament["type"], tournament["internal_id"], tournament["slug"], tournament["domain"])
        else:
            return apology("something went wrong", 400)

        # Add the tournament db ID to the tournament dict
        candidates = db.execute("SELECT * FROM tournaments WHERE name = ? AND (internal_id = ? OR internal_id IS NULL) AND slug = ? AND domain = ?",
                                tournament["name"], tournament["internal_id"], tournament["slug"], tournament["domain"])
        if len(candidates) == 1:
            # Update the id
            tournament["id"] = candidates[0]["id"]
        else:
            return apology("something went wrong", 400)

        return redirect("/import/speaker/format")

    else:
        return apology("something went wrong", 400)


@app.route("/import/speaker/format", methods=["GET", "POST"])
@login_required
def import_speakers():
    """Import speakers and get input on speaker name format"""

    # Import speaker data
    global tournament
    domain = tournament["domain"]
    slug = tournament["slug"]
    global speakers
    speakers = lookup_data(domain, slug, "speakers")

    if speakers != None:
        for speaker in speakers:
            speaker["adjudicator"] = 0
        count = len(speakers)
        return render_template("0-import-speaker-format.html", speakers=speakers, count=count, tournament=tournament)
    else:
        return apology("speakers not imported", 400)


@app.route("/import/adjudicator/format", methods=["GET", "POST"])
@login_required
def import_adjudicators():
    """Import adjudicators and get input on speaker name format"""

    # Record speaker name format from the previous page
    if request.method == "POST":
        # Ensure the format was chosen
        if not request.form.get("format"):
            return apology("must specify name format", 400)

        global speaker_name_format
        speaker_name_format = request.form.get("format")

    # Import adjudicator data
    global tournament
    domain = tournament["domain"]
    slug = tournament["slug"]
    global adjudicators
    adjudicators = lookup_data(domain, slug, "adjudicators")


    # Ensure the adjudicators are imported
    if adjudicators != None:
        for speaker in adjudicators:
            speaker["adjudicator"] = 1
        count = len(adjudicators)
        return render_template("0-import-adjudicator-format.html", speakers=adjudicators, count=count, tournament=tournament)
    else:
        return apology("adjudicators not imported", 400)


@app.route("/import/debater/check", methods=["GET", "POST"])
@login_required
def check_speakers():
    """Check that speaker names are mapped correctly"""

    global adjudicator_name_format
    if request.method == "POST":
        # Ensure the format was chosen
        if not request.form.get("format"):
            return apology("must specify name format", 400)

        adjudicator_name_format = request.form.get("format")

        global speaker_name_format
        # Assign first, middle and last name to the speakers and adjudicators
        global speakers
        for speaker in speakers:
            speaker = split_name_by_format(speaker, speaker_name_format)
        global adjudicators
        for speaker in adjudicators:
            speaker = split_name_by_format(speaker, adjudicator_name_format)

        speakers = speakers + adjudicators

        return render_template("0-import-speaker-check.html", speakers=speakers)

    else:
        if len(speakers) > 0:
            return render_template("0-import-speaker-check.html", speakers=speakers)
        else:
            return apology("something went wrong", 400)


@app.route("/import/speaker/edit", methods=["GET", "POST"])
@login_required
def edit_speakers():
    """Confirm speaker import"""

    if request.method == "POST":
        # Setup a list of speakers to be removed
        global swings
        swings = []

        # Assign first, middle and last name add internal id
        for speaker in speakers:
            if request.form.get(str(speaker["internal_id"])+"-swing"):
                # Change swing name to swing in Russian
                speaker["last_name"] = "Свингов"
                speaker["first_name"] = "Свинг"
                speaker["middle_name"] = "Свингович"
                swings.append(speaker["internal_id"])
            else:
                speaker["last_name"] = request.form.get(str(speaker["internal_id"])+"-last-name")
                speaker["first_name"] = request.form.get(str(speaker["internal_id"])+"-first-name")
                speaker["middle_name"] = request.form.get(str(speaker["internal_id"])+"-middle-name")

        return redirect("/import/speaker/confirm")

    else:
        return apology("something went wrong", 400)


@app.route("/import/speaker/confirm", methods=["GET", "POST"])
@login_required
def confirm_speakers():
    """Confirm speaker import"""
    # Check if the speaker is already in the database
    global speakers
    for speaker in speakers:
        if speaker["middle_name"] != "":
            candidates = db.execute("SELECT * FROM speakers WHERE last_name = ? AND first_name = ? AND (middle_name = ? OR middle_name IS NULL)",
                                    speaker["last_name"], speaker["first_name"], speaker["middle_name"])
        else:
            candidates = db.execute("SELECT * FROM speakers WHERE last_name = ? AND first_name = ?",
                                    speaker["last_name"], speaker["first_name"])
        if len(candidates) > 0:
            speaker["candidates"] = candidates

    return render_template("0-import-speaker-confirm.html", speakers=speakers)


@app.route("/import/speaker/add", methods=["GET", "POST"])
@login_required
def add_speakers():
    """Add speakers to the database"""
    if request.method == "POST":
        global speakers
        for speaker in speakers:
            # If speaker is in the db, connect general speaker id with tournament speaker id
            if request.form.get(str(speaker["internal_id"])+"-id"):
                speaker["id"] = request.form.get(str(speaker["internal_id"])+"-id")
                forego_search = False
            else:
                # Don't search the db, just update it
                forego_search = True

            # Import debater data into the db
            db_name = "speakers"
            search_keys = ["id"]
            if speaker["middle_name"] != "":
                update_keys = ["first_name", "last_name", "middle_name"]
            else:
                update_keys = ["first_name", "last_name"]
            if forego_search:
                speaker["id"] = add_database_entry(db_name, speaker, search_keys, update_keys, forego_search=True)
            else:
                speaker["id"] = add_database_entry(db_name, speaker, search_keys, update_keys)

            # Add speaker as tournament participant
            db_name = "tournament_participants"
            participant = {}
            global tournament
            participant["tournament_id"] = tournament["id"]
            participant["speaker_id"] = speaker["id"]
            participant["adjudicator"] = speaker["adjudicator"]
            participant["internal_name"] = speaker["name"]
            participant["speaker_internal_id"] = speaker["internal_id"]
            search_keys = ["speaker_internal_id", "tournament_id", "adjudicator"]
            update_keys = ["speaker_id", "internal_name"]
            trash_variable = add_database_entry(db_name, participant, search_keys, update_keys)

        return redirect("/import/speaker/success")

    # Can only get here with post
    else:
        return apology("something went wrong", 400)


@app.route("/import/speaker/success", methods=["GET", "POST"])
@login_required
def speakers_success():
    """Show the speakers that have been added to the database"""
    return render_template("0-import-speaker-success.html", speakers=speakers, tournament=tournament, teams=teams)


@app.route("/import/team", methods=["GET", "POST"])
@login_required
def import_teams():
    """Get teams"""

    # Clean teams just in case
    global teams
    teams = []

    # Import team data
    global tournament
    domain = tournament["domain"]
    slug = tournament["slug"]
    teams = lookup_data(domain, slug, "teams")

    # Ensure the teams are imported
    if teams == None:
        return apology("teams not imported", 400)

    global speakers
    for team in teams:
        """Clean team data"""
        team_speakers = team["speakers"]
        # Rename the id and name vars
        team["internal_id"] = team["id"]
        team["name"] = team["long_name"]
        # Record speakers' tabbycat ids in team dict
        team["speaker_one_internal_id"] = team_speakers[0]["id"]
        if len(team_speakers) > 1:
            team["speaker_two_internal_id"] = team_speakers[1]["id"]
        else:
            team["speaker_two_internal_id"] = team["speaker_one_internal_id"]
        # Check if the team has any swing speakers
        if team["speaker_one_internal_id"] in swings or team["speaker_two_internal_id"] in swings:
            team["swing"] = 1
            team["name"] = "SWING"
        else:
            team["swing"] = 0
        # Assign db id to speakers in the team
        for speaker in speakers:
            if speaker["internal_id"] == team["speaker_one_internal_id"]:
                team["speaker_one_id"] = speaker["id"]
            if speaker["internal_id"] == team["speaker_two_internal_id"]:
                team["speaker_two_id"] = speaker["id"]
        # Remove unnecessary vars
        del team["url"], team["reference"], team["short_reference"], team["code_name"], team["short_name"], team["long_name"], team["emoji"], team["speakers"]
        # Check that ids have been assigned
        if not (team["speaker_one_id"] and team["speaker_two_id"]):
            return apology("speaker ids have not been assigned for one of the teams", 400)

        # Import team data into the db
        db_name = "teams"
        search_keys = ["internal_id", "tournament_id"]
        update_keys = ["name", "swing", "speaker_one_id", "speaker_two_id"]
        team["tournament_id"] = tournament["id"]
        team["id"] = add_database_entry(db_name, team, search_keys, update_keys)

        # Check if the previous step was successful
        if not team["id"]:
            return apology("the id for a new team not found in db", 400)

    return redirect("/import/team/success")

@app.route("/import/team/success", methods=["GET", "POST"])
@login_required
def teams_success():
    """Show the speakers that have been added to the database"""
    return render_template("0-import-team-success.html", speakers=speakers, tournament=tournament, teams=teams, rounds=rounds)


@app.route("/import/round", methods=["GET", "POST"])
@login_required
def import_rounds():
    """Get rounds"""
    # Cleanup round data
    global rounds
    rounds = []

    # Import round data
    global tournament
    domain = tournament["domain"]
    slug = tournament["slug"]
    rounds = lookup_data(domain, slug, "rounds")

    # Ensure the rounds are imported
    if rounds == None:
        return apology("rounds not imported", 400)

    for round in rounds:
        # Import infoslide
        try:
            round["motion"] = lookup_link(round["url"])["motions"][0]["text"]
            round["info_slide"] = lookup_link(round["url"])["motions"][0]["info_slide"]
        except (KeyError, TypeError, ValueError):
            round["motion"] = ""
            round["info_slide"] = ""
        # Clean data
        round["internal_id"] = round["id"]
        round["short_name"] = round["abbreviation"]
        if not round["break_category"]:
            round["break_category"] = ""
        else:
            round["break_category"] = lookup_link(round["break_category"])["name"]
        # Remove unnecessary vars
        del round["id"], round["url"], round["completed"], round["draw_type"], round["draw_status"], round["silent"], round["motions_released"], round["starts_at"], round["weight"]

        # Import round data into the db
        db_name = "rounds"
        search_keys = ["internal_id", "tournament_id"]
        update_keys = ["name", "short_name", "seq", "break_category", "stage", "motion", "info_slide"]
        round["tournament_id"] = tournament["id"]
        round["id"] = add_database_entry(db_name, round, search_keys, update_keys)

        # Prepare for link cleanup in the future
        domain = tournament["domain"]
        slug = tournament["slug"]

        # Get debates (pairings)
        debates = lookup_link(round["_links"]["pairing"])
        for debate in debates:
            # Populate the entry before we import it into the db
            debate["internal_id"] = debate["id"]
            debate["round_id"] = round["id"]
            debate["tournament_id"] = tournament["id"]

            # Import debate data into the db
            db_name = "debates"
            search_keys = ["internal_id", "tournament_id"]
            update_keys = ["round_id"]
            debate["id"] = add_database_entry(db_name, debate, search_keys, update_keys)

            # Import judges
            if "adjudicators" in debate:
                # Prepare data
                adjudicator = {}
                adjudicator["debate_id"] = debate["id"]
                adjudicator["tournament_id"] = tournament["id"]
                # Get adjudicator's db id
                adjudicator["internal_id"] = debate["adjudicators"]["chair"].replace(f"https://{domain}/api/v1/tournaments/{slug}/adjudicators/", "")
                adjudicator_internal_id = adjudicator["internal_id"]
                tournament_id = tournament["id"]
                adjudicator["speaker_id"] = db.execute(f"SELECT id FROM tournament_participants WHERE speaker_internal_id = {adjudicator_internal_id} AND tournament_id = {tournament_id}")[0]["id"]
                adjudicator["role"] = "chair"

                # Import adjudication instance into the db
                db_name = "adjudications"
                search_keys = ["speaker_id", "tournament_id", "debate_id"]
                update_keys = ["role"]
                adjudicator["id"] = add_database_entry(db_name, adjudicator, search_keys, update_keys)

                if "panellists" in debate["adjudicators"]:
                    for panellist in debate["adjudicators"]["panellists"]:
                        adjudicator["internal_id"] = panellist.replace(f"https://{domain}/api/v1/tournaments/{slug}/adjudicators/", "")
                        adjudicator_internal_id = adjudicator["internal_id"]
                        adjudicator["speaker_id"] = db.execute(f"SELECT id FROM tournament_participants WHERE speaker_internal_id = {adjudicator_internal_id} AND tournament_id = {tournament_id}")[0]["id"]
                        adjudicator["role"] = "panellist"

                        # Import adjudication instance into the db
                        db_name = "adjudications"
                        search_keys = ["speaker_id", "tournament_id", "debate_id"]
                        update_keys = ["role"]
                        adjudicator["id"] = add_database_entry(db_name, adjudicator, search_keys, update_keys)

                if "trainees" in debate["adjudicators"]:
                    for trainee in debate["adjudicators"]["trainees"]:
                        adjudicator["internal_id"] = trainee.replace(f"https://{domain}/api/v1/tournaments/{slug}/adjudicators/", "")
                        adjudicator_internal_id = adjudicator["internal_id"]
                        adjudicator["speaker_id"] = db.execute(f"SELECT id FROM tournament_participants WHERE speaker_internal_id = {adjudicator_internal_id} AND tournament_id = {tournament_id}")[0]["id"]
                        adjudicator["role"] = "trainee"

                        # Import adjudication instance into the db
                        db_name = "adjudications"
                        search_keys = ["speaker_id", "tournament_id", "debate_id"]
                        update_keys = ["role"]
                        adjudicator["id"] = add_database_entry(db_name, adjudicator, search_keys, update_keys)

            # Get results
            results = lookup_link(debate["url"] + "/ballots")
            # results = lookup_link(debate["url"] + "/ballots")[0]["result"]["sheets"][0]["teams"]
            # Get to the team result
            if not results == []:
                results = results[0]["result"]["sheets"][0]["teams"]
                for result in results:
                    # Prepare data for import
                    result["tournament_id"] = tournament["id"]
                    result["debate_id"] = debate["id"]
                    # Get team id from db
                    result["team_id"] = result["team"].replace(f"https://{domain}/api/v1/tournaments/{slug}/teams/", "")
                    result["team_id"] = db.execute("SELECT id FROM teams WHERE internal_id = ? AND tournament_id = ?",
                                                   result["team_id"], result["tournament_id"])[0]["id"]
                    # Check that team is there
                    if not result["team_id"]:
                        id = debate["id"]
                        round_seq = round["seq"]
                        return apology(f"team in debate {id}, round {round_seq} does not have a correct side", 400)

                    # Assign points
                    if not result["points"]:
                        if result["win"] == True:
                            result["score"] = 4
                        else:
                            result["score"] = 0
                    else:
                        result["score"] = result["points"]

                    # Import result data into the db
                    db_name = "team_performances"
                    entry = result
                    search_keys = ["debate_id", "tournament_id", "team_id"]
                    update_keys = ["side", "score"]
                    result["id"] = add_database_entry(db_name, entry, search_keys, update_keys)

                    # Get speeches
                    global speakers
                    if "speeches" in result:
                        i = 0
                        for speech in result["speeches"]:
                            # Add and clean speech data
                            speech["tournament_id"] = tournament["id"]
                            speech["debate_id"] = debate["id"]
                            speech["score"] = int(speech["score"])
                            # Get speaker's db id
                            speech["speaker_internal_id"] = speech["speaker"].replace(f"https://{domain}/api/v1/tournaments/{slug}/speakers/", "")
                            speaker_internal_id = speech["speaker_internal_id"]
                            tournament_id = tournament["id"]
                            speech["speaker_id"] = db.execute(f"SELECT speaker_id FROM tournament_participants WHERE speaker_internal_id = {speaker_internal_id} AND tournament_id = {tournament_id}")[0]["id"]
                            # Assign position
                            if i == 0:
                                if result["side"] == "og":
                                    speech["position"] = "1"
                                elif result["side"] == "oo":
                                    speech["position"] = "2"
                                elif result["side"] == "cg":
                                    speech["position"] = "5"
                                elif result["side"] == "co":
                                    speech["position"] = "6"
                                else:
                                    return apology(f"team in debate {id}, round {round_seq} does not have a correct side", 400)
                                i = 1
                            else:
                                if result["side"] == "og":
                                    speech["position"] = "3"
                                elif result["side"] == "oo":
                                    speech["position"] = "4"
                                elif result["side"] == "cg":
                                    speech["position"] = "7"
                                elif result["side"] == "co":
                                    speech["position"] = "8"
                                else:
                                    return apology(f"team in debate {id}, round {round_seq} does not have a correct side", 400)

                            # Import speech data into the db
                            db_name = "speeches"
                            entry = speech
                            search_keys = ["debate_id", "tournament_id", "speaker_id"]
                            update_keys = ["position", "score"]
                            result["id"] = add_database_entry(db_name, entry, search_keys, update_keys)
                    else:
                        team_entry = db.execute("SELECT * FROM teams WHERE tournament_id = ? AND id = ?",
                                                   tournament["id"], result["team_id"])
                        speaker_one_id = team_entry[0]["speaker_one_id"]
                        speaker_two_id = team_entry[0]["speaker_two_id"]
                        team_speakers = [speaker_one_id, speaker_two_id]
                        for i in range(len(team_speakers)):
                            speech = {}
                            speech["tournament_id"] = tournament["id"]
                            speech["debate_id"] = debate["id"]
                            speech["speaker_id"] = team_speakers[i]
                            speech["score"] = 0
                            # Assign position
                            if i == 0:
                                if result["side"] == "og":
                                    speech["position"] = "1"
                                elif result["side"] == "oo":
                                    speech["position"] = "2"
                                elif result["side"] == "cg":
                                    speech["position"] = "5"
                                elif result["side"] == "co":
                                    speech["position"] = "6"
                                else:
                                    return apology(f"team in debate {id}, round {round_seq} does not have a correct side", 400)
                                i = 1
                            else:
                                if result["side"] == "og":
                                    speech["position"] = "3"
                                elif result["side"] == "oo":
                                    speech["position"] = "4"
                                elif result["side"] == "cg":
                                    speech["position"] = "7"
                                elif result["side"] == "co":
                                    speech["position"] = "8"
                                else:
                                    return apology(f"team in debate {id}, round {round_seq} does not have a correct side", 400)

                            # Import speech data into the db
                            db_name = "speeches"
                            entry = speech
                            search_keys = ["debate_id", "tournament_id", "speaker_id"]
                            update_keys = ["position", "score"]
                            result["id"] = add_database_entry(db_name, entry, search_keys, update_keys)

    return redirect("/import/debate/success")


@app.route("/import/debate/success", methods=["GET", "POST"])
@login_required
def debates_success():
    """Show the speakers that have been added to the database"""
    return render_template("0-import-debate-success.html", speakers=speakers, tournament=tournament, teams=teams, rounds=rounds)


@app.route("/import/elo", methods=["GET", "POST"])
@login_required
def calculate_elo():
    """Calculate and update new ELO values"""

    # TODO get the list of rounds: SELECT id FROM rounds ORDER BY seq;
    # TODO run the code for each round
    tournament_id = str(1)
    round_id = str(1)
    round = db.execute(open("sql_get_team_performances.sql").read().replace("xxxxxx", tournament_id).replace("yyyyyy", round_id))

    # Set the k-factor constant
    k_factor = 32

    # Set up a list of dict with all the speakers to have their ratings adjusted
    updated_ratings = []
    for i in range(len(round)):
        if round[i]["swing"] != 1:
            speaker_one = {"speaker": round[i]["speaker_one"],
                           "debate": round[i]["debate_id"],
                           "initial_rating": round[i]["speaker_one_rating"],
                           "rating_adjustment": 0}
            speaker_two = {"speaker": round[i]["speaker_two"],
                           "debate": round[i]["debate_id"],
                           "initial_rating": round[i]["speaker_two_rating"],
                           "rating_adjustment": 0}
            updated_ratings.extend([speaker_one, speaker_two])

    # Update ratings for the round
    for i in range(len(round)):
        for j in range(len(round)):
            # Check for teams in the same debate and not swings
            if round[i]["debate_id"] == round[j]["debate_id"] and round[i]["swing"] != 1 and round[j]["swing"] != 1 and round[i]["speaker_one"] != round[i]["speaker_two"] and round[j]["speaker_one"] != round[j]["speaker_two"]:
                # Only change score if team i won
                if round[i]["score"] > round[j]["score"]:
                    # Calculate initial team ratings
                    victor_rating = ( round[i]["speaker_one_rating"] + round[i]["speaker_two_rating"] ) / 2
                    loser_rating = ( round[j]["speaker_one_rating"] + round[j]["speaker_two_rating"] ) / 2
                    # Calculate victor's expected score
                    victors_expected_score = 1 / ( 1 + pow(10, (loser_rating - victor_rating) / 400))
                    # Calculate how much the rating will be adjusted
                    rating_adjustment = ( 1 - victors_expected_score ) * k_factor
                    # Adjust the ratings
                    k = 0
                    for update in updated_ratings:
                        if update["speaker"] == round[i]["speaker_one"]:
                            update["rating_adjustment"] = update["rating_adjustment"] + rating_adjustment
                            k = k + 1
                        if update["speaker"] == round[i]["speaker_two"]:
                            update["rating_adjustment"] = update["rating_adjustment"] + rating_adjustment
                            k = k + 1
                        if update["speaker"] == round[j]["speaker_one"]:
                            update["rating_adjustment"] = update["rating_adjustment"] - rating_adjustment
                            k = k + 1
                        if update["speaker"] == round[j]["speaker_two"]:
                            update["rating_adjustment"] = update["rating_adjustment"] - rating_adjustment
                            k = k + 1
                    if k != 4:
                        return apology("scores not updated", 400)

    # Add rating change to the speech database
    for update in updated_ratings:
        if update["rating_adjustment"] != 0:
            db.execute("UPDATE speeches SET rating_change = ? WHERE speaker_id = ? AND debate_id = ?",
                       update["rating_adjustment"], update["speaker"], update["debate"])

    updated_count = len(updated_ratings)

    return render_template("0-import-elo.html", round=round, updated_ratings=updated_ratings, updated_count=updated_count)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password confirmation is correct
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password confirmation does not match password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username does not exist
        if len(rows) > 0:
            return apology("username already taken", 400)

        # Create username and password hash
        username = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))

        # Add the user's entry into the database
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Ensure username does not exist
        if len(rows) != 1:
            return apology("unknown error", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")