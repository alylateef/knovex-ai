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
    """Mark a JWT token as revoked in Redis using its compact jti claim (not the full token).
    Using jti keeps Redis keys small (~36 bytes vs ~400 bytes for the full JWT)."""
    if redis_client is None:
        return
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        jti = unverified.get("jti")
        if not jti:
            return  # No jti claim — cannot revoke safely

        if ttl_seconds is None:
            exp_ts = unverified.get("exp")
            if exp_ts:
                remaining = int(exp_ts - time.time())
                ttl_seconds = max(1, remaining)

        if ttl_seconds is None or ttl_seconds <= 0:
            ttl_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        key = f"revoked_jti:{jti}"
        await redis_client.setex(key, ttl_seconds, "1")
    except Exception:
        pass


async def is_token_revoked(redis_client, token: str) -> bool:
    """Check if token's jti is blacklisted in Redis."""
    if redis_client is None:
        return False
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        jti = unverified.get("jti")
        if not jti:
            return False
        key = f"revoked_jti:{jti}"
        val = await redis_client.get(key)
        return val is not None
    except Exception:
        return False


async def check_rate_limit(redis_client, identifier: str, limit: int = 60, window_seconds: int = 60) -> Tuple[bool, int]:
    """
    Redis-backed true rolling sliding-window rate limiter using sorted sets (ZSET).
    Returns (is_allowed, remaining_requests).
    """
    if redis_client is None:
        return True, limit

    try:
        now = time.time()
        clear_before = now - window_seconds
        key = f"ratelimit:{identifier}:zset"

        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(key, "-inf", clear_before)
        pipe.zcard(key)
        pipe.zadd(key, {f"{now}": now})
        pipe.expire(key, window_seconds + 10)
        results = await pipe.execute()

        current_count = results[1]  # count of requests currently in sliding window
        if current_count >= limit:
            return False, 0
        return True, max(0, limit - (current_count + 1))
    except Exception:
        # Fail open safely if Redis is down
        return True, limit
