from datetime import datetime
import uuid
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint
from sqlalchemy.types import JSON as SAJSON
from sqlalchemy.orm import validates

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    team = db.Column(db.String(120), nullable=False)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class Rubric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True)
    items = db.relationship("RubricItem", backref="rubric", cascade="all, delete-orphan")

class RubricItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rubric_id = db.Column(db.Integer, db.ForeignKey("rubric.id"), nullable=False)
    criterion = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    weight = db.Column(db.Float, nullable=False, default=1.0)
    max_score = db.Column(db.Integer, nullable=False, default=5)

class EvalRound(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    rubric_id = db.Column(db.Integer, db.ForeignKey("rubric.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="draft") 
    rubric = db.relationship("Rubric")

class EvaluationToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    eval_round_id = db.Column(db.Integer, db.ForeignKey("eval_round.id"), nullable=False)
    evaluator_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    evaluatee_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)

    eval_round = db.relationship("EvalRound", backref="tokens")
    evaluator = db.relationship("Student", foreign_keys=[evaluator_id])
    evaluatee = db.relationship("Student", foreign_keys=[evaluatee_id])

    __table_args__ = (
        UniqueConstraint("eval_round_id", "evaluator_id", "evaluatee_id", name="uq_round_evalpair"),
    )

class EvaluationResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.Integer, db.ForeignKey("evaluation_token.id"), nullable=False, unique=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    scores = db.Column(SAJSON, nullable=False) 
    comments = db.Column(db.Text, nullable=True)

    token = db.relationship("EvaluationToken", backref=db.backref("response", uselist=False))                                    ###

class DevOutbox(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    to_addr = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)