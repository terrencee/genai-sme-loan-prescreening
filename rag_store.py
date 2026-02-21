import chromadb
from sentence_transformers import SentenceTransformer
from typing import Dict, List, Optional

EMBED_MODEL = "all-MiniLM-L6-v2"

class RAGStore:
    def __init__(self, path="./chroma_db"):
        self.embedder = SentenceTransformer(EMBED_MODEL)
        self.client = chromadb.PersistentClient(path=path)

    def _get_collection(self, layer: str):
        """
        Each policy layer gets its own collection.
        e.g. base_policy, state_rules, sector_rules
        """
        return self.client.get_or_create_collection(f"policy_{layer}")

    def _chunk(self, text: str, chunk_size=900, overlap=150) -> List[str]:
        chunks = []
        i = 0
        while i < len(text):
            chunks.append(text[i:i+chunk_size])
            i += chunk_size - overlap
        return chunks

    def upsert_policy(
        self,
        layer: str,
        policy_id: str,
        text: str,
        metadata: Dict,
        chunk_size: int = 900,
        overlap: int = 150
    ):
        col = self._get_collection(layer)

        try:
            col.delete(where={"policy_id": policy_id})
        except Exception:
            pass

        chunks = self._chunk(text, chunk_size, overlap)
        embs = self.embedder.encode(chunks).tolist()

        ids = [f"{policy_id}::chunk_{i}" for i in range(len(chunks))]
        metadatas = [{**metadata, "policy_id": policy_id, "layer": layer} for _ in chunks]

        col.add(ids=ids, documents=chunks, embeddings=embs, metadatas=metadatas)

    def retrieve(
        self,
        layer: str,
        query: str,
        k: int = 5,
        where: Optional[Dict] = None
    ) -> List[str]:
        col = self._get_collection(layer)
        q_emb = self.embedder.encode([query]).tolist()[0]
        res = col.query(query_embeddings=[q_emb], n_results=k, where=where)
        return res.get("documents", [[]])[0]