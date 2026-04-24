from cms.retrieval.vector_store import create_qdrant_collections as ddl


class _StubClient:
    """Records the DDL calls the module makes, and reports the collection state."""

    def __init__(self, exists: bool) -> None:
        self.exists = exists
        self.deleted: list[str] = []
        self.created: list[dict] = []

    def collection_exists(self, name):
        return self.exists

    def delete_collection(self, name):
        self.deleted.append(name)

    def create_collection(self, collection_name, vectors_config, sparse_vectors_config):
        self.created.append(
            {"name": collection_name, "vectors": vectors_config}
        )


def test_existing_collection_is_left_alone_by_default() -> None:
    client = _StubClient(exists=True)

    created = ddl.create_collection(client, "policies_v1", 1536)

    assert created is False
    assert client.deleted == []
    assert client.created == []


def test_recreate_drops_then_creates_at_the_new_size() -> None:
    client = _StubClient(exists=True)

    created = ddl.create_collection(client, "policies_v1", 512, recreate=True)

    assert created is True
    assert client.deleted == ["policies_v1"]
    assert len(client.created) == 1
    assert client.created[0]["vectors"][ddl.DENSE_VECTOR_NAME].size == 512


def test_recreate_on_a_missing_collection_just_creates_it() -> None:
    client = _StubClient(exists=False)

    created = ddl.create_collection(client, "policies_v1", 512, recreate=True)

    assert created is True
    assert client.deleted == []
    assert len(client.created) == 1
