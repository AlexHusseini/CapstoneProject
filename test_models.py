"""Tests for database models."""
import pytest
from models import db, User, Student, Rubric, RubricItem, EvalRound, EvaluationToken, EvaluationResponse, Course
from werkzeug.security import check_password_hash


@pytest.fixture
def app():
    """Create application for testing."""
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


def test_user_password_hashing(app):
    """Test that user passwords are hashed correctly."""
    with app.app_context():
        user = User(email="test@example.com")
        user.set_password("testpass123")
        assert user.password_hash != "testpass123"
        assert user.check_password("testpass123")
        assert not user.check_password("wrongpass")


def test_student_full_name(app):
    """Test Student full_name property."""
    with app.app_context():
        student = Student(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            team="Team A"
        )
        assert student.full_name == "John Doe"


def test_course_display_name(app):
    """Test Course display_name property."""
    with app.app_context():
        course_with_section = Course(name="SWE 4724", section="W01")
        assert course_with_section.display_name == "SWE 4724 section W01"
        
        course_no_section = Course(name="SWE 4724", section=None)
        assert course_no_section.display_name == "SWE 4724"


def test_rubric_relationship(app):
    """Test Rubric and RubricItem relationship."""
    with app.app_context():
        rubric = Rubric(name="Test Rubric")
        db.session.add(rubric)
        db.session.flush()
        
        item = RubricItem(
            rubric_id=rubric.id,
            criterion="Quality",
            description="Test description",
            weight=1.0,
            max_score=5
        )
        db.session.add(item)
        db.session.commit()
        
        assert len(rubric.items) == 1
        assert rubric.items[0].criterion == "Quality"


def test_eval_round_creation(app):
    """Test EvalRound creation."""
    with app.app_context():
        rubric = Rubric(name="Test Rubric")
        db.session.add(rubric)
        db.session.flush()
        
        round = EvalRound(name="Test Round", rubric_id=rubric.id, status="active")
        db.session.add(round)
        db.session.commit()
        
        assert round.name == "Test Round"
        assert round.rubric_id == rubric.id
        assert round.status == "active"


def test_evaluation_token_creation(app):
    """Test EvaluationToken creation."""
    with app.app_context():
        student1 = Student(first_name="Alice", last_name="Smith", email="alice@example.com", team="Team A")
        student2 = Student(first_name="Bob", last_name="Jones", email="bob@example.com", team="Team A")
        rubric = Rubric(name="Test Rubric")
        db.session.add_all([student1, student2, rubric])
        db.session.flush()
        
        round = EvalRound(name="Test Round", rubric_id=rubric.id, status="active")
        db.session.add(round)
        db.session.flush()
        
        token = EvaluationToken(
            eval_round_id=round.id,
            evaluator_id=student1.id,
            evaluatee_id=student2.id
        )
        db.session.add(token)
        db.session.commit()
        
        assert token.evaluator_id == student1.id
        assert token.evaluatee_id == student2.id
        assert token.token is not None


def test_evaluation_response_creation(app):
    """Test EvaluationResponse creation."""
    with app.app_context():
        student1 = Student(first_name="Alice", last_name="Smith", email="alice@example.com", team="Team A")
        student2 = Student(first_name="Bob", last_name="Jones", email="bob@example.com", team="Team A")
        rubric = Rubric(name="Test Rubric")
        db.session.add_all([student1, student2, rubric])
        db.session.flush()
        
        round = EvalRound(name="Test Round", rubric_id=rubric.id, status="active")
        db.session.add(round)
        db.session.flush()
        
        token = EvaluationToken(
            eval_round_id=round.id,
            evaluator_id=student1.id,
            evaluatee_id=student2.id
        )
        db.session.add(token)
        db.session.flush()
        
        response = EvaluationResponse(
            token_id=token.id,
            scores={"1": 4, "2": 5},
            comments="Great work!"
        )
        db.session.add(response)
        db.session.commit()
        
        assert response.scores == {"1": 4, "2": 5}
        assert response.comments == "Great work!"

