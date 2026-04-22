from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

import app as app_module


def _workspace_temp_dir(prefix: str) -> Path:
    path = Path("outputs") / f"{prefix}_{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_jpeg(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="JPEG")


def test_build_listing_result_renders_large_preview_from_existing_backend_data(monkeypatch):
    tmp_path = _workspace_temp_dir("verify_result")
    try:
        session_id = "verifysession"
        pack_dir = tmp_path / session_id / "listing_output"
        _write_jpeg(pack_dir / "Facebook_Post_Optimized" / "hero.jpg", (1080, 1350), (210, 120, 80))
        _write_jpeg(pack_dir / "Website_Optimized" / "square.jpg", (1200, 1200), (80, 120, 210))
        (pack_dir / "listing_description.txt").write_text("2021 BOBCAT T66\nNice machine", encoding="utf-8")
        (pack_dir / "metadata_internal.json").write_text(
            json.dumps({"year": 2021, "make": "Bobcat", "model": "T66", "image_count": 2}),
            encoding="utf-8",
        )

        monkeypatch.setattr(app_module, "_OUTPUTS_DIR", str(tmp_path))
        client = TestClient(app_module.app)

        resp = client.get(f"/build-listing/result/{session_id}")
        assert resp.status_code == 200
        html = resp.text
        assert 'id="image-preview-stage"' in html
        assert 'id="image-preview-primary"' in html
        assert 'class="thumb-card active"' in html
        assert "Facebook Post Optimized" in html
        assert "/outputs/verifysession/listing_output/Facebook_Post_Optimized/hero.jpg" in html
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_listing_frontend_clears_draft_only_after_success_result_url():
    html = Path("templates/build_listing.html").read_text(encoding="utf-8")
    assert html.count("clearBuildListingDraft();") == 1
    assert "if (data.result_url) {" in html
    success_idx = html.index("if (data.result_url) {")
    clear_idx = html.index("clearBuildListingDraft();")
    redirect_idx = html.index("window.location.href = data.result_url;")
    assert success_idx < clear_idx < redirect_idx


