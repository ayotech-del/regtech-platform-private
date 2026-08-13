import { useState, type FormEvent } from "react";
import { ApiError, api } from "../api/client";
import { useAuth } from "./AuthContext";

export function ConnectScreen() {
  const { connect } = useAuth();
  const [key, setKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = key.trim();
    if (!trimmed) return;

    setChecking(true);
    setError(null);
    try {
      // Validate against a real endpoint before storing -- a bad key
      // shouldn't silently "connect" and then fail on the first page.
      await api.validateApiKey(trimmed);
      connect(trimmed);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the API. Is the backend running?");
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="connect-screen">
      <form className="connect-form" onSubmit={handleSubmit}>
        <h1>RegTech Platform</h1>
        <p className="subtitle">Enter an API key to open the case dashboard.</p>
        <input
          type="password"
          placeholder="rtk_..."
          value={key}
          onChange={(e) => setKey(e.target.value)}
          autoFocus
        />
        {error && <p className="error-text">{error}</p>}
        <button type="submit" disabled={checking || !key.trim()}>
          {checking ? "Connecting..." : "Connect"}
        </button>
        <p className="hint">
          Create one with <code>python -m app.cli create-api-key &lt;slug&gt; &lt;label&gt;</code>
        </p>
      </form>
    </div>
  );
}
