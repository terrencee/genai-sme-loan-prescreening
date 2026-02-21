import streamlit as st
import fitz  # PyMuPDF
import json
import subprocess
from datetime import datetime
from rag_store import RAGStore
from policy_registry import add_policy_entry, set_policy_status, list_policies

st.set_page_config(page_title="Policy-Aware SME Pre-Screening (NSWS-style)", layout="wide")
st.title("Policy-Aware SME Loan Pre-Screening (NSWS-style Prototype)")
st.caption("LLM + Layered Policy RAG + Human-in-the-loop | Goal: reduce time spent reading complex, changing rules")

# ---------------- Core Stores ----------------
rag = RAGStore(path="./chroma_db")  # Uses separate Chroma collections per layer internally (policy_<layer>)

POLICY_LAYERS = ["base_policy", "state_rules", "sector_rules", "environment"]

# ---------------- Helpers ----------------
def pdf_to_text(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)

def call_ollama(prompt: str, model="llama3.2:latest", timeout_s: int = 180) -> str:
    """
    Safer than check_output: captures stderr and times out cleanly.
    """
    cmd = ["ollama", "run", model, prompt]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        if r.returncode != 0:
            return f"ERROR: Ollama returned code {r.returncode}\n{r.stderr.strip()}"
        return r.stdout
    except subprocess.TimeoutExpired:
        return "ERROR: Ollama call timed out."

def audit_log(event: dict):
    with open("audit_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def merge_dedup(snips, max_n=8):
    seen = set()
    out = []
    for s in snips:
        key = (s or "")[:220]
        if key and key not in seen:
            seen.add(key)
            out.append(s)
        if len(out) >= max_n:
            break
    return out

def retrieve_layer_snips(layer: str, query: str, k: int, state: str, sector: str):
    """
    Chroma where filtering doesn't handle OR conditions nicely, so we do four scoped lookups and merge:
    (state,sector), (state,ALL), (ALL,sector), (ALL,ALL). Only ACTIVE policies.
    """
    scopes = [
        {"status": "active", "state": state, "sector": sector},
        {"status": "active", "state": state, "sector": "ALL"},
        {"status": "active", "state": "ALL", "sector": sector},
        {"status": "active", "state": "ALL", "sector": "ALL"},
    ]
    merged = []
    for w in scopes:
        try:
            merged.extend(rag.retrieve(layer=layer, query=query, k=k, where=w))
        except Exception:
            # If a where filter fails for any reason, fall back to broad retrieval
            merged.extend(rag.retrieve(layer=layer, query=query, k=k))
    return merge_dedup(merged, max_n=k)

# ---------------- Sidebar: Policy Admin (NSWS-style) ----------------
st.sidebar.header("Policy Admin (NSWS-style)")
st.sidebar.caption("Upload policies by layer + scope + version. Keep drafts. Activate only after human review.")

policy_pdf = st.sidebar.file_uploader("Upload Policy PDF", type=["pdf"])

policy_layer = st.sidebar.selectbox("Policy layer", POLICY_LAYERS)

policy_state = st.sidebar.text_input("State scope (e.g., Uttarakhand or ALL)", value="ALL")
policy_sector = st.sidebar.text_input("Sector scope (e.g., warehouse or ALL)", value="ALL")
policy_version = st.sidebar.text_input("Version / Effective date (YYYY-MM-DD)", value=datetime.utcnow().date().isoformat())

policy_status = st.sidebar.selectbox("Initial status", ["draft", "active"], index=0)

if policy_pdf:
    if not policy_version.strip():
        st.sidebar.error("Please enter a version/effective date.")
    else:
        policy_bytes = policy_pdf.read()
        policy_text = pdf_to_text(policy_bytes)

        # policy_id uniquely identifies a policy version for a given scope+layer
        policy_id = f"{policy_state}::{policy_sector}::{policy_layer}::{policy_version}"

        metadata = {
            "doc_name": policy_pdf.name,
            "layer": policy_layer,
            "state": policy_state,
            "sector": policy_sector,
            "version": policy_version,
            "effective_date": policy_version,
            "status": policy_status,
        }

        # Store into the correct layer collection
        rag.upsert_policy(
            layer=policy_layer,
            policy_id=policy_id,
            text=policy_text,
            metadata=metadata
        )

        # Registry (governance record)
        add_policy_entry({
            "policy_id": policy_id,
            **metadata,
            "uploaded_at": datetime.utcnow().isoformat()
        })

        st.sidebar.success(f"Ingested: {policy_id} ({policy_status})")

st.sidebar.divider()
st.sidebar.subheader("Policy Activation (Human-in-the-loop)")

policies = list_policies()
drafts = [p for p in policies if p.get("status") == "draft"]
draft_ids = [p["policy_id"] for p in drafts]

if draft_ids:
    to_activate = st.sidebar.selectbox("Draft policy versions", draft_ids)
    if st.sidebar.button("Mark Draft → Active (Registry)", type="primary"):
        # NOTE: this updates registry; Chroma metadata remains as-uploaded.
        # For demo: upload as 'active' when you want it live OR implement re-upsert with status=active.
        set_policy_status(to_activate, "active", approved_by="analyst")
        st.sidebar.success(f"Activated (registry): {to_activate}")
else:
    st.sidebar.info("No drafts in registry.")

st.sidebar.divider()
st.sidebar.header("Run Controls")
model_name = st.sidebar.selectbox("Ollama model", ["llama3.2:latest"])
k = st.sidebar.slider("Snippets per layer (k)", 2, 6, 3)

# ---------------- Main: Case Context ----------------
st.header("Step 1 — Case Context")
case_state = st.selectbox("State", ["Uttarakhand", "Maharashtra", "ALL"])
case_sector = st.selectbox("Sector", ["warehouse", "manufacturing", "ALL"])

# ---------------- Main: Borrower docs ----------------
st.header("Step 2 — Borrower Documents")
borrower_files = st.file_uploader(
    "Upload borrower PDFs (bank statement / GST / financial summaries)",
    type=["pdf"],
    accept_multiple_files=True
)

borrower_text = ""
if borrower_files:
    for f in borrower_files:
        borrower_text += f"\n\n--- {f.name} ---\n"
        borrower_text += pdf_to_text(f.read())

colA, colB = st.columns([1, 1])
with colA:
    run_btn = st.button("Run Pre-Screening", type="primary")
with colB:
    escalate_btn = st.button("Escalate (manual)")

if escalate_btn:
    st.warning("Escalation triggered (manual). Logged to audit.")
    audit_log({"timestamp": datetime.utcnow().isoformat(), "event": "ESCALATION_CLICKED"})

# ---------------- Prompts (system-governed; not editable in UI) ----------------
EXTRACTION_PROMPT_TEMPLATE = """
You are a regulated credit/policy pre-screening assistant.
Extract key facts from borrower/project documents into STRICT JSON only (no commentary).
If unknown, use null. Do not guess.

JSON schema:
{
  "business_name": "",
  "loan_amount_requested": null,
  "annual_turnover": null,
  "avg_monthly_bank_credits": null,
  "gst_reported_sales": null,
  "existing_loan_obligations": {
    "term_loan_emi": null,
    "vehicle_loan_emi": null
  },
  "cashflow_trend": "improving|stable|declining|null",
  "red_flags": [],
  "missing_documents": []
}

Borrower documents:
{borrower_text}
"""

RATIONALE_PROMPT_TEMPLATE = """
You MUST only use the policy snippets below as authoritative sources.
Do not invent policy rules. If something is missing, say "Not enough policy context retrieved" and recommend escalation.

Context:
- State: {state}
- Sector: {sector}

Policy snippets (layered):
{snippets_block}

Borrower extraction JSON:
{extraction_json}

Task:
- List top risks (max 7)
- For each risk, cite snippet references like [BASE-2][STATE-1]
- Identify any state/sector specific compliance gates implied by retrieved policy (if any)
- Recommend escalation: YES/NO with 1-line justification
"""

MEMO_PROMPT_TEMPLATE = """
Write a 1-page pre-screen memo for a reviewer.
Professional tone, concise.

Include:
- Borrower summary (from extraction)
- Key risks (from policy-grounded rationale)
- Missing items
- Recommendation: Proceed / Hold / Reject (suggest only; human decides)

Borrower extraction JSON:
{extraction_json}

Policy-grounded rationale:
{rationale}
"""

if run_btn:
    # ---- Basic checks ----
    if not borrower_files:
        st.error("Upload at least one borrower PDF.")
        st.stop()

    # Require at least one ACTIVE policy in the system (practical check)
    any_active = any(p.get("status") == "active" for p in list_policies())
    if not any_active:
        st.error("No ACTIVE policies found. Upload at least one policy as ACTIVE (or activate a draft).")
        st.stop()

    # ---- 1) Extraction JSON ----
    st.subheader("1) Extract key facts (JSON)")
    extraction_prompt = EXTRACTION_PROMPT_TEMPLATE.format(borrower_text=borrower_text[:12000])
    extraction_raw = call_ollama(extraction_prompt, model=model_name)
    st.code(extraction_raw)

    # ---- 2) Layered RAG retrieval ----
    st.subheader("2) Policy-grounded rationale (Layered RAG)")

    query = "documentation requirements, mandatory docs, escalation thresholds, GST vs bank mismatch, cashflow volatility, sector or state compliance requirements"

    snips_base = retrieve_layer_snips("base_policy", query, k=k, state=case_state, sector=case_sector)
    snips_state = retrieve_layer_snips("state_rules", query, k=k, state=case_state, sector=case_sector)
    snips_sector = retrieve_layer_snips("sector_rules", query, k=k, state=case_state, sector=case_sector)
    snips_env = retrieve_layer_snips("environment", query, k=k, state=case_state, sector=case_sector)

    all_snips = {
        "BASE": snips_base,
        "STATE": snips_state,
        "SECTOR": snips_sector,
        "ENV": snips_env
    }

    st.markdown("**Retrieved policy snippets (layered grounding):**")
    for tag, snips in all_snips.items():
        if not snips:
            continue
        st.markdown(f"### {tag}")
        for i, snip in enumerate(snips, 1):
            with st.expander(f"{tag}-{i}"):
                st.write(snip)

    # Build snippet block with stable references
    snippet_lines = []
    for tag, snips in all_snips.items():
        for i, s in enumerate(snips, 1):
            snippet_lines.append(f"[{tag}-{i}] {s}")
    snippets_block = "\n".join(snippet_lines) if snippet_lines else "NONE RETRIEVED"

    # ---- 3) Policy-grounded rationale ----
    rationale_prompt = RATIONALE_PROMPT_TEMPLATE.format(
        state=case_state,
        sector=case_sector,
        snippets_block=snippets_block,
        extraction_json=extraction_raw
    )
    rationale = call_ollama(rationale_prompt, model=model_name)
    st.write(rationale)

    # ---- 4) Memo drafting ----
    st.subheader("3) Pre-screen memo draft (Human reviews)")
    memo_prompt = MEMO_PROMPT_TEMPLATE.format(extraction_json=extraction_raw, rationale=rationale)
    memo = call_ollama(memo_prompt, model=model_name)
    st.write(memo)

    # ---- Audit ----
    audit_log({
        "timestamp": datetime.utcnow().isoformat(),
        "event": "RUN_PRESCREEN",
        "case_state": case_state,
        "case_sector": case_sector,
        "borrower_files": [f.name for f in borrower_files],
        "rag_k_per_layer": k,
        "model": model_name,
        "policy_registry_count": len(list_policies()),
        "extraction_prompt_head": extraction_prompt[:800],
        "rationale_prompt_head": rationale_prompt[:800]
    })

    st.success("Done. Outputs generated + audit logged to audit_log.jsonl")