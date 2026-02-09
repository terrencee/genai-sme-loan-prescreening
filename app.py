import streamlit as st
import fitz  # PyMuPDF
import json
import subprocess
from datetime import datetime
from rag_store import RAGStore

st.set_page_config(page_title="SME GenAI Pre-Screening (Prototype)", layout="wide")
st.title("SME Loan GenAI Pre-Screening (Ollama Prototype)")
st.caption("LLM + RAG + Human-in-the-loop | Demo scope: document extraction + policy-grounded risk flags")

rag = RAGStore()

def pdf_to_text(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)

def call_ollama(prompt: str, model="llama3.2:latest") -> str:
    # Simple local call; good enough for prototype
    cmd = ["ollama", "run", model, prompt]
    return subprocess.check_output(cmd, text=True)

def audit_log(event: dict):
    with open("audit_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

# ---------------- Sidebar: Policy ingestion ----------------
st.sidebar.header("Step 1 — Policy (RAG)")
policy_pdf = st.sidebar.file_uploader("Upload Credit Policy PDF", type=["pdf"])

if policy_pdf:
    policy_bytes = policy_pdf.read()
    policy_text = pdf_to_text(policy_bytes)
    rag.upsert_document(policy_pdf.name, policy_text)
    st.sidebar.success("Policy indexed for RAG.")

st.sidebar.divider()
st.sidebar.header("Demo Controls")
model_name = st.sidebar.selectbox("Ollama model", ["llama3.2:latest"])
k = st.sidebar.slider("RAG snippets (k)", 3, 8, 5)

# ---------------- Main: Borrower docs ----------------
st.header("Step 2 — Borrower Documents")
borrower_files = st.file_uploader(
    "Upload borrower PDFs (bank statement / GST / financials)",
    type=["pdf"],
    accept_multiple_files=True
)

borrower_text = ""
if borrower_files:
    for f in borrower_files:
        borrower_text += f"\n\n--- {f.name} ---\n"
        borrower_text += pdf_to_text(f.read())

colA, colB = st.columns([1,1])
with colA:
    run_btn = st.button("Run Pre-Screening", type="primary")
with colB:
    escalate_btn = st.button("Escalate to Senior Credit Officer")

if escalate_btn:
    st.warning("Escalation triggered (demo). Logged to audit.")
    audit_log({"timestamp": datetime.utcnow().isoformat(), "event": "ESCALATION_CLICKED"})

if run_btn:
    if not policy_pdf:
        st.error("Upload a policy PDF first (RAG grounding).")
        st.stop()
    if not borrower_files:
        st.error("Upload at least one borrower PDF.")
        st.stop()

    # ---- 1) Extraction JSON ----
    st.subheader("1) Extract key facts (JSON)")
    extraction_prompt = f"""
You are a credit analyst assistant.
Extract key fields from borrower documents into STRICT JSON only (no commentary).
If unknown, use null.

JSON schema:
{{
  "business_name": "",
  "loan_amount_requested": null,
  "annual_turnover": null,
  "avg_monthly_bank_credits": null,
  "gst_reported_sales": null,
  "existing_loan_obligations": null,
  "cashflow_trend": "improving|stable|declining|null",
  "red_flags": ["..."],
  "missing_documents": ["..."]
}}

Borrower documents:
{borrower_text[:12000]}
"""
    extraction = call_ollama(extraction_prompt, model=model_name)
    st.code(extraction)

    # ---- 2) RAG grounded risk rationale ----
    st.subheader("2) Policy-grounded risk rationale (RAG)")
    query = "SME lending red flags, documentation requirements, GST vs bank mismatch, cashflow volatility, rework escalation"
    policy_snips = rag.retrieve(query, k=k)

    st.markdown("**Retrieved policy snippets (for grounding):**")
    for i, snip in enumerate(policy_snips, 1):
        with st.expander(f"Snippet {i}"):
            st.write(snip)

    rationale_prompt = f"""
You MUST only use the policy snippets below as authoritative sources.
Do not invent policy rules.

Policy snippets:
{chr(10).join([f"[{i+1}] {s}" for i,s in enumerate(policy_snips)])}

Borrower extraction JSON:
{extraction}

Task:
- List top risks (max 7)
- For each risk, cite snippet number(s) like [2][4]
- Recommend escalation: YES/NO with 1-line justification
"""
    rationale = call_ollama(rationale_prompt, model=model_name)
    st.write(rationale)

    # ---- 3) Credit memo ----
    st.subheader("3) Credit pre-screen memo draft (Human reviews)")
    memo_prompt = f"""
Write a 1-page pre-screen memo for a credit officer.
Professional tone, concise.

Include:
- Borrower summary (from extraction)
- Strengths (if any)
- Key risks (from policy-grounded rationale)
- Missing items
- Recommendation: Proceed / Hold / Reject (suggest only; human decides)

Borrower extraction JSON:
{extraction}

Policy-grounded rationale:
{rationale}
"""
    memo = call_ollama(memo_prompt, model=model_name)
    st.write(memo)

    # ---- Audit ----
    audit_log({
        "timestamp": datetime.utcnow().isoformat(),
        "event": "RUN_PRESCREEN",
        "policy_doc": policy_pdf.name,
        "borrower_files": [f.name for f in borrower_files],
        "rag_k": k,
        "model": model_name,
        "extraction_prompt_head": extraction_prompt[:800],
        "rationale_prompt_head": rationale_prompt[:800]
    })

    st.success("Done. Outputs generated + audit logged to audit_log.jsonl")
