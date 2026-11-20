#!/usr/bin/env python3
"""
Build the data layer for the German Psaltica Hugo site.

The script scans notations/, extracts useful metadata from every PDF,
renders first-page previews into static/thumbs/ and generates:

  data/library.json                 catalog data for the landing page
  content/library/**/_index.md      one page for every folder
  content/library/**/<note>.md      one page for every PDF

It is intentionally dependency-free (Python standard library + poppler-utils).
Run it again whenever PDFs are added, removed or renamed:

    python3 scripts/build_library.py

Options:
    --no-thumbs       skip preview generation (fast)
    --force-thumbs    regenerate all previews
    --jobs N          number of parallel PDF workers (default: 4)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "notations"
CONTENT_LIBRARY = ROOT / "content" / "library"
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "library.json"
CATEGORIES_FILE = ROOT / "categories.json"
THUMBS_DIR = ROOT / "static" / "thumbs"

THUMB_SIZE = 640
THUMB_QUALITY = 80
GENERATOR_VERSION = "1"

# ---------------------------------------------------------------------------
# Names, modes, archive detection
# ---------------------------------------------------------------------------

FOLDER_NAMES = {
    "01_Liturgie": "Liturgie",
    "02_Troparien": "Troparien",
    "03_Kondakien": "Kondakien",
    "04_Morgenlob": "Morgenlob",
    "05_Vesper": "Vesper",
    "06_Psalmen": "Psalmen",
    "07_Andere Gottesdienste": "Andere Gottesdienste",
    "08_Pas'cha": "Pas'cha",
    "99_Archiv": "Archiv",
    "00_Feste_Teile": "Feste Teile",
    "01_Zum Einzug_Feste": "Zum Einzug (Feste)",
    "02_Trisagion": "Trisagion",
    "03_Cherubikon": "Cherubikon",
    "04_Liturgika": "Liturgika",
    "05_Es ist wahrhaft würdig": "Es ist wahrhaft würdig",
    "06_9. Ode Festtage": "9. Ode (Festtage)",
    "07_Kinonikon": "Kinonikon",
    "08_Als Teilnehmer an Deinem Mystischen Mahl": "Als Teilnehmer an Deinem Mystischen Mahl",
    "09_Liturgie_Hl Basilius": "Liturgie des Hl. Basilius",
    "10_Vorgeweihten Gaben": "Vorgeweihte Gaben",
    "11_Sammlungen": "Sammlungen",
    "01_Statt Cherubikon": "Statt Cherubikon",
    "02_Statt WahrhaftWürdig": "Statt „Wahrhaft würdig“",
    "Anti_axion_estin": "Anti Axion Estin",
    "Vesperale Liturgie": "Vesperale Liturgie",
    "Sonntag_Auferstehung": "Sonntag der Auferstehung",
    "Priester_Weihe": "Priesterweihe",
    "Kanons und Katavasias": "Kanons und Katavasien",
    "Orthros Projekt 2024": "Orthros-Projekt 2024",
    "Heiligen": "Heilige",
    "Feste Teile": "Feste Teile",
    "Feste": "Feste",
    "Festtage": "Festtage",
    "Archiv": "Archiv",
    "archiv": "Archiv",
    "Archive": "Archiv",
    "corrections": "Korrekturen",
    "alt": "Alte Fassungen",
    "Vorübergehende Versionen": "Vorübergehende Versionen",
    "Panorthodoxe Jugendtreffen": "Panorthodoxe Jugendtreffen",
    "Apostellesung": "Apostellesung",
    "Doxologie": "Doxologie",
    "Trisagion_Pascha": "Trisagion (Pas'cha)",
    "9.Ode": "9. Ode",
    "Totengedenken": "Totengedenken",
}

ARCHIVE_DIRS = {
    "archiv",
    "archive",
    "alt",
    "vorübergehende versionen",
}

MODE_RE = re.compile(
    r"(?<!\d)([1-8])\s*[.\-_ ]?\s*(?:modus|mode(?:extended)?|m)"
    r"(?![a-zA-ZäöüÄÖÜß])",
    re.IGNORECASE,
)

MODE_FOLDER_RE = re.compile(
    r"^\s*([1-8])\s*[.\-_ ]?\s*(?:modus|mode(?:extended)?|m)\s*$",
    re.IGNORECASE,
)

MODE_NAME_RE = re.compile(
    r"^\s*([1-8])\s*[.\-_ ]?\s*(?:modus|mode(?:extended)?|m)"
    r"(?=$|[\s._\-])",
    re.IGNORECASE,
)

STATUS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(?:\d+(?:st|nd|rd|th)\s+)?(?:draft|entwurf)\s*\d*\b", re.IGNORECASE),
        "Entwurf",
    ),
    (re.compile(r"\bv\.?\s*([1-9])\b", re.IGNORECASE), "v"),
    (re.compile(r"\bversion\s*([1-9])\b", re.IGNORECASE), "v"),
    (re.compile(r"\bv([1-9])\b", re.IGNORECASE), "v"),
    (re.compile(r"\bnot[ _]+complete\b", re.IGNORECASE), "Unvollständig"),
    (re.compile(r"\bnicht[ _]+fertig\b", re.IGNORECASE), "Unvollständig"),
    (re.compile(r"\bwip\b", re.IGNORECASE), "WIP"),
    (re.compile(r"\b(?:old|alt)\b", re.IGNORECASE), "Alt"),
    (re.compile(r"\bfinal\b", re.IGNORECASE), "Final"),
    (re.compile(r"\bkorrigiert\b", re.IGNORECASE), "Korrigiert"),
]

GENERIC_TITLE_WORDS = {
    "sammlung",
    "sammlungen",
    "kurz",
    "kurze",
    "lang",
    "lange",
    "langversion",
    "langeversion",
    "vereinfacht",
    "version",
    "entwurf",
    "draft",
    "old",
    "alt",
    "neu",
    "final",
    "anonym",
    "unbekannt",
    "text",
    "noten",
}

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def split_camel(text: str) -> str:
    """Make long CamelCase file names readable."""
    text = re.sub(r"(?<=[a-zäöüß])(?=[A-ZÄÖÜ])", " ", text)
    text = re.sub(r"(?<=[A-ZÄÖÜ])(?=[A-ZÄÖÜ][a-zäöüß])", " ", text)
    return text


def clean_stem(stem: str) -> str:
    text = stem
    text = re.sub(r"[-_ ]*DESKTOP-[A-Z0-9]+$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[-_ ]*copy(?: \d+)?$", "", text, flags=re.IGNORECASE)
    text = text.replace("_", " ")
    text = split_camel(text)
    # SonntagKinonika2019 -> Sonntag Kinonika 2019, Sayegh3 -> Sayegh 3
    text = re.sub(r"(?<=[a-zäöüß])(?=\d+(?:st|nd|rd|th)?\b)", " ", text)
    # Graz 20230129 -> Graz 2023-01-29
    text = re.sub(r"(?<=\s)(\d{4})(\d{2})(\d{2})\b", r"\1-\2-\3", text)
    # A.Sayegh -> A. Sayegh, Hl.Kreuzes -> Hl. Kreuzes
    text = re.sub(r"(?<=[A-ZÄÖÜ])\.(?=[A-ZÄÖÜ])", ". ", text)
    # 25.Dec -> 25. Dec, 4.Modus -> 4. Modus
    text = re.sub(r"(?<=\d)\.(?=[A-Za-zÄÖÜäöüß])", ". ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^\d{2}\s+", "", text)
    text = text.strip(" -_")
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


def clean_status_text(text: str) -> str:
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)
    return re.sub(r"\s+", " ", text).strip(" -_")


def detect_status(cleaned: str) -> tuple[str | None, re.Pattern[str] | None]:
    for pattern, label in STATUS_PATTERNS:
        match = pattern.search(cleaned)
        if not match:
            continue
        if label == "v":
            return f"v{match.group(1)}", pattern
        return label, pattern
    return None, None


def strip_status(text: str, pattern: re.Pattern[str] | None) -> str:
    if not pattern:
        return text
    return clean_status_text(pattern.sub(" ", text))


def display_name(name: str) -> str:
    """Human-friendly folder name."""
    if name in FOLDER_NAMES:
        return FOLDER_NAMES[name]

    mode_match = MODE_FOLDER_RE.match(name)
    if mode_match:
        label = f"{mode_match.group(1)}. Modus"
        if "extended" in name.casefold():
            label += " (erweitert)"
        return label

    original = name
    name = re.sub(r"^\d{2}_", "", name)
    name = name.replace("_", " ")
    name = split_camel(name)
    name = re.sub(r"\s+", " ", name).strip()

    match = re.match(r"^(\d+)\s+Jugendtreffen$", name, re.IGNORECASE)
    if match:
        return f"{match.group(1)}. Jugendtreffen"

    if name.casefold() == "heiligen":
        return "Heilige"
    if name.casefold() in ARCHIVE_DIRS:
        return "Archiv"
    if name.casefold() == "corrections":
        return "Korrekturen"

    # Keep a readable fallback for unexpected folder names.
    if original and not name:
        return original
    return name or original


def mode_for_path(rel_path: Path) -> int | None:
    match = MODE_RE.search(rel_path.as_posix())
    return int(match.group(1)) if match else None


def mode_label(mode: int | None) -> str | None:
    return f"{mode}. Modus" if mode else None


def is_archive_path(rel_dir: Path) -> bool:
    for part in rel_dir.parts:
        folded = part.casefold()
        if folded.startswith("99_"):
            return True
        if folded in ARCHIVE_DIRS:
            return True
    return False


def is_mode_folder(name: str) -> bool:
    return bool(MODE_FOLDER_RE.match(name))


def context_name(rel_dir: Path) -> str:
    """Nearest meaningful folder for generic file names such as 'Sammlung'."""
    for part in reversed(rel_dir.parts):
        folded = part.casefold()
        if is_mode_folder(part) or folded in ARCHIVE_DIRS:
            continue
        return display_name(part)
    if rel_dir.parts:
        return display_name(rel_dir.parts[0])
    return "Noten"


def make_title(rel_pdf: Path) -> tuple[str, str | None]:
    cleaned = clean_stem(rel_pdf.stem)
    status, status_pattern = detect_status(cleaned)
    title = strip_status(cleaned, status_pattern)

    mode = mode_for_path(rel_pdf)
    if mode and title:
        match = MODE_NAME_RE.match(title)
        if match:
            title = clean_status_text(title[match.end() :])
        title = clean_status_text(MODE_RE.sub(" ", title))

    context = context_name(rel_pdf.parent)

    if not title:
        title = context
    else:
        first_word = re.split(r"[\s\-]+", title.casefold())[0]
        starts_with_year = bool(re.match(r"^\d{4}\b", title))
        is_generic = first_word in GENERIC_TITLE_WORDS or starts_with_year or len(title) <= 3
        if is_generic and context.casefold() not in title.casefold():
            title = f"{context} – {title}"

    title = clean_status_text(title)
    return title or cleaned, status


def normalize_search(text: str) -> str:
    text = text.casefold().replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def make_search_text(parts: list[str]) -> str:
    raw = " ".join(part for part in parts if part)
    normal = normalize_search(raw)
    # Also index the common German transliteration so "ueber" matches "über".
    transliterated = (
        raw.casefold()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    transliterated = normalize_search(transliterated)
    variants = [
        normal,
        transliterated,
        normal.replace(" ", ""),
        transliterated.replace(" ", ""),
    ]
    return " ".join(dict.fromkeys(" ".join(variants).split()))


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} B"
            value = f"{size:.1f}".rstrip("0").rstrip(".")
            return f"{value.replace('.', ',')} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def format_int_de(number: int) -> str:
    return f"{number:,}".replace(",", ".")


def iso_date_from_pdfinfo(value: str) -> str | None:
    months = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    match = re.search(
        r"[A-Z][a-z]{2}\s+([A-Z][a-z]{2})\s+(\d{1,2})\s+"
        r"\d{2}:\d{2}:\d{2}\s+(\d{4})",
        value,
    )
    if not match:
        return None
    month = months.get(match.group(1).casefold())
    if not month:
        return None
    return f"{int(match.group(3)):04d}-{month:02d}-{int(match.group(2)):02d}"


def date_label(iso_date: str | None) -> str:
    if not iso_date:
        return ""
    try:
        parsed = datetime.strptime(iso_date, "%Y-%m-%d")
    except ValueError:
        return iso_date
    return parsed.strftime("%d.%m.%Y")


# ---------------------------------------------------------------------------
# Slugs
# ---------------------------------------------------------------------------

GREEK_TRANSLITERATION = {
    "α": "a",
    "β": "v",
    "γ": "g",
    "δ": "d",
    "ε": "e",
    "ζ": "z",
    "η": "i",
    "θ": "th",
    "ι": "i",
    "κ": "k",
    "λ": "l",
    "μ": "m",
    "ν": "n",
    "ξ": "x",
    "ο": "o",
    "π": "p",
    "ρ": "r",
    "σ": "s",
    "ς": "s",
    "τ": "t",
    "υ": "y",
    "φ": "f",
    "χ": "ch",
    "ψ": "ps",
    "ω": "o",
    "ά": "a",
    "έ": "e",
    "ή": "i",
    "ί": "i",
    "ό": "o",
    "ύ": "y",
    "ώ": "o",
    "ϊ": "i",
    "ϋ": "y",
    "ΐ": "i",
    "ΰ": "y",
}


def slugify(text: str, fallback: str = "noten") -> str:
    text = text.casefold()
    text = re.sub(r"^\d{2}_", "", text)
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = "".join(GREEK_TRANSLITERATION.get(char, char) for char in text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if len(text) > 80:
        text = text[:80].rstrip("-")
    return text or fallback


def unique_slug(base: str, used: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}-{index}"
        index += 1
    used.add(candidate)
    return candidate


def natural_key(value: str) -> list[Any]:
    return [
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", value)
    ]


# ---------------------------------------------------------------------------
# PDF metadata and previews
# ---------------------------------------------------------------------------


def pdfinfo(pdf: Path) -> tuple[int, str | None]:
    try:
        result = subprocess.run(
            ["pdfinfo", str(pdf)],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0, None

    if result.returncode != 0:
        return 0, None

    pages = 0
    created = None
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            try:
                pages = int(line.split(":", 1)[1].strip())
            except ValueError:
                pages = 0
        elif line.startswith("CreationDate:"):
            created = iso_date_from_pdfinfo(line.split(":", 1)[1].strip())
    return pages, created


def make_thumb(pdf: Path, thumb_path: Path, force: bool) -> bool:
    if (
        not force
        and thumb_path.exists()
        and thumb_path.stat().st_size > 0
        and thumb_path.stat().st_mtime >= pdf.stat().st_mtime
    ):
        return True

    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    tmp_prefix = THUMBS_DIR / f".tmp-{thumb_path.stem}"
    tmp_file = tmp_prefix.with_suffix(".jpg")
    if tmp_file.exists():
        tmp_file.unlink()

    command = [
        "pdftoppm",
        "-f",
        "1",
        "-l",
        "1",
        "-singlefile",
        "-scale-to",
        str(THUMB_SIZE),
        "-jpeg",
        "-jpegopt",
        f"quality={THUMB_QUALITY}",
        str(pdf),
        str(tmp_prefix),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False

    if result.returncode != 0 or not tmp_file.exists():
        if tmp_file.exists():
            tmp_file.unlink()
        return False

    os.replace(tmp_file, thumb_path)
    return True


def build_doc_record(pdf: Path) -> dict[str, Any]:
    rel_pdf = pdf.relative_to(SOURCE)
    rel_dir = rel_pdf.parent
    stat = pdf.stat()
    pages, created = pdfinfo(pdf)

    mtime = datetime.fromtimestamp(stat.st_mtime).date().isoformat()
    created = created or mtime

    thumb_id = hashlib.sha1(rel_pdf.as_posix().encode("utf-8")).hexdigest()[:16]
    title, status = make_title(rel_pdf)
    mode = mode_for_path(rel_pdf)
    display_parts = [display_name(part) for part in rel_dir.parts]
    section_label = " › ".join(display_parts)
    category = rel_dir.parts[0] if rel_dir.parts else ""

    record = {
        "id": thumb_id,
        "title": title,
        "filename": pdf.name,
        "path": rel_pdf.as_posix(),
        "pdf": "library/" + quote(rel_pdf.as_posix(), safe="/"),
        "thumb": f"thumbs/{thumb_id}.jpg",
        "thumbId": thumb_id,
        "category": category,
        "categoryName": display_name(category) if category else "",
        "sectionKey": rel_dir.as_posix(),
        "sectionPath": display_parts,
        "sectionLabel": section_label,
        "mode": mode,
        "modeLabel": mode_label(mode),
        "archive": is_archive_path(rel_dir),
        "pages": pages,
        "bytes": stat.st_size,
        "sizeLabel": human_size(stat.st_size),
        "created": created,
        "createdLabel": date_label(created),
        "status": status,
        "search": make_search_text(
            [
                title,
                pdf.stem,
                rel_pdf.as_posix(),
                section_label,
                display_name(category) if category else "",
                mode_label(mode) or "",
                status or "",
            ]
        ),
    }
    return record


def prune_thumbs(valid_ids: set[str]) -> None:
    if not THUMBS_DIR.exists():
        return
    for thumb in THUMBS_DIR.glob("*.jpg"):
        if thumb.stem in valid_ids:
            continue
        if re.fullmatch(r"[0-9a-f]{16}", thumb.stem):
            thumb.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Folder tree
# ---------------------------------------------------------------------------


def scan_tree() -> dict[str, Any]:
    root: dict[str, Any] = {
        "name": "",
        "rel": Path(),
        "children": {},
        "docs": [],
        "slug": "",
        "slugs": [],
    }

    pdfs = sorted(
        (path for path in SOURCE.rglob("*") if path.is_file() and path.suffix.casefold() == ".pdf"),
        key=lambda path: natural_key(path.relative_to(SOURCE).as_posix()),
    )

    for pdf in pdfs:
        rel_dir = pdf.relative_to(SOURCE).parent
        node = root
        for part in rel_dir.parts:
            node = node["children"].setdefault(
                part,
                {
                    "name": part,
                    "rel": node["rel"] / part,
                    "children": {},
                    "docs": [],
                    "slug": "",
                    "slugs": [],
                },
            )
        node["docs"].append(pdf)

    return root


def assign_slugs(
    node: dict[str, Any],
    doc_slugs: dict[str, str],
    used_slugs: set[str] | None = None,
) -> None:
    used_slugs = used_slugs or set()
    for child in sorted(node["children"].values(), key=lambda item: natural_key(item["name"])):
        child["slug"] = unique_slug(slugify(child["name"]), used_slugs)
        child["slugs"] = [*node["slugs"], child["slug"]]
        assign_slugs(child, doc_slugs, set())

    used_doc_slugs: set[str] = set()
    for pdf in sorted(node["docs"], key=lambda item: natural_key(item.name)):
        pdf_key = pdf.relative_to(SOURCE).as_posix()
        doc_slugs[pdf_key] = unique_slug(slugify(pdf.stem), used_doc_slugs)


def slug_path_for(node: dict[str, Any]) -> list[str]:
    return node["slugs"]


def weight_for(name: str) -> int:
    match = re.match(r"^(\d+)", name)
    return int(match.group(1)) if match else 0


def count_subtree(node: dict[str, Any]) -> int:
    return len(node["docs"]) + sum(count_subtree(child) for child in node["children"].values())


def find_readme(rel_dir: Path) -> str | None:
    folder = SOURCE / rel_dir
    for name in ("ReadMe.txt", "Readme.txt", "README.txt", "readme.txt"):
        candidate = folder / name
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                return None
            return text or None
    return None


def load_category_overrides() -> dict[str, dict[str, Any]]:
    if not CATEGORIES_FILE.exists():
        return {}
    try:
        parsed = json.loads(CATEGORIES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def override_for(rel_dir: Path, overrides: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not rel_dir.parts:
        return {}
    key = rel_dir.as_posix()
    if key in overrides:
        return overrides[key]
    if len(rel_dir.parts) == 1 and rel_dir.parts[0] in overrides:
        return overrides[rel_dir.parts[0]]
    return {}


def serialise_tree(
    node: dict[str, Any],
    overrides: dict[str, dict[str, Any]],
    inherited_icon: str = "folder",
    inherited_accent: str = "#7a2e2e",
) -> dict[str, Any]:
    override = override_for(node["rel"], overrides) if node["rel"].parts else {}
    icon = str(override.get("icon") or (inherited_icon if node["rel"].parts else "book"))
    accent = str(override.get("accent") or inherited_accent)
    description = str(override.get("description") or "")
    archive = is_archive_path(node["rel"])

    children = [
        serialise_tree(child, overrides, icon if not child["rel"].parts else "folder", accent)
        for child in sorted(node["children"].values(), key=lambda item: natural_key(item["name"]))
    ]

    return {
        "key": node["rel"].as_posix(),
        "name": display_name(node["name"]) if node["name"] else "Notenbibliothek",
        "slug": node["slug"],
        "url": "library/" + "/".join(slug_path_for(node)) + "/" if node["slug"] else "library/",
        "count": count_subtree(node),
        "directCount": len(node["docs"]),
        "archive": archive,
        "description": description,
        "icon": icon,
        "accent": accent,
        "children": children,
    }


# ---------------------------------------------------------------------------
# Content generation
# ---------------------------------------------------------------------------


def write_page(path: Path, front_matter: dict[str, Any], body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(front_matter, ensure_ascii=False, indent=2)
    path.write_text(f"---\n{payload}\n---\n\n{body}", encoding="utf-8")


def write_section_pages(
    node: dict[str, Any],
    overrides: dict[str, dict[str, Any]],
    docs_by_path: dict[str, dict[str, Any]],
    doc_slugs: dict[str, str],
) -> None:
    rel_dir = node["rel"]
    slug_parts = slug_path_for(node)

    if not slug_parts:
        page_path = CONTENT_LIBRARY / "_index.md"
        front_matter = {
            "title": "Notenbibliothek",
            "type": "library",
            "layout": "list",
            "kind": "root",
            "description": "Alle Noten der German-Psaltica-Bibliothek durchsuchen und filtern.",
            "generated": True,
        }
        write_page(page_path, front_matter)
    else:
        override = override_for(rel_dir, overrides)
        notice = find_readme(rel_dir)
        front_matter = {
            "title": display_name(node["name"]),
            "type": "library",
            "layout": "list",
            "kind": "section",
            "sectionKey": rel_dir.as_posix(),
            "category": rel_dir.parts[0] if rel_dir.parts else "",
            "categoryName": display_name(rel_dir.parts[0]) if rel_dir.parts else "",
            "archive": is_archive_path(rel_dir),
            "description": str(override.get("description") or ""),
            "icon": str(override.get("icon") or ""),
            "accent": str(override.get("accent") or ""),
            "weight": weight_for(node["name"]),
            "generated": True,
        }
        if notice:
            front_matter["notice"] = notice
        write_page(CONTENT_LIBRARY.joinpath(*slug_parts) / "_index.md", front_matter)

    for child in sorted(node["children"].values(), key=lambda item: natural_key(item["name"])):
        write_section_pages(child, overrides, docs_by_path, doc_slugs)

    for pdf in node["docs"]:
        pdf_key = pdf.relative_to(SOURCE).as_posix()
        record = docs_by_path[pdf_key]
        doc_slug = doc_slugs[pdf_key]
        front_matter = {
            "title": record["title"],
            "type": "library",
            "layout": "single",
            "date": record["created"],
            "pdf": record["pdf"],
            "pdfPath": record["path"],
            "filename": record["filename"],
            "thumb": record["thumb"],
            "category": record["category"],
            "categoryName": record["categoryName"],
            "sectionKey": record["sectionKey"],
            "sectionPath": record["sectionPath"],
            "sectionLabel": record["sectionLabel"],
            "mode": record["mode"],
            "modeLabel": record["modeLabel"],
            "archive": record["archive"],
            "pages": record["pages"],
            "sizeBytes": record["bytes"],
            "sizeLabel": record["sizeLabel"],
            "created": record["created"],
            "createdLabel": record["createdLabel"],
            "status": record["status"],
            "search": record["search"],
            "weight": weight_for(pdf.name),
            "generated": True,
        }
        write_page(
            CONTENT_LIBRARY.joinpath(*slug_path_for(node), f"{doc_slug}.md"),
            front_matter,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate German Psaltica Hugo data.")
    parser.add_argument("--no-thumbs", action="store_true", help="Skip preview generation.")
    parser.add_argument("--force-thumbs", action="store_true", help="Regenerate all previews.")
    parser.add_argument("--jobs", type=int, default=4, help="Parallel PDF workers (default: 4).")
    args = parser.parse_args()

    if not SOURCE.is_dir():
        print(f"Source folder not found: {SOURCE}", file=sys.stderr)
        return 1

    required_commands = ("pdfinfo",) if args.no_thumbs else ("pdfinfo", "pdftoppm")
    for command in required_commands:
        if shutil.which(command) is None:
            print(
                f"Missing '{command}'. Install poppler-utils (Debian/Ubuntu: apt install poppler-utils).",
                file=sys.stderr,
            )
            return 1

    pdfs = sorted(
        (path for path in SOURCE.rglob("*") if path.is_file() and path.suffix.casefold() == ".pdf"),
        key=lambda path: natural_key(path.relative_to(SOURCE).as_posix()),
    )
    if not pdfs:
        print(f"No PDFs found in {SOURCE}", file=sys.stderr)
        return 1

    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {len(pdfs)} PDFs …")
    records: list[dict[str, Any]] = []
    failures: list[tuple[str, str]] = []

    def process(pdf: Path) -> dict[str, Any]:
        record = build_doc_record(pdf)
        thumb_path = THUMBS_DIR / f"{record['thumbId']}.jpg"
        if args.no_thumbs:
            record["thumb"] = None
        elif not make_thumb(pdf, thumb_path, args.force_thumbs):
            record["thumb"] = None
        return record

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {pool.submit(process, pdf): pdf for pdf in pdfs}
        for index, future in enumerate(as_completed(futures), start=1):
            pdf = futures[future]
            try:
                records.append(future.result())
            except Exception as exc:  # pragma: no cover - defensive
                failures.append((pdf.relative_to(SOURCE).as_posix(), str(exc)))
            if index % 25 == 0 or index == len(pdfs):
                print(f"  processed {index}/{len(pdfs)}")

    records.sort(key=lambda item: natural_key(item["path"]))
    docs_by_path = {record["path"]: record for record in records}

    # Rebuild the tree and attach slugs.
    tree = scan_tree()
    doc_slugs: dict[str, str] = {}
    assign_slugs(tree, doc_slugs)

    # Generate pages from scratch. content/library is a generated directory.
    if CONTENT_LIBRARY.exists():
        shutil.rmtree(CONTENT_LIBRARY)
    CONTENT_LIBRARY.mkdir(parents=True, exist_ok=True)

    overrides = load_category_overrides()
    write_section_pages(tree, overrides, docs_by_path, doc_slugs)

    categories = [
        serialise_tree(child, overrides)
        for child in sorted(tree["children"].values(), key=lambda item: natural_key(item["name"]))
    ]

    total_pages = sum(record["pages"] for record in records)
    total_bytes = sum(record["bytes"] for record in records)
    data = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generatorVersion": GENERATOR_VERSION,
        "total": len(records),
        "totalPages": total_pages,
        "totalPagesLabel": format_int_de(total_pages),
        "totalSize": total_bytes,
        "totalSizeLabel": human_size(total_bytes),
        "categories": categories,
        "docs": records,
    }
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if not args.no_thumbs:
        prune_thumbs({record["thumbId"] for record in records})

    print()
    print(f"Generated {len(records)} note pages in {CONTENT_LIBRARY.relative_to(ROOT)}")
    print(f"Catalog data: {DATA_FILE.relative_to(ROOT)}")
    print(f"Previews:     {THUMBS_DIR.relative_to(ROOT)}")
    print(f"Total:        {len(records)} PDFs · {format_int_de(total_pages)} pages · {human_size(total_bytes)}")
    if failures:
        print()
        print(f"{len(failures)} PDF(s) could not be processed:", file=sys.stderr)
        for path, error in failures[:20]:
            print(f"  - {path}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
