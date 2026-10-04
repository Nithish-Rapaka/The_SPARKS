import { useEffect, useState } from "react";
import {
  Check,
  ExternalLink,
  ImagePlus,
  Linkedin,
  Loader2,
  LogOut,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiClient, mediaUrl } from "../utils/api";

export default function LinkedInDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState("");
  const [post, setPost] = useState("");
  const [image, setImage] = useState(null);
  const [imageBusy, setImageBusy] = useState(false);
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [publishedPosts, setPublishedPosts] = useState([]);
  const [historyBusy, setHistoryBusy] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [selectedPostIds, setSelectedPostIds] = useState([]);

  const loadPublishedPosts = async () => {
    setHistoryBusy(true);
    setHistoryError("");
    try {
      const { data } = await apiClient.linkedinPosts();
      setPublishedPosts(data.posts);
      setSelectedPostIds((selected) =>
        selected.filter((id) =>
          data.posts.some((savedPost) => savedPost.id === id),
        ),
      );
    } catch (requestError) {
      setHistoryError(
        requestError.response?.data?.detail ||
          "Could not load your published posts.",
      );
    } finally {
      setHistoryBusy(false);
    }
  };

  useEffect(() => {
    apiClient
      .linkedinStatus()
      .then(({ data }) => setConnected(data.connected))
      .catch(() => setConnected(false));
    loadPublishedPosts();
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

  const uploadImage = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
    if (!allowedTypes.includes(file.type)) {
      setError("Choose a JPG, PNG, or WEBP image.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("Image must be smaller than 10 MB.");
      return;
    }

    setImageBusy(true);
    setError("");
    setNotice("");
    try {
      const { data } = await apiClient.uploadLinkedInImage(file);
      setImage({
        filename: data.filename,
        imageUrl: data.image_url,
        previewUrl: mediaUrl(data.image_url),
      });
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail || "Could not upload the image.",
      );
    } finally {
      setImageBusy(false);
    }
  };

  const removeImage = () => setImage(null);

  const publishPost = async () => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const { data } = await apiClient.publishLinkedInPost(
        post,
        image?.imageUrl,
        prompt.trim(),
      );
      setNotice(data.result);
      if (data.published === null) {
        return;
      } else if (data.history_saved === false) {
        setHistoryError(
          data.history_warning ||
            "The post is live on LinkedIn, but could not be saved to post history.",
        );
      } else {
        await loadPublishedPosts();
      }
    } catch (requestError) {
      const responseData = requestError.response?.data;
      if (responseData?.published === true) {
        setNotice(
          responseData.result || "LinkedIn post published successfully 🚀",
        );
        setHistoryError(
          responseData.history_warning ||
            responseData.detail ||
            "The post is live on LinkedIn, but could not be saved to post history.",
        );
      } else {
        setError(
          responseData?.detail || "LinkedIn post published successfully 🚀",
        );
      }
    } finally {
      setBusy(false);
    }
  };

  const togglePostSelection = (postId) => {
    setSelectedPostIds((selected) =>
      selected.includes(postId)
        ? selected.filter((id) => id !== postId)
        : [...selected, postId],
    );
  };

  const toggleAllPostSelection = () => {
    setSelectedPostIds((selected) =>
      selected.length === publishedPosts.length
        ? []
        : publishedPosts.map((savedPost) => savedPost.id),
    );
  };

  const deletePosts = async (postIds) => {
    const clearAll = postIds === null;
    const confirmation = clearAll
      ? "Delete all saved post history from the database? This cannot be undone."
      : `Delete ${postIds.length} selected saved post${postIds.length === 1 ? "" : "s"}? This cannot be undone.`;
    if (!window.confirm(confirmation)) return;

    setHistoryBusy(true);
    setHistoryError("");
    setError("");
    setNotice("");
    try {
      const { data } = await apiClient.deleteLinkedInPosts(postIds);
      setSelectedPostIds([]);
      setNotice(
        `Deleted ${data.deleted_count} saved post${data.deleted_count === 1 ? "" : "s"}.`,
      );
      await loadPublishedPosts();
    } catch (requestError) {
      setHistoryError(
        requestError.response?.data?.detail ||
          "Could not delete the selected post history.",
      );
    } finally {
      setHistoryBusy(false);
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
            <div className="image-upload-section">
              <div className="image-upload-heading">
                <div>
                  <h3>
                    Post image <span>Optional</span>
                  </h3>
                  <p>Add an image to publish alongside your post.</p>
                </div>
                <label className="image-upload-button">
                  {imageBusy ? (
                    <Loader2
                      size={16}
                      className="loading-icon"
                      aria-hidden="true"
                    />
                  ) : (
                    <ImagePlus size={16} aria-hidden="true" />
                  )}
                  {imageBusy
                    ? "Uploading..."
                    : image
                      ? "Replace image"
                      : "Choose image"}
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={uploadImage}
                    disabled={imageBusy || busy}
                    aria-label="Upload an image for the LinkedIn post"
                  />
                </label>
              </div>
              {image ? (
                <div className="uploaded-image-preview">
                  <img
                    src={image.previewUrl}
                    alt="Preview of the uploaded post"
                  />
                  <div className="uploaded-image-details">
                    <span>{image.filename}</span>
                    <span>Ready to publish</span>
                  </div>
                  <button
                    type="button"
                    className="remove-image-button"
                    onClick={removeImage}
                    disabled={busy}
                    aria-label="Remove uploaded image"
                  >
                    <X size={17} aria-hidden="true" />
                  </button>
                </div>
              ) : (
                <p className="image-upload-hint">
                  JPG, PNG, or WEBP · Up to 10 MB
                </p>
              )}
            </div>
            <div className="panel-footer">
              <span>{prompt.length}/1,200</span>
              <button
                className="primary-button"
                disabled={busy || imageBusy || !prompt.trim()}
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
                <p>Review the text and image, then approve to publish.</p>
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
            {image && (
              <div className="review-image-preview">
                <span>Image attached to this post</span>
                <img
                  src={image.previewUrl}
                  alt="Image that will be published with the post"
                />
              </div>
            )}
            <div className="panel-footer">
              <span className={post.length > 2800 ? "character-warning" : ""}>
                {post.length.toLocaleString()}/3,000
              </span>
              <button
                className="publish-button"
                onClick={publishPost}
                disabled={busy || imageBusy || !post.trim() || !connected}
              >
                <Send size={16} aria-hidden="true" />
                {busy ? "Publishing..." : "Approve & publish"}
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

        <section className="history-section" aria-labelledby="history-heading">
          <div className="history-heading">
            <div>
              <p className="eyebrow">PUBLISHED</p>
              <h2 id="history-heading">Post history</h2>
              <p>Your most recent 50 published posts.</p>
            </div>
            <button
              type="button"
              className="secondary-button history-refresh"
              onClick={loadPublishedPosts}
              disabled={historyBusy}
            >
              <RefreshCw
                size={15}
                className={historyBusy ? "loading-icon" : ""}
                aria-hidden="true"
              />
              {historyBusy ? "Loading..." : "Refresh"}
            </button>
          </div>

          {!historyBusy && !historyError && publishedPosts.length > 0 && (
            <div className="history-actions">
              <label className="history-select-all">
                <input
                  type="checkbox"
                  checked={selectedPostIds.length === publishedPosts.length}
                  onChange={toggleAllPostSelection}
                  aria-label="Select all displayed posts"
                />
                Select all displayed
              </label>
              <button
                type="button"
                className="history-delete-button"
                onClick={() => deletePosts(selectedPostIds)}
                disabled={historyBusy || selectedPostIds.length === 0}
              >
                <Trash2 size={15} aria-hidden="true" />
                Delete selected ({selectedPostIds.length})
              </button>
              <button
                type="button"
                className="history-delete-button"
                onClick={() => deletePosts(null)}
                disabled={historyBusy}
              >
                <Trash2 size={15} aria-hidden="true" />
                Clear all history
              </button>
            </div>
          )}

          {historyError && (
            <div className="status-message status-error" role="status">
              {historyError}
            </div>
          )}

          {historyBusy ? (
            <p className="history-empty" role="status">
              Loading published posts...
            </p>
          ) : historyError ? null : publishedPosts.length === 0 ? (
            <p className="history-empty">
              No published posts yet. Your posts will appear here after
              publishing.
            </p>
          ) : (
            <div className="history-list">
              {publishedPosts.map((savedPost) => (
                <article className="history-card" key={savedPost.id}>
                  <div className="history-card-heading">
                    <label className="history-select-post">
                      <input
                        type="checkbox"
                        checked={selectedPostIds.includes(savedPost.id)}
                        onChange={() => togglePostSelection(savedPost.id)}
                        aria-label={`Select post published ${new Date(savedPost.published_at).toLocaleString()}`}
                      />
                      <span>Published</span>
                    </label>
                    <time dateTime={savedPost.published_at}>
                      {new Date(savedPost.published_at).toLocaleString()}
                    </time>
                  </div>
                  {savedPost.prompt && (
                    <p className="history-prompt">{savedPost.prompt}</p>
                  )}
                  <p className="history-post-text">{savedPost.text}</p>
                  {savedPost.image_url && (
                    <img
                      className="history-image"
                      src={mediaUrl(savedPost.image_url)}
                      alt="Image attached to this published post"
                    />
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
