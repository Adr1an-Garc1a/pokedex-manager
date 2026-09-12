from pydantic import BaseModel

from app.schemas.user import UserRead


class GoogleLoginRequest(BaseModel):
    """Payload para /auth/google/login: solo requiere el id_token de Google.

    NO crea usuarios — si la cuenta no está registrada, el endpoint responde
    404 con el perfil de Google para que el frontend ofrezca el registro.
    """

    id_token: str


class GoogleRegisterRequest(BaseModel):
    """Payload para /auth/google/register.

    `name` es el único campo editable por el usuario en el formulario de
    registro (autocompletado con el nombre de Google, pero el usuario puede
    ajustarlo). El resto de los datos de identidad (google_sub, email,
    picture) siempre se toman del id_token verificado, nunca de lo que
    mande el cliente, para evitar suplantación.
    """

    id_token: str
    name: str | None = None


class GoogleProfilePreview(BaseModel):
    """Datos de Google devueltos cuando /auth/google/login detecta que la
    cuenta no está registrada, para autocompletar el formulario de registro.
    """

    name: str
    email: str
    picture: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
