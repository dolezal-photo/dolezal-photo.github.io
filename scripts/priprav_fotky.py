#!/usr/bin/env python3
"""Vytvori webove kopie fotografii bez opakovane ztratove komprese."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageCms, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = PROJECT_ROOT / "fotky-originaly"
MANIFEST_PATH = SOURCE_ROOT / ".komprese.json"
SETTINGS_PATH = SOURCE_ROOT / "nastaveni.json"
LOGO_DESTINATION = PROJECT_ROOT / "assets" / "images" / "logo.png"

TARGETS = {
    "kdo-jsem": PROJECT_ROOT / "content" / "kdo-jsem",
    "atelier": PROJECT_ROOT / "content" / "portfolio" / "atelier",
    "koncerty": PROJECT_ROOT / "content" / "portfolio" / "koncerty",
    "shora": PROJECT_ROOT / "content" / "portfolio" / "shora",
    "catering": PROJECT_ROOT / "content" / "portfolio" / "catering",
    "svatebni-video": PROJECT_ROOT / "content" / "portfolio" / "svatebni-video",
    "interiery": PROJECT_ROOT / "content" / "portfolio" / "interiery",
}

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
PORTFOLIO_ALBUMS = tuple(album for album in TARGETS if album != "kdo-jsem")
MEDIA_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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
    parser.add_argument(
        "--check",
        action="store_true",
        help="Pouze overi uplnost a spravnost nastaveni.",
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
        files = data.get("files")
        if data.get("version") == 2 and isinstance(files, dict):
            return files
        if data.get("version") == 1 and isinstance(files, dict):
            migrated: dict[str, dict[str, object]] = {}
            for source_key, entry in files.items():
                if not isinstance(entry, dict):
                    continue
                output_key = entry.get("output")
                signature_data = entry.get("signature")
                if isinstance(output_key, str) and isinstance(signature_data, dict):
                    migrated[output_key] = {
                        "source": source_key,
                        "signature": signature_data,
                    }
            return migrated
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {}


def save_manifest(files: dict[str, dict[str, object]]) -> None:
    payload = {"version": 2, "files": files}
    temp_path = MANIFEST_PATH.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temp_path, MANIFEST_PATH)


def load_settings() -> dict[str, object]:
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Chybi nastaveni {SETTINGS_PATH.name}.") from error
    except (json.JSONDecodeError, OSError) as error:
        raise ValueError(f"Nelze precist {SETTINGS_PATH.name}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"{SETTINGS_PATH.name} musi obsahovat JSON objekt.")
    if data.get("schema_version") != 2:
        raise ValueError("schema_version musi byt 2.")

    for section in ("media", "spolecne", "uvod", "portfolio", "kdo_jsem", "kontakt"):
        if not isinstance(data.get(section), dict):
            raise ValueError(f"Chybi povinna sekce {section}.")

    media = data["media"]
    listed_sources: dict[str, str] = {}
    for media_id, item in media.items():
        if not isinstance(media_id, str) or not MEDIA_ID_PATTERN.fullmatch(media_id):
            raise ValueError(f"Neplatne ID media: {media_id!r}.")
        if not isinstance(item, dict):
            raise ValueError(f"Media {media_id} musi byt JSON objekt.")

        media_type = item.get("typ")
        relative_source = item.get("soubor")
        status = item.get("stav")
        alt = item.get("alt")
        if media_type not in {"fotografie", "logo"}:
            raise ValueError(f"Media {media_id} ma neznamy typ {media_type!r}.")
        if status not in {"aktivni", "rezerva"}:
            raise ValueError(f"Media {media_id} ma neznamy stav {status!r}.")
        if not isinstance(relative_source, str) or not relative_source:
            raise ValueError(f"Media {media_id} nema platnou cestu souboru.")
        if not isinstance(alt, str):
            raise ValueError(f"Media {media_id} nema text alt.")
        if media_type == "fotografie" and status == "aktivni" and not alt.strip():
            raise ValueError(f"Aktivni fotografie {media_id} musi mit vyplneny alt.")

        relative_path = Path(relative_source)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"Media {media_id} ma nebezpecnou cestu.")
        source = (SOURCE_ROOT / relative_path).resolve()
        if not source.is_relative_to(SOURCE_ROOT.resolve()):
            raise ValueError(f"Media {media_id} smeruje mimo fotky-originaly.")
        if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Media {media_id} nema podporovany format.")
        if not source.is_file():
            raise ValueError(f"Soubor media {media_id} neexistuje: {relative_source}.")
        if relative_source in listed_sources:
            raise ValueError(
                f"Soubor {relative_source} je duplicitne u {listed_sources[relative_source]} "
                f"a {media_id}."
            )
        listed_sources[relative_source] = media_id

    actual_sources = {
        path.relative_to(SOURCE_ROOT).as_posix()
        for path in SOURCE_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    }
    unlisted = sorted(actual_sources - set(listed_sources))
    if unlisted:
        raise ValueError(
            "V katalogu media chybi soubory: " + ", ".join(unlisted)
        )
    missing = sorted(set(listed_sources) - actual_sources)
    if missing:
        raise ValueError(
            "Katalog media odkazuje na chybejici soubory: " + ", ".join(missing)
        )

    portfolio = data["portfolio"]
    categories = portfolio.get("kategorie")
    if not isinstance(categories, list):
        raise ValueError("portfolio.kategorie musi byt seznam.")

    category_ids: list[str] = []
    used_media: set[str] = set()
    for category in categories:
        if not isinstance(category, dict):
            raise ValueError("Kazda kategorie portfolia musi byt JSON objekt.")
        album = category.get("id")
        photo_ids = category.get("fotografie")
        cover_id = category.get("titulni_fotografie")
        if album not in PORTFOLIO_ALBUMS:
            raise ValueError(f"Neznama kategorie portfolia: {album!r}.")
        if album in category_ids:
            raise ValueError(f"Kategorie {album} je v JSON vicekrat.")
        category_ids.append(album)
        if not isinstance(photo_ids, list) or not photo_ids or not all(
            isinstance(media_id, str) for media_id in photo_ids
        ):
            raise ValueError(f"Kategorie {album} musi mit seznam fotografii.")
        if len(photo_ids) != len(set(photo_ids)):
            raise ValueError(f"Kategorie {album} obsahuje duplicitni fotografii.")
        if cover_id not in photo_ids:
            raise ValueError(
                f"Titulni fotografie kategorie {album} musi byt i v jejim seznamu."
            )
        for media_id in photo_ids:
            item = media.get(media_id)
            if not isinstance(item, dict):
                raise ValueError(f"Kategorie {album} odkazuje na nezname media {media_id}.")
            if item.get("typ") != "fotografie":
                raise ValueError(f"Media {media_id} v kategorii {album} neni fotografie.")
            if Path(item["soubor"]).parts[0] != album:
                raise ValueError(
                    f"Fotografie {media_id} nelezi ve slozce kategorie {album}."
                )
            used_media.add(media_id)

    if set(category_ids) != set(PORTFOLIO_ALBUMS):
        absent = sorted(set(PORTFOLIO_ALBUMS) - set(category_ids))
        raise ValueError("V JSON chybi kategorie: " + ", ".join(absent))

    references = {
        data["spolecne"].get("logo", {}).get("media"),
        data["uvod"].get("hero", {}).get("fotografie"),
        data["uvod"].get("o_mne", {}).get("fotografie"),
        data["kdo_jsem"].get("fotografie"),
    }
    for media_id in references:
        if not isinstance(media_id, str) or media_id not in media:
            raise ValueError(f"Stranka odkazuje na nezname media {media_id!r}.")
        used_media.add(media_id)

    logo_id = data["spolecne"]["logo"]["media"]
    if media[logo_id].get("typ") != "logo":
        raise ValueError("spolecne.logo.media musi odkazovat na typ logo.")
    portrait_id = data["kdo_jsem"]["fotografie"]
    if Path(media[portrait_id]["soubor"]).parts[0] != "kdo-jsem":
        raise ValueError("kdo_jsem.fotografie musi byt ze slozky kdo-jsem.")

    for media_id in used_media:
        if media[media_id].get("stav") != "aktivni":
            raise ValueError(
                f"Pouzite media {media_id} je oznaceno jako rezerva; zmen stav na aktivni."
            )
    unused_active = sorted(
        media_id
        for media_id, item in media.items()
        if item.get("stav") == "aktivni" and media_id not in used_media
    )
    if unused_active:
        raise ValueError(
            "Aktivni media nejsou nikde pouzita: " + ", ".join(unused_active)
        )

    return data


def is_managed_output(relative_path: str) -> bool:
    try:
        output = (PROJECT_ROOT / relative_path).resolve()
        return output == LOGO_DESTINATION.resolve() or (
            output.suffix.lower() == ".jpg"
            and any(
                output.is_relative_to(destination_dir.resolve())
                for destination_dir in TARGETS.values()
            )
        )
    except (OSError, ValueError):
        return False

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
        if icc_profile:
            # Hugo vytváří další náhledy. Převod do sRGB před exportem zajistí
            # stejné barvy i v odvozených obrázcích bez vloženého profilu.
            srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
            image = ImageCms.profileToProfile(
                image, ImageCms.ImageCmsProfile(io.BytesIO(icc_profile)),
                srgb, outputMode="RGB",
            )
            icc_profile = srgb.tobytes()
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


def optimize_logo(source: Path, destination: Path, max_edge: int) -> None:
    """Zmensi logo, odstrani prazdne bile okraje a zachova format PNG."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination.with_name(f".{destination.name}.tmp")

    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGBA")

        # Pro nalezeni obsahu se logo slozi na bile pozadi. Tenkou krajni
        # linku ignorujeme, aby exportni artefakt nerozbil automaticky orez.
        white = Image.new("RGBA", image.size, "white")
        composited = Image.alpha_composite(white, image).convert("RGB")
        difference = ImageChops.difference(
            composited, Image.new("RGB", composited.size, "white")
        ).convert("L")
        mask = difference.point(lambda value: 255 if value > 12 else 0)
        width, height = mask.size
        edge = max(12, round(min(width, height) * 0.005))
        if width > edge * 2 and height > edge * 2:
            mask.paste(0, (0, 0, width, edge))
            mask.paste(0, (0, height - edge, width, height))
            mask.paste(0, (0, 0, edge, height))
            mask.paste(0, (width - edge, 0, width, height))
        content_box = mask.getbbox()
        if content_box:
            left, top, right, bottom = content_box
            padding = max(8, round(max(right - left, bottom - top) * 0.025))
            crop_box = (
                max(0, left - padding),
                max(0, top - padding),
                min(image.width, right + padding),
                min(image.height, bottom + padding),
            )
            image = image.crop(crop_box)

        image.thumbnail(
            (min(max_edge, 1800), min(max_edge, 1800)),
            Image.Resampling.LANCZOS,
            reducing_gap=3.0,
        )
        image.save(temp_destination, format="PNG", optimize=True)

    os.replace(temp_destination, destination)


def build_tasks(settings: dict[str, object]) -> list[tuple[Path, Path, str]]:
    tasks: list[tuple[Path, Path, str]] = []
    media = settings["media"]
    for media_id, item in media.items():
        if item["stav"] != "aktivni":
            continue
        source = SOURCE_ROOT / item["soubor"]
        if item["typ"] == "logo":
            destination = LOGO_DESTINATION
            kind = "logo"
        else:
            source_section = Path(item["soubor"]).parts[0]
            destination = TARGETS[source_section] / f"{media_id}.jpg"
            kind = "photo"
        tasks.append((source, destination, kind))
    return tasks


def main() -> int:
    args = parse_args()
    try:
        settings = load_settings()
    except ValueError as error:
        print(f"CHYBA: {error}", file=sys.stderr)
        return 1

    tasks = build_tasks(settings)
    if args.check:
        reserve_count = sum(
            1 for item in settings["media"].values() if item["stav"] == "rezerva"
        )
        print(
            f"Nastaveni je v poradku: {len(settings['media'])} medii, "
            f"{len(tasks)} aktivnich a {reserve_count} rezervnich."
        )
        return 0

    manifest = load_manifest()
    updated_manifest = dict(manifest)
    processed = 0
    skipped = 0
    errors = 0
    original_bytes = 0
    web_bytes = 0
    removed = 0
    active_output_paths = {
        destination.relative_to(PROJECT_ROOT).as_posix()
        for _, destination, _ in tasks
    }

    for source, destination, kind in tasks:
        source_key = source.relative_to(PROJECT_ROOT).as_posix()
        output_key = destination.relative_to(PROJECT_ROOT).as_posix()
        current_signature = signature(source, args.max_edge, args.quality)
        if kind == "logo":
            current_signature["processor"] = "logo-v2"
        else:
            current_signature["processor"] = "photo-v2-srgb"
        manifest_entry = manifest.get(output_key, {})
        unchanged = (
            not args.force
            and destination.exists()
            and manifest_entry.get("source") == source_key
            and manifest_entry.get("signature") == current_signature
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
            if kind == "logo":
                optimize_logo(source, destination, args.max_edge)
            else:
                optimize(source, destination, args.max_edge, args.quality)
            updated_manifest[output_key] = {
                "source": source_key,
                "signature": current_signature,
            }
            original_bytes += source.stat().st_size
            web_bytes += destination.stat().st_size
            processed += 1
        except (OSError, ValueError) as error:
            print(f"CHYBA: {source}: {error}", file=sys.stderr)
            errors += 1

    if not args.dry_run and errors == 0:
        stale_outputs = set(updated_manifest) - active_output_paths
        for output_key in sorted(stale_outputs):
            updated_manifest.pop(output_key, None)
            if not is_managed_output(output_key):
                continue
            output_path = PROJECT_ROOT / output_key
            if output_path.exists():
                output_path.unlink()
                print(f"ODSTRANENO: {output_key}")
                removed += 1

    if not args.dry_run and errors == 0:
        save_manifest(updated_manifest)

    print()
    print(
        f"Hotovo: {processed} zpracovano, {skipped} beze zmeny, "
        f"{removed} starych kopii odstraneno, {errors} chyb."
    )
    if processed and original_bytes:
        reduction = 100 * (1 - web_bytes / original_bytes)
        print(
            f"Nova webova data: {web_bytes / 1024 / 1024:.1f} MB "
            f"(uspora {reduction:.1f} % oproti originalum)."
        )

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
