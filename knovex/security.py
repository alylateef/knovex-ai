import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import bcrypt
import jwt

from knovex.config import get_settings
from knovex.schemas import TokenData

settings = get_settings()

def hash_password(password: str) -> str:
    """Securely hash a plain password using bcrypt."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against bcrypt hash."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    user_id: str,
    tenant_id: str,
    role: str,
    email: str,
    expires_delta: Optional[timedelta] = None
) -> Tuple[str, str]:
    """Generate a signed JWT access token. Returns (token, jti)."""
    jti = str(uuid.uuid4())
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "email": email,
        "jti": jti,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt, jti


def decode_access_token(token: str) -> Optional[TokenData]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id")
        role: str = payload.get("role")
        email: str = payload.get("email")

        if user_id is None or tenant_id is None:
            return None

        return TokenData(user_id=user_id, tenant_id=tenant_id, role=role, email=email)
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------
# Redis Security: Token Revocation & Sliding Rate Limiter
# ---------------------------------------------------------

async def revoke_token(redis_client, token: str, ttl_seconds: Optional[int] = None) -> None:
    """Mark a JWT token as revoked in Redis until its natural expiration."""
    if redis_client is None:
        return
    try:
        if ttl_seconds is None:
            try:
                unverified = jwt.decode(token, options={"verify_signature": False})
                exp_ts = unverified.get("exp")
                if exp_ts:
                    remaining = int(exp_ts - time.time())
                    ttl_seconds = max(1, remaining)
            except Exception:
                pass
        if ttl_seconds is None or ttl_seconds <= 0:
            ttl_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        key = f"revoked_token:{token}"
        await redis_client.setex(key, ttl_seconds, "1")
    except Exception:
        pass


async def is_token_revoked(redis_client, token: str) -> bool:
    """Check if token is blacklisted in Redis."""
    if redis_client is None:
        return False
    try:
        key = f"revoked_token:{token}"
        val = await redis_client.get(key)
        return val is not None
    except Exception:
        return False


async def check_rate_limit(redis_client, identifier: str, limit: int = 60, window_seconds: int = 60) -> Tuple[bool, int]:
    """
    Redis-backed sliding window rate limiter.
    Returns (is_allowed, remaining_requests).
    """
    if redis_client is None:
        return True, limit

    try:
        current_ts = int(time.time())
        key = f"ratelimit:{identifier}:{current_ts // window_seconds}"
        current_count = await redis_client.incr(key)
        if current_count == 1:
            await redis_client.expire(key, window_seconds + 5)

        if current_count > limit:
            return False, 0
        return True, max(0, limit - current_count)
    except Exception:
        # Fail open safely if Redis is down
        return True, limit
