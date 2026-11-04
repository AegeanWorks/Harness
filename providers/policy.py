"""LLM policy: call the active OpenAI-compatible provider, fail over cleanly.

The model returns exactly one Action JSON object. Transport is stdlib
urllib HTTPS POST. Keys come from env at call time and are never logged.
On provider failure the policy returns a wait action so the loop survives;
the caller may retry or switch to the fallback provider.
"""
from __future__ import annotations

import json
import os
import urllib.request as _request
from typing import Any, Callable, Dict, Optional

from providers.providers import get_provider, list_providers, load_registry

SYSTEM = ("You are a coding agent inside a sandbox. Reply with exactly one JSON "
          "object: {\"kind\": ..., \"args\": {...}}. Kinds: read, edit, exec, "
          "test, web, delegate_fg, delegate_bg, wait, finish. No prose.")


def _post_chat(base_url: str, chat_path: str, key: str, model: str,
               messages: list, timeout_s: int, max_tokens: int) -> str:
    url = base_url.rstrip("/") + chat_path
    body = json.dumps({"model": model, "messages": messages,
                       "max_tokens": max_tokens}).encode("utf-8")
    req = _request.Request(url, data=body, method="POST",
                           headers={"Content-Type": "application/json",
                                    "Authorization": "Bearer " + key})
    with _request.urlopen(req, timeout=max(1, timeout_s)) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except ValueError:
        raise RuntimeError("provider returned non-JSON") from None
    try:
        return str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("provider returned no choices[0].message.content") from None


def _parse_action(text: str) -> Dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in reply")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, dict) or "kind" not in data:
        raise ValueError("reply is not an Action")
    args = data.get("args", {})
    return {"kind": str(data["kind"]), "args": args if isinstance(args, dict) else {}}


def call_provider(provider: Dict[str, Any], messages: list) -> Dict[str, Any]:
    """One chat call; raises on transport/parse failure (caller records wait)."""
    env_name = str(provider.get("api_key_env", ""))
    key = os.getenv(env_name, "") if env_name else ""
    if not key:
        raise RuntimeError("provider key MISSING (%s)" % env_name)
    timeout_s = int(provider.get("timeout_s", 30) or 30)
    max_tokens = int(provider.get("max_tokens", 800) or 800)
    text = _post_chat(str(provider.get("base_url", "")).rstrip("/"),
                      str(provider.get("chat_path", "/chat/completions")),
                      key, str(provider.get("model", "")), messages,
                      timeout_s, max_tokens)
    return _parse_action(text)


def llm_policy(state: Dict[str, Any], root=None,
               history: Optional[list] = None,
               request_fn: Optional[Callable] = None) -> Dict[str, Any]:
    """Policy for harness.loop.run_task: never raises, returns wait on failure."""
    from providers.providers import active_name
    name = active_name(root)
    try:
        provider = get_provider(name, root)
    except ValueError as exc:
        return {"kind": "wait", "args": {"reason": "unknown provider: " + str(exc)[:120]}}
    messages = [{"role": "system", "content": SYSTEM}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": json.dumps(
        {"step": state.get("step", 0), "last_ok": state.get("last_ok"),
         "last_output": str(state.get("last_output", ""))[:2000]})})
    fn = request_fn or (lambda prov, msgs: call_provider(prov, msgs))
    try:
        return fn(provider, messages)
    except Exception as exc:  # noqa: BLE001 - provider faults become wait rows
        return {"kind": "wait", "args": {"reason": "PROVIDER_FAIL " + str(exc)[:160]}}


def with_fallback(state: Dict[str, Any], root=None, history=None,
                  request_fn=None) -> Dict[str, Any]:
    """Try active, then fallback_provider; wait only when both fail."""
    try:
        registry = load_registry(root)
    except ValueError as exc:
        return {"kind": "wait", "args": {"reason": "PROVIDER_FAIL " + str(exc)[:160]}}
    from providers.providers import active_name
    first = active_name(root)
    fallback = str(registry.get("fallback_provider", "") or "")
    order = [first] + ([fallback] if fallback and fallback != first else [])
    last_err = ""
    fn = request_fn or (lambda prov, msgs: call_provider(prov, msgs))
    for name in order:
        try:
            provider = get_provider(name, root)
        except ValueError as exc:
            last_err = str(exc)[:160]
            continue
        messages = [{"role": "system", "content": SYSTEM}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": json.dumps(
            {"step": state.get("step", 0), "provider": name})})
        try:
            action = fn(provider, messages)
            if name != first:
                action.setdefault("args", {})
                if isinstance(action["args"], dict):
                    action["args"]["_failed_over_from"] = first
            return action
        except Exception as exc:  # noqa: BLE001 - try the next provider
            last_err = str(exc)[:160]
            continue
    void_names = [str(p.get("name")) for p in list_providers(root)] if order else []
    _ = void_names
    return {"kind": "wait", "args": {"reason": "PROVIDER_FAIL both down: " + last_err}}
