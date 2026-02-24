# Plan: Final Architecture v2

## Scope
Produce `docs/final-architecture-v2.md` following the required outline, incorporating lessons from:
- `docs/r2-db2-architecture-analysis.md`
- `docs/proposal-evaluation.md`
- `docs/framework-comparison.md`
- `docs/final-architecture.md`

## Decisions (from user clarification)
- CodeAgent explicitly described as smolagents `CodeAgent`, **runs only inside sandbox**.
- Roadmap will include **concrete durations** despite the general “no estimates” instruction.
- Output formats default to **all outputs** (PDF + Plotly HTML + CSV/Parquet + JSON summary).

## Writing Steps
1. Draft **Part 1: Product Features**
   - Section 1: Product Vision (2–3 paragraphs).
   - Section 2: Feature Catalog with categories and P0/P1/P2 priorities.
2. Draft **Part 2: Architecture**
   - Technology stack table aligned with decisions (LangGraph, LiteLLM, ClickHouse, Qdrant, E2B, Open WebUI optional).
   - Text-based architecture diagram.
   - Agent roles (inputs/outputs, LLM usage, sandbox usage).
   - LangGraph execution graph with routing + multi-query expansion loop.
   - TypedDict state design with field explanations.
   - CodeAgent & sandbox design (programmatic tool calling, no creds, limits, artifacts).
   - Multi-query expansion flow with approval and loop.
   - Protocol interfaces for LLM, SQLRunner, SchemaStore, CodeSandbox, ConversationMemory.
3. Draft **Part 3: Production Concerns**
   - Security, observability, evaluation, error handling, caching, output formats.
   - Include error taxonomy table and caching layers.
4. Draft **Part 4: Deployment & Roadmap**
   - Deployment architecture (containers, scaling, config).
   - Roadmap phases with **concrete durations** and deliverables.
   - Open WebUI integration section (optional frontend).
5. Write final document to `docs/final-architecture-v2.md`.

## References (inline in the doc)
- Use R2-DB2 patterns by referencing file paths like `src/r2-db2/core/registry.py` and `src/r2-db2/core/evaluation/`.
- Cite the requested web sources:
  - `https://huggingface.co/docs/smolagents/en/index`
  - `https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph`

## Notes
- Document must be self-contained and precise; no filler.
- Include tables, code blocks, and diagrams where appropriate.
- Maintain sandbox credential isolation and programmatic tool-calling pattern.
