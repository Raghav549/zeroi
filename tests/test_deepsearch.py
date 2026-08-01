import pytest

from zeroi.search.deepsearch import DeepSearchEngine


@pytest.mark.asyncio
async def test_deepsearch_run(monkeypatch):
    engine = DeepSearchEngine()

    async def fake_plan_queries(objective, context):
        return ["q1"]

    async def fake_search(query):
        return [
            {
                "title": "result",
                "url": "https://example.com",
                "snippet": "example snippet",
            }
        ]

    async def fake_synthesize(objective, evidence):
        return {
            "answer": "synthesized answer",
            "target": "https://example.com",
            "confidence": 0.9,
            "citations": ["https://example.com"],
        }

    monkeypatch.setattr(engine, "plan_queries", fake_plan_queries)
    monkeypatch.setattr(engine, "search", fake_search)
    monkeypatch.setattr(engine, "synthesize", fake_synthesize)

    result = await engine.run("test objective", max_rounds=1)

    assert result["answer"] == "synthesized answer"
    assert result["evidence_count"] >= 1
    assert result["confidence"] == 0.9
