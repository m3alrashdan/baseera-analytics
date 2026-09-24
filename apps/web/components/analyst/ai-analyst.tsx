"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  Database,
  FileSpreadsheet,
  FlaskConical,
  LoaderCircle,
  MessageSquare,
  Play,
  ShieldCheck,
  Sparkles,
  Upload,
  Users,
} from "lucide-react";
import type { Locale } from "@/lib/contracts";
import {
  ACTIVE,
  analystApi,
  loc,
  mergeRun,
  type AgentRun,
  type Dossier,
  type SampleInfo,
  type TeamInfo,
  type WorkspaceDataset,
} from "@/lib/analyst";
import { resourceStatusFromError } from "@/lib/api";
import { ResourceState } from "../resource-state";
import { AskTheTeam } from "./ask";
import { DossierView } from "./dossier";
import { LiveRun } from "./live-run";
import { AgentAvatar } from "./team";

type Tab = "analysis" | "ask" | "team";

export function AIAnalystWorkspace({
  locale,
  initialTab,
}: {
  locale: Locale;
  initialTab?: string;
}) {
  const ar = locale === "ar";
  const [team, setTeam] = useState<TeamInfo | null>(null);
  const [datasets, setDatasets] = useState<WorkspaceDataset[] | null>(null);
  const [samples, setSamples] = useState<SampleInfo[]>([]);
  const [datasetId, setDatasetId] = useState<string>("");
  const [versionId, setVersionId] = useState<string>("");
  const [tab, setTab] = useState<Tab>(
    initialTab === "ask" ? "ask" : initialTab === "team" ? "team" : "analysis",
  );
  const [run, setRun] = useState<AgentRun | null>(null);
  const [loadingRun, setLoadingRun] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState("");
  const [seed, setSeed] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    // The sidebar links "analyst" and "analyst/ask" reuse this component.
    setTab(
      initialTab === "ask"
        ? "ask"
        : initialTab === "team"
          ? "team"
          : "analysis",
    );
  }, [initialTab]);

  const refresh = useCallback(async (select?: string) => {
    const workspace = await analystApi.workspace();
    setDatasets(workspace.items);
    if (select) setDatasetId(select);
    else setDatasetId((current) => current || workspace.items[0]?.id || "");
    return workspace.items;
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      analystApi.team(controller.signal),
      refresh(),
      analystApi.samples(),
    ])
      .then(([info, , sampleList]) => {
        setTeam(info);
        setSamples(sampleList.items);
      })
      .catch((cause) => {
        if (!controller.signal.aborted) setError(cause);
      });
    return () => controller.abort();
  }, [refresh]);

  const dataset = datasets?.find((item) => item.id === datasetId);

  useEffect(() => {
    if (!dataset) return;
    setVersionId(dataset.latest_version_id);
  }, [dataset?.id, dataset?.latest_version_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load the latest full analysis for the selected version.
  useEffect(() => {
    if (!versionId) return;
    let cancelled = false;
    setRun(null);
    setLoadingRun(true);
    analystApi
      .runs({ dataset_version_id: versionId, mode: "autopilot", limit: "1" })
      .then(async (list) => {
        const latest = list.items[0];
        if (!latest || cancelled) return;
        const full = await analystApi.run(latest.id);
        if (!cancelled) setRun(full);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoadingRun(false);
      });
    return () => {
      cancelled = true;
    };
  }, [versionId]);

  const active = run ? ACTIVE.includes(run.status) : false;
  useEffect(() => {
    if (!run || !active) return;
    let stopped = false;
    const timer = window.setTimeout(async () => {
      try {
        const since = run.events.length;
        const next = await analystApi.run(run.id, since);
        if (stopped) return;
        setRun((current) => mergeRun(current, next, since));
        if (!ACTIVE.includes(next.status)) void refresh();
      } catch {
        if (!stopped) setRun((current) => (current ? { ...current } : current));
      }
    }, 900);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [run, active, refresh]);

  async function startAnalysis() {
    if (!versionId) return;
    setBusy("run");
    setNotice("");
    try {
      setTab("analysis");
      setRun(
        await analystApi.startRun({
          dataset_version_id: versionId,
          mode: "autopilot",
          locale,
        }),
      );
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(null);
    }
  }

  async function cancel() {
    if (!run) return;
    try {
      const next = await analystApi.cancel(run.id);
      setRun((current) =>
        current ? { ...current, status: next.status } : current,
      );
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : String(cause));
    }
  }

  async function loadSample(id: string) {
    setBusy(`sample-${id}`);
    setNotice("");
    try {
      const created = await analystApi.loadSample(id, locale);
      await refresh(created.dataset.id);
      setTab("analysis");
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(null);
    }
  }

  async function upload(file: File) {
    setBusy("upload");
    setNotice("");
    try {
      const created = await analystApi.upload(file);
      await refresh(created.dataset.id);
      setTab("analysis");
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(null);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  if (error)
    return (
      <ResourceState
        locale={locale}
        status={resourceStatusFromError(error)}
        reason={error instanceof Error ? error.message : undefined}
      />
    );
  if (!team || !datasets)
    return <ResourceState locale={locale} status="loading" />;

  const members = team.team;
  const engine = team.engine;
  const dossier =
    run?.status === "completed" && run.mode === "autopilot"
      ? (run.result as Dossier)
      : null;
  const version = dataset?.versions.find((item) => item.id === versionId);
  const compactHero = datasets.length > 0;

  return (
    <div className="stack-page ai-analyst">
      <header className={`ai-hero${compactHero ? " ai-hero--compact" : ""}`}>
        <div className="ai-hero__text">
          <p className="eyebrow">
            <Sparkles size={14} aria-hidden="true" />{" "}
            {ar ? "فريق بصيرة للمحللين الأذكياء" : "BASEERA AI analyst team"}
          </p>
          <h1>
            {ar
              ? "فريق تحليل بيانات كامل، يعمل لحسابك"
              : "A complete data-analysis team, working for you"}
          </h1>
          {!compactHero ? (
            <p>
              {ar
                ? "تسعة وكلاء متخصصين يفهمون بياناتك ويدققونها ويحللونها ويتنبؤون بها ويفسرون أسباب تغيرها، ثم يقدمون توصيات مرتبة ومحددة الأثر مع دليل لكل رقم."
                : "Nine specialist agents understand, audit, analyse and forecast your data, explain why it moved, then deliver prioritised, sized recommendations with evidence behind every number."}
            </p>
          ) : null}
          <div className="ai-hero__meta">
            <span
              className={`pill ${engine.provider === "deterministic" ? "" : "pill--teal"}`}
            >
              <Bot size={14} aria-hidden="true" />
              {engine.provider === "anthropic"
                ? `Claude · ${engine.model}`
                : engine.provider === "ollama"
                  ? `${ar ? "نموذج محلي" : "Local model"} · ${engine.model}`
                  : ar
                    ? "المحرك الخبير المدمج"
                    : "Built-in expert engine"}
            </span>
            <span className="pill pill--green">
              <ShieldCheck size={14} aria-hidden="true" />
              {ar
                ? "الصفوف الخام لا تغادر الخادم"
                : "Raw rows never leave the server"}
            </span>
          </div>
        </div>
        <ul className="ai-hero__team" aria-label={ar ? "الفريق" : "The team"}>
          {members.map((member) => (
            <li
              key={member.id}
              title={`${loc(member.name, locale)} — ${loc(member.role, locale)}`}
            >
              <AgentAvatar member={member} size={compactHero ? 32 : 40} />
              <span className={compactHero ? "sr-only" : undefined}>
                {loc(member.name, locale)}
              </span>
            </li>
          ))}
        </ul>
      </header>

      <div className="ai-layout">
        <aside
          className="dataset-rail"
          aria-label={ar ? "البيانات" : "Datasets"}
        >
          <div className="dataset-rail__head">
            <h2>{ar ? "بياناتك" : "Your data"}</h2>
            <button
              type="button"
              className="button button--secondary button--small"
              onClick={() => fileInput.current?.click()}
              disabled={busy === "upload"}
            >
              {busy === "upload" ? (
                <LoaderCircle size={14} className="spin" aria-hidden="true" />
              ) : (
                <Upload size={14} aria-hidden="true" />
              )}
              {ar ? "رفع ملف" : "Upload"}
            </button>
            <input
              ref={fileInput}
              type="file"
              hidden
              accept=".csv,.tsv,.xlsx,.json,.jsonl,.parquet"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void upload(file);
              }}
            />
          </div>
          {datasets.length ? (
            <ul className="dataset-list">
              {datasets.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={item.id === datasetId ? "active" : undefined}
                    aria-current={item.id === datasetId ? "true" : undefined}
                    onClick={() => setDatasetId(item.id)}
                  >
                    <FileSpreadsheet size={16} aria-hidden="true" />
                    <span>
                      <strong>{item.name}</strong>
                      <small>
                        {(item.versions[0]?.row_count ?? 0).toLocaleString(
                          ar ? "ar-JO" : "en-US",
                        )}{" "}
                        {ar ? "سجل" : "rows"} ·{" "}
                        {item.last_analysis
                          ? item.last_analysis.status === "completed"
                            ? ar
                              ? "حُلِّلت"
                              : "Analysed"
                            : item.last_analysis.status
                          : ar
                            ? "لم تُحلَّل بعد"
                            : "Not analysed yet"}
                      </small>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted small">
              {ar ? "لا توجد بيانات بعد." : "No datasets yet."}
            </p>
          )}
          <div className="sample-box">
            <h3>
              <FlaskConical size={15} aria-hidden="true" />{" "}
              {ar ? "جرّب ببيانات نموذجية" : "Try with sample data"}
            </h3>
            {samples.map((sample) => (
              <button
                key={sample.id}
                type="button"
                className="sample-card"
                disabled={busy === `sample-${sample.id}`}
                onClick={() => void loadSample(sample.id)}
              >
                <strong>{loc(sample.title, locale)}</strong>
                <small>{loc(sample.description, locale)}</small>
              </button>
            ))}
          </div>
        </aside>

        <section className="ai-main">
          {notice ? (
            <p className="truth-banner" role="alert">
              {notice}
            </p>
          ) : null}
          {!dataset ? (
            <div className="ai-empty">
              <Database size={40} aria-hidden="true" />
              <h2>
                {ar
                  ? "ابدأ برفع ملف أو بتجربة بيانات نموذجية"
                  : "Start by uploading a file or trying a sample"}
              </h2>
              <p className="muted">
                {ar
                  ? "CSV أو Excel أو JSON أو Parquet — مبيعات، عملاء، موارد بشرية، عمليات، مالية... الفريق يفهم أي جدول بيانات."
                  : "CSV, Excel, JSON or Parquet — sales, customers, HR, operations, finance… the team reads any table."}
              </p>
            </div>
          ) : (
            <>
              <div className="ai-main__head">
                <div>
                  <h2>{dataset.name}</h2>
                  <p className="muted small">
                    {dataset.filename} ·{" "}
                    {(version?.row_count ?? 0).toLocaleString(
                      ar ? "ar-JO" : "en-US",
                    )}{" "}
                    {ar ? "سجل" : "rows"} · {version?.columns ?? 0}{" "}
                    {ar ? "عمود" : "columns"}
                  </p>
                </div>
                {dataset.versions.length > 1 ? (
                  <label className="version-select">
                    <span>{ar ? "الإصدار" : "Version"}</span>
                    <select
                      value={versionId}
                      onChange={(event) => setVersionId(event.target.value)}
                    >
                      {dataset.versions.map((item) => (
                        <option key={item.id} value={item.id}>
                          v{item.version_number} · {item.kind} ·{" "}
                          {item.row_count.toLocaleString()}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
              </div>
              <div
                className="tabs"
                role="tablist"
                aria-label={ar ? "مساحات العمل" : "Workspaces"}
              >
                {(
                  [
                    [
                      "analysis",
                      ar ? "التحليل الشامل" : "Full analysis",
                      Sparkles,
                    ],
                    ["ask", ar ? "اسأل الفريق" : "Ask the team", MessageSquare],
                    ["team", ar ? "الفريق والمنهجية" : "Team & method", Users],
                  ] as const
                ).map(([id, label, Icon]) => (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    aria-selected={tab === id}
                    className={tab === id ? "active" : undefined}
                    onClick={() => setTab(id)}
                  >
                    <Icon size={15} aria-hidden="true" />
                    {label}
                  </button>
                ))}
              </div>

              {tab === "analysis" ? (
                loadingRun ? (
                  <ResourceState locale={locale} status="loading" compact />
                ) : run &&
                  (active || run.status !== "completed") &&
                  run.mode === "autopilot" ? (
                  <>
                    <LiveRun
                      run={run}
                      team={members}
                      locale={locale}
                      onCancel={cancel}
                    />
                    {!active ? (
                      <button
                        type="button"
                        className="button button--primary"
                        onClick={() => void startAnalysis()}
                      >
                        <Play size={16} aria-hidden="true" />
                        {ar
                          ? "شغّل التحليل مرة أخرى"
                          : "Run the analysis again"}
                      </button>
                    ) : null}
                  </>
                ) : dossier && run ? (
                  <DossierView
                    dossier={dossier}
                    runId={run.id}
                    locale={locale}
                    team={members}
                    onRerun={() => void startAnalysis()}
                    onAsk={(question) => {
                      setSeed(question);
                      setTab("ask");
                    }}
                  />
                ) : (
                  <div className="launch-card">
                    <div>
                      <h3>
                        {ar
                          ? "كلّف الفريق بتحليل شامل"
                          : "Commission a full analysis"}
                      </h3>
                      <p>
                        {ar
                          ? "سيفهم الفريق بنية البيانات، ويدقق الجودة، ويقيس الأداء والاتجاهات، ويتنبأ، ويفسر أسباب التغيّر، ويكتشف العوامل المؤثرة والشرائح والحالات الشاذة، ثم يكتب تقريرًا تنفيذيًا بتوصيات مرتبة. يستغرق عادة أقل من دقيقة."
                          : "The team will read the schema, audit quality, measure performance and trends, forecast, explain what changed and why, find drivers, segments and anomalies, then write an executive dossier with prioritised recommendations. Usually under a minute."}
                      </p>
                      <ol className="launch-steps">
                        {members.slice(1).map((member) => (
                          <li key={member.id}>
                            <AgentAvatar member={member} size={24} />
                            <span>
                              <b>{loc(member.name, locale)}</b> —{" "}
                              {loc(member.role, locale)}
                            </span>
                          </li>
                        ))}
                      </ol>
                    </div>
                    <button
                      type="button"
                      className="button button--primary button--large"
                      onClick={() => void startAnalysis()}
                      disabled={busy === "run"}
                    >
                      {busy === "run" ? (
                        <LoaderCircle
                          size={18}
                          className="spin"
                          aria-hidden="true"
                        />
                      ) : (
                        <Play size={18} aria-hidden="true" />
                      )}
                      {ar ? "ابدأ التحليل الشامل" : "Start the full analysis"}
                    </button>
                  </div>
                )
              ) : null}

              {tab === "ask" && versionId ? (
                <AskTheTeam
                  versionId={versionId}
                  locale={locale}
                  team={members}
                  seed={seed}
                  onSeedConsumed={() => setSeed(null)}
                />
              ) : null}

              {tab === "team" ? (
                <TeamPanel team={team} locale={locale} />
              ) : null}
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function TeamPanel({ team, locale }: { team: TeamInfo; locale: Locale }) {
  const ar = locale === "ar";
  const tools = (agent: string) =>
    team.tools.filter((tool) => tool.agent === agent);
  return (
    <div className="team-panel">
      <section className="principles">
        {team.principles.map((principle, index) => (
          <div key={index}>
            <ShieldCheck aria-hidden="true" />
            <p>{loc(principle, locale)}</p>
          </div>
        ))}
      </section>
      <ul className="team-roster">
        {team.team.map((member) => (
          <li key={member.id} className="roster-card">
            <AgentAvatar member={member} size={44} />
            <div>
              <h3>{loc(member.name, locale)}</h3>
              <p>{loc(member.role, locale)}</p>
              {tools(member.id).length ? (
                <p className="roster-card__tools">
                  {tools(member.id).map((tool) => (
                    <span key={tool.name} className="chip chip--muted">
                      {loc(tool.title, locale)}
                    </span>
                  ))}
                </p>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      <section className="engine-box">
        <h3>{ar ? "محرك الذكاء الاصطناعي" : "AI engine"}</h3>
        <p>
          {team.engine.provider === "deterministic"
            ? loc(team.engine.description, locale)
            : ar
              ? `المحرك النشط: ${team.engine.provider} · ${team.engine.model}. يخطط النموذج ويختار الأدوات ويكتب، بينما تحسب الأدوات الحتمية كل رقم.`
              : `Active engine: ${team.engine.provider} · ${team.engine.model}. The model plans, chooses tools and writes; deterministic tools compute every number.`}
        </p>
      </section>
    </div>
  );
}
