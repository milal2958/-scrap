"""Signed, expiring login tokens. Passwords and password hashes stay on the server."""
import base64
import hashlib
import hmac
import json
import secrets
import time

REMEMBER_SECONDS = 30 * 24 * 60 * 60


def derive_key(secret):
    if not secret:
        raise ValueError("A server secret is required")
    return hmac.new(str(secret).encode(), b"scrap/remember-login/v1", hashlib.sha256).digest()


def credential_version(key, user_id, password_hash):
    data = json.dumps([user_id, password_hash], ensure_ascii=True).encode()
    return hmac.new(key, b"credentials/" + data, hashlib.sha256).hexdigest()


def issue_token(key, user_id, password_hash, now=None):
    now = int(time.time() if now is None else now)
    payload = {"user": user_id, "exp": now + REMEMBER_SECONDS,
               "version": credential_version(key, user_id, password_hash),
               "nonce": secrets.token_urlsafe(16)}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(key, body.encode(), hashlib.sha256).hexdigest()
    return body + "." + signature


def read_token(key, token, now=None):
    """Validate signature and lifetime before using any browser-supplied identity."""
    if not isinstance(token, str) or len(token) > 2048:
        return None
    try:
        body, signature = token.split(".")
        expected = hmac.new(key, body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        now = time.time() if now is None else now
        if not isinstance(payload, dict):
            return None
        if type(payload.get("exp")) is not int or not now < payload["exp"] <= now + REMEMBER_SECONDS:
            return None
        if not isinstance(payload.get("user"), str) or not payload["user"]:
            return None
        if not isinstance(payload.get("version"), str):
            return None
        return payload
    except (ValueError, TypeError, UnicodeError):
        return None


def credentials_match(key, payload, credentials):
    current = credentials.get(payload["user"])
    return bool(current) and hmac.compare_digest(
        payload["version"], credential_version(key, payload["user"], current)
    )
