from backend.services.rag import (
    embed_text,
    load_rag_chunks,
    rebuild_rag_collection,
)
import asyncio


async def main() -> None:
    chunks = load_rag_chunks()
    print(f"Created {len(chunks)} chunks.")

    vectors: list[list[float]] = []

    for chunk in chunks:
        vector = await embed_text(chunk.page_content)
        vectors.append(vector)

        print()
        print(f"Title: {chunk.metadata['title']}")
        print(f"Source: {chunk.metadata['source']}")
        print(f"Chunk index: {chunk.metadata['chunk_index']}")
        print(f"Vector dimension: {len(vector)}")

    rebuild_rag_collection(chunks, vectors)
    print(f"Rebuilt RAG collection with {len(chunks)} chunks.")


if __name__ == "__main__":
    asyncio.run(main())
