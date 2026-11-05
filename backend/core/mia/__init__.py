"""
MIA (Mail Intelligence Assistant) Module for ATLAS 2.0.
"""

from backend.core.mia.storage import mia_storage, MIAStorage
from backend.core.mia.embeddings import vector_embedder
from backend.core.mia.ingestion import email_ingestion_service
from backend.core.mia.search import hybrid_search_engine
from backend.core.mia.agent import mia_agent, MIAAgent
from backend.core.mia.seed_data import seed_sample_emails_if_empty

__all__ = [
    "mia_storage",
    "MIAStorage",
    "vector_embedder",
    "email_ingestion_service",
    "hybrid_search_engine",
    "mia_agent",
    "MIAAgent",
    "seed_sample_emails_if_empty"
]
