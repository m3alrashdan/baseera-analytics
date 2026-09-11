from __future__ import annotations

import csv
import html
import io
import json
import re
from typing import Any

import xlsxwriter
from docx import Document

from .errors import AppError
from .ingestion import canonical_json

EXPORT_MEDIA_TYPES = {
    "html": "text/html; charset=utf-8",
    "json": "application/json",
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


def render_report_export(report: dict[str, Any], kind: str) -> bytes:
    kind = kind.lower()
    if kind not in EXPORT_MEDIA_TYPES:
        raise AppError(
            422,
            "unsupported_export_format",
            f"Supported report formats are: {', '.join(sorted(EXPORT_MEDIA_TYPES))}",
        )
    if kind == "json":
        return canonical_json(report).encode("utf-8")
    if kind == "html":
        return _html(report).encode("utf-8")
    if kind == "csv":
        return _csv(report)
    if kind == "xlsx":
        return _xlsx(report)
    if kind == "docx":
        return _docx(report)
    return _pdf(report)


def _rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in report.get("sections", []):
        result = section.get("result") if isinstance(section, dict) else None
        rows.append(
            {
                "section": section.get("title", "") if isinstance(section, dict) else "",
                "kind": section.get("kind", section.get("type", ""))
                if isinstance(section, dict)
                else "",
                "result_id": result.get("result_id", "") if isinstance(result, dict) else "",
                "value": result.get("value", "") if isinstance(result, dict) else "",
                "unit": result.get("unit", "") if isinstance(result, dict) else "",
                "status": result.get("status", "") if isinstance(result, dict) else "",
            }
        )
    return rows


def _html(report: dict[str, Any]) -> str:
    direction = "rtl" if report.get("language") == "ar" else "ltr"
    sections: list[str] = []
    for section in report.get("sections", []):
        title = html.escape(str(section.get("title", "Untitled section")))
        result = section.get("result")
        if isinstance(result, dict):
            value = html.escape(str(result.get("value")))
            unit = html.escape(str(result.get("unit") or ""))
            result_id = html.escape(str(result.get("result_id") or ""))
            warnings = "".join(
                f"<li>{html.escape(str(item))}</li>" for item in result.get("warnings", [])
            )
            sections.append(
                f"<section><h2>{title}</h2><p class=metric>{value} {unit}</p>"
                f"<p>Evidence: <code>{result_id}</code></p><ul>{warnings}</ul></section>"
            )
        else:
            narrative = html.escape(str(section.get("content", "")))
            sections.append(f"<section><h2>{title}</h2><p>{narrative}</p></section>")
    title = html.escape(str(report["title"]))
    return (
        '<!doctype html><html lang="{}" dir="{}"><head><meta charset="utf-8">'
        "<title>{}</title><style>body{{font-family:system-ui,sans-serif;max-width:900px;"
        "margin:3rem auto;padding:0 1rem;color:#172126}}h1{{border-bottom:2px solid #29806f;"
        "padding-bottom:.5rem}}section{{break-inside:avoid;margin:2rem 0}}.metric{{font-size:2rem;"
        "font-weight:700}}code{{overflow-wrap:anywhere}}</style></head><body><h1>{}</h1>"
        "<p>Snapshot version: {}</p>{}</body></html>"
    ).format(
        report.get("language", "en"), direction, title, title, report["version"], "".join(sections)
    )


def _csv(report: dict[str, Any]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output, fieldnames=["section", "kind", "result_id", "value", "unit", "status"]
    )
    writer.writeheader()
    writer.writerows(
        {key: _spreadsheet_safe(value) for key, value in row.items()} for row in _rows(report)
    )
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def _xlsx(report: dict[str, Any]) -> bytes:
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(
        output, {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False}
    )
    worksheet = workbook.add_worksheet("Report data")
    title_format = workbook.add_format({"bold": True, "font_size": 16})
    header_format = workbook.add_format({"bold": True, "bg_color": "#DCEBE7"})
    worksheet.write_string(0, 0, str(_spreadsheet_safe(report["title"])), title_format)
    fields = ["section", "kind", "result_id", "value", "unit", "status"]
    for column, field in enumerate(fields):
        worksheet.write(2, column, field, header_format)
    for row_number, row in enumerate(_rows(report), start=3):
        for column, field in enumerate(fields):
            worksheet.write(row_number, column, _spreadsheet_safe(row[field]))
    worksheet.set_column(0, 1, 28)
    worksheet.set_column(2, 2, 44)
    worksheet.set_column(3, 5, 16)
    workbook.close()
    return output.getvalue()


def _spreadsheet_safe(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip(" \n").startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def _docx(report: dict[str, Any]) -> bytes:
    document = Document()
    document.core_properties.title = str(report["title"])
    document.add_heading(str(report["title"]), level=0)
    document.add_paragraph(f"Snapshot version: {report['version']}")
    for section in report.get("sections", []):
        document.add_heading(str(section.get("title", "Untitled section")), level=1)
        result = section.get("result")
        if isinstance(result, dict):
            document.add_paragraph(f"{result.get('value')} {result.get('unit') or ''}")
            document.add_paragraph(f"Evidence: {result.get('result_id')}")
            for warning in result.get("warnings", []):
                document.add_paragraph(str(warning), style="List Bullet")
        else:
            document.add_paragraph(str(section.get("content", "")))
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def _pdf(report: dict[str, Any]) -> bytes:
    from weasyprint import CSS, HTML
    from weasyprint.urls import URLFetcher

    # Content is escaped by _html. No network, local file or data URL fetches.
    # Fontconfig resolves the installed Arabic and Latin fonts.
    fetcher = URLFetcher(allowed_protocols=(), allow_redirects=False, fail_on_errors=True)
    document = HTML(string=_html(report), url_fetcher=fetcher)
    stylesheet = CSS(
        string="""
        @page { size: A4; margin: 20mm;
            @bottom-center { content: counter(page) " / " counter(pages); font-size: 9pt; }
        }
        body { font-family: "Noto Sans Arabic", "DejaVu Sans", sans-serif;
               font-size: 10pt; margin: 0; max-width: none; }
        p { white-space: pre-wrap; overflow-wrap: anywhere; }
        code { direction: ltr; font-size: 8pt; }
        h1 { font-size: 22pt; } h2 { font-size: 14pt; }
    """,
        url_fetcher=fetcher,
    )
    return document.write_pdf(stylesheets=[stylesheet], pdf_tags=True)


def export_filename(title: str, version: int, kind: str) -> str:
    slug = "-".join(
        part for part in "".join(char.lower() if char.isalnum() else " " for char in title).split()
    )
    return f"{slug or 'report'}-v{version}.{kind}"


def report_as_json_bytes(report: dict[str, Any]) -> bytes:
    return json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")


# ----------------------------------------------------------------------------------
# Analysis brief
# ----------------------------------------------------------------------------------

BRIEF_MEDIA_TYPES = {
    "html": "text/html; charset=utf-8",
    "json": "application/json",
    "md": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}

_BRIEF_LABELS = {
    "en": {
        "title": "Data analysis brief",
        "prepared": "Prepared",
        "summary": "Executive summary",
        "condition": "Data received and its condition",
        "cleaning": "What was repaired, and why",
        "findings": "Findings",
        "forecast": "Outlook",
        "actions": "Recommended actions",
        "limits": "What this analysis does not establish",
        "method": "Method and reproducibility",
        "observation": "Observed",
        "interpretation": "Reading",
        "recommendation": "Action",
        "limitation": "Limit",
        "rows": "Rows",
        "columns": "Columns",
        "score": "Quality score",
        "grade": "Assessment",
        "column": "Column",
        "type": "Type",
        "missing": "Missing",
        "distinct": "Distinct",
        "period": "Period",
        "value": "Projection",
        "range": "Interval",
        "accuracy": "Measured accuracy",
        "no_findings": "No finding met the reporting threshold on this dataset.",
        "confidence": "Confidence",
        "decision": "Decision required",
    },
    "ar": {
        "title": "موجز تحليل البيانات",
        "prepared": "أُعدّ في",
        "summary": "الملخص التنفيذي",
        "condition": "البيانات المستلمة وحالتها",
        "cleaning": "ما جرى إصلاحه ولماذا",
        "findings": "النتائج",
        "forecast": "النظرة المستقبلية",
        "actions": "الإجراءات الموصى بها",
        "limits": "ما لا يثبته هذا التحليل",
        "method": "المنهج وقابلية إعادة الإنتاج",
        "observation": "الملاحظة",
        "interpretation": "التفسير",
        "recommendation": "الإجراء",
        "limitation": "الحد",
        "rows": "الصفوف",
        "columns": "الأعمدة",
        "score": "مؤشر الجودة",
        "grade": "التقييم",
        "column": "العمود",
        "type": "النوع",
        "missing": "مفقود",
        "distinct": "قيم مميزة",
        "period": "الفترة",
        "value": "التوقع",
        "range": "الفاصل",
        "accuracy": "الدقة المقاسة",
        "no_findings": "لم تتجاوز أي نتيجة عتبة الإبلاغ في هذه البيانات.",
        "confidence": "الثقة",
        "decision": "قرار مطلوب",
    },
}

_SEVERITY_TONE = {
    "critical": ("#a4363d", "#fde5e6"),
    "high": ("#a4363d", "#fde5e6"),
    "medium": ("#99620a", "#fcebc7"),
    "low": ("#087f8c", "#d8eff0"),
    "info": ("#52697e", "#eef1f0"),
}


_LEADING_NUMBER = re.compile(r"^\s*\d+\.\s*")


def _unnumbered(step: str) -> str:
    """Strip the log's own "1. " prefix; the list markup supplies the numbering."""
    return _LEADING_NUMBER.sub("", step)


def _brief_labels(brief: dict[str, Any]) -> dict[str, str]:
    return _BRIEF_LABELS["ar" if brief.get("locale") == "ar" else "en"]


def _brief_html(brief: dict[str, Any]) -> str:
    labels = _brief_labels(brief)
    rtl = brief.get("locale") == "ar"
    escape = html.escape
    quality = brief.get("quality") or {}
    summary = brief.get("profile_summary", {})
    font_stack = '"Noto Sans Arabic", "Noto Naskh Arabic"' if rtl else '"Inter", "Helvetica Neue"'

    def section(title: str, body: str) -> str:
        return f"<section><h2>{escape(title)}</h2>{body}</section>"

    tiles = "".join(
        f'<div class="tile"><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>'
        for label, value in [
            (labels["rows"], f"{summary.get('row_count', 0):,}"),
            (labels["columns"], f"{summary.get('column_count', 0):,}"),
            (labels["score"], quality.get("score", "—")),
            (labels["grade"], brief.get("quality_grade", "—")),
        ]
    )
    columns_rows = "".join(
        "<tr>"
        f"<td>{escape(str(column['name']))}</td>"
        f"<td>{escape(str(column['type']))}</td>"
        f"<td>{column['missing']:,}</td>"
        f"<td>{column['distinct']:,}</td>"
        "</tr>"
        for column in summary.get("columns", [])
    )
    condition = (
        f'<div class="tiles">{tiles}</div>'
        "<table><thead><tr>"
        f"<th>{escape(labels['column'])}</th><th>{escape(labels['type'])}</th>"
        f"<th>{escape(labels['missing'])}</th><th>{escape(labels['distinct'])}</th>"
        f"</tr></thead><tbody>{columns_rows}</tbody></table>"
    )

    cleaning_html = ""
    cleaning = brief.get("cleaning")
    if cleaning:
        language = "ar" if rtl else "en"
        steps = "".join(
            f"<li>{escape(_unnumbered(step))}</li>"
            for step in cleaning.get("steps", {}).get(language, [])
        )
        caveats = "".join(
            f"<li>{escape(item)}</li>" for item in cleaning.get("caveats", {}).get(language, [])
        )
        cleaning_html = section(
            labels["cleaning"],
            f'<p class="lead">{escape(cleaning.get("headline", {}).get(language, ""))}</p>'
            f"<ol>{steps}</ol>"
            + (f'<div class="caveat"><ul>{caveats}</ul></div>' if caveats else ""),
        )

    findings_html = labels["no_findings"]
    if brief.get("findings"):
        cards = []
        for finding in brief["findings"]:
            colour, tint = _SEVERITY_TONE.get(finding["severity"], _SEVERITY_TONE["info"])
            cards.append(
                f'<article class="finding" style="--tone:{colour};--tint:{tint}">'
                f'<header><span class="pill">{escape(finding["severity_label"])}</span>'
                f"<h3>{escape(finding['title'])}</h3>"
                f"<small>{escape(labels['confidence'])}: {escape(finding['confidence'])}</small>"
                "</header>"
                f"<p><b>{escape(labels['observation'])}</b> {escape(finding['observation'])}</p>"
                f"<p><b>{escape(labels['interpretation'])}</b> "
                f"{escape(finding['interpretation'])}</p>"
                f'<p class="action"><b>{escape(labels["recommendation"])}</b> '
                f"{escape(finding['recommendation'])}</p>"
                f'<p class="limit"><b>{escape(labels["limitation"])}</b> '
                f"{escape(finding['limitation'])}</p>"
                "</article>"
            )
        findings_html = "".join(cards)

    forecast_html = ""
    forecast = brief.get("forecast")
    if forecast and forecast.get("forecast"):
        rows_html = "".join(
            "<tr>"
            f"<td>{escape(str(item['period']))}</td>"
            f"<td>{item['value']:,.2f}</td>"
            f"<td>{item['lower']:,.2f} – {item['upper']:,.2f}</td>"
            "</tr>"
            for item in forecast["forecast"]
        )
        backtest = forecast.get("backtest", {})
        accuracy = (
            f"MASE {backtest['mase']} · WAPE {backtest.get('wape')} · "
            f"{backtest.get('interval_coverage')} / {backtest.get('interval_target')}"
            if backtest.get("mase") is not None
            else escape(str(backtest.get("reason", "")))
        )
        warnings = "".join(
            f"<li>{escape(item)}</li>"
            for item in forecast.get("warnings_ar" if rtl else "warnings", [])
        )
        decision = forecast.get("decision_required")
        forecast_html = section(
            labels["forecast"],
            "<table><thead><tr>"
            f"<th>{escape(labels['period'])}</th><th>{escape(labels['value'])}</th>"
            f"<th>{escape(labels['range'])}</th></tr></thead>"
            f"<tbody>{rows_html}</tbody></table>"
            f'<p class="muted">{escape(labels["accuracy"])}: {accuracy}</p>'
            + (f'<div class="caveat"><ul>{warnings}</ul></div>' if warnings else "")
            + (
                f'<div class="decision"><b>{escape(labels["decision"])}</b> '
                f"{escape(decision['ar' if rtl else 'en'])}</div>"
                if decision
                else ""
            ),
        )

    actions_html = "".join(
        f"<li><b>{escape(action['source'])}</b> — {escape(action['action'])}</li>"
        for action in brief.get("actions", [])
    )
    limits_html = "".join(f"<li>{escape(item)}</li>" for item in brief.get("limitations", []))
    method = brief.get("method", {}).get("ar" if rtl else "en", "")

    return f"""<!doctype html>
<html lang="{"ar" if rtl else "en"}" dir="{"rtl" if rtl else "ltr"}">
<head><meta charset="utf-8"><title>{escape(labels["title"])}</title>
<style>
  @page {{ size: A4; margin: 18mm 16mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: {font_stack}, system-ui, sans-serif;
         color: #142536; margin: 0; font-size: 11pt; line-height: 1.6; }}
  header.cover {{ background: #142536; color: #fff; padding: 28pt 24pt; margin-bottom: 22pt; }}
  header.cover small {{ color: #62c9cc; letter-spacing: .12em; font-weight: 700; font-size: 8pt; }}
  header.cover h1 {{ margin: 8pt 0 4pt; font-size: 26pt; letter-spacing: -.02em; }}
  header.cover p {{ margin: 0; color: #d2dddd; }}
  header.cover .lead {{ margin-top: 12pt; font-size: 12pt; color: #fff; }}
  section {{ margin: 0 0 20pt; }}
  section > h2 {{ break-after: avoid; }}
  table, .tiles {{ break-inside: avoid; }}
  h2 {{ font-size: 13pt; border-bottom: 2px solid #087f8c; padding-bottom: 5pt;
        margin: 0 0 10pt; }}
  h3 {{ font-size: 11.5pt; margin: 2pt 0 0; }}
  .tiles {{ display: flex; gap: 8pt; margin-bottom: 12pt; }}
  .tile {{ flex: 1; background: #f4f5f2; padding: 9pt 11pt; border-radius: 5pt; }}
  .tile span {{ display: block; color: #52697e; font-size: 8.5pt; }}
  .tile strong {{ font-size: 17pt; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 9.5pt; }}
  th, td {{ text-align: {"right" if rtl else "left"}; padding: 5pt 7pt;
            border-bottom: 1px solid #dfe4e3; }}
  th {{ background: #f8f9f7; font-weight: 700; color: #385067; }}
  .finding {{ border: 1px solid #dfe4e3; border-{"right" if rtl else "left"}: 4px solid var(--tone);
              padding: 11pt 13pt; margin-bottom: 10pt; border-radius: 4pt;
              break-inside: avoid; }}
  .finding header {{ margin-bottom: 7pt; }}
  .pill {{ background: var(--tint); color: var(--tone); font-size: 8pt; font-weight: 700;
           padding: 2pt 7pt; border-radius: 99pt; }}
  .finding small {{ color: #718397; font-size: 8.5pt; }}
  .finding p {{ margin: 4pt 0; }}
  .finding b {{ color: #087f8c; font-size: 9pt; text-transform: uppercase;
                letter-spacing: .04em; }}
  .finding .action b {{ color: #19704a; }}
  .finding .limit {{ color: #52697e; font-size: 9.5pt; }}
  .finding .limit b {{ color: #718397; }}
  .caveat {{ background: #fcebc7; border-radius: 4pt; padding: 8pt 12pt; margin-top: 9pt; }}
  .caveat ul {{ margin: 0; padding-{"right" if rtl else "left"}: 14pt; color: #99620a; }}
  .decision {{ background: #e5edf8; border-radius: 4pt; padding: 9pt 12pt; margin-top: 9pt; }}
  .decision b {{ color: #365e93; display: block; margin-bottom: 3pt; }}
  .muted {{ color: #52697e; font-size: 9.5pt; }}
  ol, ul {{ padding-{"right" if rtl else "left"}: 16pt; margin: 0; }}
  li {{ margin-bottom: 5pt; }}
  footer {{ border-top: 1px solid #dfe4e3; padding-top: 8pt; color: #718397; font-size: 8.5pt; }}
</style></head>
<body>
<header class="cover">
  <small>بصيرة · BASEERA</small>
  <h1>{escape(labels["title"])}</h1>
  <p>{escape(str(brief["dataset"].get("name") or brief["dataset"].get("filename") or ""))}</p>
  <p class="lead">{escape(brief["headline"])}</p>
</header>
{section(labels["condition"], condition)}
{cleaning_html}
{section(labels["findings"], findings_html)}
{forecast_html}
{section(labels["actions"], f"<ol>{actions_html}</ol>") if actions_html else ""}
{section(labels["limits"], f"<ul>{limits_html}</ul>") if limits_html else ""}
<footer>{escape(method)}<br>{escape(labels["prepared"])}: {escape(brief["generated_at"])}</footer>
</body></html>"""


def _brief_markdown(brief: dict[str, Any]) -> str:
    labels = _brief_labels(brief)
    rtl = brief.get("locale") == "ar"
    quality = brief.get("quality") or {}
    lines = [
        f"# {labels['title']}",
        "",
        f"**{brief['dataset'].get('name') or brief['dataset'].get('filename') or ''}**",
        "",
        brief["headline"],
        "",
        f"## {labels['condition']}",
        "",
        f"- {labels['rows']}: {brief['profile_summary'].get('row_count', 0):,}",
        f"- {labels['columns']}: {brief['profile_summary'].get('column_count', 0):,}",
        f"- {labels['score']}: {quality.get('score', '—')} ({brief.get('quality_grade', '—')})",
        "",
    ]
    cleaning = brief.get("cleaning")
    if cleaning:
        language = "ar" if rtl else "en"
        headline = cleaning.get("headline", {}).get(language, "")
        lines += [f"## {labels['cleaning']}", "", headline, ""]
        lines += [
            f"{index}. {step.split('. ', 1)[-1]}"
            for index, step in enumerate(cleaning.get("steps", {}).get(language, []), 1)
        ]
        lines.append("")
        for caveat in cleaning.get("caveats", {}).get(language, []):
            lines.append(f"> {caveat}")
        lines.append("")
    lines += [f"## {labels['findings']}", ""]
    if not brief.get("findings"):
        lines += [labels["no_findings"], ""]
    for finding in brief.get("findings", []):
        lines += [
            f"### {finding['title']}  ·  {finding['severity_label']}",
            "",
            f"- **{labels['observation']}** {finding['observation']}",
            f"- **{labels['interpretation']}** {finding['interpretation']}",
            f"- **{labels['recommendation']}** {finding['recommendation']}",
            f"- **{labels['limitation']}** {finding['limitation']}",
            "",
        ]
    forecast = brief.get("forecast")
    if forecast and forecast.get("forecast"):
        lines += [
            f"## {labels['forecast']}",
            "",
            f"| {labels['period']} | {labels['value']} | {labels['range']} |",
            "| --- | --- | --- |",
        ]
        lines += [
            f"| {item['period']} | {item['value']:,.2f} | "
            f"{item['lower']:,.2f} – {item['upper']:,.2f} |"
            for item in forecast["forecast"]
        ]
        lines.append("")
        for warning in forecast.get("warnings_ar" if rtl else "warnings", []):
            lines.append(f"> {warning}")
        lines.append("")
    if brief.get("actions"):
        lines += [f"## {labels['actions']}", ""]
        lines += [
            f"{index}. **{action['source']}** — {action['action']}"
            for index, action in enumerate(brief["actions"], 1)
        ]
        lines.append("")
    if brief.get("limitations"):
        lines += [f"## {labels['limits']}", ""]
        lines += [f"- {item}" for item in brief["limitations"]]
        lines.append("")
    lines += [
        f"## {labels['method']}",
        "",
        brief.get("method", {}).get("ar" if rtl else "en", ""),
        "",
        f"_{labels['prepared']}: {brief['generated_at']}_",
    ]
    return "\n".join(lines)


def _brief_docx(brief: dict[str, Any]) -> bytes:
    labels = _brief_labels(brief)
    rtl = brief.get("locale") == "ar"
    language = "ar" if rtl else "en"
    document = Document()
    document.add_heading(labels["title"], level=0)
    document.add_paragraph(
        str(brief["dataset"].get("name") or brief["dataset"].get("filename") or "")
    )
    document.add_paragraph(brief["headline"])

    document.add_heading(labels["condition"], level=1)
    quality = brief.get("quality") or {}
    document.add_paragraph(
        f"{labels['rows']}: {brief['profile_summary'].get('row_count', 0):,} · "
        f"{labels['columns']}: {brief['profile_summary'].get('column_count', 0):,} · "
        f"{labels['score']}: {quality.get('score', '—')} ({brief.get('quality_grade', '—')})"
    )
    columns = brief["profile_summary"].get("columns", [])
    if columns:
        table = document.add_table(rows=1, cols=4)
        table.style = "Light Grid Accent 1"
        for cell, heading in zip(
            table.rows[0].cells,
            [labels["column"], labels["type"], labels["missing"], labels["distinct"]],
            strict=True,
        ):
            cell.text = heading
        for column in columns:
            cells = table.add_row().cells
            cells[0].text = str(column["name"])
            cells[1].text = str(column["type"])
            cells[2].text = f"{column['missing']:,}"
            cells[3].text = f"{column['distinct']:,}"

    cleaning = brief.get("cleaning")
    if cleaning:
        document.add_heading(labels["cleaning"], level=1)
        document.add_paragraph(cleaning.get("headline", {}).get(language, ""))
        for step in cleaning.get("steps", {}).get(language, []):
            document.add_paragraph(_unnumbered(step), style="List Number")
        for caveat in cleaning.get("caveats", {}).get(language, []):
            document.add_paragraph(caveat, style="Intense Quote")

    document.add_heading(labels["findings"], level=1)
    if not brief.get("findings"):
        document.add_paragraph(labels["no_findings"])
    for finding in brief.get("findings", []):
        document.add_heading(f"{finding['title']} · {finding['severity_label']}", level=2)
        for label, body in [
            (labels["observation"], finding["observation"]),
            (labels["interpretation"], finding["interpretation"]),
            (labels["recommendation"], finding["recommendation"]),
            (labels["limitation"], finding["limitation"]),
        ]:
            paragraph = document.add_paragraph()
            paragraph.add_run(f"{label}: ").bold = True
            paragraph.add_run(body)

    forecast = brief.get("forecast")
    if forecast and forecast.get("forecast"):
        document.add_heading(labels["forecast"], level=1)
        table = document.add_table(rows=1, cols=3)
        table.style = "Light Grid Accent 1"
        for cell, heading in zip(
            table.rows[0].cells,
            [labels["period"], labels["value"], labels["range"]],
            strict=True,
        ):
            cell.text = heading
        for item in forecast["forecast"]:
            cells = table.add_row().cells
            cells[0].text = str(item["period"])
            cells[1].text = f"{item['value']:,.2f}"
            cells[2].text = f"{item['lower']:,.2f} – {item['upper']:,.2f}"
        for warning in forecast.get("warnings_ar" if rtl else "warnings", []):
            document.add_paragraph(warning, style="Intense Quote")

    if brief.get("actions"):
        document.add_heading(labels["actions"], level=1)
        for action in brief["actions"]:
            paragraph = document.add_paragraph(style="List Number")
            paragraph.add_run(f"{action['source']} — ").bold = True
            paragraph.add_run(action["action"])

    if brief.get("limitations"):
        document.add_heading(labels["limits"], level=1)
        for item in brief["limitations"]:
            document.add_paragraph(item, style="List Bullet")

    document.add_heading(labels["method"], level=1)
    document.add_paragraph(brief.get("method", {}).get(language, ""))
    document.add_paragraph(f"{labels['prepared']}: {brief['generated_at']}")

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def render_brief_document(brief: dict[str, Any], kind: str) -> tuple[bytes, str, str]:
    """Render an analysis brief. Returns the bytes, media type and file extension."""
    kind = kind.lower()
    if kind not in BRIEF_MEDIA_TYPES:
        raise AppError(
            422,
            "unsupported_export_format",
            f"Supported brief formats are: {', '.join(sorted(BRIEF_MEDIA_TYPES))}, pptx.",
            details={"requested": kind},
        )
    if kind == "json":
        return canonical_json(brief).encode("utf-8"), BRIEF_MEDIA_TYPES[kind], "json"
    if kind == "html":
        return _brief_html(brief).encode("utf-8"), BRIEF_MEDIA_TYPES[kind], "html"
    if kind == "md":
        return _brief_markdown(brief).encode("utf-8"), BRIEF_MEDIA_TYPES[kind], "md"
    if kind == "docx":
        return _brief_docx(brief), BRIEF_MEDIA_TYPES[kind], "docx"
    from weasyprint import HTML

    pdf = HTML(string=_brief_html(brief)).write_pdf()
    return pdf, BRIEF_MEDIA_TYPES["pdf"], "pdf"
