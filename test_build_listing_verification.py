from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageChops

import app as app_module
from image_pack_generator import _apply_branding_overlay


def _workspace_temp_dir(prefix: str) -> Path:
    path = Path("outputs") / f"{prefix}_{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_jpeg(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="JPEG")


def _region_diff_bbox(before: Image.Image, after: Image.Image, box: tuple[int, int, int, int]):
    left, top, right, bottom = box
    before_crop = before.crop((left, top, right, bottom))
    after_crop = after.crop((left, top, right, bottom))
    return ImageChops.difference(before_crop, after_crop).getbbox()


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


def test_branding_overlay_handles_logo_text_and_aspect_ratio_combinations():
    tmp_path = _workspace_temp_dir("verify_overlay")
    try:
        logo_path = tmp_path / "logo.png"
        logo = Image.new("RGBA", (420, 180), (0, 0, 0, 0))
        logo.paste((255, 255, 255, 255), (40, 35, 380, 145))
        logo.save(logo_path)

        cases = [
            {"size": (1080, 1350), "logo": True, "text": "Jane Smith  •  555-123-4567", "expect_left": True, "expect_right": True},
            {"size": (1200, 1200), "logo": True, "text": None, "expect_left": None, "expect_right": True},
            {"size": (1080, 1920), "logo": False, "text": "Jane Smith  •  555-123-4567", "expect_left": True, "expect_right": None},
            {"size": (1080, 1350), "logo": True, "text": "Very Long Dealer Contact Name  •  800-555-1212 ext 987  •  www.exampledealer.com", "expect_left": True, "expect_right": True},
        ]

        for case in cases:
            base = Image.new("RGB", case["size"], (36, 52, 68))
            out = _apply_branding_overlay(
                base,
                str(logo_path) if case["logo"] else None,
                case["text"],
                "ACME EQUIPMENT",
            )
            assert out.size == base.size

            left_box = (0, int(case["size"][1] * 0.72), int(case["size"][0] * 0.45), case["size"][1])
            right_box = (int(case["size"][0] * 0.62), int(case["size"][1] * 0.72), case["size"][0], case["size"][1])
            left_changed = _region_diff_bbox(base, out, left_box) is not None
            right_changed = _region_diff_bbox(base, out, right_box) is not None

            if case["expect_left"] is not None:
                assert left_changed is case["expect_left"]
            if case["expect_right"] is not None:
                assert right_changed is case["expect_right"]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_branding_overlay_falls_back_to_text_when_logo_is_unusable():
    tmp_path = _workspace_temp_dir("verify_overlay_fallback")
    try:
        tiny_logo_path = tmp_path / "tiny_logo.png"
        tiny_logo = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
        tiny_logo.paste((255, 255, 255, 255), (6, 6, 14, 14))
        tiny_logo.save(tiny_logo_path)

        base = Image.new("RGB", (1200, 1200), (62, 78, 94))
        out = _apply_branding_overlay(base, str(tiny_logo_path), None, "ACME EQUIPMENT")

        right_box = (int(base.width * 0.62), int(base.height * 0.72), base.width, base.height)
        assert _region_diff_bbox(base, out, right_box) is not None
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
