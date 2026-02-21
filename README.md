# Policy-Aware SME Loan Pre-Screening (NSWS-Style Prototype)

A GenAI-powered decision-support system designed to reduce the time
spent reading complex and evolving policy documents during SME loan or
project pre-screening.

This prototype demonstrates how:

-   Large Language Models (LLMs) can structure unstructured borrower
    documents
-   Layered Retrieval-Augmented Generation (RAG) can ground reasoning in
    versioned policy rules
-   Human-in-the-loop governance ensures safe escalation
-   Audit logging supports regulatory traceability

**Note:** This is an academic / pilot prototype. It is not
production-grade credit software.

------------------------------------------------------------------------

## Problem Statement

Credit analysts and policy reviewers spend significant time:

-   Reading long and complex policy documents
-   Tracking state-specific rule changes
-   Reconciling borrower financials against thresholds
-   Checking sector-specific or environmental conditions
-   Identifying escalation triggers

In regulatory environments (for example, single-window or state policy
systems), rules:

-   Differ by state
-   Differ by sector
-   Change frequently
-   Require version tracking and governance

This system demonstrates how to:

-   Separate policy knowledge from borrower data
-   Automatically retrieve only relevant rules
-   Ground reasoning in cited policy clauses
-   Preserve human authority over final decisions

------------------------------------------------------------------------

## System Architecture Overview

The system follows a layered policy + LLM reasoning pipeline.

------------------------------------------------------------------------

## 1. Policy Knowledge (Layered RAG)

Policy documents are uploaded via the sidebar and categorized by:

### Policy Layers

-   `base_policy` -- Central or baseline lending rules
-   `state_rules` -- State-specific policies
-   `sector_rules` -- Sector-specific rules
-   `environment` -- Environmental or compliance regulations

### Policy Scope

-   State (e.g., Uttarakhand or ALL)
-   Sector (e.g., warehouse or ALL)

### Versioning

-   Effective date / version identifier

Each policy version is:

-   Chunked into overlapping segments
-   Embedded using `all-MiniLM-L6-v2`
-   Stored in ChromaDB under a layer-specific collection

Collections used:

    policy_base_policy
    policy_state_rules
    policy_sector_rules
    policy_environment

Only policies marked **ACTIVE** are used during retrieval.

------------------------------------------------------------------------

## 2. Borrower Case Documents

Borrower documents are uploaded in the main interface and may include:

-   Bank statement summaries
-   GST summaries
-   Financial summaries
-   Project or compliance documents

These documents are:

-   Parsed into raw text
-   Concatenated per case
-   Not stored in the vector database

They are case-specific and transient.

------------------------------------------------------------------------

## End-to-End Pipeline

### Step 1: LLM Fact Extraction (No RAG)

The LLM reads borrower documents and outputs structured JSON:

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
      "cashflow_trend": "improving | stable | declining | null",
      "red_flags": [],
      "missing_documents": []
    }

This stage:

-   Normalizes messy data
-   Extracts key financial indicators
-   Identifies preliminary red flags
-   Does not apply policy logic

------------------------------------------------------------------------

### Step 2: Layered Policy Retrieval (RAG)

Based on case context (State and Sector), policy retrieval follows this
priority order:

1.  (State, Sector)
2.  (State, ALL)
3.  (ALL, Sector)
4.  (ALL, ALL)

This retrieval is performed independently across all policy layers:

-   Base policy
-   State rules
-   Sector rules
-   Environmental rules

Only ACTIVE policy versions are retrieved.

------------------------------------------------------------------------

### Step 3: Policy-Grounded Reasoning (RAG + LLM)

The LLM receives:

-   Extracted borrower JSON
-   Retrieved policy snippets (with references)
-   Explicit instructions to use only retrieved snippets

The model:

-   Maps facts to policy rules
-   Identifies policy-driven risks
-   Cites exact policy snippets (e.g., `[BASE-2][STATE-1]`)
-   Recommends escalation: YES or NO

This produces an auditable, policy-grounded rationale.

------------------------------------------------------------------------

### Step 4: Memo Drafting (LLM Formatting Only)

The LLM drafts a structured pre-screen memo including:

-   Borrower summary
-   Key risks
-   Missing documentation
-   Suggested recommendation

The model does not make final decisions.

------------------------------------------------------------------------

### Step 5: Human-in-the-Loop Decision

The analyst:

-   Reviews extracted facts
-   Reviews policy-grounded rationale
-   Decides whether to escalate, hold, or reject
-   May override AI outputs

The system logs:

-   Model used
-   Prompt headers
-   Case context
-   Policy registry state

------------------------------------------------------------------------

## Governance and Risk Controls

The prototype implements:

-   Versioned policy registry
-   Draft-to-active promotion workflow
-   Layer isolation in retrieval
-   Mandatory policy citation
-   Human escalation gate
-   Audit logging

RAG reduces hallucination risk by:

-   Constraining reasoning to retrieved policy snippets
-   Enforcing citation
-   Preventing invented policy rules

Human review remains mandatory.

------------------------------------------------------------------------

## Repository Structure

    app.py
    rag_store.py
    policy_registry.py
    chroma_db/
    policy_registry.json
    audit_log.jsonl
    requirements.txt

------------------------------------------------------------------------

## Local Setup and Execution

### Pre-requisites

-   Python 3.10 or higher
-   Ollama installed locally
-   Llama 3.2 model pulled via Ollama

### Clone the Repository

    git clone https://github.com/<your-username>/sme-genai-prototype.git
    cd sme-genai-prototype

### Install Dependencies

    pip install -r requirements.txt

### Pull the LLM Model

    ollama pull llama3.2:latest

### Run the Application

    streamlit run app.py

Open in browser:

    http://localhost:8501

------------------------------------------------------------------------

## Core Design Principle

This is not an LLM demo.

It is a policy-aware regulatory decision-support system combining:

-   Structured extraction
-   Layered retrieval
-   Human governance
