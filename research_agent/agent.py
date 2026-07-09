from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_agent.io_utils import append_jsonl, existing_result_ids, load_apps, truncate
from research_agent.models import AppInput, AppResearchResult


FINAL_TOOL_NAME = "record_app_research"
DEFAULT_OUTPUT = Path("data/pass1_raw.jsonl")
DEFAULT_FAILURES = Path("data/failures.jsonl")
DEFAULT_TRACE_DIR = Path("data/traces")


PASS1_RESEARCH_INSTRUCTIONS = """
Research each assigned app using Composio tools. Prefer official developer docs,
auth docs, pricing/access pages, changelogs, GitHub/MCP registry pages, and
support docs over blog posts or snippets. Return only by calling the
record_app_research tool with the exact schema.
"""


PASS2_RESEARCH_INSTRUCTIONS = """
Research each assigned app using Composio tools. This is the corrected pass.
Open the strongest official source pages; do not rely on search-result snippets
for final fields. Apply these corrections, each targeting a measured pass-1
failure mode:

1. AUTH - list every method a first-party developer/API page documents, and no
   more. Many APIs support several at once (e.g. OAuth2 for apps AND a personal/
   API token AND Basic); include each one you actually find documented. Do NOT
   collapse everything to just oauth2, and do NOT add a method with no first-party
   evidence. Map a personal access token / API token to "token", a documented API
   key to "api_key", HTTP Basic to "basic", and a developer token or other
   non-standard scheme to "other".

2. HUMAN REVIEW - raise the bar. Set needs_human_review=true ONLY when a
   STRUCTURED decision field (auth_methods, access_tier, api_surface.type,
   mcp_exists, or buildability_verdict) cannot be supported by the evidence you
   read. Normal pricing pages that state plan tiers are ENOUGH to decide
   access_tier - that alone is not a reason to flag. Do not flag out of generic
   caution; most well-documented apps should come back fully automated.

3. EVIDENCE URLS - must be live and canonical. Prefer top-level developer/API/
   auth/pricing doc URLs that return content to a plain GET. Avoid deep anchor
   fragments, search-result links, and JS-app routes that 404 without a browser.
   Only include a URL whose page content you actually read and that supports a
   field.

If docs are genuinely JS-rendered, gated, stale, contradictory, or too thin to
decide a structured field, then set needs_human_review=true and explain why.
Return only by calling the record_app_research tool with the exact schema.
"""


SYSTEM_PROMPT = """
You are a careful product-ops research agent evaluating whether an app can be
turned into an AI-agent toolkit today.

Use Composio's search/browse/browser tools to inspect real web pages. Favor
official documentation and first-party pages. You must not fabricate evidence
URLs or silently guess unsupported fields. If a field cannot be verified within
the available evidence, make the best schema-valid finding only when the
evidence supports it, set needs_human_review=true, and explain the ambiguity.

Auth methods must use only: oauth2, api_key, basic, token, other.
Access tier must use only: self_serve_free, self_serve_trial,
paid_plan_required, admin_approval_required, partner_gated_contact_sales.
API surface type must use only: REST, GraphQL, Both, None.
Buildability verdict must use only: ready_today, ready_with_workaround, blocked.

Buildability rubric:
- ready_today: public docs + self-serve access + documented API auth are enough
  to build a first toolkit without special approval.
- ready_with_workaround: possible but needs limited manual setup, paid tier,
  undocumented gaps, or narrow endpoints.
- blocked: no usable public API/docs, partner-only access, contact-sales gate,
  or legal/admin gate blocks toolkit development today.

Do not include prose in the final answer. Call record_app_research exactly once.
Do not call record_app_research in the same assistant turn as any other tool.
"""


def load_dotenv_if_present() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def require_agent_dependencies() -> tuple[Any, Any, Any, Any, Any]:
    cache_dir = Path(
        os.getenv(
            "COMPOSIO_CACHE_DIR",
            str(PROJECT_ROOT / "data" / ".composio-cache"),
        )
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("COMPOSIO_CACHE_DIR", str(cache_dir))
    try:
        import httpx
        import openai
        from composio import Composio
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
    except ImportError as exc:
        raise RuntimeError(
            "Missing agent dependencies. Install with: "
            "pip install -r requirements.txt"
        ) from exc
    return openai, Composio, ClientSession, streamable_http_client, httpx


def final_tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": FINAL_TOOL_NAME,
            "description": "Submit the verified structured research result for one app.",
            "parameters": AppResearchResult.model_json_schema(),
            "strict": True,
        },
    }


def openai_tool_schema(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
            "strict": False,
        },
    }


def tool_name(tool_call: Any) -> str | None:
    function = getattr(tool_call, "function", None)
    return getattr(function, "name", None)


def is_transient_error(exc: BaseException) -> bool:
    text = f"{exc.__class__.__name__}: {exc}".lower()
    transient_markers = [
        "rate limit",
        "ratelimit",
        "429",
        "timeout",
        "temporarily",
        "overloaded",
        "connection reset",
        "service unavailable",
        "503",
    ]
    return any(marker in text for marker in transient_markers)


def redact_mcp(session: Any) -> dict[str, Any]:
    mcp = getattr(session, "mcp", None)
    if not mcp:
        return {"enabled": False}
    url = getattr(mcp, "url", "")
    parsed = urlparse(str(url)) if url else None
    redacted_url = (
        f"{parsed.scheme}://{parsed.netloc}/[redacted]"
        if parsed and parsed.scheme and parsed.netloc
        else ""
    )
    headers = getattr(mcp, "headers", {}) or {}
    return {
        "enabled": True,
        "url_redacted": redacted_url,
        "header_names": sorted(headers.keys()) if isinstance(headers, dict) else [],
    }


class TraceLogger:
    def __init__(self, trace_dir: Path, app: AppInput) -> None:
        self.path = trace_dir / f"{app.id:03d}.jsonl"

    def log(self, event: str, payload: dict[str, Any] | None = None) -> None:
        append_jsonl(
            self.path,
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "event": event,
                **(payload or {}),
            },
        )


@dataclass(frozen=True)
class AgentConfig:
    model: str
    max_tokens: int
    max_tool_rounds: int
    prompt_version: str
    toolkits: list[str]
    user_id_prefix: str
    trace_dir: Path
    correction_context: str


class ComposioOpenAIResearcher:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        (
            self.openai_mod,
            self.composio_cls,
            self.mcp_client_session_cls,
            self.streamable_http_client,
            self.httpx_mod,
        ) = require_agent_dependencies()

    def research(self, app: AppInput) -> AppResearchResult:
        return asyncio.run(self._research_async(app))

    async def _research_async(self, app: AppInput) -> AppResearchResult:
        trace = TraceLogger(self.config.trace_dir, app)
        trace.log(
            "start_app",
            {
                "app": app.model_dump(mode="json"),
                "prompt_version": self.config.prompt_version,
                "model": self.config.model,
                "toolkits": self.config.toolkits,
                "correction_context": self.config.correction_context,
            },
        )

        composio = self.composio_cls()
        client = self.openai_mod.AsyncOpenAI()
        user_id = f"{self.config.user_id_prefix}-{app.id}"

        create_kwargs: dict[str, Any] = {"user_id": user_id, "mcp": True}
        if self.config.toolkits:
            create_kwargs["toolkits"] = self.config.toolkits
        session = composio.create(**create_kwargs)
        trace.log("composio_session_created", {"mcp": redact_mcp(session)})

        mcp_endpoint = getattr(session, "mcp", None)
        if not mcp_endpoint or not getattr(mcp_endpoint, "url", None):
            raise RuntimeError("Composio did not return a hosted MCP endpoint")
        mcp_url = str(mcp_endpoint.url)
        mcp_headers = dict(getattr(mcp_endpoint, "headers", {}) or {})

        pass_instructions = (
            PASS2_RESEARCH_INSTRUCTIONS
            if self.config.prompt_version == "pass2"
            else PASS1_RESEARCH_INSTRUCTIONS
        )
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": self._build_app_prompt(
                    app,
                    pass_instructions,
                    self.config.correction_context,
                ),
            }
        ]

        async with self.httpx_mod.AsyncClient(headers=mcp_headers, timeout=120.0) as http_client:
            async with self.streamable_http_client(
                mcp_url,
                http_client=http_client,
            ) as (read_stream, write_stream, _):
                async with self.mcp_client_session_cls(read_stream, write_stream) as mcp_session:
                    await mcp_session.initialize()
                    mcp_tools_response = await mcp_session.list_tools()
                    tools = [
                        openai_tool_schema(
                            tool.name,
                            tool.description or "",
                            tool.inputSchema,
                        )
                        for tool in mcp_tools_response.tools
                    ]
                    tools.append(final_tool_schema())
                    trace.log(
                        "mcp_tools_loaded",
                        {
                            "transport": "hosted_mcp_streamable_http",
                            "tool_count": len(tools),
                            "tool_names": [
                                tool["function"]["name"] for tool in tools
                            ],
                        },
                    )

                    for round_index in range(1, self.config.max_tool_rounds + 1):
                        request_kwargs: dict[str, Any] = {
                            "model": self.config.model,
                            "max_completion_tokens": self.config.max_tokens,
                            "tools": tools,
                            "messages": messages,
                        }
                        if round_index == self.config.max_tool_rounds:
                            request_kwargs["tool_choice"] = {
                                "type": "function",
                                "function": {"name": FINAL_TOOL_NAME},
                            }
                            request_kwargs["parallel_tool_calls"] = False
                        response = await client.chat.completions.create(
                            **request_kwargs,
                        )
                        message = response.choices[0].message
                        tool_calls = list(message.tool_calls or [])
                        trace.log(
                            "model_response",
                            {
                                "round": round_index,
                                "finish_reason": response.choices[0].finish_reason,
                                "usage": (
                                    response.usage.model_dump()
                                    if response.usage
                                    else None
                                ),
                                "assistant_text": message.content or "",
                            },
                        )

                        final_calls = [
                            call for call in tool_calls if tool_name(call) == FINAL_TOOL_NAME
                        ]
                        if final_calls and len(tool_calls) == len(final_calls):
                            try:
                                raw_result = json.loads(
                                    final_calls[-1].function.arguments
                                )
                                trace.log(
                                    "final_tool_called",
                                    {"raw_result": raw_result},
                                )
                                result = AppResearchResult.model_validate(raw_result)
                            except (json.JSONDecodeError, ValueError) as exc:
                                trace.log(
                                    "final_validation_failed",
                                    {
                                        "round": round_index,
                                        "error": str(exc),
                                    },
                                )
                                if round_index == self.config.max_tool_rounds:
                                    raise
                                messages.append(
                                    message.model_dump(exclude_none=True)
                                )
                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": final_calls[-1].id,
                                        "content": (
                                            "Validation failed. Correct the result and "
                                            f"call {FINAL_TOOL_NAME} alone: {exc}"
                                        ),
                                    }
                                )
                                continue
                            if (
                                result.id != app.id
                                or result.app != app.app
                                or result.category != app.category
                            ):
                                trace.log(
                                    "input_identity_corrected",
                                    {
                                        "model_identity": {
                                            "id": result.id,
                                            "app": result.app,
                                            "category": result.category,
                                        },
                                        "expected_identity": {
                                            "id": app.id,
                                            "app": app.app,
                                            "category": app.category,
                                        },
                                    },
                                )
                                result = result.model_copy(
                                    update={
                                        "id": app.id,
                                        "app": app.app,
                                        "category": app.category,
                                    }
                                )
                                result = AppResearchResult.model_validate(
                                    result.model_dump(mode="json")
                                )
                            trace.log(
                                "validated_result",
                                {"result": result.model_dump(mode="json")},
                            )
                            return result

                        if not tool_calls:
                            trace.log("no_tool_call", {"round": round_index})
                            messages.append(message.model_dump(exclude_none=True))
                            messages.append(
                                {
                                    "role": "user",
                                    "content": (
                                        "Continue the research and then call record_app_research "
                                        "with the schema."
                                    ),
                                }
                            )
                            continue

                        if final_calls:
                            trace.log(
                                "mixed_final_tool_turn",
                                {"tool_names": [tool_name(call) for call in tool_calls]},
                            )

                        trace.log(
                            "tool_calls_requested",
                            {
                                "round": round_index,
                                "calls": [
                                    {
                                        "id": call.id,
                                        "name": tool_name(call),
                                        "input": json.loads(call.function.arguments),
                                    }
                                    for call in tool_calls
                                ],
                            },
                        )
                        results = await asyncio.gather(
                            *[
                                self._call_mcp_tool(mcp_session, call)
                                if tool_name(call) != FINAL_TOOL_NAME
                                else asyncio.sleep(
                                    0,
                                    result={
                                        "content": (
                                            "Rejected: record_app_research must be called "
                                            "alone in its own model turn."
                                        ),
                                        "isError": True,
                                    },
                                )
                                for call in tool_calls
                            ]
                        )
                        trace.log(
                            "tool_results",
                            {
                                "round": round_index,
                                "result_count": len(results),
                                "results_truncated": [
                                    truncate(result, 1500) for result in results
                                ],
                            },
                        )

                        messages.append(message.model_dump(exclude_none=True))
                        for call, result in zip(tool_calls, results, strict=True):
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": call.id,
                                    "content": json.dumps(
                                        result,
                                        ensure_ascii=False,
                                        default=str,
                                    ),
                                }
                            )
                        if round_index >= self.config.max_tool_rounds - 2:
                            messages.append(
                                {
                                    "role": "user",
                                    "content": (
                                        "Conclude from the evidence already gathered. "
                                        f"Call {FINAL_TOOL_NAME} alone now; mark uncertain "
                                        "fields for human review instead of researching further."
                                    ),
                                }
                            )

        raise RuntimeError(
            f"Agent exhausted {self.config.max_tool_rounds} tool rounds without a valid "
            f"{FINAL_TOOL_NAME} call for app {app.id} {app.app}."
        )

    @staticmethod
    async def _call_mcp_tool(mcp_session: Any, tool_call: Any) -> dict[str, Any]:
        try:
            result = await mcp_session.call_tool(
                tool_call.function.name,
                arguments=json.loads(tool_call.function.arguments),
            )
            if hasattr(result, "model_dump"):
                return result.model_dump(mode="json", by_alias=True)
            return {"content": str(result), "isError": False}
        except Exception as exc:  # noqa: BLE001 - tool errors are returned to the model for recovery.
            return {
                "content": f"{exc.__class__.__name__}: {exc}",
                "isError": True,
            }

    @staticmethod
    def _build_app_prompt(
        app: AppInput,
        pass_instructions: str,
        correction_context: str,
    ) -> str:
        hint = f"\nHint URL: {app.hint_url}" if app.hint_url else ""
        correction = (
            f"\nObserved pass-1 failure modes to correct:\n{correction_context}\n"
            if correction_context
            else ""
        )
        return f"""
{pass_instructions}
{correction}

Assignment app:
- id: {app.id}
- app: {app.app}
- category: {app.category}{hint}

Required output fields:
- one-line description
- auth method(s)
- self-serve vs gated tier and why if gated
- API surface type, breadth, and whether an existing MCP exists
- buildability verdict and main blocker if not ready_today
- evidence URLs that support the answers
- rate-limit notes, notable signals, confidence, and human-review flag
"""


def research_with_retries(
    researcher: ComposioOpenAIResearcher,
    app: AppInput,
    max_attempts: int,
) -> AppResearchResult:
    last_error: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return researcher.research(app)
        except Exception as exc:  # noqa: BLE001 - retries need to classify SDK/network errors.
            last_error = exc
            if attempt >= max_attempts or not is_transient_error(exc):
                raise
            sleep_seconds = min(60.0, (2**attempt) + random.random())
            time.sleep(sleep_seconds)
    raise RuntimeError("unreachable retry state") from last_error


def select_apps(
    apps: list[AppInput],
    ids: set[int] | None,
    limit: int | None,
    already_done: set[int],
) -> list[AppInput]:
    selected = [app for app in apps if app.id not in already_done]
    if ids:
        selected = [app for app in selected if app.id in ids]
    if limit is not None:
        selected = selected[:limit]
    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Composio app-research agent.")
    parser.add_argument("--apps", type=Path, default=Path("apps.json"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--failures", type=Path, default=DEFAULT_FAILURES)
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_TRACE_DIR)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ids", type=int, nargs="*", default=None)
    parser.add_argument("--ids-file", type=Path, default=None)
    parser.add_argument("--concurrency", type=int, default=int(os.getenv("RESEARCH_CONCURRENCY", "8")))
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--max-tool-rounds", type=int, default=8)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.4"))
    parser.add_argument("--prompt-version", choices=["pass1", "pass2"], default="pass1")
    parser.add_argument(
        "--toolkits",
        default=os.getenv("COMPOSIO_TOOLKITS", "browser_tool"),
        help="Comma-separated Composio toolkit filters. Empty string leaves the session unfiltered.",
    )
    parser.add_argument("--user-id-prefix", default=os.getenv("COMPOSIO_USER_ID_PREFIX", "app-research"))
    parser.add_argument(
        "--correction-report",
        type=Path,
        default=Path("data/accuracy_report.json"),
        help="Pass-1 accuracy report used to ground the pass-2 prompt.",
    )
    parser.add_argument("--force", action="store_true", help="Ignore existing output checkpoints.")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--print-schema", action="store_true")
    return parser.parse_args()


def collect_ids(args: argparse.Namespace) -> set[int] | None:
    ids = set(args.ids or [])
    if args.ids_file:
        payload = json.loads(args.ids_file.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("--ids-file must contain a JSON array of integer IDs")
        ids.update(int(item) for item in payload)
    return ids or None


def load_correction_context(path: Path, prompt_version: str) -> str:
    if prompt_version != "pass2" or not path.exists():
        return ""
    payload = json.loads(path.read_text(encoding="utf-8"))
    lines: list[str] = []
    for failure in payload.get("common_failure_modes", []):
        lines.append(
            f"- {failure.get('mode', 'unknown')}: {failure.get('count', 0)} mismatches; "
            f"examples={failure.get('examples', [])}"
        )
    for fix in payload.get("recommended_agent_fixes", []):
        lines.append(f"- Required fix: {fix}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if args.print_schema:
        print(json.dumps(AppResearchResult.model_json_schema(), indent=2))
        return 0

    load_dotenv_if_present()
    apps = load_apps(args.apps)
    require_env("COMPOSIO_API_KEY")
    require_env("OPENAI_API_KEY")
    ids = collect_ids(args)
    if args.force:
        for path in (args.output, args.failures):
            if path.exists():
                path.unlink()
    done_ids = set() if args.force else existing_result_ids(args.output)
    selected = select_apps(apps, ids=ids, limit=args.limit, already_done=done_ids)
    if not selected:
        print("No apps to process; output checkpoint already contains selected IDs.")
        return 0

    toolkits = [toolkit.strip() for toolkit in args.toolkits.split(",") if toolkit.strip()]
    correction_context = load_correction_context(
        args.correction_report,
        args.prompt_version,
    )
    config = AgentConfig(
        model=args.model,
        max_tokens=args.max_tokens,
        max_tool_rounds=args.max_tool_rounds,
        prompt_version=args.prompt_version,
        toolkits=toolkits,
        user_id_prefix=args.user_id_prefix,
        trace_dir=args.trace_dir,
        correction_context=correction_context,
    )
    researcher = ComposioOpenAIResearcher(config)

    print(
        f"Processing {len(selected)} app(s) with concurrency={args.concurrency}, "
        f"prompt_version={args.prompt_version}, output={args.output}"
    )
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        future_map = {
            executor.submit(research_with_retries, researcher, app, args.max_attempts): app
            for app in selected
        }
        for future in concurrent.futures.as_completed(future_map):
            app = future_map[future]
            try:
                result = future.result()
                append_jsonl(args.output, result.model_dump(mode="json"))
                print(f"ok {app.id}: {app.app}")
            except Exception as exc:  # noqa: BLE001 - preserve app-level failures and continue.
                failures += 1
                failure = {
                    "id": app.id,
                    "app": app.app,
                    "category": app.category,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                }
                append_jsonl(args.failures, failure)
                print(f"failed {app.id}: {app.app}: {exc}", file=sys.stderr)
                if args.fail_fast:
                    raise

    if failures:
        print(f"Completed with {failures} failure(s). See {args.failures}.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        exit_code = 2
    raise SystemExit(exit_code)
