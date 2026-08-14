import asyncio

from backend.services.rag import answer_question


async def main() -> None:
    question = "Phở bò thường có những thành phần gì?"

    answer, chunks = await answer_question(question)

    print(f"Question: {question}")
    print()
    print(f"Answer: {answer}")

    print()
    print("Sources:")

    for chunk in chunks:
        print(
            f"- {chunk.metadata['title']} · {chunk.metadata['source']} "
            f"(score={chunk.metadata['score']})"
        )


if __name__ == "__main__":
    asyncio.run(main())
