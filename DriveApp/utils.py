# utils.py
import jwt
import datetime
from django.conf import settings


def generate_reset_token(user_id: int) -> str:
    """Generate a JWT token for password reset (expires in 1 hour)"""
    payload = {
        'user_id': user_id,
        'purpose': 'password_reset',
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        'iat': datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def decode_reset_token(token: str) -> dict:
    """Decode and validate a reset token. Raises jwt exceptions on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])