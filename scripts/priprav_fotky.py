#!/usr/bin/env python3
"""Vytvori webove kopie fotografii bez opakovane ztratove komprese."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = PROJECT_ROOT / "fotky-originaly"
MANIFEST_PATH = SOURCE_ROOT / ".komprese.json"

TARGETS = {
    "kdo-jsem": (PROJECT_ROOT / "content" / "kdo-jsem", "kdo-jsem.jpg"),
    "atelier": (PROJECT_ROOT / "content" / "atelier", None),
    "koncerty": (PROJECT_ROOT / "content" / "koncerty", None),
    "shora": (PROJECT_ROOT / "content" / "shora", None),
    "catering": (PROJECT_ROOT / "content" / "catering", None),
    "svatebni-video": (PROJECT_ROOT / "content" / "svatebni-video", None),
    "interiery": (PROJECT_ROOT / "content" / "interiery", None),
}

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pripravi nove nebo zmenene fotografie pro Hugo galerie."
    )
    parser.add_argument(
        "--max-edge",
        type=int,
        default=2400,
        help="Maximalni delka strany v pixelech (vychozi: 2400).",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=82,
        help="Kvalita JPEG od 1 do 95 (vychozi: 82).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Znovu exportuje vsechny fotografie z originalu.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pouze vypise, co by se zpracovalo.",
    )
    args = parser.parse_args()

    if args.max_edge < 400:
        parser.error("--max-edge musi byt alespon 400 px")
    if not 1 <= args.quality <= 95:
        parser.error("--quality musi byt v rozsahu 1 az 95")
    return args


def load_manifest() -> dict[str, dict[str, object]]:
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if data.get("version") == 1 and isinstance(data.get("files"), dict):
            return data["files"]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {}


def save_manifest(files: dict[str, dict[str, object]]) -> None:
    payload = {"version": 1, "files": files}
    temp_path = MANIFEST_PATH.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temp_path, MANIFEST_PATH)


def safe_stem(filename: str) -> str:
    normalized = unicodedata.normalize("NFKD", filename)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    return slug or "fotografie"


def signature(source: Path, max_edge: int, quality: int) -> dict[str, object]:
    stat = source.stat()
    return {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "max_edge": max_edge,
        "quality": quality,
    }


def flatten_transparency(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def optimize(source: Path, destination: Path, max_edge: int, quality: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination.with_name(f".{destination.name}.tmp")

    with Image.open(source) as opened:
        icc_profile = opened.info.get("icc_profile")
        image = ImageOps.exif_transpose(opened)
        image = flatten_transparency(image)
        image.thumbnail(
            (max_edge, max_edge), Image.Resampling.LANCZOS, reducing_gap=3.0
        )

        save_options: dict[str, object] = {
            "format": "JPEG",
            "quality": quality,
            "optimize": True,
            "progressive": True,
            "subsampling": "4:2:0",
        }
        if icc_profile:
            save_options["icc_profile"] = icc_profile

        image.save(temp_destination, **save_options)

    os.replace(temp_destination, destination)


def main() -> int:
    args = parse_args()
    manifest = load_manifest()
    updated_manifest = dict(manifest)
    processed = 0
    skipped = 0
    errors = 0
    original_bytes = 0
    web_bytes = 0
    claimed_destinations: dict[Path, Path] = {}

    for album, (destination_dir, fixed_filename) in TARGETS.items():
        source_dir = SOURCE_ROOT / album
        source_dir.mkdir(parents=True, exist_ok=True)

        sources = sorted(
            path
            for path in source_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )

        if fixed_filename and len(sources) > 1:
            print(
                f"CHYBA: Ve slozce {source_dir.relative_to(PROJECT_ROOT)} musi byt "
                "prave jeden obrazek.",
                file=sys.stderr,
            )
            errors += 1
            continue

        for source in sources:
            destination = destination_dir / (
                fixed_filename or f"{safe_stem(source.stem)}.jpg"
            )
            previous_source = claimed_destinations.get(destination)
            if previous_source and previous_source != source:
                print(
                    f"CHYBA: {source.name} a {previous_source.name} maji stejny webovy nazev "
                    f"{destination.name}.",
                    file=sys.stderr,
                )
                errors += 1
                continue
            claimed_destinations[destination] = source

            source_key = source.relative_to(PROJECT_ROOT).as_posix()
            current_signature = signature(source, args.max_edge, args.quality)
            manifest_entry = manifest.get(source_key, {})
            unchanged = (
                not args.force
                and destination.exists()
                and manifest_entry.get("signature") == current_signature
                and manifest_entry.get("output")
                == destination.relative_to(PROJECT_ROOT).as_posix()
            )

            if unchanged:
                print(f"PRESKOCENO: {source.relative_to(SOURCE_ROOT)}")
                skipped += 1
                continue

            print(
                f"{'PLAN' if args.dry_run else 'ZPRACOVAVAM'}: "
                f"{source.relative_to(SOURCE_ROOT)} -> "
                f"{destination.relative_to(PROJECT_ROOT)}"
            )
            if args.dry_run:
                continue

            try:
                optimize(source, destination, args.max_edge, args.quality)
                updated_manifest[source_key] = {
                    "signature": current_signature,
                    "output": destination.relative_to(PROJECT_ROOT).as_posix(),
                }
                original_bytes += source.stat().st_size
                web_bytes += destination.stat().st_size
                processed += 1
            except (OSError, ValueError) as error:
                print(f"CHYBA: {source}: {error}", file=sys.stderr)
                errors += 1

    if not args.dry_run:
        save_manifest(updated_manifest)

    print()
    print(f"Hotovo: {processed} zpracovano, {skipped} beze zmeny, {errors} chyb.")
    if processed and original_bytes:
        reduction = 100 * (1 - web_bytes / original_bytes)
        print(
            f"Nova webova data: {web_bytes / 1024 / 1024:.1f} MB "
            f"(uspora {reduction:.1f} % oproti originalum)."
        )

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
