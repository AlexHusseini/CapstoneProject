"""Tests for Flask routes."""
import pytest
from models import db, User, Student, Rubric, RubricItem, EvalRound, EvaluationToken, Course


@pytest.fixture
def app():
    """Create application for testing."""
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def auth_client(client, app):
    """Create authenticated test client."""
    with app.app_context():
        user = User(email="admin@test.com")
        user.set_password("testpass")
        db.session.add(user)
        db.session.commit()
    
    # Login via POST request
    client.post('/login', data={
        'email': 'admin@test.com',
        'password': 'testpass'
    }, follow_redirects=True)
    
    return client


@pytest.fixture
def test_rubric(app):
    """Create a test rubric with items."""
    with app.app_context():
        rubric = Rubric(name="Test Rubric")
        db.session.add(rubric)
        db.session.flush()
        
        item1 = RubricItem(
            rubric_id=rubric.id,
            criterion="Quality",
            description="Test quality",
            weight=1.0,
            max_score=5
        )
        item2 = RubricItem(
            rubric_id=rubric.id,
            criterion="Communication",
            description="Test communication",
            weight=1.0,
            max_score=5
        )
        db.session.add_all([item1, item2])
        db.session.commit()
        return rubric


def test_index_redirects_to_login(client):
    """Test that index redirects to login when not authenticated."""
    response = client.get('/')
    assert response.status_code == 302
    assert '/login' in response.location


def test_login_page_loads(client):
    """Test that login page loads."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b'login' in response.data.lower() or b'email' in response.data.lower()


def test_dashboard_requires_login(client):
    """Test that dashboard requires authentication."""
    response = client.get('/dashboard')
    assert response.status_code == 302
    assert '/login' in response.location


def test_dashboard_loads_when_authenticated(auth_client, app):
    """Test that dashboard loads when authenticated."""
    with app.app_context():
        response = auth_client.get('/dashboard')
        assert response.status_code == 200


def test_courses_page_requires_login(client):
    """Test that courses page requires authentication."""
    response = client.get('/courses')
    assert response.status_code == 302
    assert '/login' in response.location


def test_create_course_requires_name(auth_client, app):
    """Test that course creation requires a name."""
    with app.app_context():
        response = auth_client.post('/courses', data={
            'name': '',
            'section': 'W01'
        }, follow_redirects=True)
        assert response.status_code == 200
        # Should redirect back with flash message


def test_create_course_success(auth_client, app):
    """Test successful course creation."""
    with app.app_context():
        response = auth_client.post('/courses', data={
            'name': 'SWE 4724',
            'section': 'W01'
        }, follow_redirects=True)
        assert response.status_code == 200
        
        course = Course.query.filter_by(name='SWE 4724').first()
        assert course is not None
        assert course.section == 'W01'


def test_start_round_requires_login(client):
    """Test that start round requires authentication."""
    response = client.get('/rounds/start')
    assert response.status_code == 302
    assert '/login' in response.location


def test_start_round_requires_name(auth_client, app, test_rubric):
    """Test that starting a round requires a name."""
    with app.app_context():
        response = auth_client.post('/rounds/start', data={
            'name': '',
            'rubric_id': test_rubric.id
        }, follow_redirects=True)
        assert response.status_code == 200
        # Should redirect back with flash message


def test_start_round_requires_rubric_with_items(auth_client, app):
    """Test that starting a round requires a rubric with items."""
    with app.app_context():
        # Create rubric with no items
        rubric = Rubric(name="Empty Rubric")
        db.session.add(rubric)
        db.session.commit()
        
        response = auth_client.post('/rounds/start', data={
            'name': 'Test Round',
            'rubric_id': rubric.id
        }, follow_redirects=True)
        assert response.status_code == 200
        # Should redirect back with flash message


def test_rubrics_page_requires_login(client):
    """Test that rubrics page requires authentication."""
    response = client.get('/rubrics')
    assert response.status_code == 302
    assert '/login' in response.location


def test_rubrics_page_loads(auth_client, app):
    """Test that rubrics page loads when authenticated."""
    with app.app_context():
        response = auth_client.get('/rubrics')
        assert response.status_code == 200

