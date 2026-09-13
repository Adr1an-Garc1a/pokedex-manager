import { fetchCurrentUser, loginWithGoogle, registerWithGoogle } from "@/api/auth";
import { clearToken, getToken, saveToken } from "@/api/client";
import type { User } from "@/types";
import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  /** Inicia sesión con una cuenta ya registrada. Lanza
   * UserNotRegisteredError (ver api/auth.ts) si la cuenta no existe aún. */
  loginWithGoogleIdToken: (idToken: string) => Promise<void>;
  /** Da de alta una cuenta nueva a partir del id_token de Google + el
   * nombre confirmado/editado por el usuario en el formulario. */
  registerWithGoogleIdToken: (idToken: string, name: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setIsLoading(false);
      return;
    }
    fetchCurrentUser()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setIsLoading(false));
  }, []);

  const loginWithGoogleIdToken = useCallback(async (idToken: string) => {
    const response = await loginWithGoogle(idToken);
    saveToken(response.access_token);
    setUser(response.user);
  }, []);

  const registerWithGoogleIdToken = useCallback(async (idToken: string, name: string) => {
    const response = await registerWithGoogle(idToken, name);
    saveToken(response.access_token);
    setUser(response.user);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    // Defensa adicional contra fugas de datos entre cuentas: aunque cada
    // queryKey relevante ya lleva el id de usuario (ver InsightsPage.tsx,
    // VisionIdentifyPage.tsx, etc. — la corrección real del bug reportado),
    // limpiar TODO el caché de React Query al cerrar sesión garantiza que
    // ninguna respuesta cacheada (de esta cuenta, o de una key que se nos
    // olvide escopar en el futuro) pueda sobrevivir a la próxima cuenta que
    // inicie sesión en esta misma pestaña.
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo(
    () => ({ user, isLoading, loginWithGoogleIdToken, registerWithGoogleIdToken, logout }),
    [user, isLoading, loginWithGoogleIdToken, registerWithGoogleIdToken, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  }
  return context;
}
