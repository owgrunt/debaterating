import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from urllib.parse import urlparse

from helpers import apology, login_required, lookup_data, lookup_tournament, lookup_link, add_database_entry, split_name_by_format, has_yo

from datetime import datetime
from operator import itemgetter

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
break_categories = []
speaker_categories = []

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
        # Update tournament name
        global tournament
        tournament["name"] = request.form.get("name")
        tournament["short_name"] = request.form.get("short_name")

        # Add date and type from form
        tournament["date"] = request.form.get("date")
        tournament["type"] = request.form.get("type")
        if request.form.get("link"):
            tournament["page"] = request.form.get("link")

        # Import data into the db
        db_name = "tournaments"
        entry = tournament
        search_keys = ["slug", "domain"]
        update_keys = ["name", "short_name", "date", "type"]
        if "page" in tournament:
            update_keys.append("page")
        tournament["id"] = add_database_entry(db_name, entry, search_keys, update_keys)

        # Create organiser entries
        conveners = []
        for i in range(4):
            if request.form.get(f"convener-{i}"):
                conveners.append(request.form.get(f"convener-{i}"))

        for convener in conveners:
            # Add convener as tournament participant
            db_name = "tournament_participants"
            participant = {}
            participant["tournament_id"] = tournament["id"]
            participant["speaker_id"] = convener
            participant["role"] = "convener"

            entry = participant
            search_keys = ["speaker_id", "tournament_id"]
            update_keys = ["role"]
            participant["id"] = add_database_entry(db_name, entry, search_keys, update_keys)

        return redirect("/import/speaker/categories")

    else:
        return apology("something went wrong", 400)


@app.route("/import/speaker/categories", methods=["GET", "POST"])
@login_required
def import_speaker_categories():
    """Import speakers and get input on speaker name format"""

    # Import speaker data
    global tournament
    domain = tournament["domain"]
    slug = tournament["slug"]
    global speaker_categories
    speaker_categories = lookup_data(domain, slug, "speaker-categories")

    # If there are no speaker categories, just proceed
    if len(speaker_categories) > 0:
        for category in speaker_categories:
            category["internal_id"] = category["url"].replace(f"https://{domain}/api/v1/tournaments/{slug}/speaker-categories/", "")
        return render_template("0-import-speaker-categories.html", speaker_categories=speaker_categories)
    else:
        return redirect("/import/speaker/format")


@app.route("/import/speaker/categories/add", methods=["GET", "POST"])
@login_required
def import_speaker_categories_add():
    """Add speaker categories to the db"""
    global speaker_categories
    global tournament

    if request.method == "POST":
        for category in speaker_categories:
            # Get data from the form
            if request.form.get(str(category["internal_id"])+"-name") == "other":
                category["name"] = request.form.get(str(category["internal_id"])+"-name-other")
            else:
                category["name"] = request.form.get(str(category["internal_id"])+"-name")

            category["achievement"] = request.form.get(str(category["internal_id"])+"-achievement")
            category["tournament_id"] = tournament["id"]

            # Import data into the db
            db_name = "speaker_categories"
            entry = category
            search_keys = ["internal_id", "tournament_id"]
            update_keys = ["name", "achievement"]
            category["id"] = add_database_entry(db_name, entry, search_keys, update_keys)

        return redirect("/import/speaker/format")

    else:
        return redirect("/import/speaker/format")


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

    # Import team data to show team name in the next screen. The same list will be used further in team import
    global teams
    teams = []
    teams = lookup_data(domain, slug, "teams")

    if speakers != None:
        for speaker in speakers:
            speaker["role"] = "speaker"
            if "categories" in speaker:
                if len(speaker["categories"]) > 0:
                    new_categories = []
                    for category in speaker["categories"]:
                        new_category = category.replace(f"https://{domain}/api/v1/tournaments/{slug}/speaker-categories/", "")
                        new_categories = new_categories + [new_category]
                    speaker["categories"] = new_categories
            for team in teams:
                for member in team["speakers"]:
                    if speaker["id"] == member["id"]:
                        speaker["team_name"] = team["short_name"]
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
            speaker["role"] = "adjudicator"
            if speaker["adj_core"] == True:
                speaker["role"] = "ca"
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
        # Assign first, middle and last name to the speakers and adjudicators and clean up ids
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
        global tournament
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
            participant["tournament_id"] = tournament["id"]
            participant["speaker_id"] = speaker["id"]
            participant["role"] = speaker["role"]
            participant["internal_name"] = speaker["name"]
            participant["speaker_internal_id"] = speaker["internal_id"]

            entry = participant
            search_keys = ["speaker_id", "speaker_internal_id", "tournament_id"]
            update_keys = ["internal_name", "role"]
            trash_variable = add_database_entry(db_name, entry, search_keys, update_keys)

            # Add speaker categories
            global speaker_categories
            if "categories" in speaker:
                for instance in speaker["categories"]:
                    category = {}
                    db_name = "speakers_in_categories"
                    category["speaker_id"] = speaker["id"]
                    category["tournament_id"] = tournament["id"]
                    category["internal_id"] = instance
                    for global_category in speaker_categories:
                        if category["internal_id"] == global_category["internal_id"]:
                            entry = category
                            category["category_id"] = global_category["id"]
                            search_keys = ["speaker_id", "tournament_id", "internal_id"]
                            update_keys = ["category_id"]
                            category["id"] = add_database_entry(db_name, entry, search_keys, update_keys)

        # Record average speaker rating at the tournament
        tournament_id = tournament["id"]
        average_rating = db.execute(f"SELECT avg(rating) as av FROM speakers INNER JOIN tournament_participants ON speakers.id = tournament_participants.speaker_id WHERE tournament_participants.tournament_id = {tournament_id}")[0]["av"]
        db.execute(f"UPDATE tournaments SET average_rating = {average_rating} WHERE id = {tournament_id}")

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

    global teams

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
            round["break_category_internal_id"] = ""
        else:
            # Connect the break category in the db
            round["break_category_internal_id"] = round["break_category"].replace(f"https://{domain}/api/v1/tournaments/{slug}/break-categories/", "")
        # Remove unnecessary vars
        del round["id"], round["url"], round["completed"], round["draw_type"], round["draw_status"], round["silent"], round["motions_released"], round["starts_at"], round["weight"], round["break_category"]

    # Get break categories
    global break_categories
    break_categories = lookup_data(domain, slug, "break-categories")
    for break_category in break_categories:
        break_category["internal_id"] = break_category["url"].replace(f"https://{domain}/api/v1/tournaments/{slug}/break-categories/", "")

    if len(rounds) > 0:
        return render_template("0-import-round-check.html", rounds=rounds, break_categories=break_categories)
    else:
        return apology("something went wrong", 400)


@app.route("/import/debates", methods=["GET", "POST"])
@login_required
def import_debates():
    """Import debates"""
    global rounds
    global break_categories

    if request.method == "POST":
        for break_category in break_categories:
            # Get data from the form
            if request.form.get(str(break_category["internal_id"])+"-break-category") == "other":
                break_category["name"] = request.form.get(str(break_category["internal_id"])+"-break-category-other")
            else:
                break_category["name"] = request.form.get(str(break_category["internal_id"])+"-break-category")
            if break_category["is_general"] == True:
                break_category["general"] = 1
            else:
                break_category["general"] = 0

            #return render_template("0-import-round-check.html", rounds=rounds)

            # Import round data into the db
            db_name = "break_categories"
            search_keys = ["internal_id", "tournament_id"]
            update_keys = ["name", "general"]
            break_category["tournament_id"] = tournament["id"]
            break_category["id"] = add_database_entry(db_name, break_category, search_keys, update_keys)

        for round in rounds:
            # Get data from the form
            round["name"] = request.form.get(str(round["internal_id"])+"-name")
            round["short_name"] = request.form.get(str(round["internal_id"])+"-short-name")
            round["motion"] = request.form.get(str(round["internal_id"])+"-motion")
            round["info_slide"] = request.form.get(str(round["internal_id"])+"-info-slide")
            round["achievement"] = request.form.get(str(round["internal_id"])+"-achievement")
            for break_category in break_categories:
                if break_category["internal_id"] == round["break_category_internal_id"]:
                    round["break_category"] = break_category["id"]

            #return render_template("0-import-round-check.html", rounds=rounds)

            # Import round data into the db
            db_name = "rounds"
            search_keys = ["internal_id", "tournament_id"]
            update_keys = ["name", "short_name", "seq", "stage"]
            if round["motion"] != None:
                update_keys.append("motion")
            if round["info_slide"] != None:
                update_keys.append("info_slide")
            if "break_category" in round:
                update_keys.append("break_category")
            round["tournament_id"] = tournament["id"]
            round["id"] = add_database_entry(db_name, round, search_keys, update_keys)

    # Prepare for link cleanup in the future
    domain = tournament["domain"]
    slug = tournament["slug"]

    for round in rounds:
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
                adjudicator["speaker_id"] = db.execute(f"SELECT speaker_id FROM tournament_participants WHERE speaker_internal_id = {adjudicator_internal_id} AND tournament_id = {tournament_id}")[0]["speaker_id"]
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
                        adjudicator["speaker_id"] = db.execute(f"SELECT speaker_id FROM tournament_participants WHERE speaker_internal_id = {adjudicator_internal_id} AND tournament_id = {tournament_id}")[0]["speaker_id"]
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
                        adjudicator["speaker_id"] = db.execute(f"SELECT speaker_id FROM tournament_participants WHERE speaker_internal_id = {adjudicator_internal_id} AND tournament_id = {tournament_id}")[0]["speaker_id"]
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
            if results is None:
                return apology(f"tabmaster needs to publish ballots", 400)
            elif not results == []:
                results = results[0]["result"]["sheets"][0]["teams"]
                # Check if this is a final
                if round["stage"] == "E":
                    winners = 0
                    for result in results:
                        if result["win"] == True:
                            winners = winners + 1
                    if winners == 1:
                        round["final"] = True
                    else:
                        round["final"] = False
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
                            result["score"] = 3
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
                            speech["speaker_id"] = db.execute(f"SELECT speaker_id FROM tournament_participants WHERE speaker_internal_id = {speaker_internal_id} AND tournament_id = {tournament_id}")[0]["speaker_id"]
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
                            # TODO delete speech["score"] = 0
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
                            update_keys = ["position"]
                            speech["id"] = add_database_entry(db_name, entry, search_keys, update_keys)

                            # Add achievement to the database
                            if round["stage"] == "E":
                                # Use the speech dict because I'm lazy
                                speech["type"] = "team"
                                speech["name"] = round["achievement"]
                                speech["break_category"] = round["break_category"]

                                # Import achievement data into the db
                                db_name = "achievements"
                                entry = speech
                                search_keys = ["tournament_id", "speaker_id"]
                                update_keys = ["type", "name", "break_category", "debate_id"]
                                speech["id"] = add_database_entry(db_name, entry, search_keys, update_keys)

                                if round["final"] and result["win"]:
                                    speech["name"] = "победитель"
                                    # Import achievement data into the db
                                    db_name = "achievements"
                                    entry = speech
                                    search_keys = ["tournament_id", "type", "speaker_id"]
                                    update_keys = ["name", "break_category"]
                                    speech["id"] = add_database_entry(db_name, entry, search_keys, update_keys)

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

    tournament_id = tournament["id"]
    all_updated_ratings = []
    # get the list of rounds
    rounds = db.execute("SELECT id FROM rounds WHERE tournament_id = ? ORDER BY seq",
                        tournament_id)
    # Make ELO calculation for all the rounds in a sequence
    for round_instance in rounds:
        round_id = round_instance["id"]
        team_performances = db.execute(open("sql_get_team_performances.sql").read().replace("xxxxxx", str(tournament_id)).replace("yyyyyy", str(round_id)))

        # Set the k-factor constant
        k_factor = 32

        # Set up a list of dict with all the speakers to have their ratings adjusted
        updated_ratings = []
        for i in range(len(team_performances)):
            if team_performances[i]["swing"] != 1:
                speaker_one = {"speaker": team_performances[i]["speaker_one"],
                               "round": round_id,
                               "debate": team_performances[i]["debate_id"],
                               "initial_rating": team_performances[i]["speaker_one_rating"],
                               "rating_adjustment": 0}
                speaker_two = {"speaker": team_performances[i]["speaker_two"],
                               "round": round_id,
                               "debate": team_performances[i]["debate_id"],
                               "initial_rating": team_performances[i]["speaker_two_rating"],
                               "rating_adjustment": 0}
                updated_ratings.extend([speaker_one, speaker_two])

        # Create a set of unique debates in this round
        debates_in_round = set()
        for performance in team_performances:
            debates_in_round.add(performance["debate_id"])
        # Calculate the average speaker rating in the debate
        for debate in debates_in_round:
            total_rating = 0
            speakers_in_debate = 0
            for speaker in updated_ratings:
                if speaker["debate"] == debate:
                    total_rating = total_rating + speaker["initial_rating"]
                    speakers_in_debate = speakers_in_debate + 1
            average_rating = round(total_rating/speakers_in_debate)
            # Update the debate entry with the average rating
            db.execute(f"UPDATE debates SET average_rating = {average_rating} WHERE id = {debate}")

        # Update ratings for the round
        for i in range(len(team_performances)):
            # Iterate through all the other team_performances in the round
            for j in range(len(team_performances)):
                # Check for teams in the same debate and not swings
                if team_performances[i]["debate_id"] == team_performances[j]["debate_id"] and team_performances[i]["swing"] != 1 and team_performances[j]["swing"] != 1 and team_performances[i]["speaker_one"] != team_performances[i]["speaker_two"] and team_performances[j]["speaker_one"] != team_performances[j]["speaker_two"]:
                    # Only change score if team i won
                    if team_performances[i]["score"] > team_performances[j]["score"]:
                        # Calculate initial team ratings
                        victor_rating = ( team_performances[i]["speaker_one_rating"] + team_performances[i]["speaker_two_rating"] ) / 2
                        loser_rating = ( team_performances[j]["speaker_one_rating"] + team_performances[j]["speaker_two_rating"] ) / 2
                        # Calculate victor's expected score
                        modified_difference = (loser_rating - victor_rating) / 400
                        denominator = 1 + pow(10, modified_difference)
                        victors_expected_score = 1 / denominator
                        # Calculate how much the rating will be adjusted
                        expectation_deviation = 1 - victors_expected_score
                        rating_adjustment_float = k_factor * expectation_deviation
                        rating_adjustment = round(rating_adjustment_float)
                        # Adjust the ratings
                        k = 0
                        for update in updated_ratings:
                            if update["speaker"] == team_performances[i]["speaker_one"]:
                                update["rating_adjustment"] = update["rating_adjustment"] + rating_adjustment
                                k = k + 1
                            if update["speaker"] == team_performances[i]["speaker_two"]:
                                update["rating_adjustment"] = update["rating_adjustment"] + rating_adjustment
                                k = k + 1
                            if update["speaker"] == team_performances[j]["speaker_one"]:
                                update["rating_adjustment"] = update["rating_adjustment"] - rating_adjustment
                                k = k + 1
                            if update["speaker"] == team_performances[j]["speaker_two"]:
                                update["rating_adjustment"] = update["rating_adjustment"] - rating_adjustment
                                k = k + 1
                        if k != 4:
                            return apology("scores not updated", 400)

        # Update the database
        for update in updated_ratings:
            if update["rating_adjustment"] != 0:
                # Add rating change to the speech database
                db.execute("UPDATE speeches SET rating_change = ? WHERE speaker_id = ? AND debate_id = ?",
                           update["rating_adjustment"], update["speaker"], update["debate"])

                # Change the rating in the speaker database
                new_rating = update["initial_rating"] + update["rating_adjustment"]
                db.execute("UPDATE speakers SET rating = ? WHERE id = ? AND rating = ?",
                           new_rating, update["speaker"], update["initial_rating"])

        all_updated_ratings = all_updated_ratings + updated_ratings

    updated_count = len(all_updated_ratings)

    return render_template("0-import-elo.html", all_updated_ratings=all_updated_ratings, updated_count=updated_count)


@app.route("/import/speaker-scores", methods=["GET", "POST"])
@login_required
def calculate_speaker_scores():
    """Calculate new average speaker scores, record best speakers"""
    global speakers
    for speaker in speakers:
        if speaker["role"] == "speaker":
            new_average = db.execute("SELECT avg(score) FROM speeches WHERE speaker_id = ?",
                                     speaker["id"])[0]["avg(score)"]
            speaker["new_average"] = round(new_average, 2)
            db.execute("UPDATE speakers SET speaker_score = ? WHERE id = ?",
                       speaker["new_average"], speaker["id"])

    # Get best speaker(s)
    global tournament
    tournament_id = tournament["id"]
    best_speakers = db.execute(open("sql_get_best_speaker.sql").read().replace("xxxxxx", str(tournament_id)))
    if len(best_speakers) > 1:
        return apology("no best speaker found", 400)
    for speaker in best_speakers:
        achivement = {}
        achivement["tournament_id"] = tournament["id"]
        achivement["speaker_id"] = speaker["speaker_id"]
        achivement["type"] = "speaker"
        achivement["name"] = "лучший спикер"
        # Import achievement data into the db
        db_name = "achievements"
        entry = achivement
        search_keys = ["tournament_id", "speaker_id", "type"]
        update_keys = ["name"]
        achivement["id"] = add_database_entry(db_name, entry, search_keys, update_keys)

    # Get best speakers for all of the categories
    global speaker_categories
    for category in speaker_categories:
        best_speakers = db.execute(open("sql_get_best_speaker_in_category.sql").read().replace("xxxxxx", str(tournament_id)).replace("yyyyyy", str(category["id"])))
        for speaker in best_speakers:
            achivement = {}
            achivement["tournament_id"] = tournament["id"]
            achivement["speaker_id"] = speaker["speaker_id"]
            achivement["type"] = "speaker"
            achivement["name"] = category["achievement"]
            achivement["speaker_category"] = category["id"]
            # Import achievement data into the db
            db_name = "achievements"
            entry = achivement
            search_keys = ["tournament_id", "speaker_id", "type", "speaker_category"]
            update_keys = ["name"]
            achivement["id"] = add_database_entry(db_name, entry, search_keys, update_keys)

    # Set up the new global ranking by speaker scores
    db_speakers = db.execute("SELECT id, first_name, last_name, middle_name, speaker_score, rating FROM speakers ORDER BY speaker_score DESC")
    i = 1
    previous_score = 101
    current_ranking = 0
    for speaker in db_speakers:
        if speaker["speaker_score"] < previous_score:
            current_ranking = i
            previous_score = speaker["speaker_score"]
        speaker["ranking_by_speaks"] = current_ranking
        i = i + 1

    # Set up the new global ranking by rating
    db_speakers = sorted(db_speakers, key=itemgetter("rating"), reverse=True)
    i = 1
    previous_score = 10000
    current_ranking = 0
    for speaker in db_speakers:
        if speaker["rating"] < previous_score:
            current_ranking = i
            previous_score = speaker["rating"]
        speaker["ranking_by_rating"] = current_ranking
        i = i + 1

    # Create a sql query
    query = ""
    for speaker in db_speakers:
        ranking_by_speaks = speaker["ranking_by_speaks"]
        ranking_by_rating = speaker["ranking_by_rating"]
        id = speaker["id"]
        db.execute(f"UPDATE speakers SET ranking_by_speaks = {ranking_by_speaks}, ranking_by_rating = {ranking_by_rating} WHERE id = {id}")
    #     query = query + f"UPDATE speakers SET ranking_by_speaks = {ranking_by_speaks}, ranking_by_rating = {ranking_by_rating} WHERE id = {id};\n"
    # query = "BEGIN TRANSACTION;\n" + query + "COMMIT"
    # db.execute(query)

    return render_template("0-import-speaker-scores.html", speakers=speakers)


@app.route("/ranking/speaker-score", methods=["GET", "POST"])
def ranking_speaker_score():
    """Show speaker ranking"""

    speakers = db.execute("SELECT id, first_name, last_name, middle_name, speaker_score, rating FROM speakers ORDER BY speaker_score DESC")

    return render_template("0-ranking-speaker-score.html", speakers=speakers)


@app.route("/speaker", methods=["GET", "POST"])
def speaker_profile():
    """Show speaker profile"""

    if not request.args.get("id"):
            return apology("must provide speaker id", 400)

    id = request.args.get("id")

    speaker = db.execute(f"SELECT * FROM speakers WHERE id = {id}")[0]

    speeches = db.execute(open("sql_get_speeches.sql").read().replace("xxxxxx", str(id)))

    # Add additional data to the speech entries
    positions = ["ПМ", "ЛО", "ЗПМ", "ЗЛО", "ЧП", "ЧО", "СП", "СО"]
    for i in range(len(speeches)):
        # Add position name to the speech entry
        speeches[i]["position_name"] = positions[speeches[i]["position"]-1]
        # Add rating after the debate to the speech entry
        if i == 0:
            speeches[i]["rating"] = speaker["rating"]
        else:
            speeches[i]["rating"] = speeches[i-1]["rating"] - speeches[i]["rating_change"]

    speeches = sorted(speeches, key=itemgetter("id"))

    count = len(speeches)

    # Prepare data to show your average speaker score by position
    speaks_by_position_calculation = [{"number": 0, "score": 0}, {"number": 0, "score": 0}, {"number": 0, "score": 0}, {"number": 0, "score": 0}, {"number": 0, "score": 0}, {"number": 0, "score": 0}, {"number": 0, "score": 0}, {"number": 0, "score": 0}]
    for speech in speeches:
        if speech["score"] is not None:
            position = speech["position"] - 1
            speaks_by_position_calculation[position]["number"] = speaks_by_position_calculation[position]["number"] + 1
            speaks_by_position_calculation[position]["score"] = speaks_by_position_calculation[position]["score"] + speech["score"]
    speaks_by_position = []
    for i in range(len(speaks_by_position_calculation)):
        try:
            new_value = speaks_by_position_calculation[i]["score"] / speaks_by_position_calculation[i]["number"]
        except (ZeroDivisionError):
            new_value = 0
        if new_value < 65:
            new_value = 65
        new_value = round(new_value, 2)
        speaks_by_position = speaks_by_position + [new_value]

    # Prepare data to show your average points by side
    points_by_side_calculation = [{"side": "og", "number": 0, "score": 0}, {"side": "oo", "number": 0, "score": 0}, {"side": "cg", "number": 0, "score": 0}, {"side": "co", "number": 0, "score": 0}]
    for speech in speeches:
        for side in points_by_side_calculation:
            if speech["side"] == side["side"]:
                side["number"] = side["number"] + 1
                side["score"] = side["score"] + speech["team_score"]
    points_by_side = []
    for i in range(len(points_by_side_calculation)):
        try:
            new_value = points_by_side_calculation[i]["score"] / points_by_side_calculation[i]["number"]
        except (ZeroDivisionError):
            new_value = 0
        new_value = round(new_value, 2)
        points_by_side = points_by_side + [new_value]

    # Prepare data to show a pie chart of your team rankings
    team_rankings = [0, 0, 0, 0]
    for speech in speeches:
        if speech["team_score"] == 3:
            team_rankings[0] = team_rankings[0] + 1
        elif speech["team_score"] == 2:
            team_rankings[1] = team_rankings[1] + 1
        elif speech["team_score"] == 1:
            team_rankings[2] = team_rankings[2] + 1
        elif speech["team_score"] == 0:
            team_rankings[3] = team_rankings[3] + 1

    # Prepare data to show your points depending on room strength
    points_by_room_strength = []
    for speech in speeches:
        entry = {}
        entry["y"] = speech["team_score"]
        entry["x"] = speech["average_rating"]
        points_by_room_strength = points_by_room_strength + [entry]

    # Prepare data to show a chart of your team rankings by round sequence number
    round_seq = []
    rankings_by_round_seq = []
    for speech in speeches:
        if speech["seq"] not in round_seq:
            round_seq = round_seq + [speech["seq"]]
            round_instance = {"seq": speech["seq"], "score": speech["team_score"], "number": 1}
            rankings_by_round_seq = rankings_by_round_seq + [round_instance]
        else:
            for ranking in rankings_by_round_seq:
                if ranking["seq"] == speech["seq"]:
                    ranking["score"] = speech["team_score"]
                    ranking["number"] = ranking["number"] + 1
    for ranking in rankings_by_round_seq:
        ranking["average_score"] = ranking["score"] / ranking["number"]

    return render_template("0-speaker.html", speaker=speaker, speeches=speeches, count=count, speaks_by_position=speaks_by_position, points_by_side=points_by_side, points_by_room_strength=points_by_room_strength, team_rankings=team_rankings, rankings_by_round_seq=rankings_by_round_seq, round_seq=round_seq)


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