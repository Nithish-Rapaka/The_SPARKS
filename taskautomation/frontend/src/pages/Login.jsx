import { useState } from "react";
import { ArrowRight, Linkedin, LockKeyhole } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(username, password);
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail || "Sign in failed. Try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-brand-panel">
        <div className="brand-mark">
          <Linkedin aria-hidden="true" />
          <span>POST / LINKEDIN</span>
        </div>
        <div className="brand-copy">
          <p className="eyebrow">LINKEDIN POST STUDIO</p>
          <h1>Make your next post worth stopping for.</h1>
          <p className="brand-description">
            Shape an idea, review every word, then publish when it feels right.
          </p>
        </div>
        <p className="brand-footnote">A focused writing workspace</p>
      </section>

      <section className="login-form-panel">
        <div className="login-form-wrap">
          <div className="login-icon">
            <LockKeyhole aria-hidden="true" />
          </div>
          <p className="eyebrow">WELCOME BACK</p>
          <h2>Sign in</h2>
          <p className="login-intro">
            Use your workspace credentials to continue.
          </p>

          <form onSubmit={handleSubmit} className="login-form">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />

            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />

            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}

            <button
              className="primary-button login-submit"
              disabled={submitting}
            >
              {submitting ? "Signing in..." : "Continue"}
              {!submitting && <ArrowRight size={17} aria-hidden="true" />}
            </button>
          </form>
          <p className="demo-note">
            Demo workspace · server-side session · 8-hour expiry
          </p>
        </div>
      </section>
    </main>
  );
}
