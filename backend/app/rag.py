# from langchain_openai import OpenAIEmbeddings
# from app.config import settings
# from app.database import SessionLocal
# from app.models import Document, Chunk

# embeddings_model = OpenAIEmbeddings(
#     model="text-embedding-3-small",
#     api_key=settings.GROQ_API_KEY,
# )

# def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
#     chunks = []
#     start = 0
#     while start < len(text):
#         end = start + chunk_size
#         chunks.append(text[start:end])
#         start = end - overlap
#     return chunks

# def ingest_document(filename: str, text: str) -> int:
#     db = SessionLocal()
#     try:
#         doc = Document(filename=filename)
#         db.add(doc)
#         db.commit()
#         db.refresh(doc)

#         pieces = chunk_text(text)
#         vectors = embeddings_model.embed_documents(pieces)

#         for piece, vector in zip(pieces, vectors):
#             db.add(Chunk(document_id=doc.id, content=piece, embedding=vector))
#         db.commit()
#         return doc.id
#     finally:
#         db.close()

# def search_chunks(query: str, top_k: int = 4) -> list[str]:
#     db = SessionLocal()
#     try:
#         query_vector = embeddings_model.embed_query(query)
#         results = (
#             db.query(Chunk)
#             .order_by(Chunk.embedding.cosine_distance(query_vector))
#             .limit(top_k)
#             .all()
#         )
#         return [r.content for r in results]
#     finally:
#         db.close()


from sentence_transformers import SentenceTransformer
from app.database import SessionLocal
from app.models import Document, Chunk

embeddings_model = SentenceTransformer("all-MiniLM-L6-v2")

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks

def ingest_document(filename: str, text: str) -> int:
    db = SessionLocal()
    try:
        doc = Document(filename=filename)
        db.add(doc)
        db.commit()
        db.refresh(doc)

        pieces = chunk_text(text)
        vectors = embeddings_model.encode(pieces).tolist()

        for piece, vector in zip(pieces, vectors):
            db.add(Chunk(document_id=doc.id, content=piece, embedding=vector))
        db.commit()
        return doc.id
    finally:
        db.close()

def search_chunks(query: str, top_k: int = 4) -> list[str]:
    db = SessionLocal()
    try:
        query_vector = embeddings_model.encode(query).tolist()
        results = (
            db.query(Chunk)
            .order_by(Chunk.embedding.cosine_distance(query_vector))
            .limit(top_k)
            .all()
        )
        return [r.content for r in results]
    finally:
        db.close()