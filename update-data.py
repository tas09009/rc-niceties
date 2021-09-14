#!/usr/bin/env python

"""
Fetch and insert Recurse Center API data into database.
"""

import os
import logging
import sys
import requests
from dotenv import load_dotenv
from backend import db, util
from backend.models import Profile, Stint


def get_env_var(var_name, fallback=""):
    value = os.getenv(var_name) or fallback
    if not value:
        logging.error(
            f"{var_name} value not found.",
            " Ensure a .env or .flaskenv file is present",
            "with this environment variable set",
        )
        sys.exit()
    logging.info(var_name + ": " + value)
    return value


def get_people(token):
    people = []
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})
    url = "https://www.recurse.com/api/v1/profiles?limit={limit}&offset={offset}"
    limit = 50
    offset = 0

    while True:
        res = session.get(url.format(limit=limit, offset=offset))
        if res.status_code != requests.codes.ok:
            res.raise_for_status
        page = res.json()
        if page == []:
            break
        people.extend(page)
        offset += limit

    return people


def update_database(database_url, people):
    for person in people:
        id = person.get("id")

        if not Profile.query.filter_by(id=id).first():
            first_name = person.get("first_name")
            last_name = person.get("last_name")
            avatar_url = person.get("image_path")
            bio_rendered = person.get("bio_rendered")
            interests = person.get("interests_rendered")
            before_rc = person.get("before_rc_rendered")
            during_rc = person.get("during_rc_rendered")
            stints_all = person.get("stints")

            u = Profile(
                id=id,
                name=util.full_name_from_rc_person(person),
                first_name=first_name,
                last_name=last_name,
                avatar_url=avatar_url,
                bio_rendered=bio_rendered,
                interests=interests,
                before_rc=before_rc,
                during_rc=during_rc,
            )

            stint_instances = create_stints(stints_all)
            u.stints.extend(stint_instances)
            logging.info(f"Adding: {id}, {first_name}, {last_name}")
            db.session.add(u)
            db.session.commit()

        else:
            logging.info(f"Skipping: {id}")
            continue


def create_stints(stints_all):
    stint_instances = []
    for stint in stints_all:
        s = Stint(
            id=stint["id"],
            start_date=stint["start_date"],
            end_date=stint["end_date"],
            type_stint=stint["type"],
            title=stint["title"],
        )
        stint_instances.append(s)
        db.session.add(s)
        db.session.commit()
    return stint_instances


if __name__ == "__main__":

    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    database_url = get_env_var("DATABASE_URL")
    token = get_env_var("RC_API_ACCESS_TOKEN")

    logging.info("Starting database update...")
    people = get_people(token)
    logging.info(f"Found {len(people)} people")

    logging.info("Going through all users...")
    update_database(database_url, people)
    logging.info("Finished going through all users.")
