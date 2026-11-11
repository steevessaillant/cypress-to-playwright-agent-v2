"""Deterministic Cypress -> Playwright rules. This is the agent's first tool:
cheap, predictable, and it leaves TODO markers for whatever it cannot convert."""
import re

ACTIONS = {"click": "click", "dblclick": "dblclick", "type": "fill", "clear": "clear",
           "check": "check", "uncheck": "uncheck", "select": "selectOption",
           "focus": "focus", "blur": "blur"}
SIMPLE = {"be.visible": "toBeVisible()", "exist": "toBeAttached()", "be.disabled": "toBeDisabled()",
          "be.enabled": "toBeEnabled()", "be.checked": "toBeChecked()", "be.empty": "toBeEmpty()"}
VALUED = {"have.text": "toHaveText", "contain": "toContainText", "contain.text": "toContainText",
          "have.value": "toHaveValue", "have.length": "toHaveCount", "have.class": "toHaveClass",
          "have.attr": "toHaveAttribute", "have.css": "toHaveCSS"}
Q = r"""((?:'[^']*'|"[^"]*"))"""
RE_GET = re.compile(r"^(\s*)cy\.get\(" + Q + r"\)\.(\w+)\((.*)\);?\s*$")
RE_CONTAINS = re.compile(r"^(\s*)cy\.contains\(" + Q + r"\)(?:\.(\w+)\((.*)\))?;?\s*$")
RE_VISIT = re.compile(r"^(\s*)cy\.visit\((.*)\);?\s*$")
RE_WAIT = re.compile(r"^(\s*)cy\.wait\((\d+)\);?\s*$")
RE_URL = re.compile(r"^(\s*)cy\.url\(\)\.should\((.*)\);?\s*$")
STRUCT = [
    (re.compile(r"^(\s*)(?:describe|context)(\.\w+)?\("), r"\1test.describe\2("),
    (re.compile(r"^(\s*)(?:it|specify)(\.\w+)?\((.*?),\s*(?:async\s*)?(?:function\s*)?\(\)\s*(?:=>)?\s*\{\s*$"),
     r"\1test\2(\3, async ({ page }) => {"),
    (re.compile(r"^(\s*)(beforeEach|afterEach)\(\s*(?:async\s*)?(?:function\s*)?\(\)\s*(?:=>)?\s*\{\s*$"),
     r"\1test.\2(async ({ page }) => {"),
]


def split_args(s):
    out, depth, quote, cur = [], 0, None, ""
    for ch in s:
        if quote:
            cur += ch
            quote = None if ch == quote else quote
        elif ch in "'\"`":
            quote, cur = ch, cur + ch
        elif ch in "([{":
            depth, cur = depth + 1, cur + ch
        elif ch in ")]}":
            depth, cur = depth - 1, cur + ch
        elif ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def unquote(s):
    return s.strip().strip("'\"`")


def assertion(target, args):
    parts = split_args(args)
    if not parts:
        return None
    kind, vals = unquote(parts[0]), parts[1:]
    neg = kind.startswith("not.")
    base = kind[4:] if neg else kind
    exp = f"expect({target})" + (".not" if neg else "")
    if neg and base == "be.visible":
        return f"await expect({target}).toBeHidden();"
    if neg and base == "exist":
        return f"await expect({target}).toHaveCount(0);"
    if base in SIMPLE:
        return f"await {exp}.{SIMPLE[base]};"
    if base in VALUED and vals:
        return f"await {exp}.{VALUED[base]}({', '.join(vals)});"
    return None


def _emit(ind, target, method, args):
    if method in ("should", "and"):
        a = assertion(target, args)
        return f"{ind}{a}" if a else None
    if method == "type":
        if "{enter}" in args:
            return (f"{ind}await {target}.fill({args.replace('{enter}', '')});\n"
                    f"{ind}await {target}.press('Enter');")
        return f"{ind}await {target}.fill({args});"
    if method in ACTIONS:
        return f"{ind}await {target}.{ACTIONS[method]}({args});"
    return None


def convert_line(line):
    for pat, repl in STRUCT:
        if pat.match(line):
            return pat.sub(repl, line)
    m = RE_VISIT.match(line)
    if m:
        return f"{m[1]}await page.goto({m[2]});" if len(split_args(m[2])) == 1 else None
    m = RE_WAIT.match(line)
    if m:
        return f"{m[1]}await page.waitForTimeout({m[2]}); // TODO: replace hard wait with an auto-waiting assertion"
    m = RE_URL.match(line)
    if m:
        p = split_args(m[2])
        if len(p) == 2 and unquote(p[0]) in ("include", "contain"):
            return f"{m[1]}await expect(page).toHaveURL(new RegExp({p[1]}));"
        if len(p) == 2 and unquote(p[0]) in ("eq", "equal"):
            return f"{m[1]}await expect(page).toHaveURL({p[1]});"
        return None
    m = RE_GET.match(line)
    if m:
        return _emit(m[1], f"page.locator({m[2]})", m[3], m[4])
    m = RE_CONTAINS.match(line)
    if m:
        target = f"page.getByText({m[2]})"
        if not m[3]:
            return f"{m[1]}await expect({target}).toBeVisible();"
        return _emit(m[1], target, m[3], m[4])
    return None


def convert(code):
    out = ["import { test, expect } from '@playwright/test';", ""]
    todos = []
    for i, line in enumerate(code.splitlines(), 1):
        s = line.strip()
        if s.startswith("///"):
            continue
        new = convert_line(line)
        if new is None:
            if "cy." in s and not s.startswith("//"):
                todos.append({"line": i, "source": s})
                ind = line[: len(line) - len(line.lstrip())]
                new = f"{ind}// TODO(agent): migrate -> {s}"
            else:
                new = line
        out.append(new)
    return {"code": "\n".join(out) + "\n", "todo_lines": todos}
