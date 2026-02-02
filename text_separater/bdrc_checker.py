#!/usr/bin/env python3
import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests


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


def ensure_list(data: Any) -> List[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
        return data["items"]
    return [data]


def fetch_text_by_bdrc(
    session: requests.Session,
    base_url: str,
    bdrc: str,
    timeout: int,
) -> Tuple[bool, Optional[Dict[str, Any]], int]:
    url = f"{base_url.rstrip('/')}/v2/texts/{bdrc}"
    response = session.get(url, timeout=timeout)
    if response.status_code == 200:
        return True, response.json(), response.status_code
    if response.status_code == 404:
        return False, None, response.status_code
    response.raise_for_status()
    return False, None, response.status_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check BDRC ids before upload.")
    parser.add_argument("--input", help="Path to upload plan JSON.")
    parser.add_argument(
        "--input-folder",
        help="Path to a folder containing text_metadata.json.",
    )
    parser.add_argument(
        "--input-root",
        default=os.path.join(os.getcwd(), "input_json"),
        help="Root folder containing input_json subfolders.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all folders under --input-root.",
    )
    parser.add_argument("--base-url", default=os.getenv("TEXT_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--output", help="Write results JSON to this path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    def load_plan_from_folder(folder_path: str) -> List[Dict[str, Any]]:
        text_path = os.path.join(folder_path, "text_metadata.json")
        if not os.path.exists(text_path):
            raise SystemExit(f"Missing {text_path}.")
        return [{"text": load_json(text_path)}]

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

    session = requests.Session()

    results: List[Dict[str, Any]] = []
    for idx, item in enumerate(upload_plan):
        if not isinstance(item, dict):
            raise SystemExit(f"Item {idx} must be a JSON object.")
        text_payload = item.get("text")
        if not isinstance(text_payload, dict):
            raise SystemExit(f"Item {idx} must include a 'text' object.")
        bdrc = text_payload.get("bdrc")
        if not bdrc:
            raise SystemExit(f"Item {idx} missing required 'bdrc' in text.")

        exists, metadata, status = fetch_text_by_bdrc(
            session, args.base_url, bdrc, args.timeout
        )

        results.append(
            {
                "index": idx,
                "bdrc": bdrc,
                "exists": exists,
                "status": status,
                "message": "these bdrc are already present" if exists else None,
                "metadata": metadata if exists else None,
            }
        )

    write_json(args.output, results)


if __name__ == "__main__":
    main()
