import json
import os
from pathlib import Path
from typing import Dict, Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULT_SYSTEM_PROMPT = """You are ATLAS 2.0, an advanced, highly capable autonomous desktop AI assistant.
You speak clearly, efficiently, and with confidence. You assist the user with system control, information, automations, and daily workflows.
Keep your responses direct, helpful, and concise unless explicitly asked for a detailed explanation."""

DEFAULT_CONFIG: Dict[str, Any] = {
    "brain_mode": "ai",          # "ai" or "predefined"
    "listening_mode": False,     # mic actively listening
    "voice_output": True,        # TTS active
    "biometrics": {
        "enabled": False,
        "enrolled": False,
        "similarity_threshold": 0.72,
        "profile_file": "voice_profile.npy"
    },
    "llm": {
        "provider": "gemini",    # "gemini", "openrouter", "freellmapi", "ollama"
        "gemini_api_key": "",
        "gemini_model": "gemini-1.5-flash",
        "openrouter_api_key": "",
        "openrouter_model": "google/gemini-2.0-flash-exp:free",
        "freellmapi_url": "https://api.freellmapi.com/v1",
        "freellmapi_key": "",
        "freellmapi_model": "gpt-3.5-turbo",
        "ollama_url": "http://localhost:11434",
        "ollama_model": "llama3",
        "system_prompt": DEFAULT_SYSTEM_PROMPT
    },
    "tts": {
        "voice": "en-US-ChristopherNeural",
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    "telegram": {
        "enabled": False,
        "token": "",
        "allowed_chat_id": ""
    },
    "telegram_queue_access": False,
    "mia": {
        "enabled": True,
        "cloud_subagent_mode": True,  # 24/7 autonomous cloud execution even when host machine is off
        "cloud_worker_url": "",       # Cloud container/worker URL
        "provider": "gemini",      # "inherit", "gemini", "openrouter", "freellmapi", "ollama"
        "model": "gemini-1.5-flash",
        "api_key": "",
        "base_url": "",
        "mongodb_uri": "",         # MongoDB Atlas Cloud Connection String
        "mongodb_db": "atlas_mia",
        "summary_hours": 2,
        "high_confidence": 0.90,
        "min_confidence": 0.65,
        "margin_delta": 0.08
    }
}

class ConfigManager:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.config = DEFAULT_CONFIG.copy()
        self.config = self.load()

    def _apply_env_overrides(self, cfg: Dict[str, Any]):
        mia = cfg.setdefault("mia", {})
        if os.getenv("MONGODB_URI"):
            mia["mongodb_uri"] = os.getenv("MONGODB_URI")
        if os.getenv("MIA_API_KEY"):
            mia["api_key"] = os.getenv("MIA_API_KEY")
        if os.getenv("MIA_PROVIDER"):
            mia["provider"] = os.getenv("MIA_PROVIDER")
        if os.getenv("MIA_MODEL"):
            mia["model"] = os.getenv("MIA_MODEL")

    def load(self) -> Dict[str, Any]:
        if not CONFIG_FILE.exists():
            base = DEFAULT_CONFIG.copy()
            self._apply_env_overrides(base)
            self.config = base
            self.save(base)
            return base
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Merge defaults for any missing keys
                merged = DEFAULT_CONFIG.copy()
                for k, v in loaded.items():
                    if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                        merged[k].update(v)
                    else:
                        merged[k] = v
                self._apply_env_overrides(merged)
                return merged
        except Exception:
            fallback = DEFAULT_CONFIG.copy()
            self._apply_env_overrides(fallback)
            return fallback

    def save(self, config_data: Dict[str, Any] = None) -> bool:
        if config_data is not None:
            # Preserve existing keys not included in partial updates
            existing = getattr(self, "config", None) or {}
            for k, v in existing.items():
                if k not in config_data:
                    config_data[k] = v
            self.config = config_data
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def update(self, key_path: str, value: Any) -> bool:
        keys = key_path.split(".")
        target = self.config
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
        return self.save()

    def get(self, key_path: str, default: Any = None) -> Any:
        keys = key_path.split(".")
        target = self.config
        for k in keys:
            if not isinstance(target, dict) or k not in target:
                return default
            target = target[k]
        return target

config_manager = ConfigManager()
