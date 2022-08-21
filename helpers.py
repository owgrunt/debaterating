import os
from cs50 import SQL
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps
import re

# Configure CS50 Library to use SQLite database
uri = os.getenv("HEROKU_POSTGRESQL_BLUE_URL")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://")
db = SQL(uri)


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup_tournament(domain, slug):

    # Contact API
    try:
        # api_key = os.environ.get("API_KEY")
        url = f"https://{domain}/api/v1/tournaments/{slug}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        tournament = response.json()
        return {
            "name": tournament["name"],
            "short_name": tournament["short_name"],
            "internal_id": tournament["id"],
            "slug": tournament["slug"],
            "domain": domain
        }
    except (KeyError, TypeError, ValueError):
        return None


def lookup_data(domain, slug, data_type):
    """Look up quote for symbol."""

    # Contact API
    try:
        # api_key = os.environ.get("API_KEY")
        url = f"https://{domain}/api/v1/tournaments/{slug}/{data_type}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        data = response.json()
        return data
    except (KeyError, TypeError, ValueError):
        return None


def lookup_link(link):
    """Look up quote for symbol."""

    # Contact API
    try:
        # api_key = os.environ.get("API_KEY")
        response = requests.get(link)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        data = response.json()
        return data
    except (KeyError, TypeError, ValueError):
        return None

def add_database_entry(type, entry, search_keys, update_keys, forego_search=False):
    """Import entry data into the db"""

    candidates = []
    if not forego_search:
        # Prepare query and list to search for the entry
        i = 0
        search_values = []
        for key in search_keys:
            if i == 0:
                search_query = key + " = ?"
                i = 1
            else:
                search_query = search_query + " AND " + key + " = ?"
            search_values.append(entry[key])
        candidates = db.execute(f"SELECT * FROM {type} WHERE {search_query}",
                                *search_values)

    # If there are duplicate entries, return error
    if len(candidates) > 1:
        return apology(f"more than one entry {entry} of type {type} exists for the tournament", 400)

    # If entry is in the db, edit it
    elif len(candidates) == 1:
        # TODO check if there are any changes and update only then
        # Prepare query and list to update the entry
        update_query = get_update_query(update_keys, "update")
        update_values = get_update_values(update_keys, entry)
        update_values = update_values + search_values

        # Update the entry
        db.execute(f"UPDATE {type} SET {update_query} WHERE {search_query}",
                    *update_values)

    # If entry not in db, add the entry
    else:
        # Prepare query and list to add the entry
        if not forego_search:
            update_keys = update_keys + search_keys

        update_query = get_update_query(update_keys, "insert")
        update_values = get_update_values(update_keys, entry)

        add_questions = "?"
        i = 0
        for value in update_values:
            if i == 0:
                i = 1
            else:
                add_questions = add_questions + ", ?"
        # Add
        db.execute(f"INSERT INTO {type} ({update_query}) VALUES ({add_questions})",
                    *update_values)

    # Search db for newly added entry
    if not forego_search:
        database_record = db.execute(f"SELECT * FROM {type} WHERE {search_query}",
                                     *search_values)
    else:
        # Prepare query and list to search for the entry
        i = 0
        search_values = []
        for key in update_keys:
            if i == 0:
                search_query = key + " = ?"
                i = 1
            else:
                search_query = search_query + " AND " + key + " = ?"
            search_values.append(entry[key])
        database_record = db.execute(f"SELECT * FROM {type} WHERE {search_query}",
                                     *search_values)
    # Return the entry id for future use
    return database_record[0]["id"]


def get_update_query(update_keys,query_type):
    i = 0
    for key in update_keys:
        if i == 0:
            update_query = key
            if query_type == "update":
                update_query = update_query + " = ?"
            i = 1
        else:
            update_query = update_query + ", " + key
            if query_type == "update":
                update_query = update_query + " = ?"
    return update_query


def get_update_values(update_keys, entry):
    update_values = []
    for key in update_keys:
        if isinstance(entry[key], list):
            update_values.append(f"{{" + ",".join(entry[key]) + f"}}")
        else:
            update_values.append(entry[key])
    return update_values


def split_name_by_format(speaker, name_format):
    # Remove ё from speaker names
    speaker["internal_name"] = speaker["internal_name"].replace("ё", "е")
    if name_format == "fio" or name_format == "iof":
        split = speaker["internal_name"].split(" ", 2)
        if len(split) > 1:
            if name_format == "fio":
                speaker["last_name"] = split[0]
                speaker["first_name"] = split[1]
                speaker["middle_name"] = split[2]
            else:
                speaker["last_name"] = split[2]
                speaker["first_name"] = split[0]
                speaker["middle_name"] = split[1]
        else:
                speaker["last_name"] = ""
                speaker["first_name"] = split[0]
                speaker["middle_name"] = ""
    else:
        split = speaker["internal_name"].split(" ", 1)
        if len(split) > 1:
            if name_format == "fi":
                speaker["last_name"] = split[0]
                speaker["first_name"] = split[1]
                speaker["middle_name"] = ""
            else:
                speaker["last_name"] = split[1]
                speaker["first_name"] = split[0]
                speaker["middle_name"] = ""
        else:
                speaker["last_name"] = ""
                speaker["first_name"] = split[0]
                speaker["middle_name"] = ""
    return speaker

def has_yo(name):
    return bool(re.search('[ё]', name))

def calculate_elo(rounds, tournament):
    # Make ELO calculation for all the rounds in a sequence
    for round_instance in rounds:
        round_id = round_instance["id"]
        team_performances = db.execute(open("sql_get_team_performances.sql").read().replace("xxxxxx", str(tournament["id"])).replace("yyyyyy", str(round_id)))

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
                               "rating_change": 0}
                speaker_two = {"speaker": team_performances[i]["speaker_two"],
                               "round": round_id,
                               "debate": team_performances[i]["debate_id"],
                               "initial_rating": team_performances[i]["speaker_two_rating"],
                               "rating_change": 0}
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
                        rating_change_float = k_factor * expectation_deviation
                        rating_change = round(rating_change_float)
                        # Adjust the ratings
                        k = 0
                        for update in updated_ratings:
                            if update["speaker"] == team_performances[i]["speaker_one"]:
                                update["rating_change"] = update["rating_change"] + rating_change
                                k = k + 1
                            if update["speaker"] == team_performances[i]["speaker_two"]:
                                update["rating_change"] = update["rating_change"] + rating_change
                                k = k + 1
                            if update["speaker"] == team_performances[j]["speaker_one"]:
                                update["rating_change"] = update["rating_change"] - rating_change
                                k = k + 1
                            if update["speaker"] == team_performances[j]["speaker_two"]:
                                update["rating_change"] = update["rating_change"] - rating_change
                                k = k + 1
                        if k != 4:
                            return apology("scores not updated", 400)

        # Update the database
        for update in updated_ratings:
            if update["rating_change"] != 0:
                # Add rating change to the speech database
                db.execute("UPDATE speeches SET rating_change = ? WHERE speaker_id = ? AND debate_id = ?",
                           update["rating_change"], update["speaker"], update["debate"])

                # Change the rating in the speaker database
                db.execute("UPDATE speakers SET rating = 1500 + subquery.sum FROM (SELECT sum(rating_change) FROM speeches WHERE speaker_id = ?) AS subquery WHERE id = ?",
                           update["speaker"], update["speaker"])

        # Apparently, zero rating adjustments don't get recorded for an unknown reason, but I'm too lazy to fix it the right way
        db.execute(f"UPDATE speeches SET rating_change = 0 WHERE rating_change is NULL")
    return

def rank_by_rating(type):

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
    for speaker in db_speakers:
        ranking_by_speaks = speaker["ranking_by_speaks"]
        ranking_by_rating = speaker["ranking_by_rating"]
        id = speaker["id"]
        db.execute(f"UPDATE speakers SET ranking_by_speaks = {ranking_by_speaks}, ranking_by_rating = {ranking_by_rating} WHERE id = {id}")