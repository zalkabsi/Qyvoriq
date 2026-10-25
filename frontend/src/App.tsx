import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent, DragEvent, FormEvent } from "react";

type State = "OBSERVING" | "MEASURING" | "VERIFYING" | "REINSPECTION_REQUIRED" | "VERIFIED" | "HUMAN_REVIEW_REQUIRED" | "UNSUPPORTED_INSTRUMENT" | "FAILED";
type Measurement = { estimator: "geometric" | "polar"; pass_number: number; angle_deg: number; value: number; units: string; in_calibration_range: boolean; evidence: Record<string, number | string> };
type TraceEvent = { time: string; state: string; tool: string; message: string; details: Record<string, string | number | boolean | null> };
type Inspection = {
  inspection_id: string;
  state: State;
  attempt_number: number;
  reading_value: number | null;
  units: string | null;
  normalized_disagreement_pct_fs: number | null;
  image_quality: { usable?: boolean; reasons?: string[]; metrics?: Record<string, number>; glare_boxes?: number[][] };
  geometry: { center_x?: number; center_y?: number; radius_px?: number; method?: string };
  measurements: Measurement[];
  decision_reasons: string[];
  next_action: string | null;
  trace: TraceEvent[];
  evidence_url: string | null;
  created_at: string;
  expires_at: string;
};
type Benchmark = {
  available?: boolean;
  message?: string;
  dataset?: string;
  dataset_type?: string;
  samples?: number;
  opencv_version?: string;
  summary?: Record<string, { predicted_count: number; coverage: number; mae_fs_pct: number | null; p95_abs_error_fs_pct: number | null; false_accept_rate_over_5pct_fs: number | null }>;
  selective_risk_curve_fixed_mean?: { disagreement_threshold_pct_fs: number; accepted_count: number; coverage: number; selective_mae_pct_fs: number | null; false_accept_rate_over_5pct_fs: number | null }[];
  failure_rate_by_condition?: Record<string, { sample_count: number; verified_count: number; agent_abstention_rate: number; agent_selective_mae_pct_fs: number | null }>;
};

const scenarios = [
  { id: "clear", name: "Clear gauge", note: "Synthetic · same-state control" },
  { id: "glare", name: "Glass reflection", note: "Synthetic · asks for another view" },
  { id: "contradictory", name: "Two pointers", note: "Synthetic · unsupported ambiguity" },
  { id: "unsupported", name: "Digital meter", note: "Synthetic · outside scope" },
];

const initialCalibration = { minimum_value: "0", maximum_value: "100", units: "psi", start_angle_deg: "135", end_angle_deg: "45", sweep_direction: "clockwise" };

function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true as const };
  if (name === "arrow") return <svg {...common}><path d="M5 12h14M13 5l7 7-7 7" /></svg>;
  if (name === "upload") return <svg {...common}><path d="M12 16V4m0 0L7 9m5-5 5 5M4 16v4h16v-4" /></svg>;
  if (name === "camera") return <svg {...common}><path d="M4 7h3l2-2h6l2 2h3v12H4z" /><circle cx="12" cy="13" r="3.5" /></svg>;
  if (name === "gauge") return <svg {...common}><path d="M4.8 19a9 9 0 1 1 14.4 0M12 13l4-4M6 17h12" /><circle cx="12" cy="13" r="1" /></svg>;
  if (name === "shield") return <svg {...common}><path d="M12 3 20 6v5c0 5-3.3 8.3-8 10-4.7-1.7-8-5-8-10V6z" /><path d="m8.5 12 2.3 2.3 4.7-5" /></svg>;
  if (name === "activity") return <svg {...common}><path d="M3 12h4l2-6 4 12 2-6h6" /></svg>;
  if (name === "clock") return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>;
  if (name === "close") return <svg {...common}><path d="m6 6 12 12M18 6 6 18" /></svg>;
  if (name === "check") return <svg {...common}><path d="m5 12 4 4L19 6" /></svg>;
  return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M12 8v4m0 4h.01" /></svg>;
}

function stateCopy(state?: State) {
  switch (state) {
    case "VERIFIED": return { title: "Accepted under policy", badge: "VERIFIED", tone: "good", summary: "Quality, geometry, calibration, and estimator-agreement checks passed for this image." };
    case "REINSPECTION_REQUIRED": return { title: "A better view is needed", badge: "NEW VIEW", tone: "warn", summary: "The system found a measurable issue and is waiting for a new image from you." };
    case "HUMAN_REVIEW_REQUIRED": return { title: "Human review required", badge: "ESCALATED", tone: "danger", summary: "The system could not resolve the evidence within its retry limit." };
    case "UNSUPPORTED_INSTRUMENT": return { title: "Outside supported scope", badge: "UNSUPPORTED", tone: "muted", summary: "Qyvoriq supports calibrated circular gauges with one pointer and a linear scale." };
    case "FAILED": return { title: "Inspection failed", badge: "FAILED", tone: "danger", summary: "The inspection could not be completed. Review the error and try another image." };
    default: return { title: "Ready to inspect", badge: "READY", tone: "muted", summary: "Upload a gauge image and confirm its scale calibration." };
  }
}

function prettyTool(tool: string) {
  return tool.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

function App() {
  const [tab, setTab] = useState<"inspect" | "evaluation">("inspect");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<string | null>(null);
  const [result, setResult] = useState<Inspection | null>(null);
  const [calibration, setCalibration] = useState(initialCalibration);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [benchmark, setBenchmark] = useState<Benchmark | null>(null);
  const [apiToken, setApiToken] = useState("");
  const [tokenDraft, setTokenDraft] = useState("");
  const [showTokenInput, setShowTokenInput] = useState(false);
  const [tokenRequired, setTokenRequired] = useState(false);

  useEffect(() => {
    if (!file) { setPreview(null); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => () => {
    if (evidence) URL.revokeObjectURL(evidence);
  }, [evidence]);

  useEffect(() => {
    if (tab !== "evaluation" || benchmark) return;
    fetch("/api/benchmarks", { headers: authHeaders() })
      .then(async (response) => {
        if (response.status === 401) {
          setTokenRequired(true);
          setShowTokenInput(true);
          return { available: false, message: "This deployment requires an access token. Enter it in the header to load evaluation data." } as Benchmark;
        }
        return response.json() as Promise<Benchmark>;
      })
      .then((data: Benchmark) => setBenchmark(data))
      .catch(() => setBenchmark({ available: false, message: "Benchmark results are not available from the API." }));
  }, [tab, benchmark, apiToken]);

  const copy = stateCopy(result?.state);
  const canFollowUp = result?.state === "REINSPECTION_REQUIRED";
  const decisionEvents = useMemo(() => result?.trace ?? [], [result]);

  function authHeaders(): HeadersInit {
    return apiToken ? { Authorization: `Bearer ${apiToken}` } : {};
  }

  function applyToken(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setApiToken(tokenDraft.trim());
    setTokenRequired(false);
    setShowTokenInput(false);
    setBenchmark(null);
    setError("");
  }

  function setSelectedImage(next: File | null) {
    setFile(next);
    setEvidence(null);
    setError("");
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedImage(event.target.files?.[0] ?? null);
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    const next = event.dataTransfer.files?.[0];
    if (next) setSelectedImage(next);
  }

  async function loadScenario(id: string) {
    setError("");
    try {
      const response = await fetch(`/scenarios/${id}.png`);
      if (!response.ok) throw new Error("The scenario image could not be loaded.");
      const blob = await response.blob();
      setSelectedImage(new File([blob], `${id}.png`, { type: "image/png" }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The scenario image could not be loaded.");
    }
  }

  async function submitInspection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) { setError("Choose an image before starting the inspection."); return; }
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("file", file);
      if (!canFollowUp) {
        body.append("calibration", JSON.stringify({
          minimum_value: Number(calibration.minimum_value),
          maximum_value: Number(calibration.maximum_value),
          units: calibration.units,
          start_angle_deg: Number(calibration.start_angle_deg),
          end_angle_deg: Number(calibration.end_angle_deg),
          sweep_direction: calibration.sweep_direction,
        }));
      }
      const path = canFollowUp ? `/api/inspections/${result!.inspection_id}/images` : "/api/inspections";
      const response = await fetch(path, { method: "POST", headers: authHeaders(), body });
      const payload = await response.json();
      if (response.status === 401) {
        setTokenRequired(true);
        setShowTokenInput(true);
      }
      if (!response.ok) throw new Error(payload?.error?.message ?? "The inspection request failed.");
      setResult(payload as Inspection);
      const imageResponse = await fetch(payload.evidence_url, { headers: authHeaders() });
      if (imageResponse.ok) setEvidence(URL.createObjectURL(await imageResponse.blob()));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The inspection request failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Qyvoriq home">
          <span className="brand-mark"><span /><span /><span /></span>
          <span className="brand-name">qyvoriq<span className="brand-dot">.</span></span>
        </a>
        <div className="topbar-center"><span className="live-dot" /> Inspection environment <span className="topbar-divider">/</span> <span className="engine-version">OpenCV 5</span></div>
        <div className="topbar-right">{showTokenInput ? <form className="token-form" onSubmit={applyToken}><input aria-label="API access token" type="password" autoComplete="off" value={tokenDraft} onChange={(event) => setTokenDraft(event.target.value)} placeholder={tokenRequired ? "Enter access token" : "Optional API token"} /><button type="submit">Apply</button></form> : <button className={`token-button ${apiToken ? "connected" : ""}`} type="button" onClick={() => setShowTokenInput(true)}>{apiToken ? "Token set" : "Access token"}</button>}<span className="secure-pill"><Icon name="shield" size={14} /> evidence-first</span><span className="avatar">Q</span></div>
      </header>

      <div className="workspace" id="top">
        <aside className="sidebar">
          <div className="side-section-label">WORKSPACE</div>
          <button className={`nav-item ${tab === "inspect" ? "active" : ""}`} onClick={() => setTab("inspect")}><Icon name="camera" /> <span>Inspection</span><span className="nav-active-bar" /></button>
          <button className={`nav-item ${tab === "evaluation" ? "active" : ""}`} onClick={() => setTab("evaluation")}><Icon name="activity" /> <span>Evaluation</span></button>
          <div className="side-divider" />
          <div className="side-section-label">SCOPE</div>
          <div className="scope-card"><div className="scope-icon"><Icon name="gauge" size={16} /></div><div><strong>Single-pointer dial</strong><span>Linear · calibrated</span></div></div>
          <div className="scope-card"><div className="scope-icon soft"><Icon name="shield" size={16} /></div><div><strong>Abstention enabled</strong><span>Human stays in control</span></div></div>
          <div className="sidebar-bottom"><div className="retention-icon"><Icon name="clock" size={15} /></div><div><strong>Ephemeral sessions</strong><span>Images clear after 30 min</span></div></div>
        </aside>

        <main className="main-content">
          {tab === "inspect" ? (
            <>
              <section className="page-heading">
                <div><div className="eyebrow"><span className="eyebrow-line" /> TRUSTED VISUAL INSPECTION</div><h1>See the evidence.<br /><em>Know when to pause.</em></h1><p className="heading-copy">Qyvoriq reads calibrated analog gauges, checks its own visual evidence, and asks for another view when the image is unreliable.</p></div>
                <div className="heading-stat"><span className="stat-kicker">DECISION POLICY</span><div className="policy-status"><span className="policy-dot" /> Active</div><span className="stat-caption">No confidence percentages.<br />Every decision is traceable.</span></div>
              </section>

              <div className="content-grid">
                <section className="panel input-panel">
                  <div className="panel-header"><div><span className="step-number">01</span><h2>New inspection</h2></div><span className="panel-meta">JPEG · PNG · WEBP <span>≤ 10 MB</span></span></div>
                  <form onSubmit={submitInspection}>
                    <label className={`dropzone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
                      <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onFileChange} aria-label="Choose a gauge image" />
                      {preview ? <div className="upload-preview"><img src={preview} alt="Selected gauge" /><span className="image-check"><Icon name="check" size={14} /></span><div className="upload-caption"><strong>{file?.name}</strong><span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · latest observation` : ""}</span></div></div> : <div className="drop-content"><div className="upload-icon"><Icon name="upload" size={21} /></div><strong>Drop a gauge image here</strong><span>or <u>browse files</u> from your device</span><small>Keep the full dial in frame, square to the lens</small></div>}
                    </label>

                    <div className="sample-row"><span>QUICK SCENARIOS</span>{scenarios.map((scenario) => <button type="button" key={scenario.id} className="sample-button" onClick={() => void loadScenario(scenario.id)} title={scenario.note}>{scenario.name}<span>↗</span></button>)}</div>
                    <p className="sample-note">All scenarios are generated, labeled synthetic fixtures. “Clear gauge” is paired with “glass reflection” at the same 63 psi setting.</p>

                    <div className="form-section-heading"><div><span className="step-number">02</span><h3>Scale calibration</h3></div><span>Required for a numeric reading</span></div>
                    <div className="form-grid">
                      <label className="field"><span>Minimum value</span><div className="input-wrap"><input type="number" step="any" value={calibration.minimum_value} onChange={(event) => setCalibration({ ...calibration, minimum_value: event.target.value })} required /><span className="field-unit">LOW</span></div></label>
                      <label className="field"><span>Maximum value</span><div className="input-wrap"><input type="number" step="any" value={calibration.maximum_value} onChange={(event) => setCalibration({ ...calibration, maximum_value: event.target.value })} required /><span className="field-unit">HIGH</span></div></label>
                      <label className="field"><span>Units</span><input type="text" value={calibration.units} onChange={(event) => setCalibration({ ...calibration, units: event.target.value })} maxLength={20} placeholder="psi" required /></label>
                      <label className="field"><span>Needle sweep</span><select value={calibration.sweep_direction} onChange={(event) => setCalibration({ ...calibration, sweep_direction: event.target.value })}><option value="clockwise">Clockwise</option><option value="counterclockwise">Counterclockwise</option></select></label>
                      <label className="field"><span>Minimum angle <small>image degrees</small></span><input type="number" min="0" max="360" step="any" value={calibration.start_angle_deg} onChange={(event) => setCalibration({ ...calibration, start_angle_deg: event.target.value })} required /></label>
                      <label className="field"><span>Maximum angle <small>image degrees</small></span><input type="number" min="0" max="360" step="any" value={calibration.end_angle_deg} onChange={(event) => setCalibration({ ...calibration, end_angle_deg: event.target.value })} required /></label>
                    </div>
                    <div className="calibration-hint"><span className="hint-mark">i</span><span>Angle 0° points right; angles increase clockwise on the image. Enter your gauge’s actual endpoints.</span></div>
                    {error && <div className="error-banner" role="alert"><Icon name="info" size={17} />{error}</div>}
                    <button className="primary-button" type="submit" disabled={busy || !file}>{busy ? <><span className="spinner" /> Running visual checks…</> : canFollowUp ? <><Icon name="camera" size={17} /> Submit next view <Icon name="arrow" size={17} /></> : <>Start inspection <Icon name="arrow" size={17} /></>}</button>
                    <div className="safe-note"><Icon name="shield" size={15} /><span>Decision support only. Never use as the sole basis for safety-critical control.</span></div>
                  </form>
                </section>

                <section className="panel result-panel">
                  <div className="panel-header"><div><span className="step-number">03</span><h2>Inspection result</h2></div><span className={`status-pill ${copy.tone}`}><span className="status-dot" />{copy.badge}</span></div>
                  <div className={`decision-card ${copy.tone}`}>
                    <div className="decision-top"><div className="decision-symbol"><Icon name={result?.state === "VERIFIED" ? "check" : result?.state === "REINSPECTION_REQUIRED" ? "camera" : "shield"} size={18} /></div><div className="decision-title"><span>{result ? `OBSERVATION ${result.attempt_number}` : "AWAITING IMAGE"}</span><h3>{copy.title}</h3></div></div>
                    <p>{result?.decision_reasons?.[0] ?? copy.summary}</p>
                    {result?.next_action && <div className="next-action"><span>NEXT ACTION</span><strong>{result.next_action}</strong></div>}
                    {result?.state === "HUMAN_REVIEW_REQUIRED" && <div className="review-chip"><Icon name="info" size={15} /> Review with a qualified operator</div>}
                  </div>

                  <div className="reading-row"><div className="reading-main"><span className="reading-label">POLICY-ACCEPTED READING</span><div className="reading-value">{result?.reading_value !== null && result?.reading_value !== undefined ? <>{result.reading_value.toFixed(2)}<span>{result.units}</span></> : <><span className="empty-reading">—</span><span className="waiting-label">not accepted</span></>}</div></div><div className="reading-divider" /><div className="reading-secondary"><span>ESTIMATOR DELTA</span><strong>{result?.normalized_disagreement_pct_fs !== null && result?.normalized_disagreement_pct_fs !== undefined ? `${result.normalized_disagreement_pct_fs.toFixed(2)}% FS` : "—"}</strong><small>full-scale span</small></div></div>

                  <div className="evidence-section"><div className="section-label-row"><h3>Visual evidence</h3><span>{result?.geometry?.method ? result.geometry.method.replaceAll("_", " ") : "Original stays unchanged"}</span></div><div className="evidence-compare">
                    <div className="image-frame"><div className="frame-label">SOURCE VIEW</div>{preview ? <img src={preview} alt="Original inspection image" /> : <div className="empty-frame"><Icon name="camera" size={22} /><span>Upload an image to begin</span></div>}</div>
                    <div className="image-frame"><div className="frame-label">OPENCV ANNOTATION</div>{evidence ? <img src={evidence} alt="OpenCV evidence with gauge boundary, rotation center, candidate needle, and uncertainty markers" /> : <div className="empty-frame annotated-empty"><Icon name="gauge" size={22} /><span>Evidence overlay appears here</span></div>}</div>
                  </div></div>

                  <div className="detail-grid">
                    <div className="detail-block"><div className="section-label-row"><h3>Estimator checks</h3><span>{result?.measurements.length ? "2 evidence paths" : "awaiting usable evidence"}</span></div>{result?.measurements.length ? result.measurements.map((measurement) => <div className="method-row" key={`${measurement.estimator}-${measurement.pass_number}`}><span className={`method-marker ${measurement.estimator}`} /> <span className="method-name">{measurement.estimator} <small>pass {measurement.pass_number}</small></span><strong>{measurement.value.toFixed(2)} {measurement.units}</strong><Icon name={measurement.in_calibration_range ? "check" : "info"} size={15} /></div>) : <div className="empty-methods">Candidates stay hidden when evidence is insufficient.</div>}</div>
                    <div className="detail-block"><div className="section-label-row"><h3>Image quality</h3><span className={result?.image_quality.usable ? "text-good" : result ? "text-warn" : ""}>{result ? result.image_quality.usable ? "usable" : "needs attention" : "not assessed"}</span></div>{result?.image_quality.metrics ? <div className="quality-metrics"><div><span>Blur signal</span><strong>{result.image_quality.metrics.laplacian_variance?.toFixed(0) ?? "—"}</strong></div><div><span>Contrast range</span><strong>{result.image_quality.metrics.contrast_p95_p5?.toFixed(0) ?? "—"}</strong></div><div><span>Glare regions</span><strong>{result.image_quality.glare_boxes?.length ?? 0}</strong></div></div> : <div className="empty-methods">Blur, exposure, contrast, and glare checks.</div>}</div>
                  </div>

                  <div className="trace-section"><div className="section-label-row"><h3>Decision trace</h3><span>{decisionEvents.length ? `${decisionEvents.length} recorded actions` : "Live tool log"}</span></div>{decisionEvents.length ? <ol className="trace-list">{decisionEvents.slice(-7).map((event, index) => <li key={`${event.time}-${event.tool}-${index}`}><span className={`trace-marker ${event.state === "VERIFIED" ? "passed" : event.tool === "request_new_view" || event.tool === "escalate_to_human" ? "attention" : ""}`} /><div><strong>{prettyTool(event.tool)}</strong><span>{event.message}</span>{Object.keys(event.details).length > 0 && <small>{Object.entries(event.details).map(([key, value]) => `${prettyTool(key)}: ${value}`).join(" · ")}</small>}</div><time>{new Date(event.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></li>)}</ol> : <div className="trace-empty"><span className="trace-line" /><div><strong>Image received</strong><span>Tool decisions will appear as they happen.</span></div></div>}</div>

                  {result && <div className="report-footer"><span>Inspection ID <code>{result.inspection_id.slice(0, 8)}</code></span><span>Expires {new Date(result.expires_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span></div>}
                </section>
              </div>
            </>
          ) : <EvaluationView benchmark={benchmark} />}
          <footer className="page-footer"><span>QYVORIQ · THE VISION AGENT THAT KNOWS WHEN NOT TO TRUST ITS EYES</span><span>Prototype · not for safety-critical operation</span></footer>
        </main>
      </div>
    </div>
  );
}

function EvaluationView({ benchmark }: { benchmark: Benchmark | null }) {
  const summary = benchmark?.summary ?? {};
  const labels: Record<string, string> = { baseline_a_geometric: "Geometric only", baseline_b_fixed_mean: "Fixed two-method mean", qyvoriq_selective: "Qyvoriq selective policy" };
  return <section className="evaluation-page">
    <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> MEASURED EVIDENCE</div><h1>Evaluation, <em>without theater.</em></h1><p className="heading-copy">Numbers here come from a reproducible run. Synthetic results are not evidence of field performance.</p></div><span className="synthetic-badge">{benchmark?.dataset_type === "synthetic_only" ? "SYNTHETIC ONLY" : "NO DATA YET"}</span></div>
    {!benchmark || !benchmark.available ? <div className="panel no-benchmark"><Icon name="activity" size={24} /><h2>No run recorded yet</h2><p>{benchmark?.message ?? "The benchmark endpoint is loading."}</p><code>python -m benchmarks.run_benchmark --split test --samples 120</code></div> : <>
      <div className="evaluation-banner"><div><span className="banner-label">DATASET</span><strong>{benchmark.dataset}</strong></div><div><span className="banner-label">SAMPLES</span><strong>{benchmark.samples}</strong></div><div><span className="banner-label">RUNTIME</span><strong>OpenCV {benchmark.opencv_version}</strong></div><p>Controlled generated scenes · no real photographs · disjoint deterministic seed range for this split.</p></div>
      <div className="metric-cards">{["qyvoriq_selective", "baseline_b_fixed_mean", "baseline_a_geometric"].map((key) => { const item = summary[key]; return <div className={`panel metric-card ${key === "qyvoriq_selective" ? "featured" : ""}`} key={key}><span className="metric-overline">{labels[key]}</span><strong>{item?.mae_fs_pct === null || item?.mae_fs_pct === undefined ? "—" : `${item.mae_fs_pct.toFixed(2)}%`}</strong><span>mean absolute error · full scale</span><div className="metric-foot"><span>Coverage</span><b>{item ? `${(item.coverage * 100).toFixed(1)}%` : "—"}</b></div><div className="metric-foot"><span>False accepts &gt; 5% FS</span><b>{item?.false_accept_rate_over_5pct_fs === null || item?.false_accept_rate_over_5pct_fs === undefined ? "—" : `${(item.false_accept_rate_over_5pct_fs * 100).toFixed(1)}%`}</b></div></div>; })}</div>
      <div className="evaluation-grid"><div className="panel eval-panel"><div className="panel-header"><div><span className="step-number">A</span><h2>Selective risk vs coverage</h2></div><span className="panel-meta">Fixed-mean comparator</span></div><div className="risk-table"><div className="risk-head"><span>Disagreement cap</span><span>Coverage</span><span>Selective MAE</span><span>False accept</span></div>{benchmark.selective_risk_curve_fixed_mean?.map((row) => <div className="risk-row" key={row.disagreement_threshold_pct_fs}><span>{row.disagreement_threshold_pct_fs.toFixed(1)}% FS</span><div className="bar-cell"><i style={{ width: `${Math.max(1, row.coverage * 100)}%` }} /><b>{(row.coverage * 100).toFixed(0)}%</b></div><span>{row.selective_mae_pct_fs === null ? "—" : `${row.selective_mae_pct_fs.toFixed(2)}%`}</span><span>{row.false_accept_rate_over_5pct_fs === null ? "—" : `${(row.false_accept_rate_over_5pct_fs * 100).toFixed(1)}%`}</span></div>)}</div><p className="footnote">The curve varies only the two-estimator disagreement cap. Quality and calibration-range gates remain fixed.</p></div>
        <div className="panel eval-panel"><div className="panel-header"><div><span className="step-number">B</span><h2>Failure by condition</h2></div></div><div className="condition-table">{Object.entries(benchmark.failure_rate_by_condition ?? {}).map(([condition, values]) => <div className="condition-row" key={condition}><div><strong>{condition}</strong><span>{values.sample_count} samples</span></div><div className="condition-bar"><i style={{ width: `${Math.max(2, values.agent_abstention_rate * 100)}%` }} /></div><strong>{(values.agent_abstention_rate * 100).toFixed(0)}%<small> abstained</small></strong></div>)}</div><p className="footnote">A high abstention rate can be appropriate when image evidence is poor.</p></div></div>
      <div className="limitations-note"><Icon name="info" size={17} /><p><strong>Scope of this result.</strong> Synthetic dials test code behavior and policy plumbing only. Qyvoriq has not been evaluated on SyncG or a real-gauge dataset in this workspace. Do not generalize these values to factories or field use.</p></div>
    </>}
  </section>;
}

export default App;
