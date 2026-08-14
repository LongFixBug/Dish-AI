from backend.services import embeddings


def test_request_time_embedding_fails_fast_to_exact_and_vision_fallbacks() -> None:
    assert embeddings.TIMEOUT <= 3.0
    assert embeddings.embedding_http_client._max_attempts == 1
