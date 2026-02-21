from datetime import datetime, timedelta
from typing import Any, Union
from jose import jwt
import bcrypt
from app.core.config import settings

def create_access_token(subject: Union[str, Any], role: str, expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject), "role": role}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

from cryptography.fernet import Fernet
import base64

# Use ENCRYPTION_KEY from env if available, or derive from SECRET_KEY as fallback.
# In production, ENCRYPTION_KEY MUST be set in .env
def get_fernet() -> Fernet:
    if settings.ENCRYPTION_KEY:
        try:
            return Fernet(settings.ENCRYPTION_KEY.encode())
        except Exception:
            # If provided key is invalid, fallback to derivation but log/warn would be better
            pass
            
    # Derive a 32-byte key from settings.SECRET_KEY for Fernet (Fallback)
    key = base64.urlsafe_b64encode(settings.SECRET_KEY.ljust(32)[:32].encode())
    return Fernet(key)

def encrypt_token(token: str) -> str:
    if not token:
        return None
    f = get_fernet()
    return f.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    if not encrypted_token:
        return None
    f = get_fernet()
    try:
        return f.decrypt(encrypted_token.encode()).decode()
    except Exception:
        # Fallback for plain text during transition
        return encrypted_token

import hashlib

def get_token_hash(token: str) -> str:
    if not token:
        return None
    return hashlib.sha256(token.encode()).hexdigest()
