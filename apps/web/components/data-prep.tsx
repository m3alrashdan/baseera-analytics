"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  ChevronRight,
  FileSpreadsheet,
  Layers,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trash2,
  Wand2,
  X,
} from "lucide-react";
import type { Locale } from "@/lib/contracts";
import { apiRequest, postJson, resourceStatusFromError } from "@/lib/api";
import { num } from "@/lib/viz";
import { Chart } from "./chart";
import { radarOption, rankedBarOption } from "@/lib/chart-options";
import { ResourceState } from "./resource-state";
import { UploadStudio } from "./upload-studio";
import { uploadDataset } from "@/lib/api";

type Json = Record<string, any>;
const w = (locale: Locale, en: string, ar: string) =>
  locale === "ar" ? ar : en;

// ---------------------------------------------------------------------------------
// Types mirroring the cleaning API
// ---------------------------------------------------------------------------------

interface StepOption {
  name: string;
  type: "choice" | "text" | "integer" | "number" | "boolean" | "mapping";
  choices?: string[];
  default?: unknown;
  required?: boolean;
  min?: number;
  max?: number;
}

interface CatalogEntry {
  kind: string;
  scope: "cells" | "rows" | "schema";
  reversible: boolean;
  label: Record<Locale, string>;
  detail: Record<Locale, string>;
  options: StepOption[];
}

interface RecipeStep {
  kind: string;
  columns: string[];
  [key: string]: unknown;
}

const SCOPE_TONE: Record<string, string> = {
  cells: "chip--teal",
  rows: "chip--amber",
  schema: "chip--red",
};

const TYPE_LABEL: Record<string, [string, string]> = {
  identifier: ["Identifier", "معرّف"],
  number: ["Number", "رقم"],
  number_text: ["Number stored as text", "رقم مخزّن كنص"],
  date: ["Date", "تاريخ"],
  boolean: ["True/false", "صح/خطأ"],
  categorical: ["Category", "فئة"],
  email: ["Email", "بريد"],
  phone: ["Phone", "هاتف"],
  text: ["Text", "نص"],
  empty: ["Empty", "فارغ"],
};

const GRADE_TONE: Record<string, string> = {
  ready: "grade--good",
  usable_with_caveats: "grade--warn",
  repair_required: "grade--serious",
  not_fit_for_reporting: "grade--critical",
};

const GRADE_LABEL: Record<string, [string, string]> = {
  ready: ["Ready for reporting", "جاهزة للتقارير"],
  usable_with_caveats: ["Usable with caveats", "قابلة للاستخدام مع تحفظات"],
  repair_required: ["Repair required", "تحتاج إصلاحًا"],
  not_fit_for_reporting: ["Not fit for reporting", "غير صالحة للتقارير"],
  not_assessable: ["Not assessable", "غير قابلة للتقييم"],
};

const DIMENSION_LABEL: Record<Locale, Record<string, string>> = {
  en: {
    completeness: "Completeness",
    uniqueness: "Uniqueness",
    validity: "Validity",
    consistency: "Consistency",
    plausibility: "Plausibility",
  },
  ar: {
    completeness: "الاكتمال",
    uniqueness: "التفرّد",
    validity: "الصلاحية",
    consistency: "الاتساق",
    plausibility: "المعقولية",
  },
};

// ---------------------------------------------------------------------------------

export function DataPrepWorkspace({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const [datasets, setDatasets] = useState<Json[] | null>(null);
  const [versions, setVersions] = useState<Json[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [profile, setProfile] = useState<Json | null>(null);
  const [rows, setRows] = useState<Json | null>(null);
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
  const [suggested, setSuggested] = useState<Json[]>([]);
  const [recipe, setRecipe] = useState<RecipeStep[]>([]);
  const [preview, setPreview] = useState<Json | null>(null);
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);

  const version = versions.find((item) => item.id === versionId);
  const columns: string[] = version?.columns ?? profile?.columns ?? [];

  const loadDatasets = useCallback(async () => {
    try {
      const list = await apiRequest<{ items: Json[] }>("/api/v1/datasets");
      setDatasets(list.items);
      if (list.items.length && !datasetId) setDatasetId(list.items[0].id);
    } catch (cause) {
      setError(cause);
      setDatasets([]);
    }
  }, [datasetId]);

  useEffect(() => {
    void loadDatasets();
    apiRequest<{ items: CatalogEntry[] }>("/api/v1/cleaning/steps")
      .then((value) => setCatalog(value.items))
      .catch(() => setCatalog([]));
  }, [loadDatasets]);

  useEffect(() => {
    if (!datasetId) return;
    setVersions([]);
    setVersionId("");
    apiRequest<{ items: Json[] }>(
      `/api/v1/datasets/${encodeURIComponent(datasetId)}/versions`,
    )
      .then((value) => {
        setVersions(value.items);
        const latest = value.items[value.items.length - 1];
        if (latest) setVersionId(latest.id);
      })
      .catch(setError);
  }, [datasetId]);

  const inspect = useCallback(async (id: string) => {
    if (!id) return;
    setBusy("inspect");
    setError(null);
    setPreview(null);
    setRecipe([]);
    setApproved(false);
    try {
      const [profileValue, rowsValue, suggestValue] = await Promise.all([
        apiRequest<Json>(
          `/api/v1/dataset-versions/${encodeURIComponent(id)}/profile`,
        ),
        apiRequest<Json>(
          `/api/v1/dataset-versions/${encodeURIComponent(id)}/rows?limit=25`,
        ),
        postJson<Json>(
          `/api/v1/dataset-versions/${encodeURIComponent(id)}/cleaning/suggest`,
          {},
        ),
      ]);
      setProfile(profileValue);
      setRows(rowsValue);
      setSuggested(suggestValue.recommended_steps ?? []);
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(null);
    }
  }, []);

  useEffect(() => {
    if (versionId) void inspect(versionId);
  }, [versionId, inspect]);

  async function runPreview(next = recipe) {
    if (!next.length) {
      setPreview(null);
      return;
    }
    setBusy("preview");
    setError(null);
    setApproved(false);
    try {
      setPreview(
        await postJson<Json>(
          `/api/v1/dataset-versions/${encodeURIComponent(versionId)}/cleaning/preview`,
          { steps: next },
        ),
      );
    } catch (cause) {
      setError(cause);
      setPreview(null);
    } finally {
      setBusy(null);
    }
  }

  async function apply() {
    setBusy("apply");
    setError(null);
    try {
      const result = await postJson<Json>(
        `/api/v1/dataset-versions/${encodeURIComponent(versionId)}/cleaning/apply`,
        {
          steps: recipe,
          expected_version: version?.version_number ?? 1,
          approved,
        },
      );
      setNotice(
        w(
          locale,
          `Version ${result.version.version_number} was published. The source version is unchanged.`,
          `نُشر الإصدار ${result.version.version_number}. الإصدار المصدر لم يتغيّر.`,
        ),
      );
      setRecipe([]);
      setPreview(null);
      setApproved(false);
      const list = await apiRequest<{ items: Json[] }>(
        `/api/v1/datasets/${encodeURIComponent(datasetId)}/versions`,
      );
      setVersions(list.items);
      setVersionId(result.version.id);
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(null);
    }
  }

  function addStep(step: RecipeStep) {
    const next = [...recipe, step];
    setRecipe(next);
    void runPreview(next);
  }

  function updateStep(index: number, patch: Partial<RecipeStep>) {
    const next = recipe.map((step, position) =>
      position === index ? { ...step, ...patch } : step,
    );
    setRecipe(next);
    void runPreview(next);
  }

  function removeStep(index: number) {
    const next = recipe.filter((_, position) => position !== index);
    setRecipe(next);
    void runPreview(next);
  }

  function moveStep(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= recipe.length) return;
    const next = [...recipe];
    [next[index], next[target]] = [next[target], next[index]];
    setRecipe(next);
    void runPreview(next);
  }

  const quality = profile?.quality as Json | undefined;

  return (
    <div className="prep">
      <header className="prep__head">
        <div>
          <p className="eyebrow">
            {w(locale, "Data preparation", "إعداد البيانات")}
          </p>
          <h1>
            {w(locale, "Review, repair, then publish", "افحص وأصلح ثم انشر")}
          </h1>
          <p>
            {w(
              locale,
              "Nothing is changed in place. Repairs are previewed against control totals and published as a new immutable version.",
              "لا يُعدَّل شيء في مكانه. تُعاين الإصلاحات مقابل المجاميع الرقابية وتُنشر كإصدار جديد غير قابل للتعديل.",
            )}
          </p>
        </div>
        <div className="prep__head-actions">
          <button
            type="button"
            className="button button--secondary"
            onClick={() => setUploadOpen((value) => !value)}
          >
            <Plus size={16} />
            {w(locale, "Add data", "أضف بيانات")}
          </button>
          <button
            type="button"
            className="button button--ghost"
            onClick={() => void inspect(versionId)}
            disabled={!versionId || busy !== null}
          >
            <RefreshCw size={16} />
            {w(locale, "Refresh", "تحديث")}
          </button>
        </div>
      </header>

      {uploadOpen && (
        <UploadStudio
          locale={locale}
          upload={async (file: File) => {
            const result = await uploadDataset(file);
            void loadDatasets();
            setDatasetId(result.dataset_id);
            setUploadOpen(false);
            return result;
          }}
        />
      )}

      <section className="prep__picker">
        <label>
          <span>{w(locale, "Dataset", "مجموعة البيانات")}</span>
          <select
            value={datasetId}
            onChange={(event) => setDatasetId(event.target.value)}
          >
            {(datasets ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{w(locale, "Version", "الإصدار")}</span>
          <select
            value={versionId}
            onChange={(event) => setVersionId(event.target.value)}
          >
            {versions.map((item) => (
              <option key={item.id} value={item.id}>
                {w(locale, "Version", "إصدار")} {item.version_number} ·{" "}
                {item.kind === "raw"
                  ? w(locale, "as received", "كما وردت")
                  : w(locale, "cleaned", "منظّفة")}{" "}
                · {num(item.row_count, locale)} {w(locale, "rows", "صف")}
              </option>
            ))}
          </select>
        </label>
        {datasets?.length === 0 && (
          <p className="prep__empty">
            <FileSpreadsheet size={16} />
            {w(
              locale,
              "No dataset yet. Add a file to begin.",
              "لا توجد بيانات بعد. أضف ملفًا للبدء.",
            )}
          </p>
        )}
      </section>

      {error != null && (
        <ResourceState
          locale={locale}
          status={resourceStatusFromError(error)}
          reason={describe(error, locale)}
          compact
        />
      )}
      {notice && (
        <p className="success-message" role="status">
          <CheckCircle2 size={17} />
          {notice}
        </p>
      )}

      {busy === "inspect" && !profile && (
        <ResourceState locale={locale} status="loading" />
      )}

      {profile && (
        <>
          <QualityBanner locale={locale} quality={quality} profile={profile} />

          <div className="prep__grid">
            <div className="prep__main">
              <ColumnProfiles
                locale={locale}
                profile={profile}
                onFix={(step) => addStep(step)}
              />
              <DataPreview locale={locale} rows={rows} profile={profile} />
            </div>

            <aside className="prep__side">
              <RecipeBuilder
                locale={locale}
                catalog={catalog}
                columns={columns}
                recipe={recipe}
                suggested={suggested}
                busy={busy}
                onAdd={addStep}
                onUpdate={updateStep}
                onRemove={removeStep}
                onMove={moveStep}
                onApplyAll={() => {
                  const next = suggested.map((item) => item.step as RecipeStep);
                  setRecipe(next);
                  void runPreview(next);
                }}
              />
            </aside>
          </div>

          {preview && (
            <ReviewPanel
              locale={locale}
              preview={preview}
              approved={approved}
              busy={busy === "apply"}
              onApprove={setApproved}
              onApply={apply}
            />
          )}
        </>
      )}
    </div>
  );
}

function describe(error: unknown, locale: Locale): string {
  if (error && typeof error === "object" && "problem" in error) {
    const problem = (error as { problem: Json }).problem;
    const details = problem?.details ?? {};
    const available = details.available_columns as string[] | undefined;
    return [
      problem?.detail ?? problem?.title ?? String(error),
      available?.length
        ? w(locale, "Available columns: ", "الأعمدة المتاحة: ") +
          available.join(", ")
        : "",
    ]
      .filter(Boolean)
      .join(" — ");
  }
  return error instanceof Error ? error.message : String(error);
}

// ---------------------------------------------------------------------------------

function QualityBanner({
  locale,
  quality,
  profile,
}: {
  locale: Locale;
  quality: Json | undefined;
  profile: Json;
}) {
  const ar = locale === "ar";
  if (!quality?.score && quality?.score !== 0) return null;
  const grade = String(quality.grade ?? "not_assessable");
  const counts = (quality.counts ?? {}) as Json;
  const dimensions = (quality.dimensions ?? {}) as Record<string, number>;
  const tiles: Array<[string, string]> = [
    [w(locale, "Rows", "الصفوف"), num(profile.row_count, locale)],
    [w(locale, "Columns", "الأعمدة"), num(profile.column_count, locale)],
    [
      w(locale, "Empty cells", "خلايا فارغة"),
      num(counts.missing_cells ?? 0, locale),
    ],
    [
      w(locale, "Unreadable cells", "خلايا غير مقروءة"),
      num(counts.invalid_cells ?? 0, locale),
    ],
    [
      w(locale, "Duplicate rows", "صفوف مكررة"),
      num(counts.duplicate_rows ?? 0, locale),
    ],
  ];
  return (
    <section className={`quality-banner ${GRADE_TONE[grade] ?? "grade--warn"}`}>
      <div className="quality-banner__score">
        <strong>{num(quality.score, locale)}</strong>
        <span>/ 100</span>
        <em>{(GRADE_LABEL[grade] ?? ["", ""])[ar ? 1 : 0]}</em>
      </div>
      <div className="quality-banner__tiles">
        {tiles.map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <b>{value}</b>
          </div>
        ))}
      </div>
      {Object.keys(dimensions).length > 0 && (
        <div className="quality-banner__radar">
          <Chart
            locale={locale}
            height={190}
            option={radarOption(locale, dimensions, DIMENSION_LABEL[locale])}
            table={{
              columns: [
                { key: "dimension", label: w(locale, "Dimension", "البُعد") },
                {
                  key: "score",
                  label: w(locale, "Score", "الدرجة"),
                  numeric: true,
                },
              ],
              rows: Object.entries(dimensions).map(([key, value]) => ({
                dimension: DIMENSION_LABEL[locale][key] ?? key,
                score: Math.round(value * 1000) / 10,
              })),
            }}
          />
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------------

function ColumnProfiles({
  locale,
  profile,
  onFix,
}: {
  locale: Locale;
  profile: Json;
  onFix: (step: RecipeStep) => void;
}) {
  const ar = locale === "ar";
  const [open, setOpen] = useState<string | null>(null);
  const entries = Object.entries(
    (profile.column_profiles ?? {}) as Record<string, Json>,
  );
  const suggestionsByColumn = useMemo(() => {
    const map = new Map<string, Json[]>();
    for (const item of (profile.recommended_steps ?? []) as Json[]) {
      for (const column of (item.step?.columns ?? []) as string[]) {
        map.set(column, [...(map.get(column) ?? []), item]);
      }
    }
    return map;
  }, [profile]);

  return (
    <section className="panel prep__columns">
      <header className="panel-heading">
        <div>
          <h2>{w(locale, "Columns", "الأعمدة")}</h2>
          <p>
            {w(
              locale,
              "What each column actually holds, and what is wrong with it.",
              "ما يحتويه كل عمود فعليًا وما الخلل فيه.",
            )}
          </p>
        </div>
      </header>
      <ul className="column-list">
        {entries.map(([name, column]) => {
          const issues = columnIssues(column, locale);
          const fixes = suggestionsByColumn.get(name) ?? [];
          const expanded = open === name;
          return (
            <li key={name} className={expanded ? "is-open" : undefined}>
              <button
                type="button"
                className="column-list__row"
                onClick={() => setOpen(expanded ? null : name)}
                aria-expanded={expanded}
              >
                <ChevronRight className="column-list__caret" size={15} />
                <span className="column-list__name" dir="ltr">
                  {name}
                </span>
                <span className="chip chip--quiet">
                  {(TYPE_LABEL[column.semantic_type] ?? ["", ""])[ar ? 1 : 0] ||
                    column.semantic_type}
                </span>
                <span className="column-list__bar" aria-hidden="true">
                  <i
                    style={{
                      inlineSize: `${Math.round((1 - (column.missing_rate ?? 0)) * 100)}%`,
                    }}
                  />
                </span>
                <span className="column-list__meta">
                  {num(column.distinct_count, locale)}{" "}
                  {w(locale, "distinct", "مميزة")}
                </span>
                {issues.length > 0 && (
                  <span className="chip chip--amber">
                    <AlertTriangle size={12} />
                    {issues.length}
                  </span>
                )}
              </button>
              {expanded && (
                <div className="column-detail">
                  {issues.length > 0 && (
                    <ul className="column-detail__issues">
                      {issues.map((issue) => (
                        <li key={issue}>{issue}</li>
                      ))}
                    </ul>
                  )}
                  {column.numeric && (
                    <dl className="column-detail__stats">
                      {(
                        [
                          ["min", w(locale, "Minimum", "الأدنى")],
                          ["median", w(locale, "Median", "الوسيط")],
                          ["mean", w(locale, "Mean", "المتوسط")],
                          ["max", w(locale, "Maximum", "الأعلى")],
                          ["std_dev", w(locale, "Spread", "الانتشار")],
                          ["sum", w(locale, "Total", "المجموع")],
                        ] as const
                      ).map(([key, label]) => (
                        <div key={key}>
                          <dt>{label}</dt>
                          <dd>{num(column.numeric[key], locale)}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                  {Array.isArray(column.top_values) &&
                    column.top_values.length > 1 && (
                      <Chart
                        locale={locale}
                        height={Math.min(
                          230,
                          34 + column.top_values.length * 24,
                        )}
                        title={w(
                          locale,
                          "Most frequent values",
                          "أكثر القيم تكرارًا",
                        )}
                        option={rankedBarOption(
                          locale,
                          column.top_values.slice(0, 8).map((item: Json) => ({
                            label: String(item.value),
                            value: item.count,
                          })),
                          { unit: w(locale, "rows", "صفوف") },
                        )}
                        table={{
                          columns: [
                            {
                              key: "value",
                              label: w(locale, "Value", "القيمة"),
                            },
                            {
                              key: "count",
                              label: w(locale, "Rows", "الصفوف"),
                              numeric: true,
                            },
                            {
                              key: "share",
                              label: w(locale, "Share", "الحصة"),
                            },
                          ],
                          rows: column.top_values.map((item: Json) => ({
                            value: String(item.value),
                            count: item.count,
                            share: `${Math.round(item.share * 1000) / 10}%`,
                          })),
                        }}
                      />
                    )}
                  {fixes.length > 0 && (
                    <div className="column-detail__fixes">
                      <span>
                        {w(locale, "Suggested repairs", "إصلاحات مقترحة")}
                      </span>
                      {fixes.map((fix, index) => (
                        <button
                          key={index}
                          type="button"
                          className="chip-button chip-button--accent"
                          onClick={() => onFix(fix.step as RecipeStep)}
                        >
                          <Wand2 size={13} />
                          {fix.step.kind.replace(/_/g, " ")}
                          {fix.requires_human_decision && (
                            <AlertTriangle size={12} />
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function columnIssues(column: Json, locale: Locale): string[] {
  const issues: string[] = [];
  const text = column.text ?? {};
  const parse = column.numeric_parse ?? {};
  const temporal = column.temporal ?? {};
  if (column.null_count)
    issues.push(
      w(
        locale,
        `${column.null_count} empty cells (${Math.round((column.missing_rate ?? 0) * 100)}%)`,
        `${column.null_count} خلية فارغة (${Math.round((column.missing_rate ?? 0) * 100)}%)`,
      ),
    );
  if (column.semantic_type === "number_text")
    issues.push(
      w(
        locale,
        `Numbers stored as text; ${parse.unparsable ?? 0} cells cannot be read at all`,
        `أرقام مخزّنة كنص؛ ${parse.unparsable ?? 0} خلية لا تُقرأ إطلاقًا`,
      ),
    );
  if (text.case_variant_groups)
    issues.push(
      w(
        locale,
        `${text.case_variant_groups} values differ only by letter case`,
        `${text.case_variant_groups} قيمة تختلف في حالة الأحرف فقط`,
      ),
    );
  if (text.untrimmed_count)
    issues.push(
      w(
        locale,
        `${text.untrimmed_count} cells carry stray leading or trailing characters`,
        `${text.untrimmed_count} خلية تحمل محارف طرفية زائدة`,
      ),
    );
  if (temporal.mixed_formats)
    issues.push(
      w(
        locale,
        `Dates are written in ${Object.keys(temporal.formats_found ?? {}).length} different formats`,
        `التواريخ مكتوبة بـ${Object.keys(temporal.formats_found ?? {}).length} أنماط مختلفة`,
      ),
    );
  if (temporal.ambiguous_cells)
    issues.push(
      w(
        locale,
        `${temporal.ambiguous_cells} dates could be read as either day/month or month/day`,
        `${temporal.ambiguous_cells} تاريخًا يحتمل قراءتين: يوم/شهر أو شهر/يوم`,
      ),
    );
  if (column.is_constant)
    issues.push(
      w(
        locale,
        "Every row holds the same value",
        "كل الصفوف تحمل القيمة نفسها",
      ),
    );
  if (column.numeric?.outlier_count)
    issues.push(
      w(
        locale,
        `${column.numeric.outlier_count} values sit far outside the usual range`,
        `${column.numeric.outlier_count} قيمة تقع بعيدًا خارج النطاق المعتاد`,
      ),
    );
  return issues;
}

// ---------------------------------------------------------------------------------

function DataPreview({
  locale,
  rows,
  profile,
}: {
  locale: Locale;
  rows: Json | null;
  profile: Json;
}) {
  if (!rows?.items?.length) return null;
  const columns: string[] = rows.columns ?? [];
  const profiles = (profile.column_profiles ?? {}) as Record<string, Json>;
  return (
    <section className="panel">
      <header className="panel-heading">
        <div>
          <h2>{w(locale, "The data itself", "البيانات نفسها")}</h2>
          <p>
            {w(
              locale,
              `First ${rows.items.length} of ${num(rows.row_count, locale)} rows.`,
              `أول ${rows.items.length} من ${num(rows.row_count, locale)} صف.`,
            )}
          </p>
        </div>
      </header>
      <div className="table-scroll" tabIndex={0}>
        <table className="data-grid">
          <thead>
            <tr>
              <th scope="col" className="data-grid__index">
                #
              </th>
              {columns.map((column) => (
                <th key={column} scope="col">
                  <span dir="ltr">{column}</span>
                  <small>
                    {
                      (TYPE_LABEL[profiles[column]?.semantic_type] ?? ["", ""])[
                        locale === "ar" ? 1 : 0
                      ]
                    }
                  </small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.items.map((row: Json, index: number) => (
              <tr key={index}>
                <th scope="row" className="data-grid__index">
                  {index + 1}
                </th>
                {columns.map((column) => {
                  const value = row[column];
                  const empty = value === null || value === "";
                  return (
                    <td
                      key={column}
                      className={
                        empty
                          ? "is-empty"
                          : typeof value === "number"
                            ? "numeric"
                            : undefined
                      }
                    >
                      {empty ? (
                        <span className="cell-empty">
                          {w(locale, "empty", "فارغ")}
                        </span>
                      ) : (
                        String(value)
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------------

function RecipeBuilder({
  locale,
  catalog,
  columns,
  recipe,
  suggested,
  busy,
  onAdd,
  onUpdate,
  onRemove,
  onMove,
  onApplyAll,
}: {
  locale: Locale;
  catalog: CatalogEntry[];
  columns: string[];
  recipe: RecipeStep[];
  suggested: Json[];
  busy: string | null;
  onAdd: (step: RecipeStep) => void;
  onUpdate: (index: number, patch: Partial<RecipeStep>) => void;
  onRemove: (index: number) => void;
  onMove: (index: number, delta: number) => void;
  onApplyAll: () => void;
}) {
  const ar = locale === "ar";
  const [picking, setPicking] = useState(false);
  const byKind = useMemo(
    () => new Map(catalog.map((entry) => [entry.kind, entry])),
    [catalog],
  );

  return (
    <section className="panel recipe">
      <header className="panel-heading">
        <div>
          <h2>
            <Layers size={16} />
            {w(locale, "Repair pipeline", "خط الإصلاح")}
          </h2>
          <p>
            {w(
              locale,
              "Steps run in order. Each is previewed before anything is published.",
              "تُنفَّذ الخطوات بالترتيب، وتُعاين كل خطوة قبل نشر أي شيء.",
            )}
          </p>
        </div>
      </header>

      {suggested.length > 0 && recipe.length === 0 && (
        <div className="recipe__suggested">
          <p>
            <Sparkles size={15} />
            {w(
              locale,
              `${suggested.length} repairs are proposed from the column profile.`,
              `اقتُرح ${suggested.length} إصلاحًا من ملف الأعمدة.`,
            )}
          </p>
          <button
            type="button"
            className="button button--secondary"
            onClick={onApplyAll}
          >
            {w(locale, "Load all proposals", "حمّل كل المقترحات")}
          </button>
        </div>
      )}

      <ol className="recipe__steps">
        {recipe.map((step, index) => {
          const entry = byKind.get(step.kind);
          return (
            <li key={`${step.kind}-${index}`}>
              <div className="recipe__step-head">
                <span className="recipe__index">{index + 1}</span>
                <div>
                  <strong>{entry?.label?.[locale] ?? step.kind}</strong>
                  <span
                    className={`chip ${SCOPE_TONE[entry?.scope ?? "cells"]}`}
                  >
                    {entry?.scope === "rows"
                      ? w(locale, "removes rows", "يحذف صفوفًا")
                      : entry?.scope === "schema"
                        ? w(locale, "changes columns", "يغيّر الأعمدة")
                        : w(locale, "edits cells", "يعدّل خلايا")}
                  </span>
                </div>
                <div className="recipe__step-tools">
                  <button
                    type="button"
                    onClick={() => onMove(index, -1)}
                    disabled={index === 0}
                    aria-label={w(locale, "Move earlier", "حرّك للأعلى")}
                  >
                    <ArrowUp size={14} />
                  </button>
                  <button
                    type="button"
                    onClick={() => onMove(index, 1)}
                    disabled={index === recipe.length - 1}
                    aria-label={w(locale, "Move later", "حرّك للأسفل")}
                  >
                    <ArrowDown size={14} />
                  </button>
                  <button
                    type="button"
                    onClick={() => onRemove(index)}
                    aria-label={w(locale, "Remove step", "احذف الخطوة")}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              {entry?.detail && (
                <p className="recipe__detail">{entry.detail[locale]}</p>
              )}
              <div className="recipe__fields">
                <label>
                  <span>{w(locale, "Columns", "الأعمدة")}</span>
                  <select
                    multiple
                    size={Math.min(5, Math.max(2, columns.length))}
                    value={step.columns}
                    onChange={(event) =>
                      onUpdate(index, {
                        columns: Array.from(
                          event.target.selectedOptions,
                          (option) => option.value,
                        ),
                      })
                    }
                  >
                    {columns.map((column) => (
                      <option key={column} value={column}>
                        {column}
                      </option>
                    ))}
                  </select>
                </label>
                {(entry?.options ?? []).map((option) => (
                  <StepField
                    key={option.name}
                    locale={locale}
                    option={option}
                    value={step[option.name]}
                    onChange={(value) =>
                      onUpdate(index, { [option.name]: value })
                    }
                  />
                ))}
              </div>
            </li>
          );
        })}
      </ol>

      {picking ? (
        <div className="recipe__catalog">
          <header>
            <strong>{w(locale, "Add a step", "أضف خطوة")}</strong>
            <button
              type="button"
              onClick={() => setPicking(false)}
              aria-label="close"
            >
              <X size={15} />
            </button>
          </header>
          <ul>
            {catalog.map((entry) => (
              <li key={entry.kind}>
                <button
                  type="button"
                  onClick={() => {
                    const defaults: RecipeStep = {
                      kind: entry.kind,
                      columns: [],
                    };
                    for (const option of entry.options) {
                      if (option.default !== undefined)
                        defaults[option.name] = option.default;
                    }
                    onAdd(defaults);
                    setPicking(false);
                  }}
                >
                  <strong>{entry.label[locale]}</strong>
                  <span className={`chip ${SCOPE_TONE[entry.scope]}`}>
                    {entry.scope === "rows"
                      ? w(locale, "rows", "صفوف")
                      : entry.scope === "schema"
                        ? w(locale, "schema", "بنية")
                        : w(locale, "cells", "خلايا")}
                  </span>
                  <small>{entry.detail[locale]}</small>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <button
          type="button"
          className="button button--ghost recipe__add"
          onClick={() => setPicking(true)}
          disabled={!catalog.length}
        >
          <Plus size={16} />
          {w(locale, "Add a step", "أضف خطوة")}
        </button>
      )}
      {busy === "preview" && (
        <p className="recipe__busy">
          {w(locale, "Previewing…", "جارٍ المعاينة…")}
        </p>
      )}
    </section>
  );
}

function StepField({
  locale,
  option,
  value,
  onChange,
}: {
  locale: Locale;
  option: StepOption;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const label = option.name.replace(/_/g, " ");
  if (option.type === "choice") {
    return (
      <label>
        <span>{label}</span>
        <select
          value={String(value ?? option.default ?? "")}
          onChange={(event) => onChange(event.target.value)}
        >
          {(option.choices ?? []).map((choice) => (
            <option key={choice} value={choice}>
              {choice}
            </option>
          ))}
        </select>
      </label>
    );
  }
  if (option.type === "boolean") {
    return (
      <label className="checkbox-row">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
        />
        {label}
      </label>
    );
  }
  if (option.type === "mapping") {
    return (
      <label>
        <span>{label} (JSON)</span>
        <input
          value={
            typeof value === "string" ? value : JSON.stringify(value ?? {})
          }
          onChange={(event) => {
            try {
              onChange(JSON.parse(event.target.value));
            } catch {
              onChange(event.target.value);
            }
          }}
          placeholder='{"old":"new"}'
          dir="ltr"
        />
      </label>
    );
  }
  return (
    <label>
      <span>{label}</span>
      <input
        type={
          option.type === "integer" || option.type === "number"
            ? "number"
            : "text"
        }
        value={String(value ?? option.default ?? "")}
        min={option.min}
        max={option.max}
        onChange={(event) =>
          onChange(
            option.type === "integer"
              ? Number.parseInt(event.target.value, 10)
              : option.type === "number"
                ? Number(event.target.value)
                : event.target.value,
          )
        }
      />
    </label>
  );
}

// ---------------------------------------------------------------------------------

function ReviewPanel({
  locale,
  preview,
  approved,
  busy,
  onApprove,
  onApply,
}: {
  locale: Locale;
  preview: Json;
  approved: boolean;
  busy: boolean;
  onApprove: (value: boolean) => void;
  onApply: () => void;
}) {
  const ar = locale === "ar";
  const summary = (preview.summary ?? {}) as Json;
  const totals = (summary.totals ?? {}) as Json;
  const changes = ((preview.control_totals ?? {}).changes ?? []) as Json[];
  const material = changes.filter((item) => item.material);
  const language = ar ? "ar" : "en";

  return (
    <section className="panel review">
      <header className="panel-heading">
        <div>
          <h2>
            <ShieldCheck size={17} />
            {w(locale, "Review before publishing", "راجع قبل النشر")}
          </h2>
          <p>{summary.headline?.[language]}</p>
        </div>
        <div className="review__delta">
          <span>{w(locale, "Quality", "الجودة")}</span>
          <b>
            {num(summary.quality_before?.score, locale)}
            <ChevronRight size={14} />
            {num(summary.quality_after?.score, locale)}
          </b>
        </div>
      </header>

      <div className="review__tiles">
        {(
          [
            [w(locale, "Steps", "الخطوات"), totals.steps],
            [w(locale, "Cells changed", "خلايا غُيّرت"), totals.cells_changed],
            [w(locale, "Rows removed", "صفوف حُذفت"), totals.rows_removed],
            [
              w(locale, "Cells left as-is", "خلايا بقيت كما هي"),
              totals.cells_unresolved,
            ],
          ] as const
        ).map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <b>{num(Number(value ?? 0), locale)}</b>
          </div>
        ))}
      </div>

      <ol className="review__steps">
        {(summary.steps?.[language] ?? []).map(
          (line: string, index: number) => (
            <li key={index}>{line.replace(/^\s*\d+\.\s*/, "")}</li>
          ),
        )}
      </ol>

      {material.length > 0 && (
        <div className="review__totals">
          <h3>{w(locale, "Control totals", "المجاميع الرقابية")}</h3>
          <table>
            <thead>
              <tr>
                <th>{w(locale, "Column", "العمود")}</th>
                <th>{w(locale, "Before", "قبل")}</th>
                <th>{w(locale, "After", "بعد")}</th>
                <th>{w(locale, "Difference", "الفرق")}</th>
                <th>{w(locale, "Explanation", "التفسير")}</th>
              </tr>
            </thead>
            <tbody>
              {material.map((change) => (
                <tr key={change.column}>
                  <th scope="row" dir="ltr">
                    {change.column}
                  </th>
                  <td className="numeric">{num(change.before, locale)}</td>
                  <td className="numeric">{num(change.after, locale)}</td>
                  <td className="numeric">{num(change.difference, locale)}</td>
                  <td>
                    {change.note ===
                    "difference_explained_by_newly_readable_cells"
                      ? w(
                          locale,
                          `${change.cells_recovered} cells became readable`,
                          `${change.cells_recovered} خلية صارت مقروءة`,
                        )
                      : w(
                          locale,
                          "Unexplained — check this",
                          "غير مفسّر — تحقّق",
                        )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(summary.caveats?.[language] ?? []).length > 0 && (
        <ul className="review__caveats">
          {summary.caveats[language].map((item: string, index: number) => (
            <li key={index}>
              <AlertTriangle size={15} />
              {item}
            </li>
          ))}
        </ul>
      )}

      <footer className="review__footer">
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={approved}
            onChange={(event) => onApprove(event.target.checked)}
          />
          {preview.requires_review
            ? w(
                locale,
                "I have reviewed the changes above, including the control totals, and approve publishing a new immutable version.",
                "راجعت التغييرات أعلاه بما فيها المجاميع الرقابية، وأوافق على نشر إصدار جديد غير قابل للتعديل.",
              )
            : w(
                locale,
                "I approve publishing a new immutable version.",
                "أوافق على نشر إصدار جديد غير قابل للتعديل.",
              )}
        </label>
        <button
          type="button"
          className="button button--primary"
          onClick={onApply}
          disabled={!approved || busy}
        >
          <ShieldCheck size={16} />
          {busy
            ? w(locale, "Publishing…", "جارٍ النشر…")
            : w(locale, "Publish new version", "انشر إصدارًا جديدًا")}
        </button>
      </footer>
    </section>
  );
}
