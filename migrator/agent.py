"""Tool-using migration agent built on the Anthropic Messages API."""
import json
import re

import anthropic

from .lint import lint
from .rules import convert

KNOWN = {"get", "contains", "visit", "url", "wait", "intercept", "request", "fixture", "log", "window",
         "document", "title", "location", "reload", "go", "viewport", "clearCookies", "clearLocalStorage",
         "setCookie", "getCookie", "task", "exec", "readFile", "writeFile", "then", "wrap", "on"}

SYSTEM = """You are a migration agent that converts Cypress tests to Playwright (TypeScript).
Workflow: 1) analyze_cypress  2) rule_based_convert for a deterministic draft  3) resolve every TODO(agent)
and anything the rules could not handle (cy.intercept -> page.route, aliases and cy.wait('@x') ->
page.waitForResponse, multi-line chains, fixtures)  4) lint_playwright on your FULL candidate file
5) iterate until the gate passes, then call submit_final.
Rules: auto-waiting locators and web-first assertions, no hard waits, always await, exactly one test()
per Cypress it(), preserve test names. Never invent behaviour. If something cannot be migrated safely,
leave a clear // MANUAL: comment and say so in the notes."""

TOOLS = [
    {"name": "analyze_cypress", "description": "Static analysis of the original Cypress spec: counts, risks, custom commands.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "rule_based_convert", "description": "Deterministic conversion of the original spec. Returns a draft and the lines it could not convert.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "lint_playwright", "description": "Quality gate for a candidate Playwright file (leftover cy., missing await, hard waits, test parity).",
     "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
    {"name": "submit_final", "description": "Submit the final Playwright file once the quality gate passes.",
     "input_schema": {"type": "object", "properties": {"code": {"type": "string"}, "notes": {"type": "string"}},
                      "required": ["code"]}},
]


def analyze(code):
    cmds = re.findall(r"cy\.(\w+)", code)
    return {
        "tests": len(re.findall(r"^\s*(?:it|specify)(?:\.\w+)?\(", code, re.M)),
        "describe_blocks": len(re.findall(r"^\s*(?:describe|context)\(", code, re.M)),
        "hooks": re.findall(r"^\s*(before|beforeEach|after|afterEach)\(", code, re.M),
        "intercepts": cmds.count("intercept"),
        "hard_waits": len(re.findall(r"cy\.wait\(\d+\)", code)),
        "aliased_waits": len(re.findall(r"cy\.wait\('@", code)),
        "multiline_chains": len(re.findall(r"^\s*\.(should|click|type|and)\(", code, re.M)),
        "custom_commands": sorted(set(cmds) - KNOWN),
        "fixtures": len(re.findall(r"fixture", code)),
    }


def run_agent(cypress_code, api_key, model, max_steps=8):
    """Generator yielding events: text | tool_call | tool_result | final | error."""
    client = anthropic.Anthropic(api_key=api_key, timeout=120.0)
    messages = [{"role": "user", "content": f"Migrate this Cypress spec to Playwright:\n\n```js\n{cypress_code}\n```"}]
    draft = ""
    for step in range(1, max_steps + 1):
        try:
            resp = client.messages.create(model=model, max_tokens=4000, system=SYSTEM,
                                          tools=TOOLS, messages=messages)
        except Exception as exc:  # surface API/auth errors in the UI
            yield {"type": "error", "message": str(exc)}
            return
        if resp.stop_reason == "max_tokens":
            yield {"type": "error", "message": "Model output was truncated (max_tokens). Try a shorter spec."}
            return
        messages.append({"role": "assistant", "content": resp.content})
        calls = [b for b in resp.content if b.type == "tool_use"]
        for b in resp.content:
            if b.type == "text" and b.text.strip():
                yield {"type": "text", "text": b.text}
        if not calls:
            break
        results, final = [], None
        for c in calls:
            yield {"type": "tool_call", "name": c.name, "step": step}
            if c.name == "analyze_cypress":
                out = analyze(cypress_code)
            elif c.name == "rule_based_convert":
                out = convert(cypress_code)
                draft = out["code"]
            elif c.name == "lint_playwright":
                out = lint(c.input.get("code", ""), cypress_code)
            elif c.name == "submit_final":
                code = c.input.get("code", "")
                final = {"code": code, "notes": c.input.get("notes", ""), "lint": lint(code, cypress_code)}
                out = {"accepted": True}
            else:
                out = {"error": f"unknown tool {c.name}"}
            yield {"type": "tool_result", "name": c.name, "result": out}
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": json.dumps(out)})
        messages.append({"role": "user", "content": results})
        if final:
            yield {"type": "final", **final}
            return
    # Agent ran out of steps: fall back to the deterministic draft
    fallback = draft or convert(cypress_code)["code"]
    yield {"type": "final", "code": fallback, "lint": lint(fallback, cypress_code),
           "notes": "Agent hit the step limit; showing the rule-based draft."}
