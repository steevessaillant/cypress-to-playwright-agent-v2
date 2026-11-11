import os
from pathlib import Path

import streamlit as st

from migrator.agent import run_agent
from migrator.lint import lint
from migrator.rules import convert

st.set_page_config(page_title="Cypress → Playwright Agent", page_icon="🎭", layout="wide")
SAMPLE = (Path(__file__).parent / "samples" / "login.cy.js").read_text(encoding="utf-8")

st.title("🎭 Cypress → Playwright migration agent")
st.caption("Deterministic rules + an AI agent that calls tools (analyze, convert, lint, submit) "
           "until the quality gate passes.")

with st.sidebar:
    mode = st.radio("Mode", ["AI agent (Claude)", "Rules only (offline)"])
    api_key = st.text_input("Anthropic API key", value=os.getenv("ANTHROPIC_API_KEY", ""), type="password")
    model = st.text_input("Model", value=os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"))
    max_steps = st.slider("Max agent steps", 3, 12, 8)
    st.markdown("**Agent tools**\n- `analyze_cypress`\n- `rule_based_convert`\n- `lint_playwright` (quality gate)\n- `submit_final`")

left, right = st.columns(2)
with left:
    src = st.text_area("Cypress spec", value=SAMPLE, height=480)
    run = st.button("Migrate", type="primary")

with right:
    if run:
        st.session_state.pop("result", None)
        if mode.startswith("Rules"):
            res = convert(src)
            st.session_state["result"] = {"code": res["code"], "lint": lint(res["code"], src),
                                          "notes": f"Rules only. {len(res['todo_lines'])} line(s) need an agent or a human."}
        elif not api_key:
            st.error("Add an Anthropic API key in the sidebar, or switch to rules-only mode.")
        else:
            with st.status("Agent working…", expanded=True) as status:
                for ev in run_agent(src, api_key, model, max_steps):
                    if ev["type"] == "text":
                        st.write(ev["text"])
                    elif ev["type"] == "tool_call":
                        st.write(f"🔧 step {ev['step']}: `{ev['name']}`")
                    elif ev["type"] == "tool_result":
                        with st.expander(f"result: {ev['name']}"):
                            st.json(ev["result"])
                    elif ev["type"] == "error":
                        status.update(label="Agent error", state="error")
                        st.error(ev["message"])
                    elif ev["type"] == "final":
                        st.session_state["result"] = ev
                        status.update(label="Done", state="complete")

    res = st.session_state.get("result")
    if res:
        gate = res["lint"]
        c1, c2 = st.columns(2)
        c1.metric("Quality gate", "PASSED" if gate["passed"] else "FAILED")
        c2.metric("Score", gate["score"])
        if res.get("notes"):
            st.info(res["notes"])
        st.code(res["code"], language="typescript")
        st.download_button("Download .spec.ts", res["code"], file_name="migrated.spec.ts")
        if gate["issues"]:
            with st.expander(f"{len(gate['issues'])} lint issue(s)"):
                st.table(gate["issues"])
