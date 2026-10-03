import { useEffect, useState } from "react";
import {
  Check,
  ExternalLink,
  Linkedin,
  LogOut,
  Send,
  Sparkles,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiClient } from "../utils/api";

export default function LinkedInDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState("");
  const [post, setPost] = useState("");
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .linkedinStatus()
      .then(({ data }) => setConnected(data.connected))
      .catch(() => setConnected(false));
  }, []);

  const generatePost = async (event) => {
    event.preventDefault();
    if (!prompt.trim()) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const { data } = await apiClient.generateLinkedInPost(prompt.trim());
      setPost(data.text);
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail || "Could not create the post.",
      );
    } finally {
      setBusy(false);
    }
  };

  const publishPost = async () => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const { data } = await apiClient.publishLinkedInPost(post);
      setNotice(data.result);
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail || "Could not publish the post.",
      );
    } finally {
      setBusy(false);
    }
  };

  const connectAccount = () => apiClient.connectLinkedIn();

  const signOut = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <main className="studio-page">
      <header className="studio-header">
        <a
          className="studio-logo"
          href="/dashboard"
          aria-label="LinkedIn Post Studio"
        >
          <span className="studio-logo-icon">
            <Linkedin size={18} />
          </span>
          <span>Post Studio</span>
        </a>
        <div className="header-actions">
          <span className="signed-in-as">{user?.username}</span>
          <button className="quiet-button" onClick={signOut} title="Sign out">
            <LogOut size={17} aria-hidden="true" />
            <span>Sign out</span>
          </button>
        </div>
      </header>

      <section className="studio-content">
        <div className="studio-heading-row">
          <div>
            <p className="eyebrow">LINKEDIN WORKSPACE</p>
            <h1>Draft, review, publish.</h1>
          </div>
          <div
            className={`connection-state ${connected ? "is-connected" : ""}`}
          >
            <span className="connection-dot" />
            {connected ? "LinkedIn connected" : "LinkedIn not connected"}
          </div>
        </div>

        {!connected && (
          <div className="connect-banner">
            <div>
              <strong>Connect your LinkedIn account</strong>
              <p>Authorize publishing before sending a post to your profile.</p>
            </div>
            <button className="secondary-button" onClick={connectAccount}>
              Connect LinkedIn <ExternalLink size={16} aria-hidden="true" />
            </button>
          </div>
        )}

        <div className="editor-grid">
          <form className="editor-panel idea-panel" onSubmit={generatePost}>
            <div className="panel-heading">
              <span className="step-index">01</span>
              <div>
                <h2>Your idea</h2>
                <p>What would you like to share?</p>
              </div>
            </div>
            <textarea
              className="idea-input"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="A project milestone, a lesson learned, an announcement..."
              rows={8}
              maxLength={1200}
            />
            <div className="panel-footer">
              <span>{prompt.length}/1,200</span>
              <button
                className="primary-button"
                disabled={busy || !prompt.trim()}
              >
                <Sparkles size={17} aria-hidden="true" />
                {busy ? "Working..." : "Generate draft"}
              </button>
            </div>
          </form>

          <section className="editor-panel preview-panel">
            <div className="panel-heading">
              <span className="step-index">02</span>
              <div>
                <h2>Review your post</h2>
                <p>Edit the text before publishing.</p>
              </div>
            </div>
            <textarea
              className="post-input"
              value={post}
              onChange={(event) => setPost(event.target.value.slice(0, 3000))}
              placeholder="Your generated draft will appear here."
              rows={12}
              maxLength={3000}
              aria-label="LinkedIn post draft"
            />
            <div className="panel-footer">
              <span className={post.length > 2800 ? "character-warning" : ""}>
                {post.length.toLocaleString()}/3,000
              </span>
              <button
                className="publish-button"
                onClick={publishPost}
                disabled={busy || !post.trim() || !connected}
              >
                <Send size={16} aria-hidden="true" />
                {busy ? "Publishing..." : "Publish post"}
              </button>
            </div>
          </section>
        </div>

        {(notice || error) && (
          <div
            className={`status-message ${error ? "status-error" : "status-success"}`}
            role="status"
          >
            {error ? null : <Check size={17} aria-hidden="true" />}
            {error || notice}
          </div>
        )}
      </section>
    </main>
  );
}
