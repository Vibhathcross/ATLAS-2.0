import httpx
from typing import Dict, Any, List, Optional, Tuple

class LLMHub:
    """Multi-provider LLM coordinator (Gemini, OpenRouter, FreeLLMAPI, Ollama)."""

    def __init__(self):
        self.timeout = 25.0

    async def test_connection(self, provider: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Test API key and endpoint validity."""
        provider = provider.lower()
        try:
            if provider == "gemini":
                key = config.get("gemini_api_key", "").strip()
                if not key:
                    return False, "Gemini API Key is empty."
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        count = len(data.get("models", []))
                        return True, f"Connection successful! {count} models discovered."
                    else:
                        return False, f"HTTP {resp.status_code}: {resp.text[:120]}"

            elif provider == "openrouter":
                key = config.get("openrouter_api_key", "").strip()
                if not key:
                    return False, "OpenRouter API Key is empty."
                headers = {
                    "Authorization": f"Bearer {key}",
                    "HTTP-Referer": "https://github.com/atlas-ai",
                    "X-Title": "ATLAS 2.0"
                }
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
                    if resp.status_code == 200:
                        return True, "OpenRouter connected successfully."
                    else:
                        return False, f"HTTP {resp.status_code}: {resp.text[:120]}"

            elif provider == "freellmapi":
                url = config.get("freellmapi_url", "").strip()
                key = config.get("freellmapi_key", "").strip()
                if not url:
                    return False, "FreeLLMAPI Endpoint URL is required."
                headers = {"Authorization": f"Bearer {key}"} if key else {}
                test_endpoint = url.rstrip("/") + "/models"
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(test_endpoint, headers=headers)
                    if resp.status_code in (200, 404):  # Some providers don't have /models, but server is alive
                        return True, "FreeLLMAPI server is reachable."
                    return False, f"HTTP {resp.status_code}: {resp.text[:120]}"

            elif provider == "ollama":
                url = config.get("ollama_url", "http://localhost:11434").strip()
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(f"{url.rstrip('/')}/api/tags")
                    if resp.status_code == 200:
                        models = [m.get("name") for m in resp.json().get("models", [])]
                        return True, f"Ollama online! Available models: {', '.join(models) if models else 'None'}"
                    return False, f"HTTP {resp.status_code}: {resp.text[:120]}"

            return False, f"Unknown provider: {provider}"

        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    async def generate_response(
        self,
        prompt: str,
        config: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> str:
        provider = config.get("provider", "gemini").lower()
        sys_instruction = system_prompt or config.get("system_prompt", "You are ATLAS 2.0, an AI assistant.")

        if provider == "gemini":
            return await self._generate_gemini(prompt, config, sys_instruction)
        elif provider == "openrouter":
            return await self._generate_openrouter(prompt, config, sys_instruction)
        elif provider == "freellmapi":
            return await self._generate_openai_compatible(prompt, config, sys_instruction)
        elif provider == "ollama":
            return await self._generate_ollama(prompt, config, sys_instruction)
        else:
            return f"Error: Unsupported provider '{provider}'."

    async def _generate_gemini(self, prompt: str, config: Dict[str, Any], system_prompt: str) -> str:
        key = config.get("gemini_api_key", "").strip()
        model = config.get("gemini_model", "gemini-1.5-flash").strip()
        if not key:
            return "Gemini API key is not configured. Please add it in Settings."

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]}
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                except (KeyError, IndexError):
                    return "Received empty response from Gemini."
            else:
                return f"Gemini API error (Status {resp.status_code}): {resp.text[:200]}"

    async def _generate_openrouter(self, prompt: str, config: Dict[str, Any], system_prompt: str) -> str:
        key = config.get("openrouter_api_key", "").strip()
        model = config.get("openrouter_model", "google/gemini-2.0-flash-exp:free").strip()
        if not key:
            return "OpenRouter API key is not configured. Please add it in Settings."

        headers = {
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": "https://github.com/atlas-ai",
            "X-Title": "ATLAS 2.0",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                return f"OpenRouter API error ({resp.status_code}): {resp.text[:200]}"

    async def _generate_openai_compatible(self, prompt: str, config: Dict[str, Any], system_prompt: str) -> str:
        url = config.get("freellmapi_url", "https://api.freellmapi.com/v1").rstrip("/") + "/chat/completions"
        key = config.get("freellmapi_key", "").strip()
        model = config.get("freellmapi_model", "gpt-3.5-turbo").strip()

        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                return f"API error ({resp.status_code}): {resp.text[:200]}"

    async def _generate_ollama(self, prompt: str, config: Dict[str, Any], system_prompt: str) -> str:
        base_url = config.get("ollama_url", "http://localhost:11434").rstrip("/")
        model = config.get("ollama_model", "llama3").strip()
        url = f"{base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                return resp.json().get("response", "").strip()
            else:
                return f"Ollama error ({resp.status_code}): {resp.text[:200]}"

llm_hub = LLMHub()
