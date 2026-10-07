from agri_rag.ingestion.chunking import chunk_document
from agri_rag.ingestion.loaders import Document

TEXT = "# دليل\n\n## الأعراض\n" + ("جملة عن الأعراض المرضية. " * 60) + "\n\n## الوقاية\nتجنب الري المسائي."


def test_chunks_respect_size_and_sections():
    chunks = chunk_document(Document("d.md", "دليل", TEXT, {"crop": "طماطم"}), max_chars=300, overlap_chars=60)
    assert len(chunks) > 2
    assert all(len(c.body) <= 330 for c in chunks)
    assert {c.metadata["section"] for c in chunks} >= {"دليل › الأعراض", "دليل › الوقاية"}
    assert all(c.metadata["crop"] == "طماطم" for c in chunks)


def test_chunk_ids_are_deterministic():
    doc = Document("d.md", "دليل", TEXT)
    assert [c.id for c in chunk_document(doc)] == [c.id for c in chunk_document(doc)]


def test_contextual_header_present():
    c = chunk_document(Document("d.md", "دليل", TEXT))[0]
    assert c.text.startswith("دليل")
