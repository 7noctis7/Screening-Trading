import os, tempfile

import pytest

from packages.reporting import build_tearsheet_html, to_pdf


def test_html_contains_metrics():
    html = build_tearsheet_html("T", {"Sharpe": "0.46"}, [100, 101, 102])
    assert "Sharpe" in html and "<svg" in html


def test_pdf_is_written():
    pytest.importorskip("reportlab")            # PDF optionnel : sauté si la lib n'est pas installée
    p = os.path.join(tempfile.mkdtemp(), "ts.pdf")
    to_pdf("T", {"Sharpe": "0.46"}, [100, 102, 101, 105], p)
    assert os.path.getsize(p) > 500
