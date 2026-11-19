# AxiomGraph — Knowledge Base + Knowledge Graph + GraphRAG

An auditable reference project showing how a document knowledge base becomes a governed knowledge graph that an LLM can use as bounded, cited context.

## What it demonstrates

- A small **ontology**: allowlisted entity types and relations.
- **Knowledge-base ingestion** represented as entities and source-backed triples.
- A directed property graph with `networkx`.
- **Multi-hop traversal** from entities detected in a user question.
- GraphRAG-style, extractive answers with the evidence path returned to the caller.
- FastAPI, Docker, unit tests and GitHub Actions.

The example data is fictional. It deliberately uses deterministic extraction so the graph and tests are reproducible; a production extractor would use constrained LLM structured output validated against the ontology before ingestion.

## Run locally

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py "Who owns the Profile Service?" --hops 2
python main.py --serve
# POST http://127.0.0.1:8004/query
pytest -q
```

Docker: `docker compose up --build`.

## Why GraphRAG instead of RAG alone?

Vector retrieval finds semantically similar passages. A graph models explicit relationships such as ownership, lineage, policies and dependencies. For questions that require joining facts across systems, a bounded graph traversal can return a compact, explainable evidence subgraph before an LLM synthesizes the answer.

## Production path

Use structured-output LLM extraction with schema validation, entity resolution, provenance per triple, review queues for low-confidence edges, authorization-aware graph filtering, Neo4j/Neptune for scale, OpenTelemetry and evaluation sets for extraction precision, path correctness and answer faithfulness.
