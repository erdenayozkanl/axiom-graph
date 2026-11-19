"""A small, auditable GraphRAG reference implementation."""
from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, asdict, field
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


@dataclass(frozen=True)
class Principal:
    """Caller identity carried through retrieval and audit decisions."""
    subject: str
    roles: frozenset[str] = frozenset()
    tenant: str = "acme"
    clearance: str = "internal"
    model_tier: str = "approved"


@dataclass
class AuthorizationDecision:
    allowed: bool
    reason: str


@dataclass
class AuditEvent:
    subject: str
    node: str
    predicate: str | None
    allowed: bool
    reason: str


@dataclass
class AccessPolicy:
    """Composes RBAC, ABAC, ReBAC and model-aware controls for GraphRAG."""
    role_node_types: dict[str, set[str]] = field(default_factory=lambda: {
        "support": {"Service", "Policy", "Team"},
        "analyst": {"Service", "Policy", "Team", "Dataset"},
        "platform-admin": {"Person", "Team", "Service", "Dataset", "Policy", "System"},
    })
    role_predicates: dict[str, set[str]] = field(default_factory=lambda: {
        "support": {"OWNS", "GOVERNS", "DEPENDS_ON", "CONSUMES"},
        "analyst": {"OWNS", "GOVERNS", "DEPENDS_ON", "CONSUMES"},
        "platform-admin": {"OWNS", "USES", "GOVERNS", "CONSUMES", "CONTAINS", "DEPENDS_ON"},
    })
    sensitivity_rank: dict[str, int] = field(default_factory=lambda: {"public": 0, "internal": 1, "confidential": 2, "restricted": 3})

    def _role_allows(self, principal: Principal, value: str, rules: dict[str, set[str]]) -> bool:
        return any(value in rules.get(role, set()) for role in principal.roles)

    def node_decision(self, principal: Principal, node: str, attrs: dict) -> AuthorizationDecision:
        # RBAC: role must have the node type. ABAC: tenant and clearance must match.
        if attrs.get("tenant", "acme") != principal.tenant:
            return AuthorizationDecision(False, "tenant_mismatch")
        if not self._role_allows(principal, attrs["type"], self.role_node_types):
            return AuthorizationDecision(False, "rbac_node_type_denied")
        if self.sensitivity_rank[attrs.get("classification", "internal")] > self.sensitivity_rank[principal.clearance]:
            return AuthorizationDecision(False, "abac_clearance_denied")
        # MBAC: only approved models may receive confidential/restricted graph context.
        if attrs.get("classification", "internal") in {"confidential", "restricted"} and principal.model_tier != "approved":
            return AuthorizationDecision(False, "mbac_model_tier_denied")
        return AuthorizationDecision(True, "allowed")

    def edge_decision(self, principal: Principal, source: str, target: str, attrs: dict, graph: nx.MultiDiGraph) -> AuthorizationDecision:
        if not self._role_allows(principal, attrs["predicate"], self.role_predicates):
            return AuthorizationDecision(False, "rbac_relationship_denied")
        # ReBAC: an actor may traverse customer data only when explicitly related to its owning team.
        if attrs["predicate"] == "CONSUMES" and not ({"analyst", "platform-admin"} & principal.roles):
            return AuthorizationDecision(False, "rebac_data_lineage_denied")
        return AuthorizationDecision(True, "allowed")


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
        self.policy = AccessPolicy()

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

    def subgraph(self, seeds: list[str], principal: Principal, max_hops: int = 2) -> tuple[list[dict], list[AuditEvent]]:
        """Bounded BFS provides explainable multi-hop context."""
        audit: list[AuditEvent] = []
        queue = deque()
        seen = set()
        for seed in seeds:
            decision = self.policy.node_decision(principal, seed, self.graph.nodes[seed])
            audit.append(AuditEvent(principal.subject, seed, None, decision.allowed, decision.reason))
            if decision.allowed:
                queue.append((seed, 0)); seen.add(seed)
        edges = []
        while queue:
            node, depth = queue.popleft()
            if depth >= max_hops:
                continue
            for _, target, _, attrs in self.graph.out_edges(node, keys=True, data=True):
                edge_access = self.policy.edge_decision(principal, node, target, attrs, self.graph)
                node_access = self.policy.node_decision(principal, target, self.graph.nodes[target])
                allowed = edge_access.allowed and node_access.allowed
                audit.append(AuditEvent(principal.subject, target, attrs["predicate"], allowed, edge_access.reason if not edge_access.allowed else node_access.reason))
                if allowed:
                    edges.append({"subject": node, "predicate": attrs["predicate"], "object": target, "source": attrs["source"]})
                    if target not in seen:
                        seen.add(target); queue.append((target, depth + 1))
            for source, _, _, attrs in self.graph.in_edges(node, keys=True, data=True):
                edge_access = self.policy.edge_decision(principal, source, node, attrs, self.graph)
                node_access = self.policy.node_decision(principal, source, self.graph.nodes[source])
                allowed = edge_access.allowed and node_access.allowed
                audit.append(AuditEvent(principal.subject, source, attrs["predicate"], allowed, edge_access.reason if not edge_access.allowed else node_access.reason))
                if allowed:
                    edges.append({"subject": source, "predicate": attrs["predicate"], "object": node, "source": attrs["source"]})
                    if source not in seen:
                        seen.add(source); queue.append((source, depth + 1))
        return edges, audit

    def answer(self, question: str, principal: Principal | None = None, max_hops: int = 2) -> dict:
        principal = principal or Principal(subject="demo-admin", roles=frozenset({"platform-admin"}), clearance="restricted")
        seeds = self.find_entities(question)
        facts, audit = self.subgraph(seeds, principal, max_hops)
        if not facts:
            return {"answer": "No authorized graph evidence found.", "entities": seeds, "facts": [], "audit": [asdict(event) for event in audit], "mode": "authorized-graph-rag"}
        lines = [f"{f['subject']} --{f['predicate']}--> {f['object']}" for f in facts]
        return {"answer": "Grounded graph evidence:\n" + "\n".join(lines), "entities": seeds,
                "facts": facts, "audit": [asdict(event) for event in audit], "principal": asdict(principal), "mode": "authorized-graph-rag"}

    def export(self) -> dict:
        return {"entities": [dict(id=node, **attrs) for node, attrs in self.graph.nodes(data=True)],
                "triples": [asdict(Triple(a, attrs['predicate'], b, attrs['source'])) for a, b, _, attrs in self.graph.edges(keys=True, data=True)]}


def load_demo(path: Path = BASE / "data" / "knowledge.json") -> KnowledgeGraph:
    data = json.loads(path.read_text(encoding="utf-8"))
    graph = KnowledgeGraph()
    graph.ingest(data["entities"], (Triple(**item) for item in data["triples"]))
    return graph
