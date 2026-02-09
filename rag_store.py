import chromadb
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "all-MiniLM-L6-v2"

class RAGStore:
    def __init__(self, path="./chroma_db", collection_name="policy_docs"):
        self.embedder = SentenceTransformer(EMBED_MODEL)
        self.client = chromadb.PersistentClient(path=path)
        self.col = self.client.get_or_create_collection(collection_name)

    def _chunk(self, text: str, chunk_size=900, overlap=150):
        chunks = []
        i = 0
        while i < len(text):
            chunks.append(text[i:i+chunk_size])
            i += chunk_size - overlap
        return chunks

    def upsert_document(self, doc_name: str, text: str):
        chunks = self._chunk(text)
        embs = self.embedder.encode(chunks).tolist()
        ids = [f"{doc_name}::chunk_{i}" for i in range(len(chunks))]
        self.col.add(ids=ids, documents=chunks, embeddings=embs)

    def retrieve(self, query: str, k=5):
        q_emb = self.embedder.encode([query]).tolist()[0]
        res = self.col.query(query_embeddings=[q_emb], n_results=k)
        docs = res.get("documents", [[]])[0]
        return docs
