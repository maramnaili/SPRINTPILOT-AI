from sprintpilot.knowledge import (
    RetrievedGuideline,
    retrieve_project_guidelines,
    split_guideline_text,
)
import sprintpilot.knowledge as knowledge_base


class MockCollection:
    def __init__(self) -> None:
        self.documents = []
        self.metadatas = []

    def count(self) -> int:
        return len(self.documents)

    def upsert(self, *, ids, documents, metadatas) -> None:
        self.documents = list(documents)
        self.metadatas = list(metadatas)

    def query(self, *, query_texts, n_results):
        return {
            "documents": [self.documents[:n_results]],
            "metadatas": [self.metadatas[:n_results]],
            "distances": [[0.1] * min(n_results, len(self.documents))],
        }


def test_chunking_produces_non_empty_chunks() -> None:
    chunks = split_guideline_text("Use clear acceptance criteria. " * 40, chunk_size=100)

    assert chunks
    assert all(chunk.strip() for chunk in chunks)


def test_retrieval_returns_source_metadata(monkeypatch) -> None:
    collection = MockCollection()
    collection.documents = ["Write acceptance criteria for every story."]
    collection.metadatas = [{"source": "acceptance.md"}]
    monkeypatch.setattr(knowledge_base, "_get_collection", lambda: collection)

    results = retrieve_project_guidelines("acceptance criteria")

    assert results
    assert isinstance(results[0], RetrievedGuideline)
    assert results[0].source == "acceptance.md"


def test_retrieval_returns_empty_list_for_empty_knowledge_base(monkeypatch) -> None:
    collection = MockCollection()
    monkeypatch.setattr(knowledge_base, "_get_collection", lambda: collection)

    assert retrieve_project_guidelines("backlog") == []
