import pytest
from axiom_graph import KnowledgeGraph, Triple, load_demo

def test_multihop_evidence_finds_owner():
    result = load_demo().answer("Who owns the Profile Service?", max_hops=2)
    assert "PlatformTeam --OWNS--> ProfileService" in result["answer"]
    assert any(f["subject"] == "Lina" and f["object"] == "PlatformTeam" for f in result["facts"])

def test_ontology_rejects_unknown_predicate():
    graph = KnowledgeGraph()
    with pytest.raises(ValueError):
        graph.ingest([{"id":"A", "type":"Person"}, {"id":"B", "type":"Team"}], [Triple("A", "HACKS", "B", "test")])
