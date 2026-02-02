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


ID_KEYS = ("id", "text_id", "textId", "instance_id", "instanceId")
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


def write_json_file(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def log(message: str) -> None:
    sys.stderr.write(f"{Style.BRIGHT}{Fore.CYAN}{message}{Style.RESET_ALL}\n")
    sys.stderr.flush()


def ensure_list(data: Any) -> List[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
        return data["items"]
    return [data]


def extract_id(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "$oid" in value and isinstance(value["$oid"], str):
            return value["$oid"]
        for key in ID_KEYS:
            if key in value:
                found = extract_id(value[key])
                if found:
                    return found
        for child in value.values():
            found = extract_id(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = extract_id(child)
            if found:
                return found
    return None


def build_auth_header(token: Optional[str], header: str, scheme: str) -> Dict[str, str]:
    if not token:
        return {}
    if scheme:
        return {header: f"{scheme} {token}"}
    return {header: token}


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
    def summarize_value(value: Any) -> Any:
        if isinstance(value, str):
            if len(value) > 200:
                return f"<string length={len(value)}>"
            return value
        if isinstance(value, list):
            return f"<list length={len(value)}>"
        if isinstance(value, dict):
            keys = list(value.keys())
            focus_keys = {
                "type",
                "title",
                "language",
                "date",
                "bdrc",
                "category_id",
                "source",
                "colophon",
                "incipit_title",
                "copyright",
                "license",
            }
            summary = {key: summarize_value(value[key]) for key in keys if key in focus_keys}
            if summary:
                return summary
            return f"<dict keys={keys[:6]}{'...' if len(keys) > 6 else ''}>"
        return value

    def summarize_payload(payload_data: Dict[str, Any]) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        for key, value in payload_data.items():
            if key == "content":
                normalized = normalize_content(value)
                summary[key] = f"<content length={len(normalized)}>"
            elif key == "annotation":
                summary[key] = f"<annotation count={len(value) if isinstance(value, list) else 0}>"
            else:
                summary[key] = summarize_value(value)
        return summary

    response = session.post(url, json=payload, timeout=timeout)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        payload_summary = summarize_payload(payload)
        error_text = response.text.strip()
        if not error_text and response.content:
            error_text = response.content.decode("utf-8", errors="replace").strip()
        raise SystemExit(
            "Request failed "
            f"({response.status_code}) POST {url}\n"
            f"Response: {error_text or '<empty>'}\n"
            "Payload summary: "
            f"{json.dumps(payload_summary, ensure_ascii=False)}"
        ) from exc
    if response.content:
        return response.json(), response.text
    return None, response.text


def build_instance_payload(
    item: Dict[str, Any],
    default_instance_metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if "instance" in item and isinstance(item["instance"], dict):
        return item["instance"]
    if "content" not in item:
        raise ValueError("Item must include 'instance' or 'content'.")
    payload: Dict[str, Any] = {"content": normalize_content(item["content"])}
    if default_instance_metadata is not None:
        payload["metadata"] = default_instance_metadata
    if "annotation" in item:
        payload["annotation"] = item["annotation"]
    return payload


def clean_metadata(value: Any, preserve_empty_list_keys: Optional[set] = None) -> Any:
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(item, str) and not item.strip():
                continue
            cleaned_item = clean_metadata(item, preserve_empty_list_keys)
            if cleaned_item is None:
                continue
            if isinstance(cleaned_item, dict) and not cleaned_item:
                continue
            if isinstance(cleaned_item, list) and not cleaned_item:
                if preserve_empty_list_keys and key in preserve_empty_list_keys:
                    cleaned[key] = cleaned_item
                continue
            cleaned[key] = cleaned_item
        return cleaned
    if isinstance(value, list):
        items = []
        for item in value:
            cleaned_item = clean_metadata(item, preserve_empty_list_keys)
            if cleaned_item is None:
                continue
            if isinstance(cleaned_item, dict) and not cleaned_item:
                continue
            if isinstance(cleaned_item, list) and not cleaned_item:
                continue
            items.append(cleaned_item)
        return items
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload text metadata and content.")
    parser.add_argument("--input", help="Path to upload plan JSON.")
    parser.add_argument(
        "--input-folder",
        help="Path to a folder containing text_metadata.json and instance_payload.json.",
    )
    parser.add_argument(
        "--input-root",
        default=os.path.join(os.getcwd(), "input_json"),
        help="Root folder containing input_json subfolders.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Upload all folders under --input-root.",
    )
    parser.add_argument("--base-url", default=os.getenv("TEXT_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--token", default=os.getenv("TEXT_API_TOKEN"))
    parser.add_argument("--auth-header", default=os.getenv("TEXT_API_AUTH_HEADER", "Authorization"))
    parser.add_argument("--auth-scheme", default=os.getenv("TEXT_API_AUTH_SCHEME", ""))
    parser.add_argument("--instance-metadata", help="Path to instance metadata JSON.")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--skip-existing-bdrc", action="store_true")
    parser.add_argument(
        "--bdrc-cache",
        help="Path to bdrc_checker output JSON to avoid API lookups.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", help="Write results JSON to this path.")
    return parser.parse_args()


def main() -> None:
    colorama.init(autoreset=True)
    args = parse_args()
    if not args.base_url:
        raise SystemExit("Missing --base-url or TEXT_API_BASE_URL.")

    def load_plan_from_folder(folder_path: str) -> List[Dict[str, Any]]:
        text_path = os.path.join(folder_path, "text_metadata.json")
        instance_path = os.path.join(folder_path, "instance_payload.json")
        if not os.path.exists(text_path):
            raise SystemExit(f"Missing {text_path}.")
        if not os.path.exists(instance_path):
            raise SystemExit(f"Missing {instance_path}.")
        return [
            {
                "text": load_json(text_path),
                "instance": load_json(instance_path),
                "_folder": folder_path,
            }
        ]

    def attach_instance_id(folder_path: str, instance_id: str) -> None:
        instance_path = os.path.join(folder_path, "instance_payload.json")
        if os.path.exists(instance_path):
            payload = load_json(instance_path)
            if not isinstance(payload, dict):
                raise SystemExit(f"Expected an object in {instance_path}.")
            payload["instance_id"] = instance_id
            write_json_file(instance_path, payload)

        translation_path = os.path.join(folder_path, "translation_payloads.json")
        if not os.path.exists(translation_path):
            return
        payload = load_json(translation_path)
        if not isinstance(payload, list):
            raise SystemExit(f"Expected a list in {translation_path}.")
        updated = []
        for entry in payload:
            if not isinstance(entry, dict):
                raise SystemExit(f"Invalid translation entry in {translation_path}.")
            if "instance_id" not in entry:
                entry = {**entry, "instance_id": instance_id}
            updated.append(entry)
        write_json_file(translation_path, updated)

    upload_plan: List[Dict[str, Any]] = []
    if args.input:
        upload_plan = ensure_list(load_json(args.input))
    elif args.all:
        input_root = args.input_root
        if not os.path.isdir(input_root):
            raise SystemExit(f"Missing input root directory: {input_root}")
        for entry in sorted(os.listdir(input_root)):
            folder_path = os.path.join(input_root, entry)
            if not os.path.isdir(folder_path):
                continue
            upload_plan.extend(load_plan_from_folder(folder_path))
    elif args.input_folder:
        upload_plan = load_plan_from_folder(args.input_folder)
    else:
        raise SystemExit("Provide --input, --input-folder, or --all with --input-root.")

    default_instance_metadata = None
    if args.instance_metadata:
        default_instance_metadata = load_json(args.instance_metadata)

    def load_bdrc_cache(path: Optional[str]) -> Optional[set]:
        if not path:
            return None
        payload = load_json(path)
        items = ensure_list(payload)
        cached = set()
        for entry in items:
            if not isinstance(entry, dict):
                continue
            if entry.get("exists") is True and isinstance(entry.get("bdrc"), str):
                cached.add(entry["bdrc"])
        return cached

    cached_bdrc = load_bdrc_cache(args.bdrc_cache)

    session = requests.Session()
    headers = {
        "Content-Type": "application/json",
        **build_auth_header(args.token, args.auth_header, args.auth_scheme),
    }
    session.headers.update(headers)
    def bdrc_exists(bdrc: str) -> bool:
        if cached_bdrc is not None:
            return bdrc in cached_bdrc
        url = f"{args.base_url.rstrip('/')}/v2/texts/{bdrc}"
        response = session.get(url, timeout=args.timeout)
        if response.status_code == 200:
            return True
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return False


    items = upload_plan[args.start :]
    if args.limit is not None:
        items = items[: args.limit]

    results: List[Dict[str, Any]] = []
    for idx, item in enumerate(items, start=args.start):
        if not isinstance(item, dict):
            raise SystemExit(f"Item {idx} must be a JSON object.")
        if "text" not in item or not isinstance(item["text"], dict):
            raise SystemExit(f"Item {idx} must include a 'text' object.")

        text_payload = clean_metadata(item["text"], preserve_empty_list_keys={"contributions"})
        instance_payload = build_instance_payload(item, default_instance_metadata)
        if "metadata" in instance_payload:
            instance_payload["metadata"] = clean_metadata(instance_payload["metadata"])
        bdrc_value = text_payload.get("bdrc")
        folder_label = item.get("_folder") or "plan"
        log(f"[{idx}] Starting upload for {folder_label}")

        if args.skip_existing_bdrc:
            if not bdrc_value:
                raise SystemExit(f"Item {idx} missing required 'bdrc' in text.")
            if bdrc_exists(bdrc_value):
                log(f"[{idx}] Skipping (bdrc exists): {bdrc_value}")
                results.append(
                    {
                        "index": idx,
                        "bdrc": bdrc_value,
                        "skipped": True,
                        "message": "these bdrc are already present",
                    }
                )
                continue

        text_url = f"{args.base_url.rstrip('/')}/v2/texts"
        text_response, text_raw = post_json(
            session, text_url, text_payload, args.timeout, args.dry_run
        )
        text_id = extract_id(text_response) if text_response is not None else None
        if text_id:
            log(f"[{idx}] Text created: {text_id}")

        instance_url = None
        instance_response = None
        instance_raw = None
        instance_id = None
        if not args.dry_run:
            if not text_id:
                raise SystemExit(
                    f"Item {idx}: could not find text_id in response: {text_raw}"
                )
            instance_url = f"{text_url}/{text_id}/instances"
            instance_response, instance_raw = post_json(
                session, instance_url, instance_payload, args.timeout, args.dry_run
            )
            instance_id = extract_id(instance_response)
            folder_path = item.get("_folder")
            if instance_id and folder_path:
                attach_instance_id(folder_path, instance_id)
            if instance_id:
                log(f"[{idx}] Instance created: {instance_id}")

        results.append(
            {
                "index": idx,
                "text_id": text_id,
                "instance_id": instance_id,
                "text_response": text_response,
                "instance_response": instance_response,
                "text_payload": text_payload if args.dry_run else None,
                "instance_payload": instance_payload if args.dry_run else None,
            }
        )

        if args.sleep_seconds:
            time.sleep(args.sleep_seconds)

    write_json(args.output, results)


if __name__ == "__main__":
    main()
