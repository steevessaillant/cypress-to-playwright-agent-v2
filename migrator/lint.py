"""Quality gate: static checks on the generated Playwright code."""
import re


def lint(code, cypress_code=""):
    issues = []

    def add(sev, line, msg):
        issues.append({"severity": sev, "line": line, "message": msg})

    for n, raw in enumerate(code.splitlines(), 1):
        s = raw.strip()
        if s.startswith("//"):
            if "TODO(agent)" in s:
                add("error", n, "Unmigrated Cypress statement left by the rules")
            continue
        if re.search(r"\bcy\.|\bCypress\.", s):
            add("error", n, "Leftover Cypress API call")
        if re.match(r"\.(should|and|click|type|then|within|find)\(", s):
            add("error", n, "Orphan Cypress chain fragment (multi-line chain not migrated)")
        if "waitForTimeout" in s:
            add("warning", n, "Hard wait: prefer web-first assertions or waitForResponse")
        if re.match(r"(page|expect)\b", s):
            add("error", n, "Missing await on a Playwright call")
        if ".then(" in s:
            add("warning", n, "Promise chain: use async/await")
    if "@playwright/test" not in code:
        add("error", 0, "Missing import from @playwright/test")
    if cypress_code:
        src = len(re.findall(r"^\s*(?:it|specify)(?:\.\w+)?\(", cypress_code, re.M))
        dst = len(re.findall(r"^\s*test(?:\.(?:skip|only|fixme))?\(", code, re.M))
        if src != dst:
            add("error", 0, f"Test parity mismatch: {src} Cypress tests vs {dst} Playwright tests")
    errors = sum(i["severity"] == "error" for i in issues)
    warns = len(issues) - errors
    return {"passed": errors == 0, "score": max(0, 100 - 25 * errors - 5 * warns), "issues": issues}
