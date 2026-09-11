"use client";

import { useRef, useState } from "react";
import {
  CheckCircle2,
  FileSpreadsheet,
  ShieldCheck,
  UploadCloud,
  X,
} from "lucide-react";
import type { Locale, UploadAccepted } from "@/lib/contracts";

interface UploadStudioProps {
  locale: Locale;
  upload: (file: File) => Promise<UploadAccepted>;
}

const supported = ["csv", "tsv", "xlsx", "json", "jsonl", "parquet"];

export function UploadStudio({ locale, upload }: UploadStudioProps) {
  const ar = locale === "ar";
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function choose(next?: File) {
    setMessage("");
    setError("");
    if (!next) return setFile(null);
    const extension = next.name.split(".").pop()?.toLowerCase() ?? "";
    if (!supported.includes(extension)) {
      setFile(null);
      setError(
        ar
          ? "تنسيق غير مدعوم. استخدم CSV أو TSV أو XLSX أو JSON/JSONL أو Parquet."
          : "Unsupported format. Use CSV, TSV, XLSX, JSON/JSONL, or Parquet.",
      );
      return;
    }
    if (next.size > 25 * 1024 * 1024) {
      setFile(null);
      setError(
        ar
          ? "يتجاوز الملف حد 25 ميغابايت."
          : "The file exceeds the 25 MB limit.",
      );
      return;
    }
    setFile(next);
  }

  async function submit() {
    if (!file || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await upload(file);
      setMessage(
        ar
          ? `تم قبول الملف للفحص. معرّف مجموعة البيانات: ${result.dataset_id}`
          : `Upload accepted for inspection. Dataset ID: ${result.dataset_id}`,
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : ar
            ? "تعذر رفع الملف."
            : "The upload failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="upload-studio" aria-labelledby="upload-heading">
      <header className="page-header">
        <div>
          <p className="eyebrow">{ar ? "إدخال مضبوط" : "Governed ingestion"}</p>
          <h1 id="upload-heading">
            {ar ? "ارفع ملفًا وافحصه" : "Upload and inspect a file"}
          </h1>
          <p>
            {ar
              ? "يبقى الأصل دون تعديل. كل تنظيف ينشئ إصدارًا جديدًا بعد المراجعة."
              : "The original remains immutable. Cleaning creates a reviewed new version."}
          </p>
        </div>
        <span className="badge badge--ready">
          <ShieldCheck size={14} aria-hidden="true" />
          {ar ? "قراءة فقط" : "Read-only import"}
        </span>
      </header>
      <div
        className={`drop-zone${file ? " drop-zone--selected" : ""}`}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          choose(event.dataTransfer.files?.[0]);
        }}
      >
        <input
          ref={inputRef}
          id="data-file"
          type="file"
          accept=".csv,.tsv,.xlsx,.json,.jsonl,.parquet"
          onChange={(event) => choose(event.target.files?.[0])}
        />
        <label htmlFor="data-file">
          <UploadCloud size={30} aria-hidden="true" />
          <strong>{ar ? "اختر ملف البيانات" : "Choose data file"}</strong>
          <span>
            {ar
              ? "أو اسحبه هنا · 25 ميغابايت كحد أقصى"
              : "or drop it here · 25 MB maximum"}
          </span>
        </label>
        <p className="format-list">
          <bdi>CSV</bdi>
          <bdi>TSV</bdi>
          <bdi>XLSX</bdi>
          <bdi>JSONL</bdi>
          <bdi>PARQUET</bdi>
        </p>
      </div>
      {file ? (
        <div className="selected-file">
          <FileSpreadsheet size={22} aria-hidden="true" />
          <div>
            <strong>{file.name}</strong>
            <span>
              {new Intl.NumberFormat(locale === "ar" ? "ar-JO" : "en", {
                style: "unit",
                unit: "kilobyte",
                maximumFractionDigits: 1,
              }).format(file.size / 1024)}
            </span>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={() => {
              choose();
              if (inputRef.current) inputRef.current.value = "";
            }}
            aria-label={ar ? "إزالة الملف" : "Remove file"}
          >
            <X aria-hidden="true" />
          </button>
        </div>
      ) : null}
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <div className="success-message" role="status">
          <CheckCircle2 size={19} aria-hidden="true" />
          <span>{message}</span>
        </div>
      ) : null}
      <div className="upload-actions">
        <button
          className="button button--primary"
          type="button"
          onClick={submit}
          disabled={!file || busy}
        >
          {busy
            ? ar
              ? "جارٍ الإرسال…"
              : "Uploading…"
            : ar
              ? "ارفع وافحص"
              : "Upload and inspect"}
        </button>
        <p>
          {ar
            ? "لن يتم تنفيذ وحدات الماكرو أو الروابط الخارجية أو معادلات Excel."
            : "Macros, external links, and Excel formulas are never executed."}
        </p>
      </div>
    </section>
  );
}
