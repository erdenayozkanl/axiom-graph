import pytest
from axiom_graph import KnowledgeGraph, Principal, Triple, load_demo

def test_multihop_evidence_finds_owner():
    result = load_demo().answer("Who owns the Profile Service?", max_hops=2)
    assert "PlatformTeam --OWNS--> ProfileService" in result["answer"]
    assert any(f["subject"] == "Lina" and f["object"] == "PlatformTeam" for f in result["facts"])

def test_ontology_rejects_unknown_predicate():
    graph = KnowledgeGraph()
    with pytest.raises(ValueError):
        graph.ingest([{"id":"A", "type":"Person"}, {"id":"B", "type":"Team"}], [Triple("A", "HACKS", "B", "test")])

def test_support_cannot_traverse_confidential_data_lineage():
    principal = Principal("sam", frozenset({"support"}), clearance="internal")
    result = load_demo().answer("What does Profile Service consume?", principal, max_hops=2)
    assert all(f["object"] != "CustomerDataset" for f in result["facts"])
    assert any(event["reason"] == "rebac_data_lineage_denied" for event in result["audit"])

def test_approved_analyst_with_confidential_clearance_can_view_dataset():
    principal = Principal("ada", frozenset({"analyst"}), clearance="confidential", model_tier="approved")
    result = load_demo().answer("What does Profile Service consume?", principal, max_hops=1)
    assert any(f["object"] == "CustomerDataset" for f in result["facts"])

def test_unapproved_model_cannot_receive_confidential_node():
    principal = Principal("ada", frozenset({"analyst"}), clearance="confidential", model_tier="unapproved")
    result = load_demo().answer("What does Profile Service consume?", principal, max_hops=1)
    assert all(f["object"] != "CustomerDataset" for f in result["facts"])
    assert any(event["reason"] == "mbac_model_tier_denied" for event in result["audit"])
