"""Integration test: full HTTP scan pipeline with a fixture image (test_pipeline.py)."""
import sys
import os
import io
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from fastapi.testclient import TestClient

# Set a tmp DB so tests don't touch production data
import database
_TMP_DB = os.path.join(os.path.dirname(__file__), 'fixtures', '_test.db')
os.makedirs(os.path.join(os.path.dirname(__file__), 'fixtures'), exist_ok=True)
database.DB_PATH = _TMP_DB

from main import app

client = TestClient(app)
TEST_USER = 'integration-test-user'


def _make_jpeg(w=320, h=240, color=(80, 150, 80)) -> bytes:
    """Create a small solid-color JPEG for testing."""
    img = Image.new('RGB', (w, h), color)
    draw = ImageDraw.Draw(img)
    # Draw a green rectangle resembling a bottle
    draw.rectangle([80, 40, 160, 200], fill=(0, 200, 100), outline=(0, 100, 50), width=3)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return buf.getvalue()


def _make_png_too_large() -> bytes:
    buf = io.BytesIO(b'\xff\xd8\xff' + b'0' * (16 * 1024 * 1024))
    return buf.getvalue()


# ── File validation ───────────────────────────────────────────────────────────

def test_reject_oversized_file():
    large_data = b'\x89PNG' + b'0' * (16 * 1024 * 1024)
    resp = client.post(
        '/api/scan',
        files={'file': ('big.png', large_data, 'image/png')},
        headers={'X-User-Id': TEST_USER},
    )
    assert resp.status_code == 400
    assert 'large' in resp.json()['detail'].lower()


def test_reject_wrong_extension():
    resp = client.post(
        '/api/scan',
        files={'file': ('photo.gif', b'GIF89a', 'image/gif')},
        headers={'X-User-Id': TEST_USER},
    )
    assert resp.status_code == 400


def test_scan_returns_valid_structure():
    jpeg = _make_jpeg()
    resp = client.post(
        '/api/scan',
        files={'file': ('test.jpg', jpeg, 'image/jpeg')},
        headers={'X-User-Id': TEST_USER},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert 'items' in data
    assert 'image_width' in data
    assert 'image_height' in data
    assert isinstance(data['items'], list)


# ── Location endpoints ────────────────────────────────────────────────────────

def test_set_location_by_country():
    resp = client.put(
        '/api/location',
        json={'country': 'AT'},
        headers={'X-User-Id': TEST_USER},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d['region_code'] == 'AT'


def test_set_location_by_gps_austria():
    resp = client.put(
        '/api/location',
        json={'latitude': 48.2, 'longitude': 16.37},  # Vienna
        headers={'X-User-Id': TEST_USER},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d['region_code'] == 'AT'


def test_set_location_unknown_coords_falls_back_to_global():
    resp = client.put(
        '/api/location',
        json={'latitude': 0.0, 'longitude': 0.0},  # Gulf of Guinea
        headers={'X-User-Id': TEST_USER},
    )
    assert resp.status_code == 200
    assert resp.json()['region_code'] == 'GLOBAL'


# ── Instructions endpoint ─────────────────────────────────────────────────────

def test_instructions_at_pet():
    # Requires Ollama — but should return a response (even the fallback)
    resp = client.get(
        '/api/instructions',
        params={'item': 'Bottle', 'material': 'Plastic (PET)', 'region': 'AT', 'lang': 'en'},
        headers={'X-User-Id': TEST_USER},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d['bin_color'] == 'yellow'
    assert d['category'] == 'recyclable'
    assert len(d['prep_steps']) > 0
    assert d['ai_generated'] is True
    assert 'disclaimer' in d


def test_instructions_global_fallback_for_unknown_region():
    resp = client.get(
        '/api/instructions',
        params={'item': 'Can', 'material': 'Aluminum', 'region': 'XX', 'lang': 'en'},
        headers={'X-User-Id': TEST_USER},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d['category'] == 'recyclable'


# ── Consent & history ─────────────────────────────────────────────────────────

def test_history_empty_without_consent():
    uid = 'no-consent-user'
    resp = client.get('/api/history', headers={'X-User-Id': uid})
    assert resp.status_code == 200
    d = resp.json()
    assert d['total_scans'] == 0
    assert d['history'] == []


def test_consent_toggle():
    uid = 'consent-test-' + TEST_USER
    r1 = client.put('/api/consent', json={'consent': True},  headers={'X-User-Id': uid})
    assert r1.status_code == 200
    assert r1.json()['consent'] is True

    r2 = client.put('/api/consent', json={'consent': False}, headers={'X-User-Id': uid})
    assert r2.status_code == 200
    assert r2.json()['consent'] is False


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_endpoint():
    resp = client.get('/api/health')
    assert resp.status_code == 200
    d = resp.json()
    assert d['status'] == 'ok'
    assert 'ollama' in d
    assert 'AT' in d['supported_regions']
