from fastapi import FastAPI
from pydantic import BaseModel, Field
from axiom_graph import Principal, load_demo

app = FastAPI(title="AxiomGraph", version="0.1.0")
graph = load_demo()

class Query(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    max_hops: int = Field(default=2, ge=1, le=3)
    subject: str = Field(default="anonymous")
    roles: list[str] = Field(default_factory=lambda: ["support"])
    tenant: str = Field(default="acme")
    clearance: str = Field(default="internal", pattern="^(public|internal|confidential|restricted)$")
    model_tier: str = Field(default="approved", pattern="^(approved|unapproved)$")

@app.get("/health")
def health(): return {"status":"ok", "nodes": graph.graph.number_of_nodes(), "edges": graph.graph.number_of_edges()}

@app.post("/query")
def query(request: Query):
    principal = Principal(request.subject, frozenset(request.roles), request.tenant, request.clearance, request.model_tier)
    return graph.answer(request.question, principal, request.max_hops)
