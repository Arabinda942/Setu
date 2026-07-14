"""
Seed demo data so the app looks alive immediately.
Run:  python seed.py            (uses DEMO_REGION from config, default 'india')
      DEMO_REGION=generic python seed.py
"""
import os
from datetime import datetime, timedelta

from app import create_app
from extensions import db
from models import User, Resource, NeedRequest

REGION = os.environ.get("DEMO_REGION", "india")

if REGION == "india":
    PEOPLE = [
        ("Ananya Roy", "ananya@example.com", "Salt Lake, Kolkata", 22.5726, 88.3639),
        ("Rahim Sheikh", "rahim@example.com", "Howrah", 22.5958, 88.2636),
        ("Priya Nair", "priya@example.com", "Park Street, Kolkata", 22.5535, 88.3512),
        ("Suresh Gowda", "suresh@example.com", "Garia, Kolkata", 22.4650, 88.3931),
        ("Feeding Hope NGO", "ngo@example.com", "Sealdah, Kolkata", 22.5697, 88.3697),
    ]
    GIVE_TITLES = [
        ("food", "18 packed lunch meals from a wedding", "6 meals"),
        ("medicine", "Unused blood pressure medication, sealed", "1 month supply"),
        ("tuition", "Free math tutoring, class 6-10", "2 hrs/week"),
        ("funds", "Small emergency fund available", "₹1000"),
    ]
    NEED_TITLES = [
        ("food", "Meals needed for family of 5 tonight", "critical"),
        ("medicine", "Need BP medication, can't afford this month", "high"),
        ("tuition", "My daughter needs help with class 8 math", "medium"),
        ("essentials", "Need warm blankets for winter", "medium"),
    ]
else:
    PEOPLE = [
        ("Alex Morgan", "alex@example.com", "Downtown", 40.7128, -74.0060),
        ("Sam Okafor", "sam@example.com", "Uptown", 40.7831, -73.9712),
        ("Jamie Chen", "jamie@example.com", "Midtown", 40.7549, -73.9840),
        ("Riley Fernandez", "riley@example.com", "Brooklyn", 40.6782, -73.9442),
        ("Community Food Bank", "ngo@example.com", "Queens", 40.7282, -73.7949),
    ]
    GIVE_TITLES = [
        ("food", "20 surplus sandwiches from a catered event", "20 sandwiches"),
        ("medicine", "Unopened first-aid supplies", "1 kit"),
        ("tuition", "Free coding tutoring, beginner Python", "2 hrs/week"),
        ("funds", "Small emergency fund available", "$50"),
    ]
    NEED_TITLES = [
        ("food", "Meals needed for a family tonight", "critical"),
        ("medicine", "Need basic first-aid supplies", "high"),
        ("tuition", "Need help learning to code for a job switch", "medium"),
        ("essentials", "Need a warm coat for winter", "medium"),
    ]


def seed():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        users = []
        for i, (name, email, addr, lat, lng) in enumerate(PEOPLE):
            u = User(name=name, email=email, address_text=addr, lat=lat, lng=lng,
                     is_admin=(i == 0), is_ngo=(i == len(PEOPLE) - 1), is_verified=(i == len(PEOPLE) - 1),
                     trust_score=60 + i * 5)
            u.set_password("password123")
            db.session.add(u)
            users.append(u)
        db.session.commit()

        for i, (cat, title, qty) in enumerate(GIVE_TITLES):
            giver = users[i % len(users)]
            db.session.add(Resource(
                user_id=giver.id, category=cat, title=title, quantity=qty,
                description="Posted as part of Setu demo data.",
                address_text=giver.address_text, lat=giver.lat, lng=giver.lng,
                expires_at=datetime.utcnow() + timedelta(hours=8) if cat == "food" else None,
            ))

        for i, (cat, title, urgency) in enumerate(NEED_TITLES):
            requester = users[(i + 1) % len(users)]
            db.session.add(NeedRequest(
                user_id=requester.id, category=cat, title=title, urgency=urgency,
                description="Posted as part of Setu demo data.",
                address_text=requester.address_text, lat=requester.lat, lng=requester.lng,
            ))

        db.session.commit()
        print(f"Seeded {len(users)} users, {len(GIVE_TITLES)} gives, {len(NEED_TITLES)} needs. Region: {REGION}")
        print("All demo accounts use password: password123")
        print("Admin login:", users[0].email)


if __name__ == "__main__":
    seed()
