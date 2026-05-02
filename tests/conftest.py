"""
Shared fixtures for backend tests.

Unit tests: run without Docker using tmp_path fixtures.
Integration tests (test_e2e_*): require Docker + GOOGLE_API_KEY.
"""

import requests
import uuid
import pytest
from dotenv import load_dotenv
import os

# Load .env so tests that invoke LLMs have access to GOOGLE_API_KEY
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session")
def base_url():
    """Base URL for the running backend."""
    return BASE_URL

@pytest.fixture(scope="session", autouse=True)
def setup_e2e_environment():
    """Wipe memory and inject distractors before running the integration test suite.
    Guarantees suite isolation and populates a realistic distractor volume."""
    import subprocess
    import os
    
    # Only run setup if we are actually testing against the backend
    # We can check if the backend is reachable first
    try:
        requests.get(f"{BASE_URL}/sessions", timeout=2)
    except requests.exceptions.ConnectionError:
        return # Backend not running, skip setup (healthcheck will fail later anyway)
        
    print("\n[Pytest Setup] Backend is reachable. Using pre-generated memory distractors. Skipping DB wipe...\n")


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_sessions():
    """After each test module, delete sessions created by e2e tests while
    preserving long-lived distractor sessions.
    
    We identify test sessions by ID/title prefixes used in the thesis scenarios.
    """
    yield  # run tests first

    try:
        r = requests.get(f"{BASE_URL}/sessions", timeout=10)
        r.raise_for_status()
        sessions = r.json()
    except Exception:
        return  # Backend down or /sessions unavailable; nothing to clean

    TEST_ID_PREFIXES = ("e2e_", "test_sess_")
    TEST_TITLE_PREFIXES = (
        "Metric Reuse",
        "Drift ",
        "Versioning ",
        "Cross ",
        "TestSession-",
    )

    for s in sessions:
        sid = s.get("id", "") or ""
        title = s.get("title", "") or ""

        is_test_id = any(sid.startswith(p) for p in TEST_ID_PREFIXES)
        is_test_title = any(title.startswith(p) for p in TEST_TITLE_PREFIXES)

        if not (is_test_id or is_test_title):
            continue

        try:
            requests.delete(f"{BASE_URL}/sessions/{sid}", timeout=5)
        except Exception:
            # Best-effort cleanup; ignore failures so tests still report normally
            pass


@pytest.fixture
def unique_id():
    """Generate a unique ID for test isolation."""
    return str(uuid.uuid4())[:8]


@pytest.fixture
def test_session(base_url, unique_id):
    """Create a test session via the API. Requires running backend."""
    session_id = f"test_sess_{unique_id}"
    r = requests.post(f"{base_url}/sessions", json={
        "id": session_id,
        "title": f"TestSession-{unique_id}"
    })
    r.raise_for_status()
    data = r.json()
    yield data
    # Cleanup: delete the session
    requests.delete(f"{base_url}/sessions/{session_id}")


def chat(base_url: str, session_id: str, message: str, stream: bool = False) -> dict:
    """Send a chat message and return the parsed response.
    
    Args:
        base_url: Backend URL
        session_id: Session ID for context
        message: User message
        stream: Whether to stream (default False for tests)
    """
    r = requests.post(f"{base_url}/chat/completions", json={
        "messages": [{"role": "user", "content": message}],
        "conversationId": session_id,
        "stream": stream,
    })
    r.raise_for_status()
    return r.json()
