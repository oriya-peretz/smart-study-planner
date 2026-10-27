"""User accounts: password hashing, tokens, and the "who is calling?" dependency."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select

from app import db
from app.models import (
    AuthToken,
    Credentials,
    TokenPublic,
    User,
    UserPublic,
    UserSettings,
)

TOKEN_LIFETIME = timedelta(days=14)

# scrypt is deliberately slow and memory-hungry, so guessing passwords is expensive.
SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    """A random salt makes equal passwords hash differently; store "salt$hash"."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT)
    return f"{salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    salt, digest = stored.split("$")
    attempt = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **SCRYPT)
    return hmac.compare_digest(attempt.hex(), digest)  # takes the same time either way


def hash_token(token: str) -> str:
    """Tokens are long and random, so a fast hash is enough (unlike passwords)."""
    return hashlib.sha256(token.encode()).hexdigest()


# auto_error=False: a missing header reaches current_user, which answers 401.
bearer = HTTPBearer(auto_error=False)

NOT_LOGGED_IN = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    detail="Not logged in, or the session has expired",
    headers={"WWW-Authenticate": "Bearer"},
)


def current_user(
    session: db.SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    """Every protected route depends on this: no valid token, no access."""
    if credentials is None:
        raise NOT_LOGGED_IN
    token = session.get(AuthToken, hash_token(credentials.credentials))
    if token is None or token.expires_at <= datetime.now():
        raise NOT_LOGGED_IN
    return session.get(User, token.user_id)


CurrentUser = Annotated[User, Depends(current_user)]

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def sign_up(body: Credentials, session: db.SessionDep) -> User:
    email = body.email.lower()
    if session.exec(select(User).where(User.email == email)).first() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="An account with this email already exists"
        )
    user = User(email=email, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login", response_model=TokenPublic)
def log_in(body: Credentials, session: db.SessionDep) -> TokenPublic:
    user = session.exec(select(User).where(User.email == body.email.lower())).first()
    # The same answer for "no such email" and "wrong password", so the
    # response does not reveal which emails have accounts.
    if user is None or not check_password(body.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Wrong email or password"
        )
    token = secrets.token_urlsafe(32)
    session.add(
        AuthToken(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=datetime.now() + TOKEN_LIFETIME,
        )
    )
    session.commit()
    return TokenPublic(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def log_out(
    session: db.SessionDep,
    user: CurrentUser,  # checks that the token is valid before it is deleted
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
) -> None:
    session.delete(session.get(AuthToken, hash_token(credentials.credentials)))
    session.commit()


@router.get("/me", response_model=UserPublic)
def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserPublic)
def update_me(body: UserSettings, session: db.SessionDep, user: CurrentUser) -> User:
    """Change the logged-in user's own settings (today: the interface language)."""
    user.language = body.language
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
