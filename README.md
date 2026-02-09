# GenAI assissted Small and Medium Enterprise Pre Screening ( Prototype)

*We use the LLM to extract facts from borrower documents, then use RAG to retrieve the relevant policy clauses from ChromaDB, and finally generate a policy-grounded risk rationale and memo with a human escalation gate and audit logging.*

This rep containts a **locally run GenAI prototype** for SME losan pre screening designed for an academic/pilot setting.

**Sources of knowledge/ Docs being uploaded**

**A.  Policy Knowledge**

> SME credit policy, documentation rules, ecalation thresholds
> This does not change per borrower.
> Treated as a source o Truth.

**B. Borrower case documents**


> Bank statement summaries, gst, financial summaries.
> These change per case
> They are used to extract flags and compute flags

**These are the two kinds of docs we upload**

**Stepwise Pipeline**

*Step 0*

policy pdf is uploaded in the sidebar.
raw text is extracted from pdf.

**chunking** ( RAGStore._chunk)

Policy text is broken into overlapping chunks

   > A single huge policy doc wont reliably fit in context.
   > Retrieval works better at chunk level.

**Embedding**

  > Each chunk becomes a vector representing meaning.
  > These are stored in ChromaDB ( Vector DB )
      > chunk text
      > embedding vector
      > chunk id

*Policy can now be searched by semantic similarity*
**ChromaDB** > memory index enabling retrieval. Not thinking involved. Only store and search of embeddings.


**Next Step**

Borrower PDFs are uploaded in the main ection.
PDF --> text and concatenated into 1 borrower_text string.. 
Not stored in Chroma

**LLM Call 1**

  > Fact extraction into json :
    > Info extraction + normalization.
        > id business name
        > infer turnover figs
        > pick cashflow trend language
        > list redflags and missing docs.

*This step involves no RAG. Its simply the LLM reading case*
*ie it turns messy text to structured facts*

**Retrieval( RAG) from Policy**

We now issue a retrieval query.

> The qry is embedded into a vector
> Performs similarity search in ChromaDB and returns top-k policy chunks most similar to the query.

Thus what **retrieval**does is thatit selects few policy clauses relevant to the task.
Thus we dont have to dump the whole policy into the prompt.

**This is the R of RAG**

**LLM Call 2**

 Pass
 > retrieved policy snippets.
 > extracted json.
 > Our instructions to the LLM to use only the snippets ( citing snippet numbers and recommend escallation ( Y/N)
 )

 **What LLM does ?**

  > Maps facts --> Rules --> Decision recommendation.
  > Produces an explanation with citations.

**This is the AG of RAG**

**Importance of RAG in the pipeline**

 > constrains the model to our thresholds ( ie if more than 20% mismatch > material discrepancy).
 > Makes the output auditable ( tells us what clause caused which risk flag ).

**LLM Call 3**

What is passed :
   > extraction json.
   > poicy grounded rationale

*llm DRafts a memo*

Specifically, LLm performs formating, summarizing,  professional writing.
Thus it does not decide but creates a draft for the **human in the loop**.

**Human in the Loop**

The analyst ( YOU) decides
  > to escalate or not.
  > request missing docs or reject.
  > override AI if needed.

**Audit logging**

We write metadata _ prompt heads to audit_log.jsonl

This gives us 
> tracability
> " who saw what "
> helps in gov narrative.

