"""
Tests for security functions.
"""

import pytest
from datetime import datetime, timedelta
from app.core.security import (
    create_access_token,
    verify_password,
    get_password_hash,
    encrypt_token,
    decrypt_token,
    get_token_hash
)


def test_password_hash_and_verify():
    """Test password hashing and verification."""
    password = "test_password_123"
    
    hashed = get_password_hash(password)
    
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong_password", hashed)


def test_access_token_creation():
    """Test JWT token creation."""
    token = create_access_token("testuser", "admin")
    
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_access_token_with_expiry():
    """Test token with custom expiry."""
    expires = timedelta(minutes=30)
    token = create_access_token("testuser", "admin", expires_delta=expires)
    
    assert token is not None


def test_token_encryption():
    """Test token encryption and decryption."""
    original = "test_bot_token_12345"
    
    encrypted = encrypt_token(original)
    
    assert encrypted is not None
    assert encrypted != original
    
    decrypted = decrypt_token(encrypted)
    
    assert decrypted == original


def test_token_hash():
    """Test token hashing."""
    token = "test_token"
    
    hash1 = get_token_hash(token)
    hash2 = get_token_hash(token)
    
    assert hash1 == hash2
    assert hash1 != token


def test_encrypt_none_returns_none():
    """Test that encrypting None returns None."""
    assert encrypt_token(None) is None


def test_decrypt_none_returns_none():
    """Test that decrypting None returns None."""
    assert decrypt_token(None) is None


def test_token_hash_none_returns_none():
    """Test that hashing None returns None."""
    assert get_token_hash(None) is None
