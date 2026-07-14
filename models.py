from datetime import datetime, date, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

CATEGORIES = [
    ("food", "🍲 Food"),
    ("medicine", "💊 Medicine"),
    ("tuition", "📚 Tuition / Skill Time"),
    ("funds", "💰 Small Funds"),
    ("essentials", "🧺 Essentials"),
]

URGENCY_LEVELS = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30))

    address_text = db.Column(db.String(255))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

    is_admin = db.Column(db.Boolean, default=False)
    is_ngo = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)

    trust_score = db.Column(db.Integer, default=50)   # 0-100
    streak_count = db.Column(db.Integer, default=0)
    last_active_date = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    resources = db.relationship("Resource", backref="giver", lazy="dynamic", foreign_keys="Resource.user_id")
    needs = db.relationship("NeedRequest", backref="requester", lazy="dynamic", foreign_keys="NeedRequest.user_id")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def bump_streak(self):
        """Call once per day the user is meaningfully active. Idempotent per day."""
        today = date.today()
        if self.last_active_date == today:
            return
        if self.last_active_date == today - timedelta(days=1):
            self.streak_count = (self.streak_count or 0) + 1
        else:
            self.streak_count = 1
        self.last_active_date = today

    @property
    def people_helped_count(self):
        return Match.query.filter_by(giver_id=self.id, status="completed").count()

    @property
    def times_helped_count(self):
        return Match.query.filter_by(receiver_id=self.id, status="completed").count()


class Resource(db.Model):
    """A surplus posting -- something a giver has to offer."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    category = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    quantity = db.Column(db.String(60))  # free text: "6 meals", "2 hrs/week", "₹500"

    address_text = db.Column(db.String(255))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

    expires_at = db.Column(db.DateTime, nullable=True)  # e.g. food must be picked up by X
    status = db.Column(db.String(20), default="open")   # open, matched, completed, cancelled, expired
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    matches = db.relationship("Match", backref="resource", lazy="dynamic")

    @property
    def category_label(self):
        return dict(CATEGORIES).get(self.category, self.category)

    @property
    def hours_until_expiry(self):
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.utcnow()
        return delta.total_seconds() / 3600


class NeedRequest(db.Model):
    """A request -- something a receiver needs."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    category = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    urgency = db.Column(db.String(20), default="medium")

    address_text = db.Column(db.String(255))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

    status = db.Column(db.String(20), default="open")  # open, matched, fulfilled, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    matches = db.relationship("Match", backref="need", lazy="dynamic")

    @property
    def category_label(self):
        return dict(CATEGORIES).get(self.category, self.category)

    @property
    def urgency_label(self):
        return dict(URGENCY_LEVELS).get(self.urgency, self.urgency)


class Match(db.Model):
    """A proposed/confirmed/completed pairing between a Resource and a NeedRequest."""
    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resource.id"), nullable=False)
    need_id = db.Column(db.Integer, db.ForeignKey("need_request.id"), nullable=False)
    giver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    score = db.Column(db.Float, default=0)
    distance_km = db.Column(db.Float)
    status = db.Column(db.String(20), default="pending")  # pending, confirmed, completed, declined, cancelled

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    giver = db.relationship("User", foreign_keys=[giver_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
