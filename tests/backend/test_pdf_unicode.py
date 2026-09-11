import pytest
from baseera.reports import render_report_export


def test_pdf_uses_unicode_paginated_renderer_and_disables_fetching(monkeypatch):
    from weasyprint import HTML

    captured = {}
    original = HTML.write_pdf

    def inspect(document, **kwargs):
        captured["fetcher"] = document.url_fetcher
        rendered = document.render(stylesheets=kwargs["stylesheets"])
        captured["pages"] = len(rendered.pages)
        captured["title"] = rendered.metadata.title
        return original(document, **kwargs)

    monkeypatch.setattr(HTML, "write_pdf", inspect)
    report = {
        "title": "تقرير الإيرادات",
        "version": 1,
        "language": "ar",
        "sections": [
            {"title": f"القسم {i}", "content": "هذه مراجعة الإيرادات. " * 20} for i in range(20)
        ],
    }
    pdf = render_report_export(report, "pdf")
    assert pdf.startswith(b"%PDF-")
    assert captured["pages"] > 1
    assert captured["title"] == "تقرير الإيرادات"
    for url in ("https://example.invalid/private", "file:///etc/passwd", "data:text/plain,secret"):
        with pytest.raises(ValueError, match="disallowed protocol"):
            captured["fetcher"].fetch(url)
