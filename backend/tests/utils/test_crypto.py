"""Unit tests for utils/crypto.py — Fernet encryption helpers and EncryptedJSON column type.

Tests cover:
- encrypt_dict / decrypt_dict round-trip
- Encrypted values are opaque (no plaintext leakage)
- EncryptedJSON SQLAlchemy TypeDecorator bind/result value paths
- None handling
- Decryption failure → plaintext JSON fallback + warning log
- Total corruption → empty dict fallback
- Key loading from environment variable
"""
from __future__ import annotations

import json
import logging
import os

import pytest
from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_fernet(monkeypatch):
    """Give every test its own fresh Fernet key so tests don't interfere.

    Uses monkeypatch for the env var so the original value is restored
    automatically after each test. Also resets the module-level singleton.
    """
    import utils.crypto as crypto

    fresh_key = Fernet.generate_key().decode()
    monkeypatch.setenv("OANNES_SECRET_KEY", fresh_key)
    crypto._fernet = None          # force reload with the new key
    yield
    crypto._fernet = None          # ensure no stale key leaks to next test


# ---------------------------------------------------------------------------
# encrypt_dict / decrypt_dict — round-trip
# ---------------------------------------------------------------------------

class TestEncryptDecryptRoundTrip:
    def test_simple_dict_round_trips(self):
        from utils.crypto import encrypt_dict, decrypt_dict
        data = {"api_token": "super-secret", "url": "https://jira.example.com"}
        assert decrypt_dict(encrypt_dict(data)) == data

    def test_empty_dict_round_trips(self):
        from utils.crypto import encrypt_dict, decrypt_dict
        assert decrypt_dict(encrypt_dict({})) == {}

    def test_nested_dict_round_trips(self):
        from utils.crypto import encrypt_dict, decrypt_dict
        data = {"outer": {"inner": [1, 2, 3]}, "flag": True}
        assert decrypt_dict(encrypt_dict(data)) == data

    def test_unicode_values_round_trip(self):
        from utils.crypto import encrypt_dict, decrypt_dict
        data = {"name": "Ünïcödé 🔑", "token": "abc123"}
        assert decrypt_dict(encrypt_dict(data)) == data

    def test_encrypted_value_is_a_string(self):
        from utils.crypto import encrypt_dict
        ct = encrypt_dict({"key": "val"})
        assert isinstance(ct, str)

    def test_encrypted_value_is_not_plaintext(self):
        from utils.crypto import encrypt_dict
        secret = "do-not-leak-this"
        ct = encrypt_dict({"token": secret})
        assert secret not in ct

    def test_two_encryptions_of_same_data_differ(self):
        """Fernet uses random IV — same plaintext must not produce identical ciphertext."""
        from utils.crypto import encrypt_dict
        data = {"token": "abc"}
        assert encrypt_dict(data) != encrypt_dict(data)

    def test_decrypt_wrong_key_raises(self):
        """Decrypting with a different key must raise an exception."""
        import utils.crypto as crypto
        from cryptography.fernet import InvalidToken

        data = {"secret": "x"}
        ct = crypto.encrypt_dict(data)

        # Swap in a *different* fresh key only for the duration of this test
        crypto._fernet = Fernet(Fernet.generate_key())
        with pytest.raises((InvalidToken, Exception)):
            crypto.decrypt_dict(ct)


# ---------------------------------------------------------------------------
# EncryptedJSON TypeDecorator — process_bind_param
# ---------------------------------------------------------------------------

class TestEncryptedJsonBind:
    def test_none_bind_returns_none(self):
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        assert col.process_bind_param(None, None) is None

    def test_dict_bind_returns_opaque_string(self):
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        result = col.process_bind_param({"token": "secret"}, None)
        assert isinstance(result, str)
        assert "secret" not in result

    def test_empty_dict_bind_returns_string(self):
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        result = col.process_bind_param({}, None)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# EncryptedJSON TypeDecorator — process_result_value
# ---------------------------------------------------------------------------

class TestEncryptedJsonResult:
    def test_none_result_returns_none(self):
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        assert col.process_result_value(None, None) is None

    def test_valid_ciphertext_decrypts_correctly(self):
        from utils.crypto import EncryptedJSON, encrypt_dict
        col = EncryptedJSON()
        original = {"api_token": "tok-123", "board_id": "XYZ"}
        ct = encrypt_dict(original)
        assert col.process_result_value(ct, None) == original

    def test_full_column_round_trip(self):
        """process_bind_param → process_result_value must recover the original dict."""
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        original = {"url": "https://jira.test", "email": "admin@test.com", "api_token": "tok"}
        stored = col.process_bind_param(original, None)
        recovered = col.process_result_value(stored, None)
        assert recovered == original

    def test_decryption_failure_falls_back_to_plain_json(self, caplog):
        """Corrupted or pre-migration plaintext JSON must be returned with a WARNING."""
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        fallback_data = {"migrated": True, "token": "old-plain"}
        plain_json = json.dumps(fallback_data)
        with caplog.at_level(logging.WARNING, logger="utils.crypto"):
            result = col.process_result_value(plain_json, None)
        assert result == fallback_data
        assert any("decryption failed" in r.message.lower() for r in caplog.records), (
            "Expected a WARNING log when decryption fails"
        )

    def test_total_corruption_returns_empty_dict(self, caplog):
        """A value that is neither valid ciphertext nor valid JSON must return {}."""
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        with caplog.at_level(logging.WARNING, logger="utils.crypto"):
            result = col.process_result_value("not-json-not-fernet!!!###", None)
        assert result == {}

    def test_decryption_failure_does_not_raise(self):
        """Callers must never see an exception — worst case is an empty dict."""
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        result = col.process_result_value("garbage", None)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Key loading
# ---------------------------------------------------------------------------

class TestKeyLoading:
    def test_key_loaded_from_env_var(self, monkeypatch):
        """When OANNES_SECRET_KEY is set, it must be used as the Fernet key."""
        import utils.crypto as crypto

        new_key = Fernet.generate_key().decode()
        monkeypatch.setenv("OANNES_SECRET_KEY", new_key)
        crypto._fernet = None   # force reload

        fernet = crypto.get_fernet()
        ct = fernet.encrypt(b"hello")
        assert fernet.decrypt(ct) == b"hello"

    def test_get_fernet_returns_same_instance(self):
        """The singleton must return the same Fernet object on repeated calls."""
        from utils.crypto import get_fernet
        f1 = get_fernet()
        f2 = get_fernet()
        assert f1 is f2



# ---------------------------------------------------------------------------
# encrypt_dict / decrypt_dict — round-trip
# ---------------------------------------------------------------------------

class TestEncryptDecryptRoundTrip:
    def test_simple_dict_round_trips(self):
        from utils.crypto import encrypt_dict, decrypt_dict
        data = {"api_token": "super-secret", "url": "https://jira.example.com"}
        assert decrypt_dict(encrypt_dict(data)) == data

    def test_empty_dict_round_trips(self):
        from utils.crypto import encrypt_dict, decrypt_dict
        assert decrypt_dict(encrypt_dict({})) == {}

    def test_nested_dict_round_trips(self):
        from utils.crypto import encrypt_dict, decrypt_dict
        data = {"outer": {"inner": [1, 2, 3]}, "flag": True}
        assert decrypt_dict(encrypt_dict(data)) == data

    def test_unicode_values_round_trip(self):
        from utils.crypto import encrypt_dict, decrypt_dict
        data = {"name": "Ünïcödé 🔑", "token": "abc123"}
        assert decrypt_dict(encrypt_dict(data)) == data

    def test_encrypted_value_is_a_string(self):
        from utils.crypto import encrypt_dict
        ct = encrypt_dict({"key": "val"})
        assert isinstance(ct, str)

    def test_encrypted_value_is_not_plaintext(self):
        from utils.crypto import encrypt_dict
        secret = "do-not-leak-this"
        ct = encrypt_dict({"token": secret})
        assert secret not in ct

    def test_two_encryptions_of_same_data_differ(self):
        """Fernet uses random IV — same plaintext must not produce identical ciphertext."""
        from utils.crypto import encrypt_dict
        data = {"token": "abc"}
        assert encrypt_dict(data) != encrypt_dict(data)

    def test_decrypt_wrong_key_raises(self):
        from cryptography.fernet import Fernet, InvalidToken
        import utils.crypto as crypto
        data = {"secret": "x"}
        ct = crypto.encrypt_dict(data)
        # Swap in a different key
        crypto._fernet = Fernet(Fernet.generate_key())
        with pytest.raises((InvalidToken, Exception)):
            crypto.decrypt_dict(ct)


# ---------------------------------------------------------------------------
# EncryptedJSON TypeDecorator — process_bind_param
# ---------------------------------------------------------------------------

class TestEncryptedJsonBind:
    def test_none_bind_returns_none(self):
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        assert col.process_bind_param(None, None) is None

    def test_dict_bind_returns_opaque_string(self):
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        result = col.process_bind_param({"token": "secret"}, None)
        assert isinstance(result, str)
        assert "secret" not in result

    def test_empty_dict_bind_returns_string(self):
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        result = col.process_bind_param({}, None)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# EncryptedJSON TypeDecorator — process_result_value
# ---------------------------------------------------------------------------

class TestEncryptedJsonResult:
    def test_none_result_returns_none(self):
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        assert col.process_result_value(None, None) is None

    def test_valid_ciphertext_decrypts_correctly(self):
        from utils.crypto import EncryptedJSON, encrypt_dict
        col = EncryptedJSON()
        original = {"api_token": "tok-123", "board_id": "XYZ"}
        ct = encrypt_dict(original)
        assert col.process_result_value(ct, None) == original

    def test_full_column_round_trip(self):
        """process_bind_param → process_result_value must recover the original dict."""
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        original = {"url": "https://jira.test", "email": "admin@test.com", "api_token": "tok"}
        stored = col.process_bind_param(original, None)
        recovered = col.process_result_value(stored, None)
        assert recovered == original

    def test_decryption_failure_falls_back_to_plain_json(self, caplog):
        """Corrupted or pre-migration plaintext JSON must be returned with a warning."""
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        fallback_data = {"migrated": True, "token": "old-plain"}
        plain_json = json.dumps(fallback_data)
        with caplog.at_level(logging.WARNING, logger="utils.crypto"):
            result = col.process_result_value(plain_json, None)
        assert result == fallback_data
        assert any("decryption failed" in r.message.lower() for r in caplog.records), (
            "Expected a WARNING log when decryption fails"
        )

    def test_total_corruption_returns_empty_dict(self, caplog):
        """A value that is neither valid ciphertext nor valid JSON must return {}."""
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        with caplog.at_level(logging.WARNING, logger="utils.crypto"):
            result = col.process_result_value("not-json-not-fernet!!!###", None)
        assert result == {}

    def test_decryption_failure_does_not_raise(self):
        """Callers must never see an exception — worst case is an empty dict."""
        from utils.crypto import EncryptedJSON
        col = EncryptedJSON()
        # Should not raise regardless of input
        result = col.process_result_value("garbage", None)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Key loading
# ---------------------------------------------------------------------------

class TestKeyLoading:
    def test_key_loaded_from_env_var(self, monkeypatch):
        """When OANNES_SECRET_KEY is set, it must be used as the Fernet key."""
        from cryptography.fernet import Fernet
        import utils.crypto as crypto

        fresh_key = Fernet.generate_key().decode()
        monkeypatch.setenv("OANNES_SECRET_KEY", fresh_key)
        crypto._fernet = None  # force reload

        fernet = crypto.get_fernet()
        # Verify the loaded key can actually encrypt/decrypt
        ct = fernet.encrypt(b"hello")
        assert fernet.decrypt(ct) == b"hello"

    def test_get_fernet_returns_same_instance(self):
        """The singleton must return the same Fernet object on repeated calls."""
        from utils.crypto import get_fernet
        f1 = get_fernet()
        f2 = get_fernet()
        assert f1 is f2
