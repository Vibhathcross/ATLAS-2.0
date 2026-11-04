import asyncio
import io
import os
import time
import base64
from typing import List, Dict, Any, Optional

POPULAR_VOICES = [
    {"id": "en-US-ChristopherNeural", "name": "Christopher (US Male - Deep & Confident)", "gender": "Male", "locale": "en-US"},
    {"id": "en-US-GuyNeural", "name": "Guy (US Male - Energetic)", "gender": "Male", "locale": "en-US"},
    {"id": "en-US-JennyNeural", "name": "Jenny (US Female - Clear & Professional)", "gender": "Female", "locale": "en-US"},
    {"id": "en-US-AriaNeural", "name": "Aria (US Female - Expressive)", "gender": "Female", "locale": "en-US"},
    {"id": "en-GB-RyanNeural", "name": "Ryan (UK Male - Authoritative)", "gender": "Male", "locale": "en-GB"},
    {"id": "en-GB-SoniaNeural", "name": "Sonia (UK Female - Crisp British)", "gender": "Female", "locale": "en-GB"},
    {"id": "en-AU-WilliamNeural", "name": "William (AU Male - Natural)", "gender": "Male", "locale": "en-AU"},
    {"id": "en-IN-PrabhatNeural", "name": "Prabhat (India Male)", "gender": "Male", "locale": "en-IN"},
    {"id": "en-IN-NeerjaNeural", "name": "Neerja (India Female)", "gender": "Female", "locale": "en-IN"}
]

class TTSService:
    """Free, high-fidelity neural voice synthesis using edge-tts."""

    def __init__(self):
        pass

    async def list_voices(self) -> List[Dict[str, Any]]:
        try:
            import edge_tts
            all_voices = await edge_tts.list_voices()
            english_voices = [
                {"id": v["ShortName"], "name": f"{v['FriendlyName']}", "gender": v["Gender"], "locale": v["Locale"]}
                for v in all_voices if v["Locale"].startswith("en-")
            ]
            return english_voices if english_voices else POPULAR_VOICES
        except Exception as e:
            print(f"Error fetching voices: {e}")
            return POPULAR_VOICES

    def synthesize_offline_pyttsx3(self, text: str) -> bytes:
        """Free, open-source local offline speech synthesis engine using pyttsx3."""
        temp_wav = os.path.join(os.path.dirname(__file__), "..", "..", "data", f"tts_{os.getpid()}_{time.time_ns()}.wav")
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            clean_text = text.replace("*", "").replace("_", "").replace("#", "").replace("`", "")[:350]
            engine.save_to_file(clean_text, temp_wav)
            engine.runAndWait()
            if os.path.exists(temp_wav):
                with open(temp_wav, "rb") as f:
                    data = f.read()
                os.remove(temp_wav)
                return data
        except Exception as py_err:
            print(f"[TTS pyttsx3 Notice]: {py_err}")
            if os.path.exists(temp_wav):
                try: os.remove(temp_wav)
                except Exception: pass
        return self.synthesize_offline_sapi(text)

    def synthesize_offline_sapi(self, text: str) -> bytes:
        """Offline Windows SAPI.SpVoice synthesizer fallback (100% network independent)."""
        temp_wav = os.path.join(os.path.dirname(__file__), "..", "..", "data", f"sapi_{os.getpid()}_{asyncio.current_task().get_name() if asyncio.current_task() else 'sync'}.wav")
        try:
            import pythoncom
            pythoncom.CoInitialize()
            import win32com.client
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            stream.Open(temp_wav, 3, False)
            voice.AudioOutputStream = stream
            # Strip markdown formatting
            clean_text = text.replace("*", "").replace("_", "").replace("#", "").replace("`", "")[:250]
            voice.Speak(clean_text)
            stream.Close()
            if os.path.exists(temp_wav):
                with open(temp_wav, "rb") as f:
                    data = f.read()
                os.remove(temp_wav)
                return data
        except Exception as sapi_err:
            print(f"[TTS SAPI Fallback Error]: {sapi_err}")
            if os.path.exists(temp_wav):
                try: os.remove(temp_wav)
                except Exception: pass
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass
        return b""

    async def synthesize_to_bytes(self, text: str, voice: str = "en-US-ChristopherNeural", rate: str = "+0%", pitch: str = "+0Hz", timeout_sec: float = 4.5) -> bytes:
        import edge_tts
        async def _run_stream():
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            audio_stream = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_stream.write(chunk["data"])
            return audio_stream.getvalue()

        try:
            audio_data = await asyncio.wait_for(_run_stream(), timeout=timeout_sec)
            if audio_data:
                return audio_data
        except Exception as e:
            print(f"[TTS Notice] Edge-TTS unavailable ({e}). Engaging open-source local offline speech engine (pyttsx3)...")

        # Automatic offline fallback to open-source local offline speech engine
        return await asyncio.to_thread(self.synthesize_offline_pyttsx3, text)

    async def synthesize_to_base64(self, text: str, voice: str = "en-US-ChristopherNeural", rate: str = "+0%", pitch: str = "+0Hz", timeout_sec: float = 5.0) -> Optional[str]:
        audio_bytes = await self.synthesize_to_bytes(text, voice, rate, pitch, timeout_sec=timeout_sec)
        if not audio_bytes:
            return None
        return base64.b64encode(audio_bytes).decode("utf-8")

tts_service = TTSService()
