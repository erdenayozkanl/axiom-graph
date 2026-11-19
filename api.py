from fastapi import FastAPI
from pydantic import BaseModel, Field
from axiom_graph import load_demo

app = FastAPI(title="AxiomGraph", version="0.1.0")
graph = load_demo()

class Query(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    max_hops: int = Field(default=2, ge=1, le=3)

@app.get("/health")
def health(): return {"status":"ok", "nodes": graph.graph.number_of_nodes(), "edges": graph.graph.number_of_edges()}

@app.post("/query")
def query(request: Query): return graph.answer(request.question, request.max_hops)
