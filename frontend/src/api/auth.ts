import { apiClient } from "@/api/client";
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
    return error.response?.data?.detail as BackendErrorDetail | undefined;
  }
  return undefined;
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
