import re
import time
import asyncio
from typing import Dict, Any, Tuple, Optional
from backend.config import config_manager
from backend.database import db_manager
from backend.core.actions import system_actions
from backend.core.llm_hub import llm_hub
from backend.core.voice_biometrics import voice_biometrics
from backend.core.tts_service import tts_service

class AtlasEngine:
    """Core Coordinator for ATLAS 2.0."""

    def __init__(self):
        self.state_callback = None
        self._lock = asyncio.Lock()

    def set_state_callback(self, callback):
        self.state_callback = callback

    async def _emit_state(self, state: str, detail: str = ""):
        if self.state_callback:
            try:
                await self.state_callback(state, detail)
            except Exception as e:
                print(f"Error in state callback: {e}")

    async def execute_command(
        self,
        command_text: str,
        source: str = "text",
        audio_wav = None,
        image_path: Optional[str] = None
    ) -> Dict[str, Any]:
        async with self._lock:
            return await self._execute_command_internal(command_text, source, audio_wav, image_path)

    async def _execute_command_internal(
        self,
        command_text: str,
        source: str = "text",
        audio_wav = None,
        image_path: Optional[str] = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        command_clean = command_text.strip()
        config = config_manager.config
        
        speaker_verified = True
        confidence = 1.0

        bio_enabled = config.get("biometrics", {}).get("enabled", False)
        threshold = float(config.get("biometrics", {}).get("similarity_threshold", 0.72))

        # Biometric Verification: only respond when similarity matches threshold
        if bio_enabled and voice_biometrics.is_enrolled():
            if audio_wav is not None:
                await self._emit_state("processing", "Cosine check in progress...")
                is_match, conf = await asyncio.to_thread(voice_biometrics.verify_audio, audio_wav, threshold)
                speaker_verified = is_match
                confidence = float(conf)
                pct = int(confidence * 100)
                req_pct = int(threshold * 100)

                if not is_match:
                    response_msg = f"Security Mismatch: Voice does not match owner profile (Cosine: {pct}% < {req_pct}% threshold). Command blocked."
                    await self._emit_state("denied", f"Security Mismatch ({pct}%)")
                    latency = int((time.time() - start_time) * 1000)

                    db_manager.log_action(
                        source=source,
                        command=command_clean,
                        route="SECURITY_MISMATCH",
                        status="DENIED",
                        response=response_msg,
                        speaker_verified=False,
                        confidence=confidence,
                        latency_ms=latency
                    )

                    # Strictly NO voice output on mismatch; show security mismatch on chats area
                    return {
                        "success": False,
                        "command": command_clean,
                        "response": response_msg,
                        "audio_b64": None,
                        "route": "security_mismatch",
                        "speaker_verified": False,
                        "confidence": confidence,
                        "latency_ms": latency
                    }
                else:
                    await self._emit_state("processing", f"Cosine: {pct}% (>= {req_pct}%) · Verified Owner")
            elif source == "voice":
                # Voice command received without audio sample
                response_msg = "Security Mismatch: No biometric audio clip received. Command blocked."
                await self._emit_state("denied", "Voice audio missing")
                latency = int((time.time() - start_time) * 1000)
                return {
                    "success": False,
                    "command": command_clean,
                    "response": response_msg,
                    "audio_b64": None,
                    "route": "security_mismatch",
                    "speaker_verified": False,
                    "confidence": 0.0,
                    "latency_ms": latency
                }

        await self._emit_state("processing", f"Executing: {command_clean[:30]}...")

        brain_mode = config.get("brain_mode", "ai")
        route = "predefined"
        response_text = ""
        tts_spoken_text = None
        post_action = None
        success = True

        # Step 1.4: Check MIA Subagent Command ("mia:<command>" or "mia: ...")
        is_mia = bool(re.match(r"^mia\s*:", command_clean, re.IGNORECASE))
        if is_mia:
            from backend.core.mia import mia_agent
            await self._emit_state("processing", "MIA Processing...")
            mia_result = await mia_agent.execute(command_clean)
            route = f"subagent:mia:{mia_result.get('subcommand', 'query')}"
            response_text = mia_result.get("response", "")
            tts_spoken_text = mia_result.get("tts_text")
            success = mia_result.get("success", False)

        # Step 1.5: Force Send Now Command ("f:<command>" or "force:<command>")
        elif bool(re.match(r"^(?:f\s*:|force\s*:|f\s+|force\s+)\s*(.*)$", command_clean, re.IGNORECASE)):
            is_force_antigravity = True
            force_match = re.match(r"^(?:f\s*:|force\s*:|f\s+|force\s+)\s*(.*)$", command_clean, re.IGNORECASE)
            command_clean = force_match.group(1).strip()
            from backend.core.antigravity_bridge import antigravity_bridge
            route = "antigravity:force_send_now"
            relayed, msg = antigravity_bridge.send_prompt(command_clean, force_send_now=True, image_path=image_path)
            response_text = msg
            success = relayed
        else:
            is_force_antigravity = False
            # Step 2: Check Predefined Actions & Dispatch
            post_action = None
            match_info = system_actions.match_predefined_command(command_clean)
            matched = match_info[0]

            if matched and not image_path:
                action_name = match_info[1]
                result = match_info[2]
                post_action = match_info[3] if len(match_info) > 3 else None
                route = f"predefined:{action_name}"
                response_text = str(result)
            elif config.get("antigravity_mode", False) or image_path:
                # Explicit guard: NEVER redirect "#anti" or mode toggle commands to the agent
                from backend.core.actions import RE_TOGGLE_ANTI
                if RE_TOGGLE_ANTI.match(command_clean.strip()) and not image_path:
                    new_state, msg = system_actions.toggle_antigravity_mode()
                    route = "predefined:toggle_antigravity_mode"
                    response_text = msg
                    post_action = "toggle_antigravity_mode"
                    success = True
                else:
                    # Antigravity Mode: Route spoken/typed command or image directly to Antigravity
                    from backend.core.antigravity_bridge import antigravity_bridge
                    route = "antigravity:relay"
                    relayed, msg = antigravity_bridge.send_prompt(command_clean, force_send_now=False, image_path=image_path)
                    response_text = msg
                    success = relayed
            elif brain_mode == "predefined":
                route = "predefined:unmatched"
                response_text = "I didn't recognize that predefined command. You can switch to AI Brain mode for conversational requests."
                success = False
            else:
                # Step 3: AI Brain LLM Dispatch
                route = f"llm:{config.get('llm', {}).get('provider', 'gemini')}"
                try:
                    response_text = await llm_hub.generate_response(
                        prompt=command_clean,
                        config=config.get("llm", {}),
                        system_prompt=config.get("llm", {}).get("system_prompt")
                    )
                except Exception as e:
                    response_text = f"LLM execution error: {str(e)}"
                    success = False

        latency = int((time.time() - start_time) * 1000)

        # Step 4: TTS Generation if voice_output is enabled
        audio_b64 = None
        speech_text = tts_spoken_text or response_text
        if config.get("voice_output", True) and speech_text:
            await self._emit_state("speaking", "Synthesizing voice response...")
            try:
                tts_cfg = config.get("tts", {})
                audio_b64 = await tts_service.synthesize_to_base64(
                    text=speech_text,
                    voice=tts_cfg.get("voice", "en-US-ChristopherNeural"),
                    rate=tts_cfg.get("rate", "+0%"),
                    pitch=tts_cfg.get("pitch", "+0Hz")
                )
            except Exception as e:
                print(f"TTS synthesis error: {e}")

        # Step 5: Persistent DB Logging
        db_manager.log_action(
            source=source,
            command=command_clean,
            route=route,
            status="SUCCESS" if success else "FAILED",
            response=response_text,
            speaker_verified=speaker_verified,
            confidence=confidence,
            latency_ms=latency
        )

        await self._emit_state("idle", "Ready")

        return {
            "success": success,
            "response": response_text,
            "audio_b64": audio_b64,
            "route": route,
            "speaker_verified": speaker_verified,
            "confidence": confidence,
            "latency_ms": latency,
            "post_action": post_action
        }

atlas_engine = AtlasEngine()
