"""
MIA Hybrid Parallel Search Engine.
Implements multi-signal query understanding, scoring (0.25*K + 0.25*S + 0.40*V + 0.10*E),
and confidence / ambiguity management.
"""

import re
import math
from typing import Dict, Any, List, Tuple, Optional
from backend.config import config_manager
from backend.core.mia.storage import mia_storage
from backend.core.mia.embeddings import vector_embedder


class HybridSearchEngine:
    def __init__(self):
        pass

    def _tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        tokens = re.findall(r"\b[a-zA-Z0-9_\-\.\@]{2,}\b", text.lower())
        # Filter ultra-common stopwords
        stop = {"the", "a", "an", "and", "or", "to", "for", "in", "on", "at", "by", "from", "of", "with", "is", "was", "are"}
        return [t for t in tokens if t not in stop]

    def _calculate_token_coverage(self, query_tokens: List[str], target_text: str) -> float:
        if not query_tokens or not target_text:
            return 0.0
        target_lower = target_text.lower()
        matched = 0
        for token in query_tokens:
            if token in target_lower:
                matched += 1
        return matched / len(query_tokens)

    def _compute_keyword_score(self, query: str, query_tokens: List[str], email: Dict[str, Any]) -> float:
        """
        K: Matches query against subject, body, sender_name, and keywords.
        Combines exact phrase match bonus, subject match weight, and token coverage.
        """
        if not query_tokens:
            return 0.0

        q_clean = query.strip().lower()
        subject = (email.get("subject") or "").lower()
        body = (email.get("body") or "").lower()
        sender_name = (email.get("sender_name") or "").lower()
        keywords = " ".join(email.get("keywords") or []).lower()

        # Exact phrase match in subject gets near 1.0
        if q_clean in subject:
            return 1.0

        subj_cov = self._calculate_token_coverage(query_tokens, subject)
        kw_cov = self._calculate_token_coverage(query_tokens, keywords)
        body_cov = self._calculate_token_coverage(query_tokens, body)
        sender_cov = self._calculate_token_coverage(query_tokens, sender_name)

        # Weighted combination for K
        raw_k = (0.45 * subj_cov) + (0.25 * kw_cov) + (0.20 * body_cov) + (0.10 * sender_cov)
        
        # Exact phrase in body bonus
        if len(q_clean) > 8 and q_clean in body:
            raw_k = min(1.0, raw_k + 0.25)

        return min(1.0, max(0.0, raw_k))

    def _compute_summary_score(self, query: str, query_tokens: List[str], email: Dict[str, Any]) -> float:
        """
        S: Matches query against stored summary, main_topic, purpose, and search_descriptions.
        """
        if not query_tokens:
            return 0.0

        q_clean = query.strip().lower()
        summary = (email.get("summary") or "").lower()
        topic = (email.get("main_topic") or "").lower()
        purpose = (email.get("purpose") or "").lower()
        descriptions = " ".join(email.get("search_descriptions") or []).lower()

        # Exact phrase in summary or search descriptions
        if q_clean in summary or q_clean in descriptions or q_clean in purpose:
            return 1.0

        sum_cov = self._calculate_token_coverage(query_tokens, summary)
        desc_cov = self._calculate_token_coverage(query_tokens, descriptions)
        top_cov = self._calculate_token_coverage(query_tokens, topic)
        purp_cov = self._calculate_token_coverage(query_tokens, purpose)

        raw_s = (0.40 * sum_cov) + (0.30 * desc_cov) + (0.15 * purp_cov) + (0.15 * top_cov)
        return min(1.0, max(0.0, raw_s))

    def _compute_entity_score(self, query: str, query_tokens: List[str], email: Dict[str, Any]) -> float:
        """
        E: Matches query against structured entity lists (events, organizations, locations, activities).
        """
        if not query_tokens:
            return 0.0

        q_clean = query.strip().lower()
        events = " ".join(email.get("events") or []).lower()
        orgs = " ".join(email.get("organizations") or []).lower()
        locs = " ".join(email.get("locations") or []).lower()
        acts = " ".join(email.get("activities") or []).lower()
        all_entities = f"{events} {orgs} {locs} {acts}"

        if not all_entities.strip():
            return 0.0

        if q_clean in all_entities:
            return 1.0

        cov = self._calculate_token_coverage(query_tokens, all_entities)
        return min(1.0, max(0.0, cov))

    async def hybrid_search(self, query: str) -> Dict[str, Any]:
        """
        Executes parallel hybrid search across all indexed emails.
        Returns:
            {
               "status": "found" | "ambiguous" | "not_found",
               "top_email": Dict | None,
               "candidates": List[Dict],
               "scores": List[Dict],
               "query": str
            }
        """
        emails = mia_storage.get_all_emails()
        if not emails:
            return {
                "status": "not_found",
                "top_email": None,
                "candidates": [],
                "scores": [],
                "query": query,
                "reason": "No emails stored in database."
            }

        q_tokens = self._tokenize(query)
        if not q_tokens:
            return {
                "status": "not_found",
                "top_email": None,
                "candidates": [],
                "scores": [],
                "query": query,
                "reason": "Empty search query."
            }

        # Retrieve embeddings and compute query vector
        embeddings_map = mia_storage.get_all_embeddings()
        q_vec = vector_embedder.generate_local_embedding(query)

        cfg = config_manager.get("mia", {})
        high_confidence = float(cfg.get("high_confidence", 0.90))
        min_confidence = float(cfg.get("min_confidence", 0.65))
        margin_delta = float(cfg.get("margin_delta", 0.08))

        scored_results = []
        for email in emails:
            eid = email["email_id"]
            
            # 1. Keyword Score (K)
            k_score = self._compute_keyword_score(query, q_tokens, email)

            # 2. Summary Score (S)
            s_score = self._compute_summary_score(query, q_tokens, email)

            # 3. Vector Score (V)
            v_vec = embeddings_map.get(eid)
            v_score = vector_embedder.cosine_similarity(q_vec, v_vec) if v_vec else 0.0

            # 4. Entity Score (E)
            e_score = self._compute_entity_score(query, q_tokens, email)

            # Hybrid Score formula: Score = 0.25*K + 0.25*S + 0.40*V + 0.10*E
            hybrid_score = (0.25 * k_score) + (0.25 * s_score) + (0.40 * v_score) + (0.10 * e_score)

            scored_results.append({
                "email": email,
                "score": round(hybrid_score, 4),
                "k_score": round(k_score, 3),
                "s_score": round(s_score, 3),
                "v_score": round(v_score, 3),
                "e_score": round(e_score, 3)
            })

        # Sort descending by hybrid score
        scored_results.sort(key=lambda x: x["score"], reverse=True)

        top_score = scored_results[0]["score"] if scored_results else 0.0
        second_score = scored_results[1]["score"] if len(scored_results) > 1 else 0.0
        delta = top_score - second_score

        # Case 1: Below MINIMUM_CONFIDENCE -> Not Found
        if top_score < min_confidence:
            return {
                "status": "not_found",
                "top_email": None,
                "candidates": [],
                "scores": scored_results[:3],
                "query": query,
                "reason": f"Top match score ({top_score:.2f}) below minimum confidence ({min_confidence:.2f})."
            }

        # Case 2: Ambiguity check
        # If multiple close results above MINIMUM_CONFIDENCE with score delta <= margin_delta
        if len(scored_results) > 1 and second_score >= min_confidence and delta <= margin_delta:
            ambiguous_candidates = [r["email"] for r in scored_results if r["score"] >= (top_score - margin_delta)]
            return {
                "status": "ambiguous",
                "top_email": scored_results[0]["email"],
                "candidates": ambiguous_candidates[:4],
                "scores": scored_results[:4],
                "query": query,
                "top_score": top_score,
                "delta": delta,
                "reason": f"Multiple close matches found within margin delta {margin_delta} (Score 1: {top_score:.2f}, Score 2: {second_score:.2f})."
            }

        # Case 3: Found (Top score satisfies high confidence or clear delta above min_confidence)
        return {
            "status": "found",
            "top_email": scored_results[0]["email"],
            "candidates": [r["email"] for r in scored_results[:3]],
            "scores": scored_results[:3],
            "query": query,
            "top_score": top_score,
            "delta": delta
        }


hybrid_search_engine = HybridSearchEngine()
