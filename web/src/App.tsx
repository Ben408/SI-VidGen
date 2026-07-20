import { useEffect, useState, type FormEvent } from "react";

type RunStatus = "queued" | "processing" | "completed" | "failed";

type RunResult = {
  run_id: string;
  status: RunStatus;
  payload_path: string | null;
  explainer_package_path: string | null;
  script_path: string | null;
  script_version: number;
  review_status: "not_ready" | "draft" | "approved";
  auto_generate: boolean;
  generation_status: "not_requested" | "pending" | "submitted" | "failed" | "unavailable";
  generation_id: string | null;
  classification: {
    feature: string;
    intent: string;
    task_type: string;
    confidence: number;
    model: string;
  } | null;
  sources: {
    source_id: string;
    source_url: string;
    title: string;
    heading_path: string;
    score: number;
  }[];
  visual_coverage: "green" | "yellow" | "red";
  media_count: number;
  error_code: string | null;
  error_detail: string | null;
};

type Scene = {
  action: string;
  visual: string;
  voiceover: string;
  help_asset: string | null;
  source_ids: string[];
};

type Script = {
  title: string;
  narration: string;
  scenes: Scene[];
  sources: RunResult["sources"];
  generation_model: string;
};

type MediaAsset = {
  asset_id: string;
  asset_class: string | null;
  alt_text: string;
  page_title: string;
  page_url: string;
  source_url: string;
  preview_url: string;
};

type ProgressEvent = {
  run_id: string;
  stage: string;
  status: "started" | "completed" | "failed";
  timestamp: string;
  duration_ms: number | null;
  error_code: string | null;
};

const terminalStatuses: RunStatus[] = ["completed", "failed"];

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2.75 13.85 9 20 10.85 13.85 12.7 12 19l-1.85-6.3L4 10.85 10.15 9 12 2.75Z" />
      <path d="m18.25 16 .75 2.25L21.25 19 19 19.75 18.25 22l-.75-2.25L15.25 19l2.25-.75.75-2.25Z" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M4 10h11M11 6l4 4-4 4" />
    </svg>
  );
}

function App() {
  const [issueText, setIssueText] = useState("");
  const [moduleName, setModuleName] = useState("");
  const [run, setRun] = useState<RunResult | null>(null);
  const [progress, setProgress] = useState<ProgressEvent[]>([]);
  const [error, setError] = useState("");
  const [script, setScript] = useState<Script | null>(null);
  const [medias, setMedias] = useState<MediaAsset[]>([]);
  const [scriptDirty, setScriptDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [autoGenerate, setAutoGenerate] = useState(false);
  const [generationAvailable, setGenerationAvailable] = useState(false);

  useEffect(() => {
    fetch("/api/capabilities")
      .then((response) => response.json())
      .then((capabilities) => {
        setGenerationAvailable(Boolean(capabilities.higgsfield_generation));
      })
      .catch(() => setGenerationAvailable(false));
  }, []);

  useEffect(() => {
    if (!run || terminalStatuses.includes(run.status)) return;

    const interval = window.setInterval(async () => {
      try {
        const [runResponse, progressResponse] = await Promise.all([
          fetch(`/api/runs/${run.run_id}`),
          fetch(`/api/runs/${run.run_id}/progress`),
        ]);
        if (!runResponse.ok || !progressResponse.ok) {
          throw new Error("Unable to read pipeline progress");
        }
        setRun(await runResponse.json());
        setProgress(await progressResponse.json());
      } catch (pollError) {
        setError(pollError instanceof Error ? pollError.message : "Progress request failed");
      }
    }, 500);

    return () => window.clearInterval(interval);
  }, [run]);

  useEffect(() => {
    if (run?.status !== "completed") return;
    fetch(`/api/runs/${run.run_id}/script`)
      .then((response) => {
        if (!response.ok) throw new Error("Unable to load the editable script");
        return response.json();
      })
      .then((loadedScript) => {
        setScript(loadedScript);
        setScriptDirty(false);
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "Script load failed");
      });

    fetch(`/api/runs/${run.run_id}/medias`)
      .then((response) => (response.ok ? response.json() : { assets: [] }))
      .then((payload) => setMedias(Array.isArray(payload.assets) ? payload.assets : []))
      .catch(() => setMedias([]));
  }, [run?.run_id, run?.status, run?.script_version, run?.media_count]);

  async function submitIssue(event: FormEvent) {
    event.preventDefault();
    setError("");
    setProgress([]);
    setScript(null);
    setMedias([]);
    setScriptDirty(false);
    try {
      const response = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: issueText,
          module: moduleName || null,
          auto_generate: autoGenerate,
        }),
      });
      if (!response.ok) {
        throw new Error("The issue could not be submitted");
      }
      setRun(await response.json());
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Submission failed");
    }
  }

  function updateScene(index: number, field: keyof Scene, value: string) {
    if (!script) return;
    setScriptDirty(true);
    setScript({
      ...script,
      scenes: script.scenes.map((scene, sceneIndex) =>
        sceneIndex === index ? { ...scene, [field]: value } : scene,
      ),
    });
  }

  async function saveScript() {
    if (!run || !script) return;
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`/api/runs/${run.run_id}/script`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: script.title,
          narration: script.narration,
          scenes: script.scenes,
        }),
      });
      if (!response.ok) {
        const detail = await response.json();
        throw new Error(detail.detail || "Unable to save the script");
      }
      setRun(await response.json());
      setScriptDirty(false);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Script save failed");
    } finally {
      setSaving(false);
    }
  }

  async function approveScript(generateVideo: boolean) {
    if (!run || !script) return;
    setSaving(true);
    setError("");
    try {
      if (scriptDirty) {
        const saveResponse = await fetch(`/api/runs/${run.run_id}/script`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: script.title,
            narration: script.narration,
            scenes: script.scenes,
          }),
        });
        if (!saveResponse.ok) {
          const detail = await saveResponse.json();
          throw new Error(detail.detail || "Unable to save the script");
        }
        setRun(await saveResponse.json());
        setScriptDirty(false);
      }
      const response = await fetch(`/api/runs/${run.run_id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ generate_video: generateVideo }),
      });
      if (!response.ok) throw new Error("Unable to approve the script");
      setRun(await response.json());
    } catch (approvalError) {
      setError(approvalError instanceof Error ? approvalError.message : "Approval failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="app">
      <nav className="topbar" aria-label="Primary navigation">
        <div className="nav-inner">
          <a className="brand" href="/" aria-label="Sage Intacct video studio home">
            <span className="sage-wordmark">Sage</span>
            <span className="brand-divider" aria-hidden="true" />
            <span className="intacct-wordmark">Intacct</span>
          </a>
          <div className="product-name">Video Studio</div>
          <span className="prototype-badge">Local prototype</span>
        </div>
      </nav>

      <main>
        <header className="hero">
          <div className="hero-inner">
            <div className="hero-copy">
              <p className="eyebrow">AI-assisted authoring</p>
              <h1>Turn support knowledge into clear, useful videos.</h1>
              <p className="lede">
                Create a review-ready video draft from a Sage Intacct support issue.
                Your source content stays local.
              </p>
            </div>
            <div className="hero-mark" aria-hidden="true">
              <SparkIcon />
            </div>
          </div>
        </header>

        <div className="workspace">
          <section className="panel form-panel" aria-labelledby="create-heading">
            <div className="section-heading">
              <span className="step-number">01</span>
              <div>
                <p className="section-kicker">Create a draft</p>
                <h2 id="create-heading">What should the video explain?</h2>
              </div>
            </div>

            <form onSubmit={submitIssue}>
              <div className="field">
                <div className="label-row">
                  <label htmlFor="issue">Support issue</label>
                  <span>Required</span>
                </div>
                <textarea
                  id="issue"
                  value={issueText}
                  onChange={(event) => setIssueText(event.target.value)}
                  placeholder="Describe the user problem, relevant context, and the outcome they need…"
                  minLength={3}
                  required
                />
                <p className="field-hint">
                  Include the task, the audience, and where they get stuck.
                </p>
              </div>

              <div className="field">
                <label htmlFor="module">Intacct module</label>
                <input
                  id="module"
                  value={moduleName}
                  onChange={(event) => setModuleName(event.target.value)}
                  placeholder="For example: General Ledger"
                />
                <p className="field-hint">Optional, but helps focus the source search.</p>
              </div>

              <label className={`toggle-row ${!generationAvailable ? "disabled" : ""}`}>
                <input
                  type="checkbox"
                  checked={autoGenerate}
                  disabled={!generationAvailable}
                  onChange={(event) => setAutoGenerate(event.target.checked)}
                />
                <span className="toggle-control" aria-hidden="true" />
                <span>
                  <strong>Generate video automatically</strong>
                  <small>
                    {generationAvailable
                      ? "Skip manual review and send a valid draft directly to Higgsfield."
                      : "Available after the Higgsfield API is configured."}
                  </small>
                </span>
              </label>

              <button
                className="primary-action"
                disabled={run ? !terminalStatuses.includes(run.status) : false}
              >
                <SparkIcon />
                <span>
                  {run && !terminalStatuses.includes(run.status)
                    ? "Creating your draft…"
                    : "Generate video draft"}
                </span>
                <ArrowIcon />
              </button>
            </form>
          </section>

          <aside className="guidance" aria-labelledby="guidance-heading">
            <p className="section-kicker">Before you begin</p>
            <h2 id="guidance-heading">A better brief makes a better video.</h2>
            <ul>
              <li>
                <span>1</span>
                <div>
                  <strong>Be specific</strong>
                  <p>Describe one user goal per draft.</p>
                </div>
              </li>
              <li>
                <span>2</span>
                <div>
                  <strong>Add context</strong>
                  <p>Include the role, module, and expected result.</p>
                </div>
              </li>
              <li>
                <span>3</span>
                <div>
                  <strong>Review the output</strong>
                  <p>Confirm every step before publishing.</p>
                </div>
              </li>
            </ul>
            <div className="privacy-note">
              <span className="privacy-icon" aria-hidden="true">✓</span>
              <p><strong>Local by design</strong>Your issue stays in your local workflow.</p>
            </div>
          </aside>
        </div>

        {(run || error) && (
          <section className="panel status" aria-live="polite">
            <div className="status-heading">
              <div>
                <p className="section-kicker">Pipeline activity</p>
                <h2>Draft status</h2>
              </div>
              {run && <span className={`badge ${run.status}`}>{run.status}</span>}
            </div>

            {error && <p className="error">{error}</p>}
            {run?.status === "failed" && (
              <p className="error">
                {run.error_code || "Pipeline failed"}
                {run.error_detail ? ` — ${run.error_detail}` : ""}
              </p>
            )}
            <ol className="timeline">
              {progress.map((item, index) => (
                <li key={`${item.stage}-${item.status}-${index}`}>
                  <span className="timeline-dot" aria-hidden="true" />
                  <strong>{item.stage}</strong>
                  <span>{item.status}</span>
                  {item.duration_ms !== null && <small>{item.duration_ms} ms</small>}
                </li>
              ))}
            </ol>

          {run?.status === "completed" && (
            <div className="review">
              {run.classification && (
                <div className="review-summary">
                  <div>
                    <span>Feature</span>
                    <strong>{run.classification.feature}</strong>
                  </div>
                  <div>
                    <span>Task</span>
                    <strong>{run.classification.task_type}</strong>
                  </div>
                  <div>
                    <span>Confidence</span>
                    <strong>{Math.round(run.classification.confidence * 100)}%</strong>
                  </div>
                  <div>
                    <span>Local model</span>
                    <strong>{run.classification.model}</strong>
                  </div>
                  <div>
                    <span>Help visuals</span>
                    <strong className={`coverage-${run.visual_coverage || "red"}`}>
                      {run.visual_coverage || "red"} · {run.media_count || 0} media
                    </strong>
                  </div>
                </div>
              )}

              <div className="source-review">
                <h3>Official help sources</h3>
                <ul>
                  {run.sources.map((source) => (
                    <li key={source.source_id}>
                      <a href={source.source_url} target="_blank" rel="noreferrer">
                        {source.title}
                      </a>
                      <span>{source.heading_path || "Topic overview"}</span>
                      <small>{Math.round(source.score * 100)}% relevance</small>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="media-preview">
                <div className="media-preview-heading">
                  <h3>Images for Higgsfield</h3>
                  <span>
                    {medias.length
                      ? `${medias.length} attached · review before generate`
                      : "No Help screenshots attached for this run"}
                  </span>
                </div>
                {medias.length > 0 && (
                  <ul className="media-grid">
                    {medias.map((asset, index) => (
                      <li key={asset.asset_id}>
                        <a
                          href={asset.preview_url}
                          target="_blank"
                          rel="noreferrer"
                          title={asset.alt_text || asset.page_title}
                        >
                          <img
                            src={asset.preview_url}
                            alt={asset.alt_text || `Help visual ${index + 1}`}
                            loading="lazy"
                          />
                        </a>
                        <div>
                          <strong>
                            {index + 1}. {asset.asset_class || "image"}
                          </strong>
                          <span>{asset.alt_text || asset.page_title || "Help asset"}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {script && (
                <div className="script-editor">
                  <div className="editor-heading">
                    <div>
                      <p className="section-kicker">Editable script · version {run.script_version}</p>
                      <h3>Review every line before generation</h3>
                    </div>
                    <span className={`review-state ${run.review_status}`}>
                      {run.review_status}
                    </span>
                  </div>

                  <label>
                    Video title
                    <input
                      value={script.title}
                      onChange={(event) => {
                        setScriptDirty(true);
                        setScript({ ...script, title: event.target.value });
                      }}
                    />
                  </label>
                  <label>
                    Narration
                    <textarea
                      value={script.narration}
                      onChange={(event) => {
                        setScriptDirty(true);
                        setScript({ ...script, narration: event.target.value });
                      }}
                    />
                  </label>

                  <div className="scene-list">
                    {script.scenes.map((scene, index) => (
                      <fieldset key={`scene-${index}`}>
                        <legend>Scene {index + 1}</legend>
                        <label>
                          Action
                          <textarea
                            value={scene.action}
                            onChange={(event) =>
                              updateScene(index, "action", event.target.value)
                            }
                          />
                        </label>
                        <label>
                          Visual
                          <textarea
                            value={scene.visual}
                            onChange={(event) =>
                              updateScene(index, "visual", event.target.value)
                            }
                          />
                        </label>
                        <label>
                          Voiceover
                          <textarea
                            value={scene.voiceover}
                            onChange={(event) =>
                              updateScene(index, "voiceover", event.target.value)
                            }
                          />
                        </label>
                        <p className="grounding-note">
                          Grounded by: {scene.source_ids.join(", ")}
                          {scene.help_asset && <> · Help asset locked to source</>}
                        </p>
                      </fieldset>
                    ))}
                  </div>

                  <div className="review-actions">
                    <button
                      type="button"
                      className="download secondary"
                      onClick={saveScript}
                      disabled={saving || !scriptDirty}
                    >
                      {saving
                        ? "Saving…"
                        : scriptDirty
                          ? "Save new version"
                          : "Saved"}
                    </button>
                    <button
                      type="button"
                      className="download secondary"
                      onClick={() => approveScript(false)}
                      disabled={saving}
                    >
                      Approve script
                    </button>
                    <button
                      type="button"
                      className="download"
                      onClick={() => approveScript(true)}
                      disabled={saving || !generationAvailable}
                    >
                      Approve &amp; send to Higgsfield
                      <ArrowIcon />
                    </button>
                  </div>

                  {run.generation_status !== "not_requested" && (
                    <p className={`generation-status ${run.generation_status}`}>
                      Video generation: {run.generation_status}
                      {run.generation_id && ` · ${run.generation_id}`}
                    </p>
                  )}
                </div>
              )}

              <div className="artifact-actions">
                <a className="download" href={`/api/runs/${run.run_id}/script`} download>
                  Download grounded script
                  <ArrowIcon />
                </a>
                <a className="download secondary" href={`/api/runs/${run.run_id}/payload`}>
                  Download Higgsfield payload
                  <ArrowIcon />
                </a>
                {run.explainer_package_path && (
                  <a
                    className="download secondary"
                    href={`/api/runs/${run.run_id}/explainer-package`}
                  >
                    Download explainer package
                    <ArrowIcon />
                  </a>
                )}
              </div>
              <p className="credit-note">
                {run.generation_status === "submitted"
                  ? "The approved script was submitted to Higgsfield."
                  : "No video request has been sent. Saving an edit rebuilds the payload automatically."}
              </p>
            </div>
          )}
          </section>
        )}
      </main>

      <footer>
        <p>Sage Intacct Video Studio</p>
        <span>Prototype V0 · For internal review</span>
      </footer>
    </div>
  );
}

export default App;
