# Setu (सेतु) — Bridge Surplus to Need

A hyperlocal matching platform that connects people with surplus (food, medicine,
tutoring time, small funds, essentials) to people nearby who need exactly that —
ranked by an explainable urgency/distance/expiry/trust scoring engine instead of
a static first-come-first-served feed.

**Core daily loop:** open dashboard → see 1–3 ranked matches → propose → both sides
confirm → mark complete → impact counter and streak go up.

## Why this is different from a generic donation app
- **Multi-resource**, not just food: food, medicine, tuition/skill time, small cash,
  essentials — one matching engine, one trust system.
- **Explainable AI-style matching**, not a browse list: every suggested match shows
  its score and *why* (urgency + proximity + expiry + trust), so it's not a black box.
- **Trust score** that grows only when both sides confirm a completed match — a
  lightweight reputation system that doesn't require heavy bureaucracy.
- **Public transparency dashboard** (`/impact`) — every completed match is counted
  publicly, addressing the #1 reason people distrust donation platforms: not
  knowing where their contribution actually went.

## Project structure
```
setu/
  app.py          # routes: auth, dashboard, posting, matching actions, admin
  models.py       # User, Resource, NeedRequest, Match, Notification
  matching.py     # haversine distance + explainable scoring engine
  config.py       # DB config (SQLite locally, Postgres-ready via DATABASE_URL)
  extensions.py   # db / login_manager singletons
  seed.py         # demo data generator (India or generic region)
  templates/      # dark-themed Jinja templates
  static/         # single CSS file + one small JS file (no external CDN deps)
  requirements.txt
  Procfile        # for Render/Heroku-style deploys
```

## Run locally
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# generate demo data (India-flavored by default)
python seed.py
# or: DEMO_REGION=generic python seed.py

python app.py
# visit http://localhost:5000
# demo login: ananya@example.com / password123  (admin account)
```

## Deploying to Render (or similar)
This app is built to avoid the exact ephemeral-filesystem trap you hit with Auro:

1. **Do not rely on SQLite in production.** Add a free Render Postgres instance,
   copy its "Internal Database URL", and set it as the `DATABASE_URL` env var on
   the web service. `config.py` already handles the `postgres://` → `postgresql://`
   rewrite Render's URL needs for SQLAlchemy.
2. Set `SECRET_KEY` to a random string in the environment.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app` (already in the `Procfile`)
5. After first deploy, run `python seed.py` once via Render's shell if you want
   demo data (optional — real users can just start posting).

## Matching engine (the core idea, in `matching.py`)
```
score = urgency_weight(need)                     # critical=40 ... low=10
      + proximity_bonus(distance, radius=25km)   # linear decay, closer = higher
      + expiry_bonus(resource)                   # perishables expiring soon rank up
      + trust_bonus(requester.trust_score)        # mild nudge toward reliable users
```
Tune the weights in `config.py` (`URGENCY_WEIGHTS`, `MAX_PROXIMITY_SCORE`, etc.)
without touching any route or template code.

## Extending this later
- Swap the scoring function for a learned model — the surrounding app doesn't change.
- Add a real map view (Leaflet) once you're ready to add a CDN dependency deliberately.
- Add SMS/WhatsApp notifications for match proposals (Twilio) instead of in-app only.
- Add an NGO bulk-posting mode for shelters/food banks with recurring surplus.
