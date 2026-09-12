from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, verify_google_id_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import GoogleLoginRequest, TokenResponse
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/google", response_model=TokenResponse)
def login_with_google(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    """Recibe el id_token que el frontend obtuvo de Google Sign-In, lo valida,
    crea/actualiza el usuario local y devuelve nuestro propio JWT de sesión.
    """
    google_user = verify_google_id_token(payload.id_token)

    user = db.query(User).filter(User.google_sub == google_user.sub).one_or_none()
    if user is None:
        user = User(
            google_sub=google_user.sub,
            email=google_user.email,
            name=google_user.name,
            picture_url=google_user.picture,
        )
        db.add(user)
    else:
        user.name = google_user.name
        user.picture_url = google_user.picture

    db.commit()
    db.refresh(user)

    access_token = create_access_token(user_id=user.id, email=user.email)
    return TokenResponse(access_token=access_token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
