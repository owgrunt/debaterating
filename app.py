import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from urllib.parse import urlparse

from helpers import apology, login_required, lookup_data, lookup_tournament, lookup_link, add_database_entry, split_name_by_format, calculate_elo, update_rankings, execute_insert, tournament_average_rating, has_yo

from datetime import datetime
from operator import itemgetter
import subprocess

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
# db = SQL("sqlite:///debaterating.db")
uri = os.getenv("HEROKU_POSTGRESQL_BLUE_URL")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://")
db = SQL(uri)


# @app.after_request
# def after_request(response):
#     """Ensure responses aren't cached"""
#     response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
#     response.headers["Expires"] = 0
#     response.headers["Pragma"] = "no-cache"
#     return response


@app.route("/")
def index():

    return render_template("index.html")


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

@app.route("/import", methods=["GET", "POST"])
@login_required
def start_import():
    """Start importing the tournament"""
    return render_template("import/tournament.html")

# @app.route("/import/backup", methods=["GET", "POST"])
# @login_required
# def start_backup():
#     if request.method == "POST":
#         subprocess.run(["bash pg:backups:capture HEROKU_POSTGRESQL_BLUE", "-l"])
#         # os.system("heroku pg:backups:capture HEROKU_POSTGRESQL_BLUE -a debaterating")
#         return render_template("import/backup.html")

#     else:
#         # Check if we want to backup the db
#         return render_template("import/backup.html")


@app.route("/import/tournament", methods=["GET", "POST"])
@login_required
def import_tournament():
    """Process the link"""
    if request.method == "POST":
        # Create the variable
        tournament = {}

        # Clear the tournaments that haven't been imported completely
        db.execute("DELETE FROM tournaments WHERE import_complete = 0")

        # Ensure the address was submitted
        if not request.form.get("address"):
            return apology("must provide an address", 400)

        address = urlparse(request.form.get("address"))

        domain = address[1]
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
        tournament = lookup_tournament(domain, slug)
        tournament["slug"] = slug
        tournament["domain"] = domain
        tournament["import_complete"] = 0

        # Import data into the db
        db_name = "tournaments"
        entry = tournament
        search_keys = ["slug", "domain"]
        update_keys = ["name", "short_name", "import_complete"]
        add_database_entry(db_name, entry, search_keys, update_keys)

        return redirect("/import/tournament/edit")

    # Can only get here with post
    else:
        return apology("something went wrong", 400)


@app.route("/import/tournament/edit", methods=["GET", "POST"])
@login_required
def import_tournament_edit():
    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    return render_template("import/tournament-edit.html", tournament=tournament)


@app.route("/import/tournament/add", methods=["GET", "POST"])
@login_required
def add_tournament():
    """Add the tournament"""

    if request.method == "POST":
        # Get tournament
        tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
        if len(tournament) != 1:
            return apology("more than one tournaments being imported", 400)
        tournament = tournament[0]

        # Update tournament name
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
        add_database_entry(db_name, entry, search_keys, update_keys)

        # Create organiser entries
        conveners = []
        for i in range(4):
            if request.form.get(f"convener-{i}"):
                conveners.append(request.form.get(f"convener-{i}"))

        for convener_id in conveners:
            candidates = db.execute(f"SELECT * FROM speakers WHERE id = {convener_id}")
            if len(candidates) != 1:
                return apology(f"convener id {convener_id} not found", 400)
            else:
                # Add convener as tournament participant
                participant = candidates[0]
                db_name = "tournament_participants"
                participant["tournament_id"] = tournament["id"]
                participant["speaker_id"] = convener_id
                participant["role"] = "convener"

                entry = participant
                search_keys = ["speaker_id", "tournament_id"]
                update_keys = ["role", "first_name", "last_name"]
                if participant["middle_name"] is not None:
                    update_keys.append("middle_name")
                add_database_entry(db_name, entry, search_keys, update_keys)

        return redirect("/import/speaker/categories")

    else:
        return apology("something went wrong", 400)


@app.route("/import/speaker/categories", methods=["GET", "POST"])
@login_required
def import_speaker_categories():
    """Import speakers and get input on speaker name format"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]
    domain = tournament["domain"]
    slug = tournament["slug"]

    # Import speaker data
    speaker_categories = lookup_data(tournament["domain"], tournament["slug"], "speaker-categories")

    # If there are no speaker categories, just proceed
    if len(speaker_categories) > 0:
        for category in speaker_categories:
            category["internal_id"] = category["url"].replace(f"https://{domain}/api/v1/tournaments/{slug}/speaker-categories/", "")
            category["achievement"] = "undefined"
            category["tournament_id"] = tournament["id"]

            # Import data into the db
            db_name = "speaker_categories"
            entry = category
            search_keys = ["internal_id", "tournament_id"]
            update_keys = ["name", "achievement"]
            add_database_entry(db_name, entry, search_keys, update_keys)
        return render_template("import/speaker-categories.html", speaker_categories=speaker_categories)
    else:
        return redirect("/import/speaker/format")


@app.route("/import/speaker/categories/add", methods=["GET", "POST"])
@login_required
def import_speaker_categories_add():
    """Add speaker categories to the db"""

    if request.method == "POST":
        # Get tournament
        tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
        if len(tournament) != 1:
            return apology("more than one tournaments being imported", 400)
        tournament_id = tournament[0]["id"]

        # Get categories
        speaker_categories = db.execute(f"SELECT * FROM speaker_categories WHERE tournament_id = {tournament_id}")
        if len(speaker_categories) < 1:
            return apology("no categories found", 400)

        for category in speaker_categories:
            # Get data from the form
            if request.form.get(str(category["internal_id"])+"-name") == "other":
                category["name"] = request.form.get(str(category["internal_id"])+"-name-other")
            else:
                category["name"] = request.form.get(str(category["internal_id"])+"-name")

            category["achievement"] = request.form.get(str(category["internal_id"])+"-achievement")
            category["tournament_id"] = tournament_id

            # Import data into the db
            db_name = "speaker_categories"
            entry = category
            search_keys = ["internal_id", "tournament_id"]
            update_keys = ["name", "achievement"]
            add_database_entry(db_name, entry, search_keys, update_keys)

        return redirect("/import/speaker/format")

    else:
        return redirect("/import/speaker/format")


@app.route("/import/speaker/format", methods=["GET", "POST"])
@login_required
def import_speakers():
    """Import speakers and get input on speaker name format"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]
    domain = tournament["domain"]
    slug = tournament["slug"]

    # Import speaker data
    speakers = []
    speakers = lookup_data(tournament["domain"], tournament["slug"], "speakers")

    # Import team data to show team name in the next screen. The same list will be used further in team import
    teams = lookup_data(tournament["domain"], tournament["slug"], "teams")
    for team in teams:
            # Add team to the DB
            db_name = "teams"
            team["tournament_id"] = tournament["id"]
            team["name"] = team["long_name"]
            team["internal_id"] = team["id"]
            # Add speakers' internal ids to be able to easily connect speaker ids to the team in the future
            team["speaker_internal_ids"] = []
            for speaker in team["speakers"]:
                team["speaker_internal_ids"].append(str(speaker["id"]))

            entry = team
            search_keys = ["internal_id", "tournament_id"]
            update_keys = ["name", "speaker_internal_ids"]
            add_database_entry(db_name, entry, search_keys, update_keys)

    if speakers != None:
        for participant in speakers:
            participant["role"] = "speaker"
            if "categories" in participant:
                if len(participant["categories"]) > 0:
                    new_categories = []
                    for category in participant["categories"]:
                        new_category = category.replace(f"https://{domain}/api/v1/tournaments/{slug}/speaker-categories/", "")
                        new_categories = new_categories + [new_category]
                    participant["categories"] = new_categories

            for team in teams:
                for member in team["speakers"]:
                    if participant["id"] == member["id"]:
                        participant["team_name"] = team["short_name"]

            # Add speaker as tournament participant
            db_name = "tournament_participants"
            participant["tournament_id"] = tournament["id"]
            participant["internal_name"] = participant["name"]
            participant["internal_id"] = participant["id"]

            entry = participant
            search_keys = ["internal_id", "tournament_id"]
            update_keys = ["internal_name", "role", "team_name"]
            if "categories" in participant:
                if len(participant["categories"]) > 0:
                    update_keys.append("categories")
            add_database_entry(db_name, entry, search_keys, update_keys)

        count = len(speakers)
        return render_template("import/speaker-format.html", speakers=speakers, count=count, tournament=tournament)
    else:
        return apology("speakers not imported", 400)


@app.route("/import/adjudicator/format", methods=["GET", "POST"])
@login_required
def import_adjudicators():
    """Import adjudicators and get input on speaker name format"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    # Record speaker name format from the previous page
    if request.method == "POST":
        # Ensure the format was chosen
        if not request.form.get("format"):
            return apology("must specify name format", 400)
        db.execute(f"UPDATE tournaments SET speaker_name_format = ? WHERE id = ?",
                   request.form.get("format"), tournament["id"])

    # Import adjudicator data
    adjudicators = lookup_data(tournament["domain"], tournament["slug"], "adjudicators")

    # Ensure the adjudicators are imported
    if adjudicators != None:
        for participant in adjudicators:
            participant["role"] = "adjudicator"
            if participant["adj_core"] == True:
                participant["role"] = "ca"

            # Add adjudicator as tournament participant
            db_name = "tournament_participants"
            participant["tournament_id"] = tournament["id"]
            participant["internal_name"] = participant["name"]
            participant["internal_id"] = participant["id"]

            entry = participant
            search_keys = ["internal_id", "tournament_id"]
            update_keys = ["internal_name", "role"]
            add_database_entry(db_name, entry, search_keys, update_keys)

        count = len(adjudicators)
        return render_template("import/adjudicator-format.html", speakers=adjudicators, count=count, tournament=tournament)
    else:
        return apology("adjudicators not imported", 400)


@app.route("/import/debater/check", methods=["GET", "POST"])
@login_required
def check_speakers():
    """Check that speaker names are mapped correctly"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    if request.method == "POST":
        # Ensure the format was chosen
        if not request.form.get("format"):
            return apology("must specify name format", 400)
        db.execute(f"UPDATE tournaments SET adjudicator_name_format = ? WHERE id = ?",
                   request.form.get("format"), tournament["id"])

        # Assign first, middle and last name to the speakers and adjudicators and clean up ids
        participants = db.execute(f"SELECT * FROM tournament_participants WHERE tournament_id = ?",
                                  tournament["id"])
        for participant in participants:
            if participant["role"] == "speaker":
                participant = split_name_by_format(participant, tournament["speaker_name_format"])
                db.execute(f"UPDATE tournament_participants SET first_name = ?, last_name = ?, middle_name = ? WHERE id = ?",
                           participant["first_name"], participant["last_name"], participant["middle_name"], participant["id"])
            if participant["role"] == "adjudicator" or participant["role"] == "ca":
                participant = split_name_by_format(participant, tournament["adjudicator_name_format"])
                db.execute(f"UPDATE tournament_participants SET first_name = ?, last_name = ?, middle_name = ? WHERE id = ?",
                           participant["first_name"], participant["last_name"], participant["middle_name"], participant["id"])

        participants = db.execute(f"SELECT * FROM tournament_participants WHERE tournament_id = ? AND role != 'convener'",
                                  tournament["id"])
        for participant in participants:
            participant["internal_id"] = str(participant["internal_id"])
            participant["request"] = ""
            for i in range(len(participant["internal_id"])):
                participant["request"] = participant["request"] + "\\\\3" + participant["internal_id"][i]
        if len(participants) > 0:
            return render_template("import/speaker-check.html", speakers=participants)
        else:
            return apology("no participants", 400)

    else:
        participants = db.execute(f"SELECT * FROM tournament_participants WHERE tournament_id = ? AND role != 'convener'",
                                  tournament["id"])
        for participant in participants:
            participant["internal_id"] = str(participant["internal_id"])
            participant["request"] = ""
            for i in range(len(participant["internal_id"])):
                participant["request"] = participant["request"] + "\\\\3" + participant["internal_id"][i]
        if len(participants) > 0:
            return render_template("import/speaker-check.html", speakers=participants)
        else:
            return apology("no participants", 400)


@app.route("/import/speaker/edit", methods=["GET", "POST"])
@login_required
def edit_speakers():
    """Confirm speaker import"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    if request.method == "POST":
        participants = db.execute(f"SELECT * FROM tournament_participants WHERE tournament_id = ? AND role != 'convener'",
                                  tournament["id"])

        # Assign first, middle and last name add internal id
        for participant in participants:
            if "internal_id" in participant:
                if request.form.get(str(participant["internal_id"])+"-swing"):
                    # Change swing name to swing in Russian
                    db.execute(f"UPDATE tournament_participants SET first_name = 'Свинг', last_name = 'Свингов', middle_name = 'Свингович', role = 'swing' WHERE id = ?",
                               participant["id"])
            else:
                participant["last_name"] = request.form.get(str(participant["internal_id"])+"-last-name")
                participant["first_name"] = request.form.get(str(participant["internal_id"])+"-first-name")
                participant["middle_name"] = request.form.get(str(participant["internal_id"])+"-middle-name")
                db.execute(f"UPDATE tournament_participants SET first_name = ?, last_name = ?, middle_name = ? WHERE id = ?",
                           participant["first_name"], participant["last_name"], participant["middle_name"], participant["id"])

        return redirect("/import/speaker/confirm")

    else:
        return apology("something went wrong", 400)


@app.route("/import/speaker/confirm", methods=["GET", "POST"])
@login_required
def confirm_speakers():
    """Confirm speaker import"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    # Get societies
    societies = db.execute("SELECT * FROM societies")

    # Check if the speaker is already in the database
    participants = db.execute(f"SELECT * FROM tournament_participants WHERE tournament_id = ? AND role != 'convener'",
                              tournament["id"])
    for participant in participants:
        if participant["middle_name"] != "":
            candidates = db.execute("SELECT * FROM speakers WHERE last_name = ? AND first_name = ? AND (middle_name = ? OR middle_name IS NULL)",
                                    participant["last_name"], participant["first_name"], participant["middle_name"])
        else:
            candidates = db.execute("SELECT * FROM speakers WHERE last_name = ? AND first_name = ?",
                                    participant["last_name"], participant["first_name"])
        if len(candidates) > 0:
            participant["candidates"] = candidates
        if len(candidates) == 1:
            if candidates[0]["society_id"] is not None:
                participant["society_id"] = candidates[0]["society_id"]

    return render_template("import/speaker-confirm.html", speakers=participants, societies=societies)


@app.route("/import/speaker/add", methods=["GET", "POST"])
@login_required
def add_speakers():
    """Add speakers to the database"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    # Get tournament participants
    speakers = db.execute(f"SELECT * FROM tournament_participants WHERE tournament_id = ? AND role != 'convener'",
                              tournament["id"])
    # Get speaker_categories
    speaker_categories = db.execute(f"SELECT * FROM speaker_categories WHERE tournament_id = ?",
                                    tournament["id"])
    if request.method == "POST":
        for speaker in speakers:
            # If speaker is in the db, connect general speaker id with tournament speaker id
            if request.form.get(str(speaker["internal_id"])+"-id"):
                speaker["id"] = request.form.get(str(speaker["internal_id"])+"-id")
                forego_search = False
            else:
                # Don't search the db, just update it
                forego_search = True
            speaker["society_id"] = request.form.get(str(speaker["internal_id"])+"-society-id")

            # Import debater data into the db
            db_name = "speakers"
            entry = speaker
            search_keys = ["id"]
            update_keys = ["first_name", "last_name"]
            if speaker["middle_name"] != "":
                update_keys.append("middle_name")
            if speaker["society_id"] is not None:
                update_keys.append("society_id")
            if forego_search:
                speaker["speaker_id"] = add_database_entry(db_name, entry, search_keys, update_keys, forego_search=True)
            else:
                speaker["speaker_id"] = add_database_entry(db_name, entry, search_keys, update_keys)
            # TODO speaker ID is required here, maybe add last_tournament_id to speaker entry to avoid search

            # Check that the speaker's ELO is correct
            if speaker["role"] == "speaker":
                sum_rating = db.execute(f"SELECT sum(rating_change) FROM speeches WHERE speaker_id = ?", speaker["speaker_id"])[0]["sum"]
                if sum_rating is not None:
                    db.execute("UPDATE speakers SET rating = 1500 + ? WHERE id = ?", sum_rating, speaker["speaker_id"])

            # Add speaker id to tournament participant
            db_name = "tournament_participants"
            search_keys = ["internal_id", "tournament_id"]
            update_keys = ["speaker_id"]
            add_database_entry(db_name, entry, search_keys, update_keys)

            # Add speaker categories
            if speaker["categories"] is not None:
                for instance in speaker["categories"]:
                    category = {}
                    db_name = "speakers_in_categories"
                    category["speaker_id"] = speaker["speaker_id"]
                    category["tournament_id"] = tournament["id"]
                    category["internal_id"] = int(instance)
                    for global_category in speaker_categories:
                        if category["internal_id"] == global_category["internal_id"]:
                            entry = category
                            category["category_id"] = global_category["id"]
                            search_keys = ["speaker_id", "tournament_id", "internal_id"]
                            update_keys = ["category_id"]
                            add_database_entry(db_name, entry, search_keys, update_keys)

        # Record average speaker ELO at the tournament
        tournament_average_rating(tournament)

        return redirect("/import/speaker/success")

    # Can only get here with post
    else:
        return apology("something went wrong", 400)


@app.route("/import/speaker/success", methods=["GET", "POST"])
@login_required
def speakers_success():
    """Show the speakers that have been added to the database"""
    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]
    # Get speakers
    speakers = db.execute(f"SELECT * FROM speakers RIGHT JOIN tournament_participants ON tournament_participants.speaker_id = speakers.id WHERE tournament_participants.tournament_id = ? AND tournament_participants.role != 'convener'",
                              tournament["id"])
    return render_template("import/speaker-success.html", speakers=speakers, tournament=tournament)


@app.route("/import/team", methods=["GET", "POST"])
@login_required
def import_teams():
    """Get teams"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    # Ensure the teams are imported
    teams = db.execute(f"SELECT * FROM teams WHERE tournament_id = ?",
                       tournament["id"])
    if teams == None:
        return apology("teams not imported", 400)

    for team in teams:
        team["tournament_id"] = tournament["id"]
        team_speakers = []
        for speaker in team["speaker_internal_ids"]:
            tournament_participant = db.execute(f"SELECT speaker_id, role FROM tournament_participants WHERE tournament_id = ? AND internal_id = ?",
                                    tournament["id"], speaker)[0]
            team_speakers.append(tournament_participant["speaker_id"])
            if tournament_participant["role"] == "swing":
                team["swing"] = 1
        team["speaker_one_id"] = team_speakers[0]
        if len(team_speakers) == 2:
            team["speaker_two_id"] = team_speakers[1]

        # Import team data into the db
        db_name = "teams"
        search_keys = ["internal_id", "tournament_id"]
        update_keys = ["swing", "speaker_one_id", "speaker_two_id"]
        add_database_entry(db_name, team, search_keys, update_keys)

    return redirect("/import/team/success")

@app.route("/import/team/success", methods=["GET", "POST"])
@login_required
def teams_success():
    """Show the speakers that have been added to the database"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    # Ensure the teams are imported
    teams = db.execute(f"SELECT * FROM teams WHERE tournament_id = ?",
                       tournament["id"])
    if teams == None:
        return apology("teams not imported", 400)

    return render_template("import/team-success.html", teams=teams)


@app.route("/import/round", methods=["GET", "POST"])
@login_required
def import_rounds():
    """Get rounds"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    # Prepare for link cleanup
    domain = tournament["domain"]
    slug = tournament["slug"]

    # Get break categories
    break_categories = lookup_data(tournament["domain"], tournament["slug"], "break-categories")
    for break_category in break_categories:
        break_category["internal_id"] = break_category["url"].replace(f"https://{domain}/api/v1/tournaments/{slug}/break-categories/", "")
        break_category["tournament_id"] = tournament["id"]
        if break_category["is_general"] == True:
            break_category["general"] = 1
        else:
            break_category["general"] = 0

        # Import break category data into the db
        db_name = "break_categories"
        entry = break_category
        search_keys = ["internal_id", "tournament_id"]
        update_keys = ["name", "general"]
        break_category["tournament_id"] = tournament["id"]
        add_database_entry(db_name, entry, search_keys, update_keys)

    # Import round data
    rounds = lookup_data(tournament["domain"], tournament["slug"], "rounds")
    if rounds == None:
        return apology("rounds not imported", 400)

    for round in rounds:
        # Import infoslide
        try:
            round["motion"] = lookup_link(round["url"])["motions"][0]["text"]
            round["info_slide"] = lookup_link(round["url"])["motions"][0]["info_slide"]
        except (KeyError, TypeError, ValueError):
            round["motion"] = None
            round["info_slide"] = None
        round["short_name"] = round["abbreviation"]
        if "break_category" in round:
            if round["break_category"] is not None:
                round["break_category_internal_id"] = round["break_category"].replace(f"https://{domain}/api/v1/tournaments/{slug}/break-categories/", "")
                round["break_category"] = db.execute(f"SELECT id FROM break_categories WHERE tournament_id = ? AND internal_id = ?",
                                                     tournament["id"], round["break_category_internal_id"])[0]["id"]
        round["tournament_id"] = tournament["id"]

        # Import round data into the db
        db_name = "rounds"
        search_keys = ["seq", "tournament_id"]
        update_keys = ["name", "short_name", "stage"]
        if round["motion"] != None:
            update_keys.append("motion")
        if round["info_slide"] != None:
            update_keys.append("info_slide")
        if round["break_category"] != None:
            update_keys.append("break_category")
        round["tournament_id"] = tournament["id"]
        add_database_entry(db_name, round, search_keys, update_keys)

    if len(rounds) > 0:
        return render_template("import/round-check.html", rounds=rounds, break_categories=break_categories)
    else:
        return apology("something went wrong", 400)


@app.route("/import/round-success", methods=["GET", "POST"])
@login_required
def add_rounds():
    """Import debates"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    # Get break_categories
    break_categories = db.execute(f"SELECT * FROM break_categories WHERE tournament_id = ?",
                                  tournament["id"])

    # Get rounds
    rounds = db.execute(f"SELECT * FROM rounds WHERE tournament_id = ? ORDER BY seq",
                        tournament["id"])

    if request.method == "POST":
        for break_category in break_categories:
            # Get data from the form
            new_name = ""
            if request.form.get(str(break_category["internal_id"])+"-break-category") == "other":
                new_name = request.form.get(str(break_category["internal_id"])+"-break-category-other")
            else:
                new_name = request.form.get(str(break_category["internal_id"])+"-break-category")
            if break_category["name"] != new_name:
                break_category["name"] = new_name
                break_category["tournament_id"] = tournament["id"]

                # Update break categories data in the db
                db_name = "break_categories"
                search_keys = ["internal_id", "tournament_id"]
                update_keys = ["name"]
                add_database_entry(db_name, break_category, search_keys, update_keys)

        for round in rounds:
            # Get data from the form
            round["name"] = request.form.get(str(round["seq"])+"-name")
            round["short_name"] = request.form.get(str(round["seq"])+"-short-name")
            round["motion"] = request.form.get(str(round["seq"])+"-motion")
            round["info_slide"] = request.form.get(str(round["seq"])+"-info-slide")
            round["achievement"] = request.form.get(str(round["seq"])+"-achievement")
            round["tournament_id"] = tournament["id"]

            # Import round data into the db
            db_name = "rounds"
            search_keys = ["seq", "tournament_id"]
            update_keys = ["name", "short_name", "achievement"]
            if round["motion"] != "None" and round["motion"] != None:
                update_keys.append("motion")
            if round["info_slide"] != "None" and round["info_slide"] != None:
                update_keys.append("info_slide")
            add_database_entry(db_name, round, search_keys, update_keys)

    return render_template("import/round-success.html", rounds=rounds, break_categories=break_categories)


@app.route("/import/debates", methods=["GET", "POST"])
@login_required
def import_debates():
    """Import debates"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    rounds = db.execute(f"SELECT * FROM rounds WHERE tournament_id = ? ORDER BY seq",
                       tournament["id"])

    for round in rounds:
        if round["import_complete"] == 0:
            db.execute(f"DELETE FROM rounds where id = ?", round["id"])

            # Re-Import round data into the db
            db_name = "rounds"
            search_keys = ["seq", "tournament_id"]
            update_keys = ["name", "short_name", "stage"]
            if round["motion"] != None:
                update_keys.append("motion")
            if round["info_slide"] != None:
                update_keys.append("info_slide")
            if round["break_category"] != None:
                update_keys.append("break_category")
            round["tournament_id"] = tournament["id"]
            add_database_entry(db_name, round, search_keys, update_keys)

    rounds = db.execute(f"SELECT * FROM rounds WHERE tournament_id = ? AND import_complete IS null ORDER BY seq",
                        tournament["id"])

    if len(rounds) == 0:
        db.execute(f"UPDATE rounds SET import_complete = NULL WHERE tournament_id = ?",
                   tournament["id"])
        rounds = db.execute(f"SELECT * FROM rounds WHERE tournament_id = ? AND import_complete IS null ORDER BY seq",
                            tournament["id"])

    # Prepare for link cleanup
    domain = tournament["domain"]
    slug = tournament["slug"]

    # Get debates (pairings)
    round = rounds[0]
    db.execute(f"UPDATE rounds SET import_complete = 0 WHERE id = ?", round["id"])

    seq = round["seq"]
    debates = lookup_link(f"https://{domain}/api/v1/tournaments/{slug}/rounds/{seq}/pairings")
    if debates == None:
        offending_link = round["_links"]["pairing"]
        return apology(f"pairings not imported: {offending_link}", 400)
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
        # TODO need to put select debate["id"] here if I remove it in add_database_entry

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
            adjudicator["speaker_id"] = db.execute(f"SELECT speaker_id FROM tournament_participants WHERE internal_id = {adjudicator_internal_id} AND tournament_id = {tournament_id}")[0]["speaker_id"]
            adjudicator["role"] = "chair"

            # Import adjudication instance into the db
            db_name = "adjudications"
            search_keys = ["speaker_id", "tournament_id", "debate_id"]
            update_keys = ["role"]
            add_database_entry(db_name, adjudicator, search_keys, update_keys)

            if "panellists" in debate["adjudicators"]:
                for panellist in debate["adjudicators"]["panellists"]:
                    adjudicator["internal_id"] = panellist.replace(f"https://{domain}/api/v1/tournaments/{slug}/adjudicators/", "")
                    adjudicator_internal_id = adjudicator["internal_id"]
                    adjudicator["speaker_id"] = db.execute(f"SELECT speaker_id FROM tournament_participants WHERE internal_id = {adjudicator_internal_id} AND tournament_id = {tournament_id}")[0]["speaker_id"]
                    adjudicator["role"] = "panellist"

                    # Import adjudication instance into the db
                    db_name = "adjudications"
                    search_keys = ["speaker_id", "tournament_id", "debate_id"]
                    update_keys = ["role"]
                    add_database_entry(db_name, adjudicator, search_keys, update_keys)

            if "trainees" in debate["adjudicators"]:
                for trainee in debate["adjudicators"]["trainees"]:
                    adjudicator["internal_id"] = trainee.replace(f"https://{domain}/api/v1/tournaments/{slug}/adjudicators/", "")
                    adjudicator_internal_id = adjudicator["internal_id"]
                    adjudicator["speaker_id"] = db.execute(f"SELECT speaker_id FROM tournament_participants WHERE internal_id = {adjudicator_internal_id} AND tournament_id = {tournament_id}")[0]["speaker_id"]
                    adjudicator["role"] = "trainee"

                    # Import adjudication instance into the db
                    db_name = "adjudications"
                    search_keys = ["speaker_id", "tournament_id", "debate_id"]
                    update_keys = ["role"]
                    add_database_entry(db_name, adjudicator, search_keys, update_keys)

        # Get results
        results = lookup_link(debate["url"] + "/ballots")
        # Get to the team result
        if results is None:
            return apology(f"tabmaster needs to publish ballots", 400)
        else:
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
                result["ironman"] = 0
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
                update_keys = ["side", "score", "ironman"]
                add_database_entry(db_name, entry, search_keys, update_keys)

                # Get speeches
                if "speeches" in result:
                    i = 0
                    for speech in result["speeches"]:
                        # Add and clean speech data
                        speech["tournament_id"] = tournament["id"]
                        speech["debate_id"] = debate["id"]
                        speech["team_id"] = result["team_id"]
                        speech["score"] = int(speech["score"])
                        speech["ironman"] = 0
                        if speech["ghost"] == True:
                            speech["ironman"] = 1
                            result["ironman"] = 1
                            # Set team_performances to ironman
                            db_name = "team_performances"
                            entry = result
                            search_keys = ["debate_id", "tournament_id", "team_id"]
                            update_keys = ["ironman"]
                            add_database_entry(db_name, entry, search_keys, update_keys)
                        # Get speaker's db id
                        speech["speaker_internal_id"] = speech["speaker"].replace(f"https://{domain}/api/v1/tournaments/{slug}/speakers/", "")
                        speech["speaker_id"] = db.execute(f"SELECT speaker_id FROM tournament_participants WHERE internal_id = ? AND tournament_id = ?",
                                                            speech["speaker_internal_id"], tournament["id"])[0]["speaker_id"]
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
                        search_keys = ["debate_id", "tournament_id", "speaker_id", "position"]
                        update_keys = ["score", "team_id", "ironman"]
                        add_database_entry(db_name, entry, search_keys, update_keys)
                # For elimination rounds
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

                        speech["team_id"] = result["team_id"]
                        # Import speech data into the db
                        db_name = "speeches"
                        entry = speech
                        search_keys = ["debate_id", "tournament_id", "speaker_id"]
                        update_keys = ["position", "team_id"]
                        add_database_entry(db_name, entry, search_keys, update_keys)

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
                            add_database_entry(db_name, entry, search_keys, update_keys)

                            if round["final"] and result["win"]:
                                speech["name"] = "победитель"
                                # Import achievement data into the db
                                db_name = "achievements"
                                entry = speech
                                search_keys = ["tournament_id", "type", "speaker_id"]
                                update_keys = ["name", "break_category"]
                                add_database_entry(db_name, entry, search_keys, update_keys)

    db.execute(f"UPDATE rounds SET import_complete = 1 WHERE id = ?", round["id"])
    rounds = db.execute(f"SELECT * FROM rounds WHERE tournament_id = ? AND import_complete is null ORDER BY seq",
                        tournament["id"])
    if len(rounds) == 0:
        return redirect("/import/debate/success")

    else:
        return redirect("/import/debates")


@app.route("/import/debate/success", methods=["GET", "POST"])
@login_required
def debates_success():
    """Show the rounds that have been added to the database"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    # Get rounds
    rounds = db.execute(f"SELECT * FROM rounds WHERE tournament_id = ? ORDER BY seq",
                       tournament["id"])
    debates = db.execute(f"SELECT * FROM debates WHERE tournament_id = ?",
                         tournament["id"])
    speeches = db.execute(f"SELECT * FROM speeches WHERE tournament_id = ?",
                          tournament["id"])
    team_performances = db.execute(f"SELECT * FROM team_performances WHERE tournament_id = ?",
                          tournament["id"])

    for round in rounds:
        round["debates"] = []
        for debate in debates:
            if debate["round_id"] == round["id"]:
                round["debates"].append(debate)
        for debate in round["debates"]:
            for speech in speeches:
                if speech["debate_id"] == debate["id"]:
                    position = speech["position"]
                    debate[str(position)] = speech["score"]
            for performance in team_performances:
                if performance["debate_id"] == debate["id"]:
                    side = performance["side"]
                    debate[side] = performance["score"]

    return render_template("import/debate-success.html", rounds=rounds)


@app.route("/import/elo", methods=["GET", "POST"])
@login_required
def update_elo():
    """Calculate and update new ELO values"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    # Get the list of rounds
    rounds = db.execute("SELECT id FROM rounds WHERE tournament_id = ? ORDER BY seq",
                        tournament["id"])
    calculate_elo(rounds, tournament)

    return redirect("/import/elo/success")


@app.route("/import/elo/success", methods=["GET", "POST"])
@login_required
def elo_success():
    """Show the rounds that have been added to the database"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    # Get speeches
    speeches = db.execute(f"SELECT * FROM speeches WHERE tournament_id = ?",
                          tournament["id"])

    return render_template("import/elo.html", speeches=speeches)

@app.route("/import/speaker-scores", methods=["GET", "POST"])
@login_required
def calculate_speaker_scores():
    """Calculate new average speaker scores, record best speakers"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    # Update new speaker score
    speakers = db.execute(f"SELECT * FROM tournament_participants WHERE tournament_id = ?", tournament["id"])
    for speaker in speakers:
        if speaker["role"] == "speaker":
            new_average = db.execute("SELECT avg(score) FROM speeches WHERE speaker_id = ?",
                                     speaker["speaker_id"])[0]["avg"]
            if new_average != None:
                speaker["new_average"] = round(new_average, 2)
                db.execute("UPDATE speakers SET speaker_score = ? WHERE id = ?",
                           speaker["new_average"], speaker["speaker_id"])

    # Get best speaker(s)
    tournament_id = tournament["id"]
    best_speakers = db.execute(open("sql_get_best_speaker.sql").read().replace("xxxxxx", str(tournament_id)))
    if len(best_speakers) < 1:
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
        add_database_entry(db_name, entry, search_keys, update_keys)

    # Get best speakers for all of the categories
    speaker_categories = db.execute(f"SELECT * FROM speaker_categories WHERE tournament_id = {tournament_id}")
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
            add_database_entry(db_name, entry, search_keys, update_keys)

    # Update global rankings by speaker scores and ELO
    update_rankings("both")

    speakers = db.execute(f"SELECT * FROM speakers RIGHT JOIN tournament_participants ON speakers.id = tournament_participants.speaker_id WHERE tournament_participants.tournament_id = ?", tournament["id"])

    return render_template("import/speaker-scores.html", speakers=speakers)


@app.route("/import/best-adjudicator", methods=["GET", "POST"])
@login_required
def get_best_adjudicator():
    """Get best adjudicator(s)"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    adjudicators = db.execute(f"SELECT tp.*, s.first_name, s.last_name FROM tournament_participants tp INNER JOIN speakers s ON tp.speaker_id = s.id WHERE tournament_id = ? AND role = 'adjudicator'",
                              tournament["id"])

    return render_template("import/best-adjudicator.html", adjudicators=adjudicators)


@app.route("/import/best-adjudicator/success", methods=["GET", "POST"])
@login_required
def import_best_adjudicator():
    """Record best adjudicator(s) in the db"""

    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) != 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    if request.method == "POST":
        best_adjudicators = []
        # Get data from form 1
        if request.form.get("1") != "no":
            best_adjudicators.append({"speaker_id": request.form.get("1")})
        if request.form.get("2") != "no":
            best_adjudicators.append({"speaker_id": request.form.get("2")})
        if request.form.get("3") != "no":
            best_adjudicators.append({"speaker_id": request.form.get("3")})
        if len(best_adjudicators) > 0:
            no_adjudicator = False
            for adjudicator in best_adjudicators:
                # Prepare data to be added into the db
                adjudicator["tournament_id"] = tournament["id"]
                adjudicator["type"] = "adjudicator"
                adjudicator["name"] = "лучший судья"
                # Import achievement data into the db
                db_name = "achievements"
                entry = adjudicator
                search_keys = ["tournament_id", "speaker_id", "type"]
                update_keys = ["name"]
                add_database_entry(db_name, entry, search_keys, update_keys)
                # Get name for confirmation
                speaker_db = db.execute("SELECT first_name, last_name FROM speakers WHERE id = ?",
                                                    adjudicator["speaker_id"])[0]
                adjudicator["first_name"] = speaker_db["first_name"]
                adjudicator["last_name"] = speaker_db["last_name"]
        else:
            no_adjudicator = True
    else:
        no_adjudicator = True

    return render_template("import/best-adjudicator-success.html", best_adjudicators=best_adjudicators, no_adjudicator=no_adjudicator)


@app.route("/import/success", methods=["GET", "POST"])
@login_required
def import_complete():
    # Get tournament
    tournament = db.execute("SELECT * FROM tournaments WHERE import_complete = 0")
    if len(tournament) > 1:
        return apology("more than one tournaments being imported", 400)
    tournament = tournament[0]

    db.execute("UPDATE tournaments SET import_complete = 1 WHERE import_complete = 0")

    return render_template("import/success.html", tournament=tournament)



"""Admin Actions"""



@app.route("/recalculate-elo", methods=["GET", "POST"])
@login_required
def recalculate_elo_start():
    """Recalculate ELO for all tournaments values"""

    return render_template("admin/recalculate-elo.html")


@app.route("/recalculate-elo-success", methods=["GET", "POST"])
@login_required
def recalculate_elo():
    """Recalculate ELO for all tournaments values"""

    # Clear the tournaments that haven't been imported completely
    db.execute("DELETE FROM tournaments WHERE import_complete = 0")

    # Get tournaments
    tournaments = db.execute("SELECT * FROM tournaments WHERE update_complete = 0 ORDER BY date")
    if len(tournaments) == 0:
        tournaments = db.execute("SELECT * FROM tournaments WHERE update_complete = 1")
        if len(tournaments) == 0:
            # start update
            db.execute("UPDATE tournaments SET update_complete = 0")
            # Set everyone's ELO to 1500
            db.execute("UPDATE speakers SET rating = 1500")
            db.execute("UPDATE speeches SET rating_change = 0")
            tournaments = db.execute("SELECT * FROM tournaments WHERE update_complete = 0 ORDER BY date")
        else:
            update_rankings("rating")
            db.execute("UPDATE tournaments SET update_complete = NULL")
            return render_template("admin/recalculate-elo-success.html")

    # Recalculate ELO
    tournament = tournaments[0]
    tournament_average_rating(tournament)

    # Get the list of rounds
    rounds = db.execute(f"SELECT id FROM rounds WHERE tournament_id = ? ORDER BY seq",
                        tournament["id"])
    calculate_elo(rounds, tournament)

    db.execute(f"UPDATE tournaments SET update_complete = 1 WHERE id = ?", tournament["id"])

    return redirect("/recalculate-elo-success")


@app.route("/add-speaker", methods=["GET", "POST"])
@login_required
def add_speaker():
    """Add a single speaker"""

    if request.method == "POST":
        speaker = {}
        speaker["last_name"] = request.form.get("last-name")
        speaker["first_name"] = request.form.get("first-name")
        speaker["middle_name"] = request.form.get("middle-name")
        speaker["society_id"] = request.form.get("society")
        if len(speaker["middle_name"]) < 1:
            candidates = db.execute(f"SELECT * FROM speakers WHERE last_name = ? AND first_name = ?",
                       speaker["last_name"], speaker["first_name"])
        else:
            candidates = db.execute(f"SELECT * FROM speakers WHERE last_name = ? AND first_name = ? AND middle_name = ?",
                       speaker["last_name"], speaker["first_name"], speaker["middle_name"])
        if len(candidates) != 0:
            return apology("speaker already exists", 400)
        else:
            update_keys = ["last_name", "first_name"]
            if len(speaker["middle_name"]) > 0:
                update_keys.append("middle_name")
            if speaker["society_id"] is not None:
                update_keys.append("society_id")
            execute_insert("speakers", speaker, update_keys)

            if len(speaker["middle_name"]) < 1:
                speaker = db.execute(f"SELECT * FROM speakers WHERE last_name = ? AND first_name = ?",
                                speaker["last_name"], speaker["first_name"])[0]
            else:
                speaker = db.execute(f"SELECT * FROM speakers WHERE last_name = ? AND first_name = ? AND middle_name = ?",
                                speaker["last_name"], speaker["first_name"], speaker["middle_name"])[0]

            return render_template("admin/add-speaker-success.html", speaker=speaker)

    else:
        societies = db.execute(f"SELECT * FROM societies")

        return render_template("admin/add-speaker.html", societies=societies)


@app.route("/edit-speaker", methods=["GET", "POST"])
@login_required
def edit_speaker():
    if request.method == "POST":
        speaker = {}
        speaker["id"] = request.form.get("speaker-id")
        if not request.form.get("last-name"):
            return apology("must provide last_name", 400)
        if not request.form.get("first-name"):
            return apology("must provide first_name", 400)
        speaker["last_name"] = request.form.get("last-name")
        speaker["first_name"] = request.form.get("first-name")
        speaker["middle_name"] = request.form.get("middle-name")
        speaker["society_id"] = request.form.get("society-id")
        if speaker["society_id"] == "no":
            speaker["society_id"] = None
        if len(speaker["middle_name"]) < 1:
            candidates = db.execute(f"SELECT * FROM speakers WHERE last_name = ? AND first_name = ?",
                                    speaker["last_name"], speaker["first_name"])
        else:
            candidates = db.execute(f"SELECT * FROM speakers WHERE last_name = ? AND first_name = ? AND middle_name = ?",
                                    speaker["last_name"], speaker["first_name"], speaker["middle_name"])
        if len(candidates) > 0:
            if len(candidates) > 1:
                return apology("more that one speaker with these first_name and last_name", 400)
            if candidates[0]["id"] != int(speaker["id"]):
                candidate = candidates[0]["id"]
                speaker = speaker["id"]
                return apology(f"speaker already exists: {candidate}, {speaker}", 400)
        db_name = "speakers"
        entry = speaker
        search_keys = ["id"]
        update_keys = ["last_name", "first_name", "middle_name"]
        if len(speaker["middle_name"]) == 0:
            speaker["middle_name"] = None
        if request.form.get("society-id"):
            update_keys.append("society_id")
        add_database_entry(db_name, entry, search_keys, update_keys)

        return render_template("admin/edit-speaker-success.html", speaker=speaker)

    else:
        if not request.args.get("id"):
            return apology("must provide debater id", 400)

        speaker = db.execute(f"SELECT * FROM speakers WHERE id = ?", request.args.get("id"))[0]
        societies = db.execute(f"SELECT * FROM societies")

        if speaker["middle_name"] is None:
            del speaker["middle_name"]

        return render_template("admin/edit-speaker.html", societies=societies, speaker=speaker)


@app.route("/add-society", methods=["GET", "POST"])
@login_required
def add_society():
    """Add a society"""

    if request.method == "POST":
        society = {}
        society["name"] = request.form.get("name")
        society["short_name"] = request.form.get("short-name")
        society["city"] = request.form.get("city")
        society["page"] = request.form.get("page")
        candidates = db.execute(f"SELECT * FROM societies WHERE name = ? OR short_name = ?",
                                society["name"], society["short_name"])
        if len(candidates) != 0:
            return apology("society already exists", 400)
        else:
            update_keys = ["name", "short_name"]
            if len(society["city"]) > 0:
                update_keys.append("city")
            if len(society["page"]) > 0:
                update_keys.append("page")
            execute_insert("societies", society, update_keys)
            society = db.execute(f"SELECT * FROM societies WHERE name = ? AND short_name = ?",
                                 society["name"], society["short_name"])[0]

            return render_template("admin/add-society-success.html", society=society)

    else:
        return render_template("admin/add-society.html")


@app.route("/add-society-speakers", methods=["GET", "POST"])
@login_required
def import_society_speakers():
    """Import society's speakers"""

    if request.method == "POST":
        society_id = request.form.get("society")
        speakers = request.form.get("speakers").split(",")
        speakers_updated = []
        speakers_not_updated = []
        for speaker_id in speakers:
            candidates = db.execute(f"SELECT * FROM speakers WHERE id = {speaker_id}")
            if len(candidates) != 1:
                speakers_not_updated.append(speaker_id)
            else:
                db.execute(f"UPDATE speakers SET society_id = {society_id} WHERE id = {speaker_id}")
                speakers_updated.append(speaker_id)
        return render_template("admin/add-society-speakers-success.html", speakers_updated=speakers_updated, speakers_not_updated=speakers_not_updated, society_id=society_id)
    else:
        societies = db.execute(f"SELECT * FROM societies")

        return render_template("admin/add-society-speakers.html", societies=societies)


@app.route("/join-speakers", methods=["GET", "POST"])
@login_required
def join_speakers():
    if request.method == "POST":
        if not request.form.get("id-1"):
            return apology("speaker_one not specified", 400)
        speaker_one_id = request.form.get("id-1")
        if not request.form.get("id-2"):
            return apology("speaker_two not specified", 400)
        speaker_two_id = request.form.get("id-2")

        # Check if they've participated in a single comp
        participations = db.execute(f"SELECT count(id) as count, tournament_id FROM tournament_participants WHERE speaker_id = {speaker_one_id} OR speaker_id = {speaker_two_id} GROUP BY tournament_id ORDER BY count DESC")
        if participations[0]["count"] > 1:
            tournament_id = participations[0]["tournament_id"]
            return apology(f"Speakers appear in the same tournament {tournament_id}", 400)

        # Replace speaker two with speaker one
        db.execute(f"UPDATE teams SET speaker_one_id = {speaker_one_id} WHERE speaker_one_id = {speaker_two_id}")
        db.execute(f"UPDATE teams SET speaker_two_id = {speaker_one_id} WHERE speaker_two_id = {speaker_two_id}")
        db.execute(f"UPDATE speeches SET speaker_id = {speaker_one_id} WHERE speaker_id = {speaker_two_id}")
        db.execute(f"UPDATE tournament_participants SET speaker_id = {speaker_one_id} WHERE speaker_id = {speaker_two_id}")
        db.execute(f"UPDATE adjudications SET speaker_id = {speaker_one_id} WHERE speaker_id = {speaker_two_id}")
        db.execute(f"UPDATE achievements SET speaker_id = {speaker_one_id} WHERE speaker_id = {speaker_two_id}")
        db.execute(f"UPDATE speakers_in_categories SET speaker_id = {speaker_one_id} WHERE speaker_id = {speaker_two_id}")

        # Remove speaker two
        db.execute(f"DELETE FROM speakers WHERE id = {speaker_two_id}")

        return render_template("admin/join-speakers-success.html", speaker_one_id=speaker_one_id, speaker_two_id=speaker_two_id)

    else:
        speakers = db.execute(f"SELECT * FROM speakers")

        return render_template("admin/join-speakers.html", speakers=speakers)


@app.route("/edit-tournament-data", methods=["GET", "POST"])
@login_required
def edit_tournament_data():
    if request.method == "POST":
        # Update data
        tournament = {}
        tournament["id"] = request.form.get("tournament-id")
        tournament["name"] = request.form.get("name")
        tournament["short_name"] = request.form.get("short-name")
        tournament["date"] = request.form.get("date")
        tournament["type"] = request.form.get("type")
        tournament["page"] = request.form.get("link")
        if len(tournament["page"]) == 0:
            tournament["page"] = None

        # Import data into the db
        db_name = "tournaments"
        entry = tournament
        search_keys = ["id"]
        update_keys = ["name", "short_name", "date", "type", "page"]
        add_database_entry(db_name, entry, search_keys, update_keys)

        return render_template("admin/edit-tournament-data-success.html", tournament=tournament)

    else:
        if not request.args.get("id"):
                return apology("must provide tournament id", 400)
        # Get tournament
        tournament = db.execute(f"SELECT * FROM tournaments WHERE id = ?", request.args.get("id"))
        if len(tournament) != 1:
            return apology("tournament not found", 400)
        tournament = tournament[0]

        return render_template("admin/edit-tournament-data.html", tournament=tournament)


@app.route("/edit-tournament-adjudicators", methods=["GET", "POST"])
@login_required
def edit_tournament_adjudicators():
    if request.method == "POST":
        tournament_id = request.form.get("tournament-id")
        # Get judges
        tournament_participants = db.execute(f"SELECT * FROM tournament_participants WHERE tournament_id = {tournament_id} AND (role = 'adjudicator'  OR role = 'ca')")

        for participant in tournament_participants:
            role = request.form.get("role-" + str(participant["id"]))
            if role != participant["role"]:
                db.execute(f"UPDATE tournament_participants SET role = ? WHERE tournament_id = {tournament_id} AND id = ?", role, participant["id"])

        tournament_participants = db.execute(f"SELECT * FROM tournament_participants WHERE tournament_id = {tournament_id} AND (role = 'adjudicator'  OR role = 'ca')")
        return render_template("admin/edit-tournament-adjudicators-success.html", tournament_participants=tournament_participants, tournament_id=tournament_id)

    else:
        if not request.args.get("id"):
                return apology("must provide tournament id", 400)
        tournament_id = request.args.get("id")
        # Get judges
        tournament_participants = db.execute(f"SELECT * FROM tournament_participants WHERE tournament_id = {tournament_id} AND (role = 'adjudicator'  OR role = 'ca')")

        return render_template("admin/edit-tournament-adjudicators.html", tournament_participants=tournament_participants, tournament_id=tournament_id)



""" Info Pages """



@app.route("/speakers", methods=["GET", "POST"])
def speaker_list():
    """Show speaker ranking"""

    speakers = db.execute("SELECT * FROM speakers ORDER BY speaker_score DESC")

    return render_template("speakers.html", speakers=speakers)


@app.route("/societies", methods=["GET", "POST"])
def society_list():
    """Show societies"""

    societies = db.execute("SELECT * FROM societies ORDER BY name")

    return render_template("society/societies.html", societies=societies)


@app.route("/society", methods=["GET", "POST"])
def society():
    """Show society's speakers"""

    if not request.args.get("id"):
            return apology("must provide society id", 400)

    id = request.args.get("id")

    society = db.execute(f"SELECT * FROM societies WHERE id = {id}")[0]

    speakers = db.execute(f"SELECT * FROM speakers WHERE society_id = ? ORDER BY speaker_score DESC",
                          society["id"])

    return render_template("society/society.html", speakers=speakers, society=society)


@app.route("/tournaments", methods=["GET", "POST"])
def tournament_list():
    """Show societies"""

    tournaments = db.execute("SELECT * FROM tournaments WHERE import_complete = 1 ORDER BY date DESC")

    return render_template("tournament/tournaments.html", tournaments=tournaments)


@app.route("/tournament", methods=["GET", "POST"])
def tournament():
    """Show tournament profile"""

    if not request.args.get("id"):
            return apology("must provide tournament id", 400)

    id = request.args.get("id")

    tournament = db.execute(f"SELECT * FROM tournaments WHERE id = {id}")[0]

    # Get speaker achievements
    achievements = db.execute(f"SELECT a.*, bc.name AS break_category_name, sc.name AS speaker_category_name, s.last_name, s.first_name, s.id AS speaker_id FROM achievements a LEFT JOIN break_categories bc ON a.break_category = bc.id LEFT JOIN speaker_categories sc ON a.speaker_category = sc.id INNER JOIN speakers s on a.speaker_id = s.id WHERE a.tournament_id = {id}")
    break_categories_len = len(db.execute(f"SELECT id FROM break_categories WHERE tournament_id = {id}"))
    speaker_categories_len = len(db.execute(f"SELECT id FROM speaker_categories WHERE tournament_id = {id}"))
    # Order achievements by importance
    for achievement in achievements:
        if achievement["type"] == "team":
            if achievement["name"] == "победитель":
                achievement["priority"] = achievement["break_category"]
            elif achievement["name"] == "финалист":
                achievement["priority"] = break_categories_len + speaker_categories_len + 2 + achievement["break_category"]
            elif achievement["name"] == "полуфиналист":
                achievement["priority"] = ( break_categories_len * 2 ) + speaker_categories_len + 2 + achievement["break_category"]
            elif achievement["name"] == "четвертьфиналист":
                achievement["priority"] = ( break_categories_len * 3 ) + speaker_categories_len + 2 + achievement["break_category"]
            elif achievement["name"] == "октофиналист":
                achievement["priority"] = ( break_categories_len * 4 ) + speaker_categories_len + 2 + achievement["break_category"]
            else:
                achievement["priority"] = ( break_categories_len * 5 ) + speaker_categories_len + 3
        if achievement["type"] == "speaker":
            if achievement["speaker_category"] == None:
                achievement["priority"] = break_categories_len + 1
            else:
                achievement["priority"] = break_categories_len + achievement["speaker_category"] + 1
        if achievement["type"] == "adjudicator":
            achievement["priority"] = break_categories_len + speaker_categories_len + 2
    achievements = sorted(achievements, key=itemgetter("priority"))

    # Get rounds
    rounds = db.execute(f"SELECT * FROM rounds WHERE tournament_id = {id} ORDER BY seq")

    # Get participants to show judges and conveners
    participants = db.execute(f"SELECT s.first_name, s.last_name, p.role, s.id FROM tournament_participants p INNER JOIN speakers s ON p.speaker_id = s.id WHERE tournament_id = {id}")

    # Get speaker categories to make links to speaker tabs
    speaker_categories = db.execute(f"SELECT id, name FROM speaker_categories WHERE tournament_id = {id}")

    return render_template("tournament/tournament.html", tournament=tournament, achievements=achievements, rounds=rounds, participants=participants, speaker_categories=speaker_categories)


@app.route("/speaker-tab", methods=["GET", "POST"])
def speaker_tab():
    """Show speaker tab for a tournament"""

    if not request.args.get("id"):
            return apology("must provide tournament id", 400)

    id = request.args.get("id")

    tournament = db.execute(f"SELECT * FROM tournaments WHERE id = {id}")[0]

    if not request.args.get("category"):
        # Get all tournament speakers
        speakers = db.execute(f"SELECT speeches.speaker_id, avg(speeches.score) AS average_score, sum(speeches.rating_change) AS rating, speakers.first_name, speakers.last_name FROM speeches INNER JOIN speakers ON speeches.speaker_id = speakers.id WHERE tournament_id = {id} GROUP BY speaker_id, speakers.first_name, speakers.last_name")
        # No category needed
        category_text = ""
    else:
        # Get speakers in this category
        category_id = request.args.get("category")
        speakers = db.execute(f"SELECT speeches.speaker_id, avg(speeches.score) AS average_score, sum(speeches.rating_change) AS rating, speakers.first_name, speakers.last_name FROM speeches INNER JOIN speakers ON speeches.speaker_id = speakers.id INNER JOIN speakers_in_categories sic ON speeches.speaker_id = sic.speaker_id WHERE speeches.tournament_id = {id} AND sic.category_id = {category_id} GROUP BY speeches.speaker_id, speakers.first_name, speakers.last_name")
        category = db.execute(f"SELECT name FROM speaker_categories WHERE id = {category_id} AND tournament_id = {id}")[0]
        category_text = " (" + category["name"] + ")"

    # Give speakers 0 average score if they have no average
    for speaker in speakers:
        if speaker["average_score"] == None:
            speaker["average_score"] = 0
        speaker["average_score"] = round(speaker["average_score"], 2)
    # Sort speakers by speaker points
    speakers = sorted(speakers, key=itemgetter("average_score"), reverse=True)
    i = 1
    previous_score = 101
    current_ranking = 0
    for speaker in speakers:
        if speaker["average_score"] < previous_score:
            current_ranking = i
            previous_score = speaker["average_score"]
        speaker["ranking_by_speaks"] = current_ranking
        i = i + 1

    return render_template("tournament/speaker-tab.html", tournament=tournament, speakers=speakers, category_text=category_text)


@app.route("/team-tab", methods=["GET", "POST"])
def team_tab():
    """Show speaker tab for a tournament"""

    if not request.args.get("id"):
            return apology("must provide tournament id", 400)

    id = request.args.get("id")

    tournament = db.execute(f"SELECT * FROM tournaments WHERE id = {id}")[0]

    if not request.args.get("category"):
        # Get all tournament teams
        teams = db.execute(open("sql_get_team_tab.sql").read().replace("xxxxxx", str(id)))
        # No category needed
        category_text = ""
    else:
        # Get teams in this category
        category_id = request.args.get("category")
        teams = db.execute(open("sql_get_team_tab_category.sql").read().replace("xxxxxx", str(id)).replace("yyyyyy", category_id))
        category = db.execute(f"SELECT name FROM speaker_categories WHERE id = {category_id} AND tournament_id = {id}")[0]
        category_text = " (" + category["name"] + ")"

    # Sort teams by team points
    i = 1
    previous_score = 101
    current_ranking = 0
    for team in teams:
        if team["team_score"] < previous_score:
            current_ranking = i
            previous_score = team["team_score"]
        team["ranking"] = current_ranking
        i = i + 1

    return render_template("tournament/team-tab.html", tournament=tournament, teams=teams, category_text=category_text)


@app.route("/round", methods=["GET", "POST"])
def round_debates():
    """Show speaker tab for a tournament"""

    if not request.args.get("id"):
            return apology("must provide round id", 400)

    round_id = request.args.get("id")

    round = db.execute(f"SELECT r.*, t.short_name AS tournament_name FROM rounds r INNER JOIN tournaments t ON r.tournament_id = t.id WHERE r.id = {round_id}")[0]

    debates = db.execute(f"SELECT * FROM debates WHERE round_id = {round_id}")
    for debate in debates:
        debate_id = debate["id"]
        # Get speeches and sort by position
        debate["speeches"] = db.execute(f"SELECT speaker_id, position, s.first_name, s.last_name, ss.score FROM speeches ss INNER JOIN speakers s ON ss.speaker_id = s.id WHERE debate_id = {debate_id}")
        debate["speeches"] = sorted(debate["speeches"], key=itemgetter("position"))
        # Get teams and sort by position
        debate["team_performances"] = db.execute(f"SELECT * FROM team_performances WHERE debate_id = {debate_id}")
        for team in debate["team_performances"]:
            if team["side"] == "og":
                team["position"] = 1
            elif team["side"] == "oo":
                team["position"] = 2
            elif team["side"] == "cg":
                team["position"] = 3
            elif team["side"] == "co":
                team["position"] = 4
        debate["team_performances"] = sorted(debate["team_performances"], key=itemgetter("position"))
        # Get adjudicators and sort by role
        debate["adjudicators"] = db.execute(f"SELECT a.speaker_id, a.role, s.first_name, s.last_name FROM adjudications a INNER JOIN speakers s ON a.speaker_id = s.id WHERE debate_id = {debate_id}")
        for adjudicator in debate["adjudicators"]:
            if adjudicator["role"] == "chair":
                adjudicator["position"] = 1
            elif adjudicator["role"] == "panellist":
                adjudicator["position"] = 2
            else:
                adjudicator["position"] = 3
        debate["adjudicators"] = sorted(debate["adjudicators"], key=itemgetter("position"))
    debates = sorted(debates, key=itemgetter("average_rating"), reverse=True)

    return render_template("tournament/round.html", round=round, debates=debates)


@app.route("/speaker", methods=["GET", "POST"])
def speaker():
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
            round_seq.append(speech["seq"])
            round_instance = {"seq": speech["seq"], "score": speech["team_score"], "number": 1}
            rankings_by_round_seq = rankings_by_round_seq + [round_instance]
        else:
            for ranking in rankings_by_round_seq:
                if ranking["seq"] == speech["seq"]:
                    ranking["score"] = ranking["score"] + speech["team_score"]
                    ranking["number"] = ranking["number"] + 1
    for ranking in rankings_by_round_seq:
        ranking["average_score"] = ranking["score"] / ranking["number"]
        ranking["average_score"] = round(ranking["average_score"], 2)

    # Get the latest speaker achievements
    achievements = db.execute(f"SELECT a.*, bc.name AS break_category_name, t.short_name AS tournament_name FROM achievements a LEFT JOIN break_categories bc ON a.break_category = bc.id INNER JOIN tournaments t ON a.tournament_id = t.id WHERE speaker_id = {id} ORDER BY id DESC LIMIT 5")

    # Get the tournaments the speaker participated in
    participations = db.execute("SELECT tp.*, t.name, t.short_name FROM tournament_participants tp INNER JOIN tournaments t ON tp.tournament_id = t.id WHERE speaker_id = ? AND tp.role = ? ORDER BY id DESC LIMIT 5",
                                id, "speaker")
    adjudications = db.execute("SELECT tp.*, t.name, t.short_name FROM tournament_participants tp INNER JOIN tournaments t ON tp.tournament_id = t.id WHERE speaker_id = ? AND tp.role != ? ORDER BY id DESC LIMIT 5",
                                id, "speaker")

    if speaker["society_id"] is not None:
        society = db.execute(f"SELECT * FROM societies WHERE id = ?", speaker["society_id"])[0]
        return render_template("speaker/speaker.html", speaker=speaker, speeches=speeches, count=count, speaks_by_position=speaks_by_position, points_by_side=points_by_side, points_by_room_strength=points_by_room_strength, team_rankings=team_rankings, rankings_by_round_seq=rankings_by_round_seq, round_seq=round_seq, participations=participations, achievements=achievements, adjudications=adjudications, society=society)
    return render_template("speaker/speaker.html", speaker=speaker, speeches=speeches, count=count, speaks_by_position=speaks_by_position, points_by_side=points_by_side, points_by_room_strength=points_by_room_strength, team_rankings=team_rankings, rankings_by_round_seq=rankings_by_round_seq, round_seq=round_seq, participations=participations, achievements=achievements, adjudications=adjudications)


@app.route("/achievements", methods=["GET", "POST"])
def achievement_list():
    """Show speaker achievements"""
    if not request.args.get("id"):
            return apology("must provide speaker id", 400)

    id = request.args.get("id")

    speaker = db.execute(f"SELECT * FROM speakers WHERE id = {id}")[0]

    achievements = db.execute(f"SELECT a.*, bc.name AS break_category_name, t.name AS tournament_name, t.date AS date FROM achievements a LEFT JOIN break_categories bc ON a.break_category = bc.id LEFT JOIN tournaments t ON a.tournament_id = t.id WHERE speaker_id = {id} ORDER BY id DESC")

    return render_template("speaker/achievements.html", achievements=achievements, speaker=speaker)


@app.route("/participation", methods=["GET", "POST"])
def tournaments_by_speaker():
    """Show speaker tournaments"""
    if not request.args.get("id"):
            return apology("must provide speaker id", 400)

    id = request.args.get("id")

    speaker = db.execute(f"SELECT * FROM speakers WHERE id = {id}")[0]

    tournaments = db.execute(f"SELECT tp.*, t.name AS tournament_name, t.date AS date FROM tournament_participants tp LEFT JOIN tournaments t ON tp.tournament_id = t.id WHERE speaker_id = {id} ORDER BY id DESC")

    return render_template("speaker/participation.html", tournaments=tournaments, speaker=speaker)


# @app.route("/register", methods=["GET", "POST"])
# def register():
#     """Register user"""

#     # Forget any user_id
#     session.clear()

#     # User reached route via POST (as by submitting a form via POST)
#     if request.method == "POST":

#         # Ensure username was submitted
#         if not request.form.get("username"):
#             return apology("must provide username", 400)

#         # Ensure password was submitted
#         elif not request.form.get("password"):
#             return apology("must provide password", 400)

#         # Ensure password confirmation is correct
#         elif request.form.get("password") != request.form.get("confirmation"):
#             return apology("password confirmation does not match password", 400)

#         # Query database for username
#         rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

#         # Ensure username does not exist
#         if len(rows) > 0:
#             return apology("username already taken", 400)

#         # Create username and password hash
#         username = request.form.get("username")
#         hash = generate_password_hash(request.form.get("password"))

#         # Add the user's entry into the database
#         db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)

#         # Query database for username
#         rows = db.execute("SELECT * FROM users WHERE username = ?", username)

#         # Ensure username does not exist
#         if len(rows) != 1:
#             return apology("unknown error", 403)

#         # Remember which user has logged in
#         session["user_id"] = rows[0]["id"]

#         # Redirect user to home page
#         return redirect("/")

#     # User reached route via GET (as by clicking a link or via redirect)
#     else:
#         return render_template("register.html")

@app.errorhandler(404)
def page_not_found(e):
    return apology("Page not found", 404)

@app.errorhandler(500)
def page_not_found(e):
    return apology("Internal Server Error", 500)