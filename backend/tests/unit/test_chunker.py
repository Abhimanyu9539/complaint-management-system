from cms.ingestion.transform.chunker import chunk_case, chunk_policy


def test_case_chunking_remains_atomic() -> None:
    text = "COMPLAINT:\nThe device failed.\n\nRESOLUTION:\nReplacement issued."

    assert chunk_case(text) == [text]


def test_policy_chunks_keep_heading_breadcrumb() -> None:
    text = (
        "# Returns Policy\n\n"
        "## 1. Window\n\n"
        "Items may be returned within 30 days.\n\n"
        "## 2. Exceptions\n\n"
        "Courtesy extensions may apply."
    )

    chunks = chunk_policy(text)

    assert len(chunks) == 2
    assert chunks[0].startswith("Returns Policy > 1. Window")
    assert chunks[1].startswith("Returns Policy > 2. Exceptions")
