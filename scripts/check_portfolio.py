"""Verify portfolio links, frozen facts and actual media; optional explicit media export.

FFmpeg/FFprobe are optional presentation tooling, not application dependencies.
This command never calls models, changes evaluation labels or stages Git files.
"""

import argparse
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MEDIA_MANIFEST = ROOT / "data/manifests/t5_4_portfolio_media.json"
TEXT_BINDINGS = ROOT / "data/manifests/t5_4_portfolio_text_bindings.json"
ASSETS = ROOT / "docs/assets"
DOCS = [
    ROOT / "README.md",
    ROOT / "docs/architecture.md",
    ROOT / "docs/interview.md",
    ROOT / "docs/portfolio-demo.md",
    ROOT / "docs/portfolio-review.md",
    ROOT / "docs/portfolio.html",
]


def fingerprint(file):
    return sha256(file.read_bytes()).hexdigest()


def lf_fingerprint(file):
    return sha256(file.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load(file):
    return json.loads(file.read_text(encoding="utf-8"))


def command(arguments):
    return subprocess.run(arguments, check=True, capture_output=True, text=True, encoding="utf-8")


def probe(file):
    result = json.loads(
        command(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(file)]
        ).stdout
    )
    streams = result["streams"]
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    return {
        "sha256": fingerprint(file),
        "size_bytes": file.stat().st_size,
        "width": video["width"],
        "height": video["height"],
        "codec": video["codec_name"],
        "pixel_format": video["pix_fmt"],
        "duration_seconds": float(result["format"].get("duration", 0)),
        "frame_rate": video["avg_frame_rate"],
        "audio_streams": sum(stream["codec_type"] == "audio" for stream in streams),
    }


def fast_start(file):
    boxes = []
    with file.open("rb") as handle:
        while header := handle.read(8):
            size, name = int.from_bytes(header[:4]), header[4:]
            extra = 0
            if size == 1:
                size, extra = int.from_bytes(handle.read(8)), 8
            if size < 8 + extra:
                break
            boxes.append(name)
            handle.seek(size - 8 - extra, 1)
    return b"moov" in boxes and b"mdat" in boxes and boxes.index(b"moov") < boxes.index(b"mdat")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []
        self.ids = set()
        self.external_assets = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        for name in ("href", "src"):
            if target := attributes.get(name):
                self.targets.append(target)
                if tag != "a" and urlsplit(target).scheme in ("http", "https"):
                    self.external_assets.append(target)


def explicit_export(recording_dir, encode, checks):
    recording_dir = recording_dir.resolve()
    assert recording_dir.is_relative_to(ROOT / "data/processed"), "raw footage must be ignored"
    recording = load(recording_dir / "recording.json")
    assert recording["passed"] and recording["schema_version"] == "portfolio-recording-v1"
    assert recording["live_development_requests"] == 3
    assert recording["new_held_out_inference_requests"] == 0
    assert recording["response_interception"] is False and recording["voice_over"] is False
    assert [row["case_id"] for row in recording["cases"]] == ["DEV-SUMMER", "D31", "D46"]
    assert [row["status"] for row in recording["cases"]] == [
        "answered",
        "answered",
        "insufficient_evidence",
    ]
    checks.append("live development recording / 0 new held-out / no response interception")
    for file, digest in recording["input_file_sha256"].items():
        assert fingerprint(ROOT / file) == digest, f"frozen input changed: {file}"
    checks.append("recording input hashes remain unchanged")

    video = recording_dir / "regularag-demo.mp4"
    if encode:
        assert not video.exists(), "encode must not overwrite an earlier export"
        command(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "warning",
                "-n",
                "-i",
                str(recording_dir / recording["raw_video"]),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "26",
                "-r",
                "15",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-an",
                str(video),
            ]
        )
    info = probe(video)
    assert 180 <= info["duration_seconds"] <= 300 and info["codec"] == "h264"
    assert info["audio_streams"] == 0 and fast_start(video)
    checks.append("explicit MP4 export / H.264 / 3–5min / captions only / faststart")

    # V1's source-focused viewport clips the lower answer. Use its actual pre-click
    # video frame for the public answer image; never reconstruct text or a response.
    answer = recording_dir / "demo-answer.png"
    if (recording_dir / "frame-multi-answer.png").exists():
        answer = recording_dir / "frame-multi-answer.png"
    source = recording_dir / "demo-source.png"
    if not source.exists():
        source = recording_dir / "demo-answer.png"
    pairs = {
        "demo-answer.png": answer,
        "demo-source.png": source,
        "demo-workspace.png": recording_dir / "demo-workspace.png",
        "demo-no-answer.png": recording_dir / "demo-no-answer.png",
        "regularag-demo.mp4": video,
    }
    assert ASSETS.is_dir() and not MEDIA_MANIFEST.exists(), "explicit export requires new targets"
    for name, input_file in pairs.items():
        assert input_file.is_file() and not (ASSETS / name).exists(), f"refuse overwrite: {name}"
    for name, input_file in pairs.items():
        shutil.copyfile(input_file, ASSETS / name)
    assets = {f"docs/assets/{name}": probe(ASSETS / name) for name in pairs}
    assets["docs/assets/architecture.svg"] = {
        "sha256": fingerprint(ASSETS / "architecture.svg"),
        "size_bytes": (ASSETS / "architecture.svg").stat().st_size,
    }
    manifest = {
        "schema_version": "portfolio-media-v1",
        "recorded_at": recording["recorded_at"],
        "browser_channel": recording["browser_channel"],
        "browser_version": recording["browser_version"],
        "recording_sha256": fingerprint(recording_dir / recording["raw_video"]),
        "recording_assertions": recording["assertions"],
        "input_file_sha256": recording["input_file_sha256"],
        "cases": recording["cases"],
        "scenes": recording["scenes"],
        "assets": assets,
        "live_development_requests": 3,
        "new_held_out_inference_requests": 0,
        "response_interception": False,
        "voice_over": False,
        "public_excerpt_ids": ["class_size", "summer"],
        "answer_image_origin": "Actual continuous footage at 114s"
        if answer.name.startswith("frame-")
        else "Actual live browser viewport before citation scroll",
        "conditions": recording["notes"],
        "publication_scope": recording["published_source_content"],
    }
    with MEDIA_MANIFEST.open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return manifest


def seal_text_bindings(manifest):
    """Seal a new presentation-only CRLF/LF registry from exact recorded bytes.

    This never rewrites original inputs/freezes, and cannot seal drifted inputs.
    It does not normalize inference code or the evaluation runner's source guards.
    """
    files = dict(manifest["input_file_sha256"])
    files["docs/assets/architecture.svg"] = manifest["assets"]["docs/assets/architecture.svg"][
        "sha256"
    ]
    for file, digest in files.items():
        assert fingerprint(ROOT / file) == digest, f"refuse to seal drifted bytes: {file}"
    result = {
        "schema_version": "portfolio-text-checkout-v1",
        "media_manifest_lf_sha256": lf_fingerprint(MEDIA_MANIFEST),
        "lf_sha256": {file: lf_fingerprint(ROOT / file) for file in files},
        "conditions": "Presentation-reader-only Git CRLF/LF equivalence, sealed from "
        "exact recording bytes. Original raw hashes/freezes/runner source guards remain "
        "unchanged; not historical inference reproduction.",
    }
    with TEXT_BINDINGS.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"text_bindings_sealed": True, "files": len(files)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording", type=Path, help="ignored raw capture directory")
    parser.add_argument("--encode", action="store_true", help="explicit FFmpeg MP4 conversion")
    parser.add_argument(
        "--publish-media", action="store_true", help="copy curated media to new Git-visible assets"
    )
    parser.add_argument("--summary", type=Path, help="write a new ID/hash-only validation summary")
    parser.add_argument(
        "--seal-text-bindings", action="store_true", help="seal new checkout-only CRLF/LF registry"
    )
    args = parser.parse_args()
    assert not args.encode or args.publish_media, "encoding requires explicit export"
    assert not args.publish_media or args.recording, "export requires actual recording"
    assert not args.seal_text_bindings or not (args.publish_media or args.summary)
    checks = []
    if args.publish_media:
        assert args.summary is None, "export media first; run full validation separately"
        explicit_export(args.recording, args.encode, checks)
        print(json.dumps({"media_exported": True, "export_checks": checks}, indent=2))
        return
    manifest = load(MEDIA_MANIFEST)
    if args.seal_text_bindings:
        seal_text_bindings(manifest)
        return
    assert manifest["schema_version"] == "portfolio-media-v1"
    text_bindings = load(TEXT_BINDINGS)
    assert text_bindings["schema_version"] == "portfolio-text-checkout-v1"
    assert lf_fingerprint(MEDIA_MANIFEST) == text_bindings["media_manifest_lf_sha256"]
    checkout_eol_differences = []

    def same_recorded_content(file, digest):
        if fingerprint(ROOT / file) == digest:
            return True
        if (
            file in text_bindings["lf_sha256"]
            and lf_fingerprint(ROOT / file) == text_bindings["lf_sha256"][file]
        ):
            checkout_eol_differences.append(file)
            return True
        return False

    for file, expected in manifest["assets"].items():
        asset = ROOT / file
        assert same_recorded_content(file, expected["sha256"]), f"media drift: {file}"
        if asset.suffix != ".svg":
            assert probe(asset) == expected, f"probe drift: {file}"
    checks.append("public media SHA/dimensions/codec/duration verified")
    video_file = ASSETS / "regularag-demo.mp4"
    video = manifest["assets"]["docs/assets/regularag-demo.mp4"]
    assert 180 <= video["duration_seconds"] <= 300
    assert (video["width"], video["height"], video["pixel_format"]) == (1440, 900, "yuv420p")
    assert fast_start(video_file)
    command(["ffmpeg", "-v", "error", "-xerror", "-i", str(video_file), "-f", "null", "-"])
    checks.append("entire MP4 decodes without error / faststart / duration3–5min")
    for file, digest in manifest["input_file_sha256"].items():
        assert same_recorded_content(file, digest), f"bound evaluation input drift: {file}"
    checks.append(
        "bound dataset/config/M4 metrics/freeze/ledger content unchanged; "
        "only Git CRLF/LF equivalence"
    )

    dev = load(ROOT / "data/manifests/t4_4_development_metrics.json")
    test = load(ROOT / "data/manifests/t4_4_held_out_metrics.json")
    expected = {
        "correctness": ((47, 47), (19, 28)),
        "required_fact_recall": ((65, 65), (32, 43)),
        "citation_support_precision": ((60, 60), (29, 108)),
        "faithfulness": ((60, 60), (108, 108)),
        "correct_rejection": ((8, 8), (0, 7)),
        "clarification_field_recall": ((12, 12), (0, 20)),
    }
    for key, (dev_value, test_value) in expected.items():
        for metrics, pair in ((dev, dev_value), (test, test_value)):
            metric = metrics["answers"]["overall"][key]
            assert (metric["numerator"], metric["denominator"]) == pair
    assert round(test["operations"]["stages"]["end_to_end_ms"]["p95"] / 1000, 3) == 32.707
    for name in ("README.md", "docs/portfolio.html", "docs/interview.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert all(number in text for number in ("19/28", "29/108", "108/108", "32.707"))
    checks.append(
        "portfolio benchmark numerators/denominators/p95 match frozen authoritative metrics"
    )

    links_checked, output_links = 0, []
    for file in DOCS:
        text = file.read_text(encoding="utf-8")
        if file.suffix == ".html":
            reader = Links()
            reader.feed(text)
            assert not reader.external_assets, "deck must be offline/self-contained"
            targets = reader.targets
        else:
            targets = re.findall(r"!?\[[^\]]*\]\(([^\s)]+)\)", text)
        for target in targets:
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path:
                continue
            linked = (file.parent / unquote(parsed.path)).resolve()
            if args.summary and linked == args.summary.resolve() and not linked.exists():
                output_links.append(linked)
                links_checked += 1
                continue
            assert linked.is_file() and linked.is_relative_to(ROOT), (
                f"broken link: {file.name} → {target}"
            )
            if parsed.fragment and linked.suffix == ".html":
                reader = Links()
                reader.feed(linked.read_text(encoding="utf-8"))
                assert parsed.fragment in reader.ids, f"missing slide anchor: {target}"
            links_checked += 1
    checks.append(f"{links_checked} local document/media links and HTML anchors resolve")
    result = {
        "schema_version": "portfolio-validation-v1",
        "checked_at": datetime.now(UTC).isoformat(),
        "passed": True,
        "assertions": checks,
        "media_manifest_sha256": fingerprint(MEDIA_MANIFEST),
        "video_sha256": fingerprint(video_file),
        "video_duration_seconds": video["duration_seconds"],
        "local_links_checked": links_checked,
        "new_held_out_inference_requests": 0,
        "text_checkout_line_endings_only": checkout_eol_differences,
        "conditions": "Static portfolio/media/frozen-fact checks; no inference "
        "or independent human presentation/quality review.",
    }
    if args.summary:
        with args.summary.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    assert all(file.is_file() for file in output_links), "output report links must resolve"
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
