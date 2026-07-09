from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from research_agent.models import AppInput, AppResearchResult


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    tmp_path.replace(path)


def append_jsonl(path: Path, payload: Any) -> None:
    ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=str))
        handle.write("\n")


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSONL at {path}:{line_no}: {exc}") from exc


def load_apps(path: Path) -> list[AppInput]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. Add the assignment-provided 100-app apps.json file "
            "at the repo root; the agent deliberately does not regenerate it."
        )
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON array of app objects")

    apps: list[AppInput] = []
    for index, raw_app in enumerate(payload, start=1):
        if not isinstance(raw_app, dict):
            raise ValueError(f"apps.json item {index} must be an object")
        normalized = dict(raw_app)
        normalized.setdefault("id", index)
        apps.append(AppInput.model_validate(normalized))
    return apps


def load_results(path: Path) -> list[AppResearchResult]:
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist")
    if path.suffix == ".jsonl":
        rows = list(iter_jsonl(path))
    else:
        payload = read_json(path)
        if isinstance(payload, dict) and "results" in payload:
            rows = payload["results"]
        elif isinstance(payload, list):
            rows = payload
        else:
            raise ValueError(f"{path} must be a JSON array, JSONL, or object with results[]")
    return [AppResearchResult.model_validate(row) for row in rows]


def load_result_map(path: Path) -> dict[int, AppResearchResult]:
    return {result.id: result for result in load_results(path)}


def existing_result_ids(path: Path) -> set[int]:
    ids: set[int] = set()
    if not path.exists():
        return ids
    for row in iter_jsonl(path):
        row_id = row.get("id")
        if isinstance(row_id, int):
            ids.add(row_id)
    return ids


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "app"


def truncate(value: Any, max_chars: int = 2000) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...[truncated]"

