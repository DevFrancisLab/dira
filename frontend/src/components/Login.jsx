import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useRouter } from "../routing";
import { AuthScreen } from "./AuthScreen";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function Login() {
  const { login } = useAuth();
  const { navigate } = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    if (pending) return;
    const trimmed = email.trim();
    if (!trimmed || !password) {
      setError("Email and password are required.");
      return;
    }
    if (!EMAIL.test(trimmed)) {
      setError("Enter a valid email address.");
      return;
    }
    setError("");
    setPending(true);
    try {
      await login({ email: trimmed, password });
    } catch (reason) {
      setError(reason.message);
      setPending(false);
    }
  }

  return (
    <AuthScreen
      title="Welcome back"
      switchText="Don't have an account?"
      switchLabel="Create account"
      onSwitch={() => navigate("/register")}
    >
      <form className="auth-form" onSubmit={onSubmit} noValidate>
        <label>
          Email
          <input
            type="email"
            name="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            disabled={pending}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={pending}
          />
        </label>
        {error ? <p className="auth-error" role="alert">{error}</p> : null}
        <button className="auth-submit" type="submit" disabled={pending}>
          {pending ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </AuthScreen>
  );
}
