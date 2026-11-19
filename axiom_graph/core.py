"""A small, auditable GraphRAG reference implementation."""
from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import networkx as nx

BASE = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Triple:
    subject: str
    predicate: str
    object: str
    source: str


class Ontology:
    """Allowlisted types and predicates prevent arbitrary graph mutation."""
    node_types = {"Person", "Team", "Service", "Dataset", "Policy", "System"}
    predicates = {"OWNS", "USES", "GOVERNS", "CONSUMES", "CONTAINS", "DEPENDS_ON"}

    def validate(self, triple: Triple, kinds: dict[str, str]) -> None:
        if triple.predicate not in self.predicates:
            raise ValueError(f"unknown predicate: {triple.predicate}")
        for entity in (triple.subject, triple.object):
            if entity not in kinds or kinds[entity] not in self.node_types:
                raise ValueError(f"unknown entity/type: {entity}")


class KnowledgeGraph:
    def __init__(self, ontology: Ontology | None = None):
        self.ontology = ontology or Ontology()
        self.graph = nx.MultiDiGraph()

    def ingest(self, entities: list[dict], triples: Iterable[Triple]) -> int:
        kinds = {e["id"]: e["type"] for e in entities}
        for e in entities:
            if e["type"] not in self.ontology.node_types:
                raise ValueError(f"unknown type: {e['type']}")
            self.graph.add_node(e["id"], **e)
        count = 0
        for triple in triples:
            self.ontology.validate(triple, kinds)
            self.graph.add_edge(triple.subject, triple.object, key=triple.predicate,
                                predicate=triple.predicate, source=triple.source)
            count += 1
        return count

    def find_entities(self, question: str) -> list[str]:
        terms = set(re.findall(r"\w+", question.casefold()))
        scored = []
        for entity, attrs in self.graph.nodes(data=True):
            text = f"{entity} {attrs.get('name', '')} {attrs.get('description', '')}".casefold()
            score = len(terms & set(re.findall(r"\w+", text)))
            if score:
                scored.append((score, entity))
        return [entity for _, entity in sorted(scored, reverse=True)[:4]]

    def subgraph(self, seeds: list[str], max_hops: int = 2) -> list[dict]:
        """Bounded BFS provides explainable multi-hop context."""
        queue = deque((seed, 0) for seed in seeds)
        seen = set(seeds)
        edges = []
        while queue:
            node, depth = queue.popleft()
            if depth >= max_hops:
                continue
            for _, target, _, attrs in self.graph.out_edges(node, keys=True, data=True):
                edges.append({"subject": node, "predicate": attrs["predicate"], "object": target, "source": attrs["source"]})
                if target not in seen:
                    seen.add(target); queue.append((target, depth + 1))
            for source, _, _, attrs in self.graph.in_edges(node, keys=True, data=True):
                edges.append({"subject": source, "predicate": attrs["predicate"], "object": node, "source": attrs["source"]})
                if source not in seen:
                    seen.add(source); queue.append((source, depth + 1))
        return edges

    def answer(self, question: str, max_hops: int = 2) -> dict:
        seeds = self.find_entities(question)
        facts = self.subgraph(seeds, max_hops)
        if not facts:
            return {"answer": "No graph evidence found.", "entities": seeds, "facts": [], "mode": "extractive-graph-rag"}
        lines = [f"{f['subject']} --{f['predicate']}--> {f['object']}" for f in facts]
        return {"answer": "Grounded graph evidence:\n" + "\n".join(lines), "entities": seeds,
                "facts": facts, "mode": "extractive-graph-rag"}

    def export(self) -> dict:
        return {"entities": [dict(id=node, **attrs) for node, attrs in self.graph.nodes(data=True)],
                "triples": [asdict(Triple(a, attrs['predicate'], b, attrs['source'])) for a, b, _, attrs in self.graph.edges(keys=True, data=True)]}


def load_demo(path: Path = BASE / "data" / "knowledge.json") -> KnowledgeGraph:
    data = json.loads(path.read_text(encoding="utf-8"))
    graph = KnowledgeGraph()
    graph.ingest(data["entities"], (Triple(**item) for item in data["triples"]))
    return graph
