# Cypress → Playwright migration agent (v2)

A Streamlit demo of an **AI agent that uses tools** to migrate Cypress specs to Playwright (TypeScript).

## How it works
1. `analyze_cypress`: static analysis (tests, intercepts, hard waits, multi-line chains, custom commands)
2. `rule_based_convert`: deterministic draft; anything it can't convert is marked `TODO(agent)`
3. The model resolves the gaps (`cy.intercept` → `page.route`, aliased waits → `waitForResponse`, ...)
4. `lint_playwright`: **quality gate** (leftover `cy.`, missing `await`, hard waits, test-count parity)
5. The agent loops until the gate passes, then calls `submit_final`

Cheap deterministic rules do the bulk of the work; the LLM only handles what rules can't, and its output
is always verified by a non-AI gate. **Rules-only mode runs offline, no API key needed.**

## Run (Windows PowerShell)
```powershell
cd C:\src\cypress-to-playwright-agent-v2
.\run.ps1                       # creates .venv, installs, runs tests, starts the app
```
Or manually:
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```
Agent mode needs an Anthropic API key (Claude Console, separate from a Claude Pro subscription):
`$env:ANTHROPIC_API_KEY = "sk-ant-..."` or paste it in the sidebar. Never commit it.

## Layout
`app.py` UI · `migrator/rules.py` rules · `migrator/lint.py` quality gate · `migrator/agent.py` agent loop ·
`tests/` pytest · `.github/workflows/ci.yml` CI · `run.ps1` Windows launcher
