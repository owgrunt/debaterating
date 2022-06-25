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
        candidates = db.execute(f"SELECT COUNT(*) FROM {type} WHERE {search_query}",
                                *search_values)

        # If there are duplicate entries, return error
        if candidates[0]["count"] > 1:
            return apology(f"more than one entry {entry} of type {type} exists for the tournament", 400)

        # If entry is in the db, edit it
        elif candidates[0]["count"] == 1:
            # Prepare query and list to update the entry
            i = 0
            update_values = []
            for key in update_keys:
                if i == 0:
                    update_query = key + " = ?"
                    i = 1
                else:
                    update_query = update_query + ", " + key + " = ?"
                update_values.append(entry[key])
            update_values = update_values + search_values
            # Update the entry
            db.execute(f"UPDATE {type} SET {update_query} WHERE {search_query}",
                       *update_values)

    # If entry not in db, add the entry
    else:
        # Prepare query and list to add the entry
        i = 0
        update_values = []
        if not forego_search:
            update_keys = update_keys + search_keys
        for key in update_keys:
            if i == 0:
                update_query = key
                i = 1
            else:
                update_query = update_query + ", " + key
            update_values.append(entry[key])

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



def split_name_by_format(speaker, name_format):
    # Change id to comp id
    speaker["internal_id"] = speaker["id"]
    # Remove unnecessary vars
    del speaker["id"], speaker["_links"], speaker["url"]
    # Remove ё from speaker names
    speaker["name"] = speaker["name"].replace("ё", "е")
    if name_format == "fio" or name_format == "iof":
        split = speaker["name"].split(" ", 2)
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
        split = speaker["name"].split(" ", 1)
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
