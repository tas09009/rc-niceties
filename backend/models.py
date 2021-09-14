from datetime import datetime
from os import urandom

from backend import db


class User(db.Model):
    __tablename__ = 'user'

    # id is the RC user ID
    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    profile_id = db.Column(db.ForeignKey('profile.id'))
    anonymous_by_default = db.Column(db.Boolean)
    random_seed = db.Column(db.LargeBinary(32))

    def __init__(self, id, profile_id, name, **kwargs):
        self.id = id
        self.name = name
        self.profile_id = profile_id
        self.anonymous_by_default = kwargs.get("anonymous_by_default", False)
        self.random_seed = urandom(32)

    def __repr__(self):
        return '<User:{} ({})>'.format(self.id, self.name)


class Nicety(db.Model):
    __tablename__ = 'nicety'

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.ForeignKey('profile.id'))  # RC user ID
    target_id = db.Column(db.ForeignKey('profile.id'))  # RC user ID
    anonymous = db.Column(db.Boolean)
    text = db.Column(db.Text, nullable=True)
    no_read = db.Column(db.Boolean)
    date_updated = db.Column(db.Text)
    stint = db.Column(db.ForeignKey('stint.id'))

    __table_args__ = (db.UniqueConstraint("author_id", "target_id"),)

    def __init__(self, author_id, target_id, stint, **kwargs):
        self.author_id = author_id
        self.target_id = target_id
        self.anonymous = kwargs.get("anonymous", False)
        self.text = kwargs.get("text", None)
        self.no_read = kwargs.get("no_read", False)
        self.date_updated = kwargs.get("date_updated", "")
        self.stint = kwargs.get('stint')

    def __repr__(self):
        return '<Nicety:{}>'.format(self.id)

class Profile(db.Model):
    __tablename__ = 'profile'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(500))
    first_name = db.Column(db.String)
    last_name = db.Column(db.String)
    avatar_url = db.Column(db.String(500), nullable=True)
    bio_rendered = db.Column(db.String)
    interests = db.Column(db.String)
    before_rc = db.Column(db.String)
    during_rc = db.Column(db.String)
    stints = db.relationship('Stint', backref='profile')

    def __init__(self, id, name, **kwargs):
        self.id = id
        self.name = name
        self.avatar_url = kwargs.get("avatar_url", None)

    def __repr__(self):
        return '<Profile:{} ({})'.format(self.id, self.name)

class Stint(db.Model):
    __tablename__ = 'stint'

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.ForeignKey('profile.id'))
    type_stint = db.Column(db.String)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    title = db.Column(db.String)
    
    def __init__(self, start_date, end_date, **kwargs):
        self.type_stint = kwargs.get("type_stint", "retreat")
        self.title = kwargs.get("title", None)

    def __repr__(self):
        return '<Stint:{}>'.format(self.id)

class SiteConfiguration(db.Model):
    __tablename__ = 'site_configuration'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.PickleType)

    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __repr__(self):
        return '<Site Configuration:{}>'.format(self.key)


class Cache(db.Model):
    __tablename__ = 'cache'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.PickleType)
    last_updated = db.Column(db.DateTime)

    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.last_updated = datetime.now()

    def __repr__(self):
        return '<Cache:{} ({})>'.format(self.key, self.last_updated)
