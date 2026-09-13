import { Navbar } from "@/components/Navbar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useAuth } from "@/context/AuthContext";
import { CollectionPage } from "@/pages/CollectionPage";
import { InsightsPage } from "@/pages/InsightsPage";
import { LoginPage } from "@/pages/LoginPage";
import { PokedexChatPage } from "@/pages/PokedexChatPage";
import { PokedexPage } from "@/pages/PokedexPage";
import { VisionIdentifyPage } from "@/pages/VisionIdentifyPage";
import { Navigate, Route, Routes } from "react-router-dom";

export default function App() {
  const { user, isLoading } = useAuth();

  return (
    <div className="min-h-screen">
      {user && <Navbar />}
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/pokedex"
          element={
            <ProtectedRoute>
              <PokedexPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/collection"
          element={
            <ProtectedRoute>
              <CollectionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/identificar"
          element={
            <ProtectedRoute>
              <VisionIdentifyPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <PokedexChatPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/insights"
          element={
            <ProtectedRoute>
              <InsightsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/"
          element={
            isLoading ? null : <Navigate to={user ? "/pokedex" : "/login"} replace />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
