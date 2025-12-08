"""
Database models for the Peer Evaluation System.

This module defines all SQLAlchemy models representing the database schema:
- User: Admin/professor accounts with authentication
- Student: Students enrolled in courses
- Course: Course/section organization
- Rubric: Evaluation rubrics with criteria
- RubricItem: Individual criteria within a rubric
- EvalRound: Evaluation rounds/periods
- EvaluationToken: Unique tokens for each evaluator-evaluatee pair
- EvaluationResponse: Submitted evaluation scores and comments
- DevOutbox: Development email storage (when SMTP not configured)
"""

from datetime import datetime
import uuid
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint
from sqlalchemy.types import JSON as SAJSON
from sqlalchemy.orm import validates

# SQLAlchemy database instance (initialized by Flask app)
db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Admin/professor user account model.
    
    Stores login credentials for professors who manage the evaluation system.
    Uses Flask-Login's UserMixin for session management.
    """
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password: str):
        """Hash and store a password securely."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        return check_password_hash(self.password_hash, password)

class Student(db.Model):
    """Student model representing enrolled students.
    
    Each student belongs to a team and optionally a course.
    Students can be evaluators (giving evaluations) or evaluatees (receiving evaluations).
    """
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    team = db.Column(db.String(120), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=True)

    @property
    def full_name(self):
        """Return formatted full name (first + last)."""
        return f"{self.first_name} {self.last_name}"

class Rubric(db.Model):
    """Rubric model for evaluation criteria.
    
    A rubric contains multiple RubricItems (criteria) that define
    what aspects of performance are being evaluated.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True)
    # Relationship: deleting a rubric also deletes all its items
    items = db.relationship("RubricItem", backref="rubric", cascade="all, delete-orphan")

class Course(db.Model):
    """Course model for organizing students by course/section.
    
    Courses can have multiple sections (e.g., "SWE 4724" with sections "W01", "W02").
    Students are associated with a course via course_id foreign key.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    section = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    students = db.relationship("Student", backref="course")

    @property
    def display_name(self):
        """Return formatted course name with section if available."""
        return f"{self.name} section {self.section}" if self.section else self.name

class RubricItem(db.Model):
    """Individual criterion within a rubric.
    
    Each item defines:
    - criterion: Name of the evaluation criterion (e.g., "Communication")
    - description: Detailed description with scoring anchors
    - weight: Relative importance in weighted scoring
    - max_score: Maximum possible score (typically 1-5)
    """
    id = db.Column(db.Integer, primary_key=True)
    rubric_id = db.Column(db.Integer, db.ForeignKey("rubric.id"), nullable=False)
    criterion = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    weight = db.Column(db.Float, nullable=False, default=1.0)
    max_score = db.Column(db.Integer, nullable=False, default=5)

class EvalRound(db.Model):
    """Evaluation round model representing a single evaluation period.
    
    Each round:
    - Has a name (e.g., "Fall 2025 - Sprint 1")
    - Uses a specific rubric
    - Has a status: "draft", "active", or "closed"
    - Contains multiple EvaluationTokens (one per evaluator-evaluatee pair)
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    rubric_id = db.Column(db.Integer, db.ForeignKey("rubric.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="draft")  # draft, active, or closed
    rubric = db.relationship("Rubric")

class EvaluationToken(db.Model):
    """Unique evaluation token for each evaluator-evaluatee pair.
    
    Each token represents one evaluation opportunity:
    - One student (evaluator) evaluating another student (evaluatee)
    - Within a specific evaluation round
    - Has a unique token string used in the evaluation URL
    
    The UniqueConstraint ensures no duplicate (round, evaluator, evaluatee) pairs,
    preventing the same student from evaluating the same peer twice in one round.
    """
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

    # Database constraint: prevents duplicate evaluations (same evaluator can't evaluate same student twice in one round)
    __table_args__ = (
        UniqueConstraint("eval_round_id", "evaluator_id", "evaluatee_id", name="uq_round_evalpair"),
    )

class EvaluationResponse(db.Model):
    """Submitted evaluation response model.
    
    Stores the actual evaluation data:
    - scores: JSON dict mapping rubric item IDs to numeric scores
    - comments: Optional text feedback
    - submitted_at: Timestamp when evaluation was completed
    
    Each token can only have one response (unique token_id constraint).
    """
    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.Integer, db.ForeignKey("evaluation_token.id"), nullable=False, unique=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    scores = db.Column(SAJSON, nullable=False) 
    comments = db.Column(db.Text, nullable=True)

    # One-to-one relationship: each token has at most one response
    token = db.relationship("EvaluationToken", backref=db.backref("response", uselist=False))

class DevOutbox(db.Model):
    """Development outbox for storing emails when SMTP is not configured.
    
    In development mode (no SMTP server), emails are stored here instead of being sent.
    Professors can view these emails in the UI to access evaluation links.
    """
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    to_addr = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)