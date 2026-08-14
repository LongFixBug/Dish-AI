from pathlib import PurePosixPath

from pydantic import BaseModel, Field, field_validator, model_validator


class RagDocumentSpec(BaseModel):
    """Một tài liệu được phép nạp vào corpus RAG V0."""

    document_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=100)
    file: str = Field(min_length=5, max_length=300)

    @field_validator("file")
    @classmethod
    def validate_file(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or path.suffix != ".txt":
            raise ValueError("file phải là đường dẫn .txt tương đối, không có '..'.")
        return path.as_posix()


class RagCorpusManifest(BaseModel):
    """Danh sách đầy đủ tài liệu mà ingestion được phép đọc."""

    documents: list[RagDocumentSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_documents(self) -> "RagCorpusManifest":
        document_ids = [document.document_id for document in self.documents]
        files = [document.file for document in self.documents]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("document_id không được trùng nhau.")
        if len(files) != len(set(files)):
            raise ValueError("file không được trùng nhau.")
        return self


class RagChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = " ".join(value.split())

        if not normalized:
            raise ValueError("Câu hỏi không được chỉ gồm khoảng trắng.")

        return normalized


class RagSource(BaseModel):
    document_id: str
    title: str
    source: str
    score: float


class RagChatResponse(BaseModel):
    answer: str
    sources: list[RagSource]
