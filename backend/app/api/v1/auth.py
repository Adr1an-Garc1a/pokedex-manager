from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, verify_google_id_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import GoogleLoginRequest, GoogleRegisterRequest, TokenResponse
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/google/login", response_model=TokenResponse)
def login_with_google(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    """Inicia sesión con una cuenta de Google YA REGISTRADA.

    Este endpoint NUNCA crea usuarios. Si el google_sub del id_token no
    existe en nuestra tabla `users`, responde 404 con `code:
    "user_not_registered"` y el perfil de Google (nombre/email/foto) para
    que el frontend redirija al formulario de registro, ya autocompletado.
    Esto es lo que garantiza que solo entren usuarios registrados.
    """
    google_user = verify_google_id_token(payload.id_token)

    user = db.query(User).filter(User.google_sub == google_user.sub).one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "user_not_registered",
                "message": "Esta cuenta de Google aún no está registrada en PokéDex Manager.",
                "profile": {
                    "name": google_user.name,
                    "email": google_user.email,
                    "picture": google_user.picture,
                },
            },
        )

    access_token = create_access_token(user_id=user.id, email=user.email)
    return TokenResponse(access_token=access_token, user=UserRead.model_validate(user))


@router.post(
    "/google/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_with_google(payload: GoogleRegisterRequest, db: Session = Depends(get_db)):
    """Registra una cuenta de Google nueva.

    El id_token se valida contra los certificados públicos de Google en
    cada llamada (nunca se confía en datos que el cliente pudiera mandar sin
    firmar). El único campo que el usuario puede editar es `name`; si no lo
    manda, se usa el nombre que trae la cuenta de Google.
    """
    google_user = verify_google_id_token(payload.id_token)

    existing = db.query(User).filter(User.google_sub == google_user.sub).one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "user_already_registered",
                "message": "Esta cuenta ya está registrada. Intenta iniciar sesión.",
            },
        )

    user = User(
        google_sub=google_user.sub,
        email=google_user.email,
        name=(payload.name or google_user.name),
        picture_url=google_user.picture,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(user_id=user.id, email=user.email)
    return TokenResponse(access_token=access_token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
