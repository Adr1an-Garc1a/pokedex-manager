import { useAuth } from "@/context/AuthContext";
import { GoogleLogin } from "@react-oauth/google";
import { useState } from "react";
import { Navigate } from "react-router-dom";

export function LoginPage() {
  const { user, loginWithGoogleIdToken } = useAuth();
  const [error, setError] = useState<string | null>(null);

  if (user) {
    return <Navigate to="/pokedex" replace />;
  }

  return (
    <div className="flex min-h-[80vh] flex-col items-center justify-center gap-8 px-4 text-center">
      <div className="flex flex-col items-center gap-3">
        <img src="/pokeball.svg" alt="PokéDex Manager" className="h-20 w-20 drop-shadow-lg" />
        <h1 className="font-display text-4xl font-extrabold text-poke-ink">
          PokéDex <span className="text-poke-teal-dark">Manager</span>
        </h1>
        <p className="max-w-md font-body text-poke-ink-soft">
          Explora la Pokédex y arma tu colección personal. Inicia sesión con tu
          cuenta de Google para empezar tu aventura.
        </p>
      </div>

      <div className="poke-card p-6">
        <GoogleLogin
          onSuccess={(credentialResponse) => {
            setError(null);
            const idToken = credentialResponse.credential;
            if (!idToken) {
              setError("No se recibió credencial de Google. Intenta de nuevo.");
              return;
            }
            loginWithGoogleIdToken(idToken).catch(() =>
              setError("No se pudo iniciar sesión. Intenta de nuevo.")
            );
          }}
          onError={() => setError("Falló el inicio de sesión con Google.")}
        />
        {error && <p className="mt-3 text-sm text-poke-coral">{error}</p>}
      </div>

      <p className="text-xs text-poke-ink-soft">
        ¿No ves el botón de Google? Configura{" "}
        <code className="rounded bg-poke-mist px-1">VITE_GOOGLE_CLIENT_ID</code> en tu
        archivo <code className="rounded bg-poke-mist px-1">.env</code>.
      </p>
    </div>
  );
}
