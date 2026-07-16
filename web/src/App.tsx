import { useEffect, useState, type FormEvent } from "react";

type RunStatus = "queued" | "processing" | "completed" | "failed";

type RunResult = {
  run_id: string;
  status: RunStatus;
  payload_path: string | null;
  error_code: string | null;
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

function App() {
  const [issueText, setIssueText] = useState("");
  const [moduleName, setModuleName] = useState("");
  const [run, setRun] = useState<RunResult | null>(null);
  const [progress, setProgress] = useState<ProgressEvent[]>([]);
  const [error, setError] = useState("");

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

  async function submitIssue(event: FormEvent) {
    event.preventDefault();
    setError("");
    setProgress([]);
    try {
      const response = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: issueText,
          module: moduleName || null,
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

  return (
    <main className="shell">
      <header>
        <p className="eyebrow">Local prototype · V0</p>
        <h1>SI VidGen</h1>
        <p className="lede">
          Turn an Intacct support issue into a reviewable Higgsfield payload.
        </p>
      </header>

      <section className="panel">
        <form onSubmit={submitIssue}>
          <label htmlFor="issue">Support issue</label>
          <textarea
            id="issue"
            value={issueText}
            onChange={(event) => setIssueText(event.target.value)}
            placeholder="Describe the user problem, context, and desired outcome…"
            minLength={3}
            required
          />

          <label htmlFor="module">Intacct module (optional)</label>
          <input
            id="module"
            value={moduleName}
            onChange={(event) => setModuleName(event.target.value)}
            placeholder="For example: General Ledger"
          />

          <button disabled={run ? !terminalStatuses.includes(run.status) : false}>
            {run && !terminalStatuses.includes(run.status) ? "Processing…" : "Generate draft"}
          </button>
        </form>
      </section>

      {(run || error) && (
        <section className="panel status" aria-live="polite">
          <div className="status-heading">
            <h2>Run status</h2>
            {run && <span className={`badge ${run.status}`}>{run.status}</span>}
          </div>

          {error && <p className="error">{error}</p>}
          <ol className="timeline">
            {progress.map((item, index) => (
              <li key={`${item.stage}-${item.status}-${index}`}>
                <strong>{item.stage}</strong>
                <span>{item.status}</span>
                {item.duration_ms !== null && <small>{item.duration_ms} ms</small>}
              </li>
            ))}
          </ol>

          {run?.status === "completed" && (
            <a className="download" href={`/api/runs/${run.run_id}/payload`}>
              Download Higgsfield payload
            </a>
          )}
        </section>
      )}
    </main>
  );
}

export default App;
