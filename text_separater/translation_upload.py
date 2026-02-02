#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import colorama
import requests
from colorama import Fore, Style


DEFAULT_BASE_URL = "https://api-aq25662yyq-uc.a.run.app"


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Optional[str], payload: Any) -> None:
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    else:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")


def log(message: str) -> None:
    sys.stderr.write(f"{Style.BRIGHT}{Fore.CYAN}{message}{Style.RESET_ALL}\n")
    sys.stderr.flush()


def ensure_list(data: Any) -> List[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
        return data["items"]
    return [data]


def flatten_content(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            parts.extend(flatten_content(item))
        return parts
    raise ValueError("Content must be a string or array of strings.")


def normalize_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    parts = [part for part in flatten_content(value) if part is not None]
    return "\n".join(parts)


def post_json(
    session: requests.Session,
    url: str,
    payload: Dict[str, Any],
    timeout: int,
    dry_run: bool,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if dry_run:
        return None, None
    response = session.post(url, json=payload, timeout=timeout)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = response.text.strip()
        if detail:
            raise requests.HTTPError(f"{exc} - {detail}", response=response) from exc
        raise
    if response.content:
        return response.json(), response.text
    return None, response.text


def build_translation_payload(
    item: Dict[str, Any],
    strip_annotations: bool,
    author_person_id: Optional[str],
) -> Dict[str, Any]:
    if "translation" in item and isinstance(item["translation"], dict):
        payload = item["translation"]
    else:
        payload = {k: v for k, v in item.items() if k != "instance_id"}
    if "content" in payload:
        payload["content"] = normalize_content(payload["content"])
    if strip_annotations:
        payload.pop("segmentation", None)
        payload.pop("target_annotation", None)
        payload.pop("alignment_annotation", None)
    if author_person_id and "author" not in payload:
        payload["author"] = {"person_id": author_person_id}
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload translations for instances.")
    parser.add_argument("--input", required=True, help="Path to translations JSON.")
    parser.add_argument("--base-url", default=os.getenv("TEXT_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--strip-annotations",
        action="store_true",
        help="Remove segmentation/target/alignment annotations before upload.",
    )
    parser.add_argument(
        "--author-person-id",
        help="Author person_id to include if missing.",
    )
    parser.add_argument(
        "--skip-missing-instance-id",
        action="store_true",
        help="Skip items missing instance_id instead of failing.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", help="Write results JSON to this path.")
    return parser.parse_args()


def main() -> None:
    colorama.init(autoreset=True)
    args = parse_args()
    translations = ensure_list(load_json(args.input))

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    items = translations[args.start :]
    if args.limit is not None:
        items = items[: args.limit]

    results: List[Dict[str, Any]] = []
    for idx, item in enumerate(items, start=args.start):
        if not isinstance(item, dict):
            raise SystemExit(f"Item {idx} must be a JSON object.")
        instance_id = item.get("instance_id")
        if not instance_id:
            if args.skip_missing_instance_id:
                log(f"[{idx}] Skipping (missing instance_id)")
                continue
            raise SystemExit(f"Item {idx} missing required 'instance_id'.")

        log(f"[{idx}] Uploading translation for instance {instance_id}")
        payload = build_translation_payload(
            item,
            args.strip_annotations,
            args.author_person_id,
        )
        if "content" not in payload:
            raise SystemExit(f"Item {idx} missing required 'content'.")

        url = f"{args.base_url.rstrip('/')}/v2/instances/{instance_id}/translation"
        response_json, response_raw = post_json(
            session, url, payload, args.timeout, args.dry_run
        )
        if response_json is not None:
            log(f"[{idx}] Translation uploaded")

        results.append(
            {
                "index": idx,
                "instance_id": instance_id,
                "response": response_json,
                "payload": payload if args.dry_run else None,
            }
        )

        if args.sleep_seconds:
            time.sleep(args.sleep_seconds)

    write_json(args.output, results)


if __name__ == "__main__":
    main()
