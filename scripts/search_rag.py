import asyncio

from backend.services.rag import search_chunks


async def main() -> None:
    question = "Phở bò thường có những thành phần gì?"

    chunks = await search_chunks(question)

    print(f"Question: {question}")

    for chunk in chunks:
        print()
        print(f"Score: {chunk.metadata['score']}")
        print(f"Title: {chunk.metadata['title']}")
        print(f"Source: {chunk.metadata['source']}")
        print(f"Content: {chunk.page_content}")


if __name__ == "__main__":
    asyncio.run(main())
