"""
MIA 24/7 Cloud Subagent Worker.
Enables MIA to run continuously in the cloud (AWS/GCP/Railway/Render)
even when the local computer is turned off.
Synchronizes all settings from MongoDB Atlas and processes incoming emails & queries.
"""

import os
import sys
import json
import asyncio
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import config_manager
from backend.core.mia.storage import mia_storage
from backend.core.mia.agent import mia_agent
from backend.core.mia.ingestion import email_ingestion_service


class MIACloudWorker:
    """
    24/7 Autonomous Cloud Worker for MIA Subagent.
    Runs in cloud container or serverless environment.
    All settings saved in ATLAS 2.0 Control Panel automatically reflect in this cloud worker.
    """

    def __init__(self):
        self.is_running = False
        self.cloud_provider = os.getenv("MIA_CLOUD_PROVIDER", "cloud_native")
        self.last_config_sync = None

    def sync_latest_config_from_cloud(self) -> bool:
        """Pulls the latest user configurations saved from ATLAS Control Panel in MongoDB Atlas."""
        cloud_cfg = mia_storage.get_cloud_config()
        if cloud_cfg and isinstance(cloud_cfg, dict):
            local_mia = config_manager.config.setdefault("mia", {})
            local_mia.update(cloud_cfg)
            self.last_config_sync = datetime.datetime.now(datetime.timezone.utc).isoformat()
            return True
        return False

    def get_cloud_status(self) -> Dict[str, Any]:
        has_llm, llm_msg = mia_agent.check_llm_status()
        backend = mia_storage.get_backend_type()
        stats = mia_storage.get_stats()
        
        return {
            "status": "online" if self.is_running else "configured",
            "cloud_sync": backend == "mongodb_atlas",
            "backend": backend,
            "has_llm": has_llm,
            "llm_message": llm_msg,
            "always_on_enabled": config_manager.get("mia.cloud_subagent_mode", True),
            "cloud_worker_url": config_manager.get("mia.cloud_worker_url", ""),
            "last_config_sync": self.last_config_sync,
            "stats": stats
        }

    async def execute_cloud_command(self, command: str) -> Dict[str, Any]:
        """Executes a command (e.g. from Telegram or Cloud Webhook) directly in the cloud."""
        self.sync_latest_config_from_cloud()
        return await mia_agent.execute(command)

    async def ingest_cloud_email(self, email_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Ingests and summarizes an email directly in the cloud."""
        self.sync_latest_config_from_cloud()
        return await email_ingestion_service.ingest_email(email_dict)

    async def run_worker_loop(self):
        """Continuous 24/7 cloud processing loop."""
        self.is_running = True
        print("[MIA Cloud Worker] Initializing 24/7 Autonomous Subagent...")
        print(f"[MIA Cloud Worker] Backend Storage: {mia_storage.get_backend_type()}")

        while self.is_running:
            try:
                # 1. Sync any config changes made in the Control Panel
                synced = self.sync_latest_config_from_cloud()
                if synced:
                    print(f"[MIA Cloud Worker] Synced updated settings from MongoDB Atlas ({self.last_config_sync})")

                # 2. Check pending cloud jobs if any
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[MIA Cloud Worker Error]: {e}")
                await asyncio.sleep(10)

        self.is_running = False
        print("[MIA Cloud Worker] Stopped.")

    def stop(self):
        self.is_running = False


mia_cloud_worker = MIACloudWorker()

if __name__ == "__main__":
    print("=" * 60)
    print("ATLAS 2.0 - MIA Autonomous Cloud Subagent Worker")
    print("Running 24/7 cloud sync even when host machine is off.")
    print("=" * 60)
    try:
        asyncio.run(mia_cloud_worker.run_worker_loop())
    except KeyboardInterrupt:
        print("\nShutdown requested.")
