"""Tests for the ID obfuscator utility"""

import pytest

from src.utils.id_obfuscator import (
    ENTITY_PREFIXES,
    decode,
    encode,
    format_public_id,
    parse_public_id,
)


class TestEncodeDecode:
    """Tests for encode/decode roundtrip"""

    def test_encode_positive_int(self):
        encoded = encode(42)
        assert isinstance(encoded, str)
        assert len(encoded) >= 10
        assert encoded.isalnum()

    def test_encode_decode_roundtrip(self):
        for real_id in [1, 42, 100, 999, 1000000]:
            encoded = encode(real_id)
            decoded = decode(encoded)
            assert decoded == real_id, f"Failed roundtrip for {real_id}: {encoded} -> {decoded}"

    def test_consecutive_ids_differ(self):
        id1 = encode(42)
        id2 = encode(43)
        assert id1 != id2, "Consecutive IDs should produce different encoded strings"

    def test_decode_invalid_string(self):
        assert decode("") is None
        assert decode("!!!") is None
        assert decode("abc123!!!") is None

    def test_decode_none(self):
        assert decode("") is None

    def test_encode_negative_raises(self):
        with pytest.raises(ValueError, match="Cannot encode negative ID"):
            encode(-1)


class TestFormatParse:
    """Tests for format_public_id / parse_public_id"""

    def test_format_review(self):
        public_id = format_public_id("review", 42)
        assert public_id.startswith("rev_")
        assert len(public_id) > 4
        # The part after rev_ should be decodable
        encoded = public_id.split("_", 1)[1]
        assert decode(encoded) == 42

    def test_parse_review(self):
        public_id = format_public_id("review", 42)
        result = parse_public_id(public_id)
        assert result is not None
        entity, real_id = result
        assert entity == "review"
        assert real_id == 42

    def test_format_parse_roundtrip_all_types(self):
        for entity_type in ENTITY_PREFIXES:
            for real_id in [1, 42, 999]:
                public_id = format_public_id(entity_type, real_id)
                result = parse_public_id(public_id)
                assert result is not None, f"Failed to parse {public_id}"
                assert result == (entity_type, real_id)

    def test_parse_invalid(self):
        assert parse_public_id("") is None
        assert parse_public_id("no_underscore") is None
        assert parse_public_id("xxx_") is None
        assert parse_public_id("xxx_invalid") is None

    def test_unknown_entity_type_raises(self):
        with pytest.raises(ValueError, match="Unknown entity type"):
            format_public_id("unknown", 42)

    def test_format_score(self):
        public_id = format_public_id("score", 100)
        assert public_id.startswith("sco_")
        result = parse_public_id(public_id)
        assert result == ("score", 100)

    def test_format_user(self):
        public_id = format_public_id("user", 5)
        assert public_id.startswith("usr_")
        result = parse_public_id(public_id)
        assert result == ("user", 5)

    def test_format_rule(self):
        public_id = format_public_id("rule", 7)
        assert public_id.startswith("rule_")
        result = parse_public_id(public_id)
        assert result == ("rule", 7)
