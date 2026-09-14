import hashlib
import time
import uuid
import bcrypt
import jwt
import config


def hash_password(password: str) -> str:
    return bcrypt.hashpw(hashlib.sha256(password.encode()).hexdigest().encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        return bcrypt.checkpw(hashlib.sha256(password.encode()).hexdigest().encode(), encoded.encode())
    except ValueError:
        return False


def create_token(user_id: str, version: int) -> str:
    now = int(time.time())
    return jwt.encode({'sub': user_id, 'ver': version, 'iat': now, 'exp': now + 86400, 'iss': 'plainly'}, config.JWT_SECRET, algorithm='HS256')


def decode_token(token: str) -> dict:
    payload = jwt.decode(token, config.JWT_SECRET, algorithms=['HS256'], issuer='plainly', options={'require': ['exp', 'iat', 'sub', 'ver']})
    try:
        uuid.UUID(payload['sub'])
    except (ValueError, TypeError, AttributeError):
        raise jwt.InvalidTokenError('Invalid subject')
    return payload
