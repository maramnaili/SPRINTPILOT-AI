from dataclasses import dataclass
from pathlib import Path

import chromadb

from sprintpilot.config import settings


@dataclass
class RetrievedGuideline:
    text: str
    source: str
    score: float


def _get_collection():
    persist_directory = Path(settings.chroma_persist_directory)
    persist_directory.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_directory))
    return client.get_or_create_collection("project_guidelines")


def split_guideline_text(text: str, chunk_size: int = 800) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        current.append(word)
        if len(" ".join(current)) >= chunk_size:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return [chunk for chunk in chunks if chunk.strip()]


def upload_guideline(source_name: str, content: str) -> int:
    if not source_name.strip():
        raise ValueError("Source name is required.")
    if not content.strip():
        raise ValueError("Guideline content is required.")

    collection = _get_collection()
    chunks = split_guideline_text(content)
    ids = [
        f"{source_name}-{index}"
        for index in range(len(chunks))
    ]
    collection.upsert(
        ids=ids,
        documents=chunks,
        metadatas=[{"source": source_name} for _ in chunks],
    )
    return len(chunks)


def retrieve_project_guidelines(
    query: str,
    *,
    max_results: int = 3,
) -> list[RetrievedGuideline]:
    query = query.strip()
    if not query:
        raise ValueError("Retrieval query is required.")
    if max_results <= 0:
        raise ValueError("max_results must be greater than zero.")

    collection = _get_collection()
    if collection.count() == 0:
        return []

    result = collection.query(
        query_texts=[query],
        n_results=min(max_results, collection.count()),
    )
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    retrieved: list[RetrievedGuideline] = []
    for index, text in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else 0.0
        retrieved.append(RetrievedGuideline(
            text=text,
            source=str(metadata.get("source", "unknown")),
            score=float(distance),
        ))
    return retrieved


def list_guideline_sources() -> list[str]:
    collection = _get_collection()
    if collection.count() == 0:
        return []

    records = collection.get(include=["metadatas"])
    sources: set[str] = set()
    for metadata in records.get("metadatas", []):
        if metadata and metadata.get("source"):
            sources.add(str(metadata["source"]))
    return sorted(sources)
