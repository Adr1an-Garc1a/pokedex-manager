import { AxiosError } from "axios";

/** Extrae un mensaje legible de un error de axios contra nuestra API.
 * Nuestros endpoints (incluidos los de IA) devuelven siempre
 * `{"detail": "mensaje en español"}` en los errores, así que basta con
 * mostrar ese texto tal cual en vez de un genérico "algo salió mal". */
export function getErrorMessage(
  error: unknown,
  fallback = "Ocurrió un error inesperado. Intenta de nuevo."
): string {
  if (error instanceof AxiosError) {
    if (!error.response) {
      return "No se pudo conectar con el backend. Verifica tu conexión e intenta de nuevo.";
    }
    const detail = error.response.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    return `${fallback} (código ${error.response.status})`;
  }
  return fallback;
}
