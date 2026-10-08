import { useEffect } from "react";
import { Login } from "./components/Login";
import { Register } from "./components/Register";
import { useAuth } from "./context/AuthContext";
import { useRouter } from "./routing";
import App from "./App";

const AUTH_PATHS = new Set(["/login", "/register"]);

function Redirect({ to }) {
  const { navigate } = useRouter();
  useEffect(() => {
    navigate(to, { replace: true });
  }, [navigate, to]);
  return <div className="boot"> </div>;
}

export function Root() {
  const { user, loading } = useAuth();
  const { path } = useRouter();

  useEffect(() => {
    if (path === "/login") document.title = "Sign in · DIRA";
    else if (path === "/register") document.title = "Create account · DIRA";
    else document.title = "CAT Intelligence · Nairobi";
  }, [path]);

  if (loading) return <div className="boot">Checking your session…</div>;
  if (!user && !AUTH_PATHS.has(path)) return <Redirect to="/login" />;
  if (user && path !== "/dashboard") return <Redirect to="/dashboard" />;
  if (path === "/register") return <Register />;
  if (path === "/login") return <Login />;
  return <App />;
}
