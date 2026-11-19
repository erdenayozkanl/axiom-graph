# AxiomGraph — Knowledge Base + Knowledge Graph + GraphRAG

An auditable reference project showing how a document knowledge base becomes a governed knowledge graph that an LLM can use as bounded, cited context.

## What it demonstrates

- A small **ontology**: allowlisted entity types and relations.
- **Knowledge-base ingestion** represented as entities and source-backed triples.
- A directed property graph with `networkx`.
- **Multi-hop traversal** from entities detected in a user question.
- **RBAC** node-label and relationship allowlists; a support role cannot retrieve every graph type.
- **ABAC** tenant isolation and classification/clearance checks on every node.
- **ReBAC** traversal controls for sensitive relationship paths such as data lineage.
- **MBAC (model-based access control)**: unapproved models never receive confidential graph nodes.
- An audit decision for every allowed/denied node or edge, returned with the answer.
- GraphRAG-style, extractive answers with the authorized evidence path returned to the caller.
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

## Governed retrieval: what can the LLM see?

The LLM never receives the whole graph. Retrieval evaluates policy *before* an
edge or node becomes context. The API accepts a caller identity, roles, tenant,
clearance and model tier. Its response contains `facts` (the only context that
may be sent to an LLM) plus `audit` (every allow/deny decision and its reason).

```json
{
  "question": "What does Profile Service consume?",
  "subject": "sam",
  "roles": ["support"],
  "tenant": "acme",
  "clearance": "internal",
  "model_tier": "approved"
}
```

The support caller can see the service but cannot traverse `CONSUMES` into the
confidential `CustomerDataset`; the audit records `rebac_data_lineage_denied`.
An `analyst` with confidential clearance and an approved model can retrieve that
path. A model with `unapproved` tier is denied even for an authorized analyst.

## Why GraphRAG instead of RAG alone?

Vector retrieval finds semantically similar passages. A graph models explicit relationships such as ownership, lineage, policies and dependencies. For questions that require joining facts across systems, a bounded graph traversal can return a compact, explainable evidence subgraph before an LLM synthesizes the answer.

## Production path

Use structured-output LLM extraction with schema validation, entity resolution, provenance per triple, review queues for low-confidence edges, external identity claims, policy-as-code, durable audit storage, Neo4j/Neptune for scale, OpenTelemetry and evaluation sets for extraction precision, path correctness and answer faithfulness.
