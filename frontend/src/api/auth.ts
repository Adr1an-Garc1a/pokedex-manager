import { API_BASE_URL, apiClient } from "@/api/client";
import type { GoogleProfilePreview, User } from "@/types";
import { AxiosError } from "axios";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

/** Error tipado que lanza loginWithGoogle cuando el backend responde 404
 * porque la cuenta de Google todavía no está registrada. El LoginPage lo
 * usa para saltar al formulario de registro, ya autocompletado. */
export class UserNotRegisteredError extends Error {
  readonly profile: GoogleProfilePreview;

  constructor(profile: GoogleProfilePreview) {
    super("user_not_registered");
    this.name = "UserNotRegisteredError";
    this.profile = profile;
  }
}

export class UserAlreadyRegisteredError extends Error {
  constructor() {
    super("user_already_registered");
    this.name = "UserAlreadyRegisteredError";
  }
}

interface BackendErrorDetail {
  code?: string;
  message?: string;
  profile?: GoogleProfilePreview;
}

function extractDetail(error: unknown): BackendErrorDetail | undefined {
  if (error instanceof AxiosError) {
    const raw = error.response?.data?.detail;
    // FastAPI a veces manda detail como string plano (ej. errores 500 sin
    // manejar) en vez del objeto {code, message, ...} que usan nuestros
    // endpoints de auth. Normalizamos para no romper el resto del código.
    if (typeof raw === "string") {
      return { message: raw };
    }
    return raw as BackendErrorDetail | undefined;
  }
  return undefined;
}

/** Convierte cualquier error de axios en un mensaje legible para mostrar en
 * la UI, en vez de un "no se pudo iniciar sesión" genérico que no dice nada
 * sobre la causa real (backend caído, CORS bloqueado, 500, etc.). */
export function describeAuthError(error: unknown): string {
  if (error instanceof AxiosError) {
    if (!error.response) {
      // Axios nunca recibió respuesta: red caída, backend no disponible, o
      // el navegador bloqueó la respuesta por CORS (el caso más común: el
      // backend no tiene el origen del frontend en CORS_ORIGINS). En
      // cualquiera de los dos casos el navegador no expone el detalle
      // exacto a JavaScript por seguridad, así que mostramos ambas
      // hipótesis para que sea fácil de diagnosticar.
      return (
        `No se pudo conectar con el backend en ${API_BASE_URL}. ` +
        "Puede ser que el servicio esté caído, o que esté bloqueando " +
        "el origen del frontend por CORS (revisa la consola del navegador: " +
        "si dice 'blocked by CORS policy', hay que actualizar CORS_ORIGINS " +
        "en el backend con la URL real del frontend)."
      );
    }

    const detail = extractDetail(error);
    if (detail?.message) {
      return `El backend respondió ${error.response.status}: ${detail.message}`;
    }
    return `El backend respondió con un error inesperado (${error.response.status}).`;
  }

  return "Ocurrió un error inesperado. Revisa la consola del navegador.";
}

/** Inicia sesión con una cuenta de Google YA REGISTRADA.
 *
 * Nunca crea usuarios: si el backend responde 404 con
 * code === "user_not_registered", se relanza como UserNotRegisteredError
 * (con el perfil de Google) para que la UI ofrezca registrarse.
 */
export async function loginWithGoogle(idToken: string): Promise<TokenResponse> {
  try {
    const { data } = await apiClient.post<TokenResponse>("/auth/google/login", {
      id_token: idToken,
    });
    return data;
  } catch (error) {
    const detail = extractDetail(error);
    if (detail?.code === "user_not_registered" && detail.profile) {
      throw new UserNotRegisteredError(detail.profile);
    }
    throw error;
  }
}

/** Registra una cuenta de Google nueva. `name` es editable por el usuario
 * en el formulario (autocompletado con el nombre que trae Google). */
export async function registerWithGoogle(
  idToken: string,
  name: string
): Promise<TokenResponse> {
  try {
    const { data } = await apiClient.post<TokenResponse>("/auth/google/register", {
      id_token: idToken,
      name,
    });
    return data;
  } catch (error) {
    const detail = extractDetail(error);
    if (detail?.code === "user_already_registered") {
      throw new UserAlreadyRegisteredError();
    }
    throw error;
  }
}

export async function fetchCurrentUser(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me");
  return data;
}
