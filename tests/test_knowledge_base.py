"""Unit tests for the knowledge base lookup (test_knowledge_base.py)."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import knowledge_base


def test_at_pet_rule():
    rule = knowledge_base.lookup_rule('AT', 'Plastic (PET)')
    assert rule is not None
    assert rule['bin_color'] == 'yellow'
    assert rule['category'] == 'recyclable'
    assert isinstance(rule['prep'], list)
    assert len(rule['prep']) > 0


def test_de_glass_rule():
    rule = knowledge_base.lookup_rule('DE', 'Glass')
    assert rule is not None
    assert 'white' in rule['bin_color'].lower() or 'green' in rule['bin_color'].lower()


def test_kr_organic_has_bag_instruction():
    rule = knowledge_base.lookup_rule('KR', 'Organic')
    assert rule is not None
    # Korea requires designated food waste bags
    all_text = ' '.join(rule.get('prep', []) + [rule.get('notes', '')])
    assert 'bag' in all_text.lower() or '봉투' in all_text


def test_global_fallback_for_unknown_region():
    rule = knowledge_base.lookup_rule('XX', 'Paper')
    assert rule is not None  # falls back to GLOBAL
    assert rule['category'] == 'recyclable'


def test_fuzzy_lookup():
    # 'Plastic' should match 'Plastic (PET)' or 'Plastic' depending on fuzzy logic
    rule = knowledge_base.lookup_rule('AT', 'Plastic')
    assert rule is not None


def test_no_rule_for_unknown_material():
    rule = knowledge_base.lookup_rule('AT', 'XyzUnknownMaterial999')
    # Should fall back to GLOBAL, and GLOBAL also won't have it → None
    assert rule is None


def test_list_supported_regions():
    regions = knowledge_base.list_supported_regions()
    codes = [r['code'] for r in regions]
    assert 'AT' in codes
    assert 'DE' in codes
    assert 'KR' in codes
    assert 'GLOBAL' in codes
