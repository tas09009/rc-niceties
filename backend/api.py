from flask import json, jsonify, request, abort, url_for, redirect
from flask.views import MethodView
import random

from backend import app, rc, db
from backend.models import Nicety, SiteConfiguration
from backend.auth import current_user, needs_authorization, faculty_only
from datetime import datetime, timedelta
from sqlalchemy import func

import backend.cache as cache
import backend.config as config
import backend.util as util

import sys
from functools import partial
from urllib.request import Request, urlopen
from operator import is_not

@app.route('/api/v1/self')
@needs_authorization
def get_self_info():
    self_info = rc.get('people/me').data
    return jsonify(self_info)


@app.route('/gee')
def ya():
    return jsonify(batch_people(29))

@app.route('/api/v1/all-niceties', methods=['GET'])
@needs_authorization
def all_niceties():
    ret = {}    # Mapping from target_id to a list of niceties for that person
    last_target = None
    is_rachel = current_user().id == 770
    two_weeks_from_now = datetime.now() - timedelta(days=14)
    if is_rachel == True:
        valid_niceties = (Nicety.query
                          #.filter(Nicety.end_date < two_weeks_from_now)
                          .order_by(Nicety.target_id)
                          .all())
        for n in valid_niceties:
            if n.target_id != last_target:
                # ... set up the test for the next one
                last_target = n.target_id
                ret[n.target_id] = []  # initialize the dictionary
            if n.anonymous == False:
                ret[n.target_id].append({
                    'author_id': n.author_id,
                    'name': json.loads(person(n.author_id).data)['full_name'],
                    'no_read': n.no_read,
                    'text': n.text,
                })
            else:
                ret[n.target_id].append({
                    'text': n.text,
                    'no_read': n.no_read,
                })
        return jsonify([
            {
                'to_name': json.loads(person(k).data)['full_name'],
                'to_id': json.loads(person(k).data)['id'],
                'niceties': v
            }
            for k, v in ret.items()
        ])
    else:
        return jsonify({'authorized': "false"})

@app.route('/api/v1/all-niceties', methods=['POST'])
@needs_authorization
def overwrite_niceties():
    is_rachel = current_user().id == 770
    nicety_text = request.form.get("text")
    nicety_author = request.form.get("author_id")
    nicety_target = request.form.get("target_id")
    if is_rachel == True:
        (Nicety.query
         .filter(Nicety.author_id==nicety_author)
         .filter(Nicety.target_id==nicety_target)
         .update({'text': nicety_text}))
        db.session.commit()
        return jsonify({'status': 'OK'})
    else:
        return jsonify({'authorized': "false"})

@app.route('/api/v1/load-niceties')
@needs_authorization
def load_unsent_niceties():
    user_id = current_user().id
    niceties = (Nicety.query
                .filter(Nicety.end_date > datetime.now())
                .filter(Nicety.author_id == user_id)
                .all())
    ret = [{
        'target_id': n.target_id,
        'text': n.text,
        'anonymous': n.anonymous,
        'no_read': n.no_read,
        'date_updated': n.date_updated
    } for n in niceties]
    return jsonify(ret)

@app.route('/api/v1/show-niceties')
@needs_authorization
def get_niceties_for_current_user():
    ret = []
    whoami = current_user().id
    two_weeks_from_now = datetime.now() - timedelta(days=14)
    valid_niceties = (Nicety.query
                      .filter(Nicety.end_date + timedelta(days=1) < datetime.now()) # show niceties one day after the end date
                      .filter(Nicety.target_id == whoami)
                      .all())
    for n in valid_niceties:
        if n.anonymous == True:
            store = {
                'end_date': n.end_date,
                'anonymous': n.anonymous,
                'text': n.text,
                'no_read': n.no_read,
                'date_updated': n.date_updated
            }
        else:
            store = {
                'avatar_url': json.loads(person(n.author_id).data)['avatar_url'],
                'name': json.loads(person(n.author_id).data)['name'],
                'author_id': n.author_id,
                'end_date': n.end_date,
                'anonymous': n.anonymous,
                'text': n.text,
                'no_read': n.no_read,
                'date_updated': n.date_updated

            }
        ret.append(store)
    return jsonify(ret)
    pass

def batch_people(batch_id):
    cache_key = 'batches_people_list:{}'.format(batch_id)
    try:
        people = cache.get(cache_key)
    except cache.NotInCache:
        people = []
        for p in rc.get('batches/{}/people'.format(batch_id)).data:
            if p['github'] is not None:
                try:
                    repos = json.loads(urlopen("https://api.github.com/users/{}/repos".format(p['github'])).read())
                    repo_info = []
                    for repo in repos:
                        repo_info.append({
                            'name': repo['name'],
                            'description': repo['description'],
                        })
                except:
                    repo_info = []
                    e = sys.exc_info()[:2]
            if p['interests'] is not None:
                placeholder = util.name_from_rc_person(p) + " has got the following interests: " + p['interests']
            else:
                placeholder = "Say something nice about " + util.name_from_rc_person(p) + "!"

            latest_end_date = None
            for stint in p['stints']:
                if stint['end_date'] is not None:
                    e = datetime.strptime(stint['end_date'], '%Y-%m-%d')
                    if latest_end_date is None or e > latest_end_date:
                        latest_end_date = e
            people.append({
                'id': p['id'],
                'is_faculty': p['is_faculty'],
                'is_hacker_schooler': p['is_hacker_schooler'],
                'name': util.name_from_rc_person(p),
                'full_name': util.full_name_from_rc_person(p),
                'avatar_url': p['image'],
                'stints': p['stints'],
                'bio': p['bio'],
                'interests': p['interests'],
                'before_rc': p['before_rc'],
                'during_rc': p['during_rc'],
                'job': p['job'],
                'twitter': p['twitter'],
                'github': p['github'],
                'repos': repo_info,
                'end_date': latest_end_date,
            })
        cache.set(cache_key, people)
    return people

@app.route('/api/v1/faculty')
@needs_authorization
def get_faculty():
    faculty = get_current_faculty()
    return jsonify(faculty)

def get_current_faculty():
    ''' faculty will always appear in
    the most recent batch!
    '''
    faculty = []
    for batch in get_current_batches():
        for p in batch_people(batch['id']):
            if p['is_faculty'] == True:
                faculty.append(p)
    return faculty

def get_users(batches):
    return [person for batch in batches for person in batch_people(batch['id'])]

def get_current_batches():
    cache_key = 'open_batches_list'
    try:
        batches = cache.get(cache_key)
    except cache.NotInCache:
        batches = rc.get('batches').data
        cache.set(cache_key, batches)
    ret = [batch for batch in batches if util.latest_batches(batch['end_date'])]
    if len(ret) == 1:
        ret = []
    return ret

def get_current_users():
    return get_users(get_current_batches())

def partition_current_users(users):
    ret = {
        'staying': [],
        'leaving': []
    }
    user_stints = [user['stints'] for user in users]
    end_dates = []
    for stints in user_stints:
        if stints != []:
            for stint in stints:
                if stint['end_date'] is not None and stint['type'] == 'retreat':
                    end_dates.append(stint['end_date'])
    end_dates = sorted(list(set(end_dates)))
    end_dates = end_dates[::-1]
    staying_date = datetime.strptime(end_dates[0], "%Y-%m-%d")
    leaving_date = datetime.strptime(end_dates[1], "%Y-%m-%d")
    for u in users:
        # Batchlings have   is_hacker_schooler = True,      is_faculty = False
        # Faculty have      is_hacker_schooler = ?,         is_faculty = True
        # Residents have    is_hacker_schooler = False,     is_faculty = False
        if ((u['is_hacker_schooler'] and not u['is_faculty']) or
            (not u['is_faculty'] and not u['is_hacker_schooler'] and config.get(config.INCLUDE_RESIDENTS, False)) or
            (u['is_faculty'] and config.get(config.INCLUDE_FACULTY, False))):
            if u['end_date'] == staying_date:
                ret['staying'].append(u)
            elif u['end_date'] == leaving_date:
                ret['leaving'].append(u)
            else:
                pass
    return ret

@app.route('/api/v1/people2')
@needs_authorization
def display_people():
    current = get_current_users()
    if current == []:
        return jsonify({'status': 'closed'})
    people = partition_current_users(current)
    user_id = current_user().id
    current_user_leaving = False
    leaving = []
    to_display = None
    for person in people['leaving']:
        if person['id'] == user_id:
            current_user_leaving = True
        else:
            leaving.append(person)
    staying = list(person for person in people['staying'])
    faculty = get_current_faculty()
    # there needs to be a better way to do this!
    special = [person for person in faculty if person['name'] == "Lisa" or person['name'] == "Allie" or person['name'] == "John"]
    random.seed(current_user().random_seed)
    random.shuffle(staying)
    random.shuffle(leaving)
    random.shuffle(special)
    if current_user_leaving == True:
        to_display = {
            'staying': staying,
            'leaving': leaving,
            'special': special
        }
        #to_display = staying + leaving
    else:
        to_display = {
            'leaving': leaving,
            'special': special
        }
        #to_display = leaving
    return jsonify(to_display)

@app.route('/api/v1/people/<int:person_id>')
@needs_authorization
def person(person_id):
    cache_key = 'person:{}'.format(person_id)
    try:
        return cache.get(cache_key)
    except cache.NotInCache:
        p = rc.get('people/{}'.format(person_id)).data
        person = {
            'id': p['id'],
            'name': p['first_name'],
            'full_name': p['first_name'] + " " + p['last_name'],
            'avatar_url': p['image'],
            'is_faculty': p['is_faculty'],
            'bio': p['bio'],
            'interests': p['interests'],
            'before_rc': p['before_rc'],
            'during_rc': p['during_rc'],
            'job': p['job'],
            'twitter': p['twitter'],
            'github': p['github'],
        }
        person_json = jsonify(person)
        cache.set(cache_key, person_json)
        return person_json

@app.route('/api/v1/post-niceties', methods=['POST'])
@needs_authorization
def save_niceties():
    niceties_to_save = json.loads(request.form.get("niceties", "[]"))
    for n in niceties_to_save:
        nicety = (
            Nicety
            .query      # Query is always about getting Nicety objects from the database
            .filter_by(
                end_date=datetime.strptime(n.get("end_date"), "%Y-%m-%d").date(),
                target_id=n.get("target_id"),
                author_id=current_user().id)
            .one_or_none())
        if nicety is None:
            nicety = Nicety(
                end_date=datetime.strptime(n.get("end_date"), "%Y-%m-%d").date(),
                target_id=n.get("target_id"),
                author_id=current_user().id)
            db.session.add(nicety)
            # We need to add for the new one, but we don't need to add where we have used .query
            # Now any change to the nicety object (variable) is tracked by the object
            # so it knows what it will have to update.
            # And then when we call db.session.commit() that knows about the object
            # (beacuse Nicety.query... uses the db.session behind the scenes).
            # So then db.session.commit() sends the update (or insert) for every object
            # in the session. This includes every object created by a [model].query and
            # everything added to the session with db.session.add().
        nicety.anonymous = n.get("anonymous", current_user().anonymous_by_default)
        text = n.get("text").strip()
        if '' == text:
            text = None
        nicety.text = text
        nicety.faculty_reviewed = False
        nicety.no_read = n.get("no_read")
        nicety.date_updated = n.get("date_updated")
    db.session.commit()
    return jsonify({'status': 'OK'})

class SiteSettingsAPI(MethodView):
    def get(self):
        user = current_user()
        if user is None:
            return redirect(url_for('authorized'))
        if not user.faculty:
            return abort(403)
        return jsonify({c.key: config.to_frontend_value(c) for c in SiteConfiguration.query.all()})

    def post(self):
        if current_user() is None:
            redirect(url_for('authorized'))
            user = current_user()
        if not user.faculty:
            return abort(403)
        key = request.form.get('key', None)
        value = request.form.get('value', None)
        try:
            try:
                config.set(key, config.from_frontend_value(key, json.loads(value)))
                return jsonify({'status': 'OK'})
            except ValueError:
                return abort(404)
        except:
            return abort(400)

app.add_url_rule(
    '/api/v1/site_settings',
    view_func=SiteSettingsAPI.as_view('site_settings'))
