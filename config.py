import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "setu-dev-secret-change-in-production")

    # DB: defaults to SQLite for local dev. On Render, set DATABASE_URL to a
    # Postgres instance (Render's free Postgres works fine) so data survives
    # deploys/restarts -- SQLite on Render's ephemeral disk WILL get wiped.
    _db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'setu.db')}")
    if _db_url.startswith("postgres://"):
        # Render/Heroku give old-style postgres:// URLs; SQLAlchemy needs postgresql://
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 'india' seeds PDS/rupee-flavored demo data, 'generic' seeds a generic global city.
    DEMO_REGION = os.environ.get("DEMO_REGION", "india")

    # Matching engine weights (tune these to change platform behavior)
    URGENCY_WEIGHTS = {"critical": 40, "high": 30, "medium": 20, "low": 10}
    MAX_PROXIMITY_SCORE = 30      # km-based, decays with distance
    MAX_EXPIRY_BONUS = 20         # resources expiring soon get boosted
    MAX_TRUST_BONUS = 15          # reliable users get slightly prioritized
    MATCH_SEARCH_RADIUS_KM = 25   # ignore matches farther than this
