import { UserNotRegisteredError } from "@/api/auth";
import { useAuth } from "@/context/AuthContext";
import type { GoogleProfilePreview } from "@/types";
import { GoogleLogin } from "@react-oauth/google";
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

export function LoginPage() {
  const { user, loginWithGoogleIdToken, registerWithGoogleIdToken } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Cuando el backend responde "cuenta no registrada", guardamos aquí el
  // id_token (para reusarlo en el registro) y el perfil de Google que
  // autocompleta el formulario.
  const [pendingIdToken, setPendingIdToken] = useState<string | null>(null);
  const [pendingProfile, setPendingProfile] = useState<GoogleProfilePreview | null>(null);
  const [displayName, setDisplayName] = useState("");

  if (user) {
    return <Navigate to="/pokedex" replace />;
  }

  function handleGoogleSuccess(idToken: string | undefined) {
    setError(null);
    if (!idToken) {
      setError("No se recibió credencial de Google. Intenta de nuevo.");
      return;
    }

    loginWithGoogleIdToken(idToken).catch((err) => {
      if (err instanceof UserNotRegisteredError) {
        // No existe todavía en nuestra base de datos: no lo dejamos pasar,
        // lo mandamos a completar su registro con los datos autocompletados.
        setPendingIdToken(idToken);
        setPendingProfile(err.profile);
        setDisplayName(err.profile.name);
      } else {
        setError("No se pudo iniciar sesión. Intenta de nuevo.");
      }
    });
  }

  function handleRegisterSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pendingIdToken) return;

    setError(null);
    setIsSubmitting(true);
    registerWithGoogleIdToken(pendingIdToken, displayName.trim() || (pendingProfile?.name ?? ""))
      .catch(() => setError("No se pudo completar el registro. Intenta de nuevo."))
      .finally(() => setIsSubmitting(false));
  }

  function cancelRegistration() {
    setPendingIdToken(null);
    setPendingProfile(null);
    setError(null);
  }

  return (
    <div className="flex min-h-[80vh] flex-col items-center justify-center gap-8 px-4 py-10 text-center">
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

      {pendingProfile ? (
        <form onSubmit={handleRegisterSubmit} className="poke-card flex w-full max-w-sm flex-col gap-4 p-6">
          <div className="flex flex-col items-center gap-2">
            {pendingProfile.picture && (
              <img
                src={pendingProfile.picture}
                alt={pendingProfile.name}
                className="h-16 w-16 rounded-full border-2 border-poke-teal"
              />
            )}
            <p className="font-display text-lg font-bold text-poke-ink">
              ¡Bienvenido, {pendingProfile.name}!
            </p>
            <p className="text-sm text-poke-ink-soft">
              Aún no tienes cuenta en PokéDex Manager. Confirma tus datos para
              registrarte — se autocompletan con tu cuenta de Google.
            </p>
          </div>

          <div className="flex flex-col gap-1 text-left">
            <label htmlFor="email" className="text-xs font-semibold text-poke-ink-soft">
              Correo (de tu cuenta de Google)
            </label>
            <input
              id="email"
              value={pendingProfile.email}
              disabled
              className="poke-input opacity-70"
            />
          </div>

          <div className="flex flex-col gap-1 text-left">
            <label htmlFor="displayName" className="text-xs font-semibold text-poke-ink-soft">
              Nombre para mostrar
            </label>
            <input
              id="displayName"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              minLength={1}
              className="poke-input"
            />
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={cancelRegistration}
              className="poke-btn-secondary flex-1"
              disabled={isSubmitting}
            >
              Cancelar
            </button>
            <button type="submit" className="poke-btn-primary flex-1" disabled={isSubmitting}>
              {isSubmitting ? "Registrando..." : "Completar registro"}
            </button>
          </div>
        </form>
      ) : (
        <div className="poke-card p-6">
          <GoogleLogin
            onSuccess={(credentialResponse) => handleGoogleSuccess(credentialResponse.credential)}
            onError={() => setError("Falló el inicio de sesión con Google.")}
          />
        </div>
      )}

      {error && <p className="text-sm text-poke-coral">{error}</p>}

      <p className="text-xs text-poke-ink-soft">
        ¿No ves el botón de Google? Configura{" "}
        <code className="rounded bg-poke-mist px-1">VITE_GOOGLE_CLIENT_ID</code> en tu
        archivo <code className="rounded bg-poke-mist px-1">.env</code>.
      </p>
    </div>
  );
}
