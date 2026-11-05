"""
ATLAS 2.0 - MIA Cloud Ingestion & Subagent Microservice.
Lightweight, headless, cloud-native FastAPI server designed for Cloud Run, Render, or Koyeb.
Synchronizes directly with MongoDB Atlas and handles Google Apps Script email webhooks 24/7.
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, Any

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from backend.config import config_manager
from backend.core.mia import (
    mia_agent,
    mia_storage,
    email_ingestion_service,
    seed_sample_emails_if_empty
)

app = FastAPI(
    title="ATLAS 2.0 - MIA Cloud Intelligence Service",
    description="24/7 Autonomous Email Ingestion and Vector Search Subagent",
    version="2.0.0"
)

# Apply environment variables if running in cloud container (e.g. Render / Cloud Run)
def _apply_cloud_env_overrides():
    mongo_uri = os.getenv("MONGODB_URI") or os.getenv("MIA_MONGODB_URI")
    if mongo_uri:
        config_manager.update("mia.mongodb_uri", mongo_uri)
    api_key = os.getenv("MIA_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        config_manager.update("mia.api_key", api_key)
    model = os.getenv("MIA_MODEL")
    if model:
        config_manager.update("mia.model", model)
    provider = os.getenv("MIA_PROVIDER")
    if provider:
        config_manager.update("mia.provider", provider)

_apply_cloud_env_overrides()

# Enable CORS for Google Apps Script and external webhooks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    print("[MIA Cloud Service] Starting headless subagent...")
    backend = mia_storage.get_backend_type()
    print(f"[MIA Cloud Service] Storage Backend: {backend}")
    has_llm, llm_msg = mia_agent.check_llm_status()
    print(f"[MIA Cloud Service] LLM Status: {has_llm} ({llm_msg})")

@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "service": "ATLAS 2.0 MIA Cloud Subagent",
        "backend": mia_storage.get_backend_type(),
        "timestamp": time.time()
    }

def _sync_cloud_settings():
    """Dynamically applies any updated LLM or MIA settings saved from local Control Panel to MongoDB Atlas."""
    try:
        cloud_cfg = mia_storage.get_cloud_config()
        if cloud_cfg and isinstance(cloud_cfg, dict):
            local_mia = config_manager.config.setdefault("mia", {})
            local_mia.update(cloud_cfg)
    except Exception as e:
        print(f"[MIA Cloud Settings Sync Warn]: {e}")

@app.get("/api/mia/status")
async def get_mia_status():
    _sync_cloud_settings()
    has_llm, llm_msg = mia_agent.check_llm_status()
    stats = mia_storage.get_stats()
    mia_cfg = config_manager.get("mia", {})
    return {
        "has_llm": has_llm,
        "llm_message": llm_msg,
        "backend": mia_storage.get_backend_type(),
        "provider": mia_cfg.get("provider", "gemini"),
        "model": mia_cfg.get("model", ""),
        "stats": stats
    }

@app.post("/api/mia/ingest")
async def ingest_email_api(payload: Dict[str, Any]):
    """Receives email payloads sent by Google Apps Script syncEmailsToMIA webhook."""
    try:
        _sync_cloud_settings()
        if not payload.get("email_id"):
            payload["email_id"] = payload.get("id") or f"email-cloud-{int(time.time() * 1000)}"
        record = await email_ingestion_service.ingest_email(payload)
        return {"status": "ok", "email": record}
    except Exception as e:
        print(f"[MIA Cloud Ingest Error]: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mia/query")
async def query_mia_api(payload: Dict[str, Any]):
    """Queries stored email intelligence via natural language command."""
    _sync_cloud_settings()
    cmd = payload.get("command", "")
    res = await mia_agent.execute(cmd)
    return res

@app.post("/api/mia/seed")
async def seed_mia(payload: Dict[str, Any] = None):
    force = bool((payload or {}).get("force", False))
    stats = await seed_sample_emails_if_empty(force=force)
    return {"status": "ok", "stats": stats}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("cloud_app:app", host="0.0.0.0", port=port, reload=False)
