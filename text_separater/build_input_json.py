#!/usr/bin/env python3
import argparse
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def sanitize_folder_name(name: str) -> str:
    cleaned = name.strip()
    cleaned = re.sub(r"[\\/:\*\?\"<>\|]", "_", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "untitled"


def pick_title_value(incipit_title: Any) -> Optional[str]:
    if isinstance(incipit_title, str):
        return incipit_title
    if isinstance(incipit_title, dict):
        for key in ("bo", "en", "zh"):
            if key in incipit_title and incipit_title[key]:
                return incipit_title[key]
        for value in incipit_title.values():
            if value:
                return value
    return None


def build_text_payload(metadata: Dict[str, Any], fallback_title: str) -> Dict[str, Any]:
    title_payload: Dict[str, str] = {}
    incipit_title = metadata.get("incipit_title") or {}
    if isinstance(incipit_title, dict):
        if incipit_title.get("bo"):
            title_payload["bo"] = incipit_title["bo"]
        if incipit_title.get("en"):
            title_payload["en"] = incipit_title["en"]
    if "en" not in title_payload:
        title_payload["en"] = fallback_title

    payload: Dict[str, Any] = {
        "type": metadata.get("text_type"),
        "title": title_payload,
        "language": metadata.get("language"),
        "date": metadata.get("date"),
        "bdrc": metadata.get("bdrc"),
        "category_id": metadata.get("category_id"),
    }
    for key in ("contributions", "license"):
        if key in metadata:
            payload[key] = metadata.get(key)
    if "copyright" in metadata:
        payload["copyright"] = normalize_copyright(metadata.get("copyright"))
    return payload


def build_instance_payload(entry: Dict[str, Any]) -> Dict[str, Any]:
    metadata = entry.get("metadata", {})
    instance_metadata = {
        "type": metadata.get("instance_type"),
        "source": metadata.get("source"),
        "colophon": metadata.get("colophon"),
        "incipit_title": metadata.get("incipit_title"),
    }
    payload: Dict[str, Any] = {
        "metadata": instance_metadata,
        "annotation": entry.get("segment_annotation", []),
        "content": entry.get("content", ""),
    }
    return payload


def build_translation_payload(entry: Dict[str, Any], fallback_title: str) -> Dict[str, Any]:
    metadata = entry.get("metadata", {})
    title_value = pick_title_value(metadata.get("incipit_title")) or fallback_title

    author = None
    contributions = metadata.get("contributions") or []
    if isinstance(contributions, list):
        for contrib in contributions:
            if isinstance(contrib, dict) and contrib.get("person_id"):
                author = {"person_id": contrib["person_id"]}
                break

    segmentation = [
        {"span": span["span"]}
        for span in entry.get("segment_annotation", [])
        if isinstance(span, dict) and "span" in span
    ]
    target_annotation = [
        {"span": {"start": span["start"], "end": span["end"]}, "index": idx}
        for idx, span in enumerate(entry.get("target_annotation", []))
        if isinstance(span, dict) and "start" in span and "end" in span
    ]
    alignment_annotation = [
        {
            "span": {"start": span["start"], "end": span["end"]},
            "index": idx,
            "alignment_index": [idx],
        }
        for idx, span in enumerate(entry.get("alignment_annotation", []))
        if isinstance(span, dict) and "start" in span and "end" in span
    ]

    payload: Dict[str, Any] = {
        "language": metadata.get("language"),
        "content": entry.get("content", ""),
        "title": title_value,
        "source": metadata.get("source"),
        "category_id": metadata.get("category_id"),
        "segmentation": segmentation,
        "target_annotation": target_annotation,
        "alignment_annotation": alignment_annotation,
        "copyright": normalize_copyright(metadata.get("copyright")),
        "license": metadata.get("license"),
    }
    if author:
        payload["author"] = author
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build input JSON files for APIs.")
    parser.add_argument(
        "--source-dir",
        default=os.path.join(os.getcwd(), "json"),
        help="Directory containing source JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(os.getcwd(), "input_json"),
        help="Directory to write API input JSON files.",
    )
    return parser.parse_args()


def normalize_copyright(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    cleaned = value.strip().lower()
    if cleaned in {"unknown", "unk"}:
        return "Unknown"
    if cleaned in {"in copyright", "in-copyright"}:
        return "In copyright"
    if cleaned in {"public domain", "public_domain", "public-domain"}:
        return "Public domain"
    return value


def main() -> None:
    args = parse_args()
    source_dir = args.source_dir
    output_dir = args.output_dir

    for filename in os.listdir(source_dir):
        if not filename.lower().endswith(".json"):
            continue
        source_path = os.path.join(source_dir, filename)
        data = load_json(source_path)

        root_texts = data.get("root_texts") or []
        translations = data.get("translations") or []
        if not root_texts:
            continue

        base_title = os.path.splitext(filename)[0].strip()
        root_entry = root_texts[0]
        root_meta = root_entry.get("metadata", {})
        incipit_title_value = pick_title_value(root_meta.get("incipit_title")) or base_title
        folder_name = sanitize_folder_name(incipit_title_value)
        folder_path = os.path.join(output_dir, folder_name)

        text_payload = build_text_payload(root_meta, base_title)
        instance_payload = build_instance_payload(root_entry)
        translation_payloads = [
            build_translation_payload(translation, base_title)
            for translation in translations
        ]

        write_json(os.path.join(folder_path, "text_metadata.json"), text_payload)
        write_json(os.path.join(folder_path, "instance_payload.json"), instance_payload)
        if translation_payloads:
            write_json(
                os.path.join(folder_path, "translation_payloads.json"),
                translation_payloads,
            )


if __name__ == "__main__":
    main()
