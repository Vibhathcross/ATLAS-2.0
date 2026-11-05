"""
MIA Vector Embeddings Module.
Provides vector generation for email content and search queries using:
1. Google Gemini Embeddings API (if API key available)
2. Normalized dense semantic vectorizer (word & char n-grams) for fast local vector similarity.
"""

import math
import re
import json
import httpx
from typing import List, Dict, Any, Optional

EMBED_DIM = 256

class VectorEmbedder:
    def __init__(self):
        self._vocab_cache: Dict[str, int] = {}

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        # Words and 3-char subwords for robust partial matching
        tokens = re.findall(r"[a-z0-9_\-\.\@]+", text)
        subwords = []
        for word in tokens:
            if len(word) >= 4:
                for i in range(len(word) - 2):
                    subwords.append(word[i:i+3])
        return tokens + subwords

    def _hash_token(self, token: str, dim: int = EMBED_DIM) -> int:
        h = 2166136261
        for char in token:
            h = (h ^ ord(char)) * 16777619
            h &= 0xFFFFFFFF
        return h % dim

    def generate_local_embedding(self, text: str, dim: int = EMBED_DIM) -> List[float]:
        """Generates a normalized dense vector embedding using hashing term-frequency and subwords."""
        vec = [0.0] * dim
        tokens = self._tokenize(text)
        if not tokens:
            return vec

        for t in tokens:
            idx = self._hash_token(t, dim)
            # Weight full words more than subwords
            weight = 2.0 if len(t) > 3 else 1.0
            vec[idx] += weight

        # L2 Normalization
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [round(x / norm, 6) for x in vec]
        return vec

    async def generate_gemini_embedding(self, text: str, api_key: str, model: str = "text-embedding-004") -> Optional[List[float]]:
        """Calls Gemini API for text embedding."""
        if not api_key:
            return None

        # Clean model name if full path passed
        model_name = model if not model.startswith("models/") else model.split("/")[-1]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:embedContent?key={api_key}"
        payload = {
            "model": f"models/{model_name}",
            "content": {
                "parts": [{"text": text[:8000]}]
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    values = data.get("embedding", {}).get("values", [])
                    if values:
                        # Normalize vector
                        norm = math.sqrt(sum(v * v for v in values))
                        if norm > 0:
                            return [round(v / norm, 6) for v in values]
                        return values
        except Exception as e:
            print(f"[MIA Embeddings] Gemini API error: {e}")

        return None

    async def get_embedding(self, text: str, api_key: Optional[str] = None, model: Optional[str] = None) -> List[float]:
        """Returns Gemini vector if key is provided and succeeds; otherwise returns local dense vector."""
        if api_key:
            gemini_vec = await self.generate_gemini_embedding(text, api_key, model or "text-embedding-004")
            if gemini_vec:
                return gemini_vec
        return self.generate_local_embedding(text)

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Computes cosine similarity between two float vectors."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 <= 0.0 or norm2 <= 0.0:
            return 0.0
        sim = dot / (norm1 * norm2)
        # Clamp to [0, 1]
        return max(0.0, min(1.0, float(sim)))


vector_embedder = VectorEmbedder()
