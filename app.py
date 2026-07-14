from datetime import datetime
from functools import wraps

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)

from config import Config
from extensions import db, login_manager
from models import User, Resource, NeedRequest, Match, Notification, CATEGORIES, URGENCY_LEVELS
from matching import score_pair, best_needs_for_resource, best_resources_for_need


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    register_routes(app)

    with app.app_context():
        db.create_all()

    return app


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def notify(user_id, message, link=None):
    db.session.add(Notification(user_id=user_id, message=message, link=link))


def register_routes(app):

    # ---------- Public ----------
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        stats = {
            "resources": Resource.query.count(),
            "needs": NeedRequest.query.count(),
            "completed": Match.query.filter_by(status="completed").count(),
            "users": User.query.count(),
        }
        return render_template("index.html", stats=stats)

    @app.route("/impact")
    def impact():
        completed = Match.query.filter_by(status="completed").all()
        by_category = {}
        for m in completed:
            cat = m.resource.category if m.resource else "other"
            by_category[cat] = by_category.get(cat, 0) + 1
        top_givers = (
            db.session.query(User, db.func.count(Match.id).label("cnt"))
            .join(Match, Match.giver_id == User.id)
            .filter(Match.status == "completed")
            .group_by(User.id)
            .order_by(db.desc("cnt"))
            .limit(5)
            .all()
        )
        return render_template(
            "impact.html",
            total_completed=len(completed),
            by_category=by_category,
            categories=dict(CATEGORIES),
            top_givers=top_givers,
        )

    # ---------- Auth ----------
    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            address = request.form.get("address", "").strip()
            lat = request.form.get("lat") or None
            lng = request.form.get("lng") or None

            if not name or not email or len(password) < 6:
                flash("Please fill all fields. Password must be at least 6 characters.", "error")
                return render_template("register.html")

            if User.query.filter_by(email=email).first():
                flash("An account with that email already exists.", "error")
                return render_template("register.html")

            user = User(
                name=name, email=email, address_text=address,
                lat=float(lat) if lat else None,
                lng=float(lng) if lng else None,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(f"Welcome to Setu, {name.split()[0]}! Post your first give or need to get started.", "success")
            return redirect(url_for("dashboard"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user)
                user.bump_streak()
                db.session.commit()
                return redirect(url_for("dashboard"))
            flash("Invalid email or password.", "error")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    # ---------- Dashboard ----------
    @app.route("/dashboard")
    @login_required
    def dashboard():
        current_user.bump_streak()
        db.session.commit()

        my_resources = current_user.resources.filter(Resource.status != "cancelled").order_by(Resource.created_at.desc()).all()
        my_needs = current_user.needs.filter(NeedRequest.status != "cancelled").order_by(NeedRequest.created_at.desc()).all()

        # Build suggested matches for each of my open resources / needs
        open_needs = NeedRequest.query.filter_by(status="open").all()
        open_resources = Resource.query.filter_by(status="open").all()

        suggestions_as_giver = []
        for r in my_resources:
            if r.status != "open":
                continue
            others = [n for n in open_needs if n.user_id != current_user.id]
            for s, d, need in best_needs_for_resource(r, others, limit=3):
                suggestions_as_giver.append({"resource": r, "need": need, "score": s, "distance": d})
        suggestions_as_giver.sort(key=lambda x: x["score"], reverse=True)

        suggestions_as_receiver = []
        for n in my_needs:
            if n.status != "open":
                continue
            others = [r for r in open_resources if r.user_id != current_user.id]
            for s, d, resource in best_resources_for_need(n, others, limit=3):
                suggestions_as_receiver.append({"resource": resource, "need": n, "score": s, "distance": d})
        suggestions_as_receiver.sort(key=lambda x: x["score"], reverse=True)

        pending_matches = Match.query.filter(
            ((Match.giver_id == current_user.id) | (Match.receiver_id == current_user.id)),
            Match.status.in_(["pending", "confirmed"])
        ).order_by(Match.created_at.desc()).all()

        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(10).all()

        return render_template(
            "dashboard.html",
            my_resources=my_resources,
            my_needs=my_needs,
            suggestions_as_giver=suggestions_as_giver[:5],
            suggestions_as_receiver=suggestions_as_receiver[:5],
            pending_matches=pending_matches,
            notifications=notifications,
        )

    # ---------- Posting ----------
    @app.route("/give/new", methods=["GET", "POST"])
    @login_required
    def new_give():
        if request.method == "POST":
            expires_raw = request.form.get("expires_at")
            expires_at = None
            if expires_raw:
                try:
                    expires_at = datetime.strptime(expires_raw, "%Y-%m-%dT%H:%M")
                except ValueError:
                    pass
            r = Resource(
                user_id=current_user.id,
                category=request.form.get("category"),
                title=request.form.get("title", "").strip(),
                description=request.form.get("description", "").strip(),
                quantity=request.form.get("quantity", "").strip(),
                address_text=request.form.get("address", "").strip() or current_user.address_text,
                lat=float(request.form.get("lat")) if request.form.get("lat") else current_user.lat,
                lng=float(request.form.get("lng")) if request.form.get("lng") else current_user.lng,
                expires_at=expires_at,
            )
            db.session.add(r)
            db.session.commit()
            flash("Posted! We'll surface it to nearby people who need it.", "success")
            return redirect(url_for("dashboard"))
        return render_template("give_form.html", categories=CATEGORIES)

    @app.route("/need/new", methods=["GET", "POST"])
    @login_required
    def new_need():
        if request.method == "POST":
            n = NeedRequest(
                user_id=current_user.id,
                category=request.form.get("category"),
                title=request.form.get("title", "").strip(),
                description=request.form.get("description", "").strip(),
                urgency=request.form.get("urgency", "medium"),
                address_text=request.form.get("address", "").strip() or current_user.address_text,
                lat=float(request.form.get("lat")) if request.form.get("lat") else current_user.lat,
                lng=float(request.form.get("lng")) if request.form.get("lng") else current_user.lng,
            )
            db.session.add(n)
            db.session.commit()
            flash("Your request is live. You'll be matched as soon as something nearby fits.", "success")
            return redirect(url_for("dashboard"))
        return render_template("need_form.html", categories=CATEGORIES, urgency_levels=URGENCY_LEVELS)

    @app.route("/browse")
    @login_required
    def browse():
        category = request.args.get("category")
        q_res = Resource.query.filter_by(status="open")
        q_need = NeedRequest.query.filter_by(status="open")
        if category:
            q_res = q_res.filter_by(category=category)
            q_need = q_need.filter_by(category=category)
        resources = q_res.order_by(Resource.created_at.desc()).all()
        needs = q_need.order_by(NeedRequest.created_at.desc()).all()
        return render_template("browse.html", resources=resources, needs=needs, categories=CATEGORIES, selected_category=category)

    # ---------- Matching actions ----------
    @app.route("/match/propose/<int:resource_id>/<int:need_id>", methods=["POST"])
    @login_required
    def propose_match(resource_id, need_id):
        resource = Resource.query.get_or_404(resource_id)
        need = NeedRequest.query.get_or_404(need_id)

        if resource.user_id != current_user.id and need.user_id != current_user.id:
            abort(403)
        if resource.status != "open" or need.status != "open":
            flash("That item is no longer available.", "error")
            return redirect(url_for("dashboard"))

        score, distance = score_pair(resource, need, receiver_trust_score=need.requester.trust_score or 50)

        match = Match(
            resource_id=resource.id, need_id=need.id,
            giver_id=resource.user_id, receiver_id=need.user_id,
            score=score, distance_km=distance, status="pending",
        )
        resource.status = "matched"
        need.status = "matched"
        db.session.add(match)

        notify(resource.user_id, f'Your "{resource.title}" was matched to a nearby request. Confirm to proceed.', url_for("dashboard"))
        notify(need.user_id, f'Good news -- "{need.title}" may be fulfilled by "{resource.title}". Confirm to proceed.', url_for("dashboard"))

        db.session.commit()
        flash("Match proposed! Both sides need to confirm before contact details are shared.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/match/<int:match_id>/confirm", methods=["POST"])
    @login_required
    def confirm_match(match_id):
        match = Match.query.get_or_404(match_id)
        if current_user.id not in (match.giver_id, match.receiver_id):
            abort(403)
        match.status = "confirmed"
        match.confirmed_at = datetime.utcnow()
        other_id = match.receiver_id if current_user.id == match.giver_id else match.giver_id
        notify(other_id, "Your match was confirmed. Coordinate pickup/handover, then mark it complete.", url_for("dashboard"))
        db.session.commit()
        flash("Confirmed. Coordinate the handover, then mark it complete once done.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/match/<int:match_id>/complete", methods=["POST"])
    @login_required
    def complete_match(match_id):
        match = Match.query.get_or_404(match_id)
        if current_user.id not in (match.giver_id, match.receiver_id):
            abort(403)
        match.status = "completed"
        match.completed_at = datetime.utcnow()
        match.resource.status = "completed"
        match.need.status = "fulfilled"

        # Trust score nudges for both parties following through
        match.giver.trust_score = min(100, (match.giver.trust_score or 50) + 5)
        match.receiver.trust_score = min(100, (match.receiver.trust_score or 50) + 5)

        other_id = match.receiver_id if current_user.id == match.giver_id else match.giver_id
        notify(other_id, "Match marked complete. Thank you for following through!", url_for("impact"))
        db.session.commit()
        flash("Marked complete. That's one more person helped today.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/match/<int:match_id>/cancel", methods=["POST"])
    @login_required
    def cancel_match(match_id):
        match = Match.query.get_or_404(match_id)
        if current_user.id not in (match.giver_id, match.receiver_id):
            abort(403)
        match.status = "cancelled"
        match.resource.status = "open"
        match.need.status = "open"
        other_id = match.receiver_id if current_user.id == match.giver_id else match.giver_id
        notify(other_id, "A match was cancelled. Both posts are open again.", url_for("dashboard"))
        db.session.commit()
        flash("Match cancelled. Both posts are open again.", "info")
        return redirect(url_for("dashboard"))

    # ---------- Profile ----------
    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            current_user.name = request.form.get("name", current_user.name).strip()
            current_user.phone = request.form.get("phone", "").strip()
            current_user.address_text = request.form.get("address", "").strip()
            lat, lng = request.form.get("lat"), request.form.get("lng")
            if lat and lng:
                current_user.lat, current_user.lng = float(lat), float(lng)
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("profile"))
        return render_template("profile.html")

    # ---------- Admin ----------
    @app.route("/admin")
    @admin_required
    def admin_panel():
        users = User.query.order_by(User.created_at.desc()).all()
        flagged_low_trust = User.query.filter(User.trust_score < 30).all()
        return render_template("admin.html", users=users, flagged=flagged_low_trust)

    @app.route("/admin/verify/<int:user_id>", methods=["POST"])
    @admin_required
    def admin_verify(user_id):
        u = User.query.get_or_404(user_id)
        u.is_verified = not u.is_verified
        db.session.commit()
        return redirect(url_for("admin_panel"))

    @app.route("/notifications/read/<int:notif_id>", methods=["POST"])
    @login_required
    def mark_notification_read(notif_id):
        n = Notification.query.get_or_404(notif_id)
        if n.user_id != current_user.id:
            abort(403)
        n.is_read = True
        db.session.commit()
        return jsonify({"ok": True})


app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
