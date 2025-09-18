import argparse
import os
from datetime import datetime
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort, current_app
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
from io import BytesIO
import pandas as pd
from .config import Config
from .models import (
    db, User, Student, Rubric, RubricItem, EvalRound,
    EvaluationToken, EvaluationResponse, DevOutbox
)
from .mailer import send_email
from .nlp import detect_red_flags, simple_summarize, openai_summarize
from sqlalchemy import or_

load_dotenv()

def create_app():
    app = Flask(__name__, instance_relative_config=True, template_folder="templates", static_folder="static")

    from datetime import timezone, datetime

    def to_local_timestr(dt):
        """Convert a UTC (naive or tz-aware) datetime to local timezone and return the formatted string."""
        if not dt:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone()
        s = local.strftime("%m-%d-%Y %I:%M %p")
        return s.replace(" 0", " ")

    app.jinja_env.filters["to_local"] = to_local_timestr

    app.config.from_object(Config)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "").strip()
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for("dashboard"))
            flash("Invalid credentials.", "danger")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        rounds = EvalRound.query.order_by(EvalRound.created_at.desc()).all()
        students_count = Student.query.count()
        rubrics = Rubric.query.all()
        return render_template("dashboard.html", rounds=rounds, students_count=students_count, rubrics=rubrics)

    @app.route("/students")
    @login_required
    def students():
        all_students = Student.query.order_by(Student.last_name, Student.first_name).all()
        return render_template("upload_students.html", students=all_students)

    @app.route("/students/upload", methods=["GET", "POST"])
    @login_required
    def upload_students():
        if request.method == "POST":
            file = request.files.get("file")
            if not file:
                flash("Please choose a CSV file.", "warning")
                return redirect(request.url)

            import csv, io
            decoded = file.stream.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(decoded))
            required = {"first_name", "last_name", "email", "team"}
            if not required.issubset(set(reader.fieldnames or [])):
                flash(f"CSV must include columns: {', '.join(required)}", "danger")
                return redirect(request.url)

            Student.query.delete()
            db.session.commit()

            added = 0
            for row in reader:
                email = row["email"].strip().lower()
                if not email:
                    continue
                exists = Student.query.filter_by(email=email).first()
                if exists:
                    exists.first_name = row["first_name"].strip()
                    exists.last_name = row["last_name"].strip()
                    exists.team = row["team"].strip()
                else:
                    s = Student(
                        first_name=row["first_name"].strip(),
                        last_name=row["last_name"].strip(),
                        email=email,
                        team=row["team"].strip(),
                    )
                    db.session.add(s)
                    added += 1
            db.session.commit()
            flash(f"Upload complete. {added} students added.", "success")
            return redirect(url_for("upload_students"))
        all_students = Student.query.order_by(Student.last_name, Student.first_name).all()
        return render_template("upload_students.html", students=all_students)

    @app.route("/rubrics", methods=["GET","POST"])
    @login_required
    def rubrics():
        if request.method == "POST":
            name = request.form.get("name","").strip() or f"Rubric {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            r = Rubric(name=name, active=True)
            db.session.add(r); db.session.commit()
            flash("Rubric created. Add items below.", "success")
            return redirect(url_for("edit_rubric", rubric_id=r.id))
        rubrics = Rubric.query.all()
        return render_template("rubrics.html", rubrics=rubrics)
    
    
    @app.route("/rubrics/<int:rubric_id>", methods=["GET","POST"])
    @login_required
    def edit_rubric(rubric_id):
        rubric = db.session.get(Rubric, rubric_id) or abort(404)
        if request.method == "POST":
            # add item
            criterion = request.form.get("criterion","").strip()
            description = request.form.get("description","").strip()
            weight = float(request.form.get("weight","1") or 1)
            max_score = int(request.form.get("max_score","5") or 5)
            if not criterion:
                flash("Criterion is required.", "warning")
            else:
                db.session.add(RubricItem(rubric_id=rubric.id, criterion=criterion, description=description, weight=weight, max_score=max_score))
                db.session.commit()
                flash("Item added.", "success")
            return redirect(request.url)
        return render_template("manage_rubric.html", rubric=rubric)

    @app.route("/rubrics/<int:rubric_id>/delete", methods=["POST"])
    @login_required
    def delete_rubric(rubric_id):
        rubric = db.session.get(Rubric, rubric_id) or abort(404)
        db.session.delete(rubric)
        db.session.commit()
        flash(f"Rubric '{rubric.name}' deleted.", "info")
        return redirect(url_for("rubrics"))

    @app.route("/rubrics/<int:rubric_id>/delete_item/<int:item_id>", methods=["POST"])
    @login_required
    def delete_rubric_item(rubric_id, item_id):
        item = db.session.get(RubricItem, item_id) or abort(404)
        db.session.delete(item); db.session.commit()
        flash("Item deleted.", "info")
        return redirect(url_for("edit_rubric", rubric_id=rubric_id))
    
    @app.route("/rubrics/upload", methods=["GET","POST"])
    @login_required
    def upload_rubric():
        if request.method == "POST":
            rname = request.form.get("name","Uploaded Rubric")
            file = request.files.get("file")
            if not file:
                flash("Choose a CSV first.", "warning"); return redirect(request.url)
            import csv, io
            decoded = file.stream.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(decoded))
            required = {"criterion", "weight", "max_score"}
            if not required.issubset(set(reader.fieldnames or [])):
                flash(f"CSV must include columns: {', '.join(required)}", "danger")
                return redirect(request.url)
            r = Rubric(name=rname, active=True)
            db.session.add(r); db.session.flush()
            for row in reader:
                db.session.add(RubricItem(
                    rubric_id=r.id,
                    criterion=row["criterion"].strip(),
                    description=row.get("description","").strip(),
                    weight=float(row["weight"] or 1),
                    max_score=int(row["max_score"] or 5)
                ))
            db.session.commit()
            flash(f"Rubric '{r.name}' uploaded.", "success")
            return redirect(url_for("dashboard"))
        return render_template("upload_rubric.html")

    @app.route("/rounds/start", methods=["GET","POST"])
    @login_required
    def start_round():
        rubrics = Rubric.query.all()
        if request.method == "POST":
            name = request.form.get("name","").strip() or f"Round {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            rubric_id = int(request.form.get("rubric_id"))
            selected_list_id = request.form.get("student_list_id")  
            r = EvalRound(name=name, rubric_id=rubric_id, status="active")
            db.session.add(r); db.session.flush()
        
            students = Student.query.all()
            by_team = {}
            for s in students:
                by_team.setdefault(s.team, []).append(s)
            pairs = 0
            for team, members in by_team.items():
                for evaluator in members:
                    for evaluatee in members:
                        if evaluator.id == evaluatee.id: 
                            continue
                        db.session.add(EvaluationToken(eval_round_id=r.id, evaluator_id=evaluator.id, evaluatee_id=evaluatee.id))
                        pairs += 1
            db.session.commit()

            base = request.url_root.rstrip("/")
            emails = 0
            for team, members in by_team.items():
                for evaluator in members:
                    tokens = EvaluationToken.query.filter_by(eval_round_id=r.id, evaluator_id=evaluator.id).all()
                    links = [f"- Evaluate {t.evaluatee.full_name}: {base}" + url_for('evaluate', token=t.token) for t in tokens]
                    body = f"""Hello {evaluator.first_name},

    You have peer evaluations to complete for round '{r.name}'. Please complete a form for each teammate:

    {chr(10).join(links)}

    Each link is unique to you and your teammate. Please do not share.

    Thank you.
    """
                    send_email(evaluator.email, f"Peer Evaluations - {r.name}", body)
                    for t in tokens:
                        t.sent_at = datetime.utcnow()
                    emails += 1
            db.session.commit()

            flash(f"Round '{r.name}' started. Generated {pairs} evaluation links and sent {emails} emails (or outbox entries).", "success")
            return redirect(url_for("dashboard"))

        return render_template("start_round.html", rubrics=rubrics)

    @app.route("/outbox")
    @login_required
    def outbox():
        msgs = DevOutbox.query.order_by(DevOutbox.created_at.desc()).limit(200).all()
        return render_template("outbox.html", msgs=msgs)

    @app.route("/evaluate/<token>", methods=["GET","POST"])
    def evaluate(token):
        t = EvaluationToken.query.filter_by(token=token).first_or_404()
        round = t.eval_round
        if round.status != "active":
            return render_template("evaluation_form.html", closed=True, t=t, rubric=round.rubric)
        if request.method == "POST":
            if t.submitted_at is not None:
                flash("This evaluation was already submitted.", "warning")
                return redirect(request.url)
            scores = {}
            for item in round.rubric.items:
                key = f"criterion_{item.id}"
                try:
                    val = int(request.form.get(key, "0"))
                except ValueError:
                    val = 0
                val = max(0, min(item.max_score, val))
                scores[str(item.id)] = val
            comments = request.form.get("comments","").strip()
            resp = EvaluationResponse(token_id=t.id, scores=scores, comments=comments)
            t.submitted_at = datetime.utcnow()
            db.session.add(resp); db.session.commit()
            return render_template("evaluation_form.html", submitted=True, t=t, rubric=round.rubric)
        return render_template("evaluation_form.html", t=t, rubric=round.rubric)

    @app.route("/rounds/<int:round_id>/report")
    @login_required
    def report(round_id):
        r = db.session.get(EvalRound, round_id) or abort(404)
        tokens = EvaluationToken.query.filter_by(eval_round_id=round_id).all()
        rows = []
        for t in tokens:
            evaluator = t.evaluator.full_name
            evaluatee = t.evaluatee.full_name
            team = t.evaluatee.team
            if t.response:
                submitted = t.response.submitted_at
                scores = t.response.scores
                comments = t.response.comments or ""
            else:
                submitted = None
                scores = {}
                comments = ""
            rows.append({
                "round": r.name,
                "team": team,
                "evaluator": evaluator,
                "evaluatee": evaluatee,
                "submitted_at": submitted.isoformat() if submitted else "",
                "scores": scores,
                "comments": comments
            })
        rubric_items = {str(it.id): (it.criterion, it.weight, it.max_score) for it in r.rubric.items}
        raw_records = []
        for row in rows:
            base = {
                "Round": row["round"],
                "Team": row["team"],
                "Evaluator": row["evaluator"],
                "Evaluatee": row["evaluatee"],
                "Submitted At": row["submitted_at"],
                "Comments": row["comments"]
            }
            for cid, (crit, weight, max_score) in rubric_items.items():
                base[f"{crit} (score/{max_score})"] = row["scores"].get(cid, "")
            raw_records.append(base)
        df_raw = pd.DataFrame(raw_records)

        per_eval = []
        for row in rows:
            s = row["scores"]
            if not s: 
                continue
            total_weight = sum(w for (_, w, _) in rubric_items.values())
            if total_weight == 0: total_weight = 1
            weighted = 0.0
            for cid, (crit, weight, max_score) in rubric_items.items():
                val = int(s.get(cid, 0))
                weighted += (val / max_score) * weight if max_score else 0
            score_pct = (weighted / total_weight) * 100.0
            per_eval.append({
                "Evaluatee": row["evaluatee"],
                "Team": row["team"],
                "Evaluator": row["evaluator"],
                "Score %": round(score_pct, 2)
            })
        df_eval = pd.DataFrame(per_eval)
        if not df_eval.empty:
            df_scores = df_eval.groupby(["Evaluatee", "Team"]).agg(
                Avg_Score_Pct=("Score %", "mean"),
                N_Evals=("Score %", "count")
            ).reset_index().sort_values(["Team","Evaluatee"])
        else:
            df_scores = pd.DataFrame(columns=["Evaluatee","Team","Avg_Score_Pct","N_Evals"])

        summaries = []
        by_student_comments = {}
        for row in rows:
            if row["comments"]:
                by_student_comments.setdefault((row["evaluatee"], row["team"]), []).append(row["comments"])
        api_key = current_app.config.get("OPENAI_API_KEY")
        for (eval_name, team), comments in by_student_comments.items():
            if api_key:
                summary = openai_summarize(api_key, comments)
            else:
                summary = simple_summarize(comments, max_sentences=3)
            flags = sorted({f for c in comments for f in detect_red_flags(c)})
            summaries.append({
                "Evaluatee": eval_name,
                "Team": team,
                "Summary": summary,
                "Red Flags": ", ".join(flags)
            })
        df_sum = pd.DataFrame(summaries) if summaries else pd.DataFrame(columns=["Evaluatee","Team","Summary","Red Flags"])

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_raw.to_excel(writer, sheet_name="RawFeedback", index=False)
            df_scores.to_excel(writer, sheet_name="Scores", index=False)
            df_sum.to_excel(writer, sheet_name="Summaries", index=False)
        output.seek(0)
        filename = f"peer-eval-report-round-{r.id}.xlsx"
        return send_file(output, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.route("/rounds/<int:round_id>/close", methods=["POST"])
    @login_required
    def close_round(round_id):
        r = db.session.get(EvalRound, round_id) or abort(404)
        r.status = "closed"
        db.session.commit()
        flash("Round closed. Evaluations can no longer be submitted.", "info")
        return redirect(url_for("dashboard"))

    @app.route("/rounds/<int:round_id>/delete", methods=["POST"])
    @login_required
    def delete_round(round_id):
        r = db.session.get(EvalRound, round_id) or abort(404)

        tokens = EvaluationToken.query.filter_by(eval_round_id=round_id).all()
        token_ids = [t.id for t in tokens]
        token_strings = [t.token for t in tokens if getattr(t, "token", None)]

        deleted_outbox = False
        try:
            outs = DevOutbox.query.filter_by(eval_round_id=round_id).all()
            for o in outs:
                db.session.delete(o)
            deleted_outbox = True
        except Exception:
            pass

        if not deleted_outbox:
            try:
                if token_ids:
                    outs = DevOutbox.query.filter(DevOutbox.token_id.in_(token_ids)).all()
                    for o in outs:
                        db.session.delete(o)
                    deleted_outbox = True
            except Exception:
                pass

        if not deleted_outbox and token_strings:
            try:
                filters = [DevOutbox.body.contains(ts) for ts in token_strings]
                if filters:
                    outs = DevOutbox.query.filter(or_(*filters)).all()
                    for o in outs:
                        db.session.delete(o)
            except Exception:
                pass

        for t in tokens:
            if getattr(t, "response", None):
                try:
                    db.session.delete(t.response)
                except Exception:
                    pass
            db.session.delete(t)

        db.session.delete(r)
        db.session.commit()
        flash("Round deleted (tokens, responses, and related outbox entries removed).", "info")
        return redirect(url_for("dashboard"))
    return app

def init_db(app):
    with app.app_context():
        db.create_all()

def seed_admin(app, email: str, password: str):
    with app.app_context():
        existing = User.query.filter_by(email=email.lower()).first()
        if existing:
            print("Admin already exists.")
            return
        u = User(email=email.lower())
        u.set_password(password)
        db.session.add(u); db.session.commit()
        print(f"Created admin user: {email}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Peer Evaluation App")
    parser.add_argument("--init-admin", action="store_true", help="Create an admin user (interactive)")
    args = parser.parse_args()

    app = create_app()
    init_db(app)

    if args.init_admin:
        email = input("Admin email: ").strip()
        pwd = input("Admin password: ").strip()
        seed_admin(app, email, pwd)
    else:
        app.run(host="0.0.0.0", port=5000)