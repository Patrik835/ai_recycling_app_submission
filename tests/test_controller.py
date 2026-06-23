"""Unit tests for controller logic (scan pipeline, instructions, impact)."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import database
from controller import _infer_category, get_impact_stats

# ── _infer_category ───────────────────────────────────────────────────────────

def test_infer_category_recyclable():
    assert _infer_category('Plastic (PET)') == 'recyclable'
    assert _infer_category('Glass') == 'recyclable'
    assert _infer_category('Aluminum') == 'recyclable'
    assert _infer_category('Paper') == 'recyclable'
    assert _infer_category('Cardboard') == 'recyclable'


def test_infer_category_compostable():
    assert _infer_category('Organic') == 'compostable'
    assert _infer_category('Food Waste') == 'compostable'


def test_infer_category_special():
    assert _infer_category('E-Waste') == 'special disposal'
    assert _infer_category('Electronic Device') == 'special disposal'


def test_infer_category_landfill():
    assert _infer_category('Unknown material') == 'landfill'


# ── database consent gate ─────────────────────────────────────────────────────

def test_consent_gate(tmp_path, monkeypatch):
    """History must NOT be saved when consent is False (NfReq10, SUC5)."""
    db_path = str(tmp_path / 'test.db')
    monkeypatch.setattr(database, 'DB_PATH', db_path)
    database.init_db()

    uid = 'test-user-001'
    database.ensure_user(uid)
    database.set_consent(uid, False)

    database.save_scan(uid, 'Bottle', 'Plastic (PET)', 'recyclable', 'AT', 0.18, 2.6)

    rows, co2, energy, total = database.get_history(uid)
    assert total == 0, "No scans should be saved without consent"


def test_save_with_consent(tmp_path, monkeypatch):
    """History IS saved when consent is True."""
    db_path = str(tmp_path / 'test.db')
    monkeypatch.setattr(database, 'DB_PATH', db_path)
    database.init_db()

    uid = 'test-user-002'
    database.ensure_user(uid)
    database.set_consent(uid, True)

    database.save_scan(uid, 'Can', 'Aluminum', 'recyclable', 'DE', 9.0, 14.0)

    rows, co2, energy, total = database.get_history(uid)
    assert total == 1
    assert abs(co2 - 9.0) < 0.01
    assert rows[0]['item_name'] == 'Can'


def test_clear_history_on_revoke_consent(tmp_path, monkeypatch):
    """When consent is revoked, history is cleared (GDPR)."""
    db_path = str(tmp_path / 'test.db')
    monkeypatch.setattr(database, 'DB_PATH', db_path)
    database.init_db()

    uid = 'test-user-003'
    database.ensure_user(uid)
    database.set_consent(uid, True)
    database.save_scan(uid, 'Bottle', 'Glass', 'recyclable', 'AT', 0.3, 0.5)

    # Revoke consent
    database.set_consent(uid, False)
    database.clear_history(uid)

    rows, co2, energy, total = database.get_history(uid)
    assert total == 0
