import os
import io
import sys
import time
import json
import uuid
import base64
import asyncio
import subprocess
import webbrowser
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import config_manager
from backend.database import db_manager
from backend.core.actions import system_actions
from backend.core.llm_hub import llm_hub
from backend.core.tts_service import tts_service
from backend.core.voice_biometrics import voice_biometrics
from backend.core.telegram_bot import telegram_bridge, TelegramBridge
from backend.core.engine import atlas_engine
from backend.core.antigravity_watcher import antigravity_watcher
from backend.core.mia import mia_agent, mia_storage, seed_sample_emails_if_empty, email_ingestion_service

app = FastAPI(title="ATLAS 2.0 Engine", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"

active_connections: List[WebSocket] = []

async def broadcast_ws(event: str, data: Any):
    payload = json.dumps({"event": event, "data": data})
    disconnected = []
    for ws in active_connections:
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in active_connections:
            active_connections.remove(ws)

async def on_engine_state(state: str, detail: str = ""):
    await broadcast_ws("state_change", {"state": state, "detail": detail})

atlas_engine.set_state_callback(on_engine_state)

async def on_telegram_command(command: str, source: str = "telegram", image_path: Optional[str] = None):
    result = await atlas_engine.execute_command(command, source=source, image_path=image_path)
    
    # Execute any system post action (e.g. lock workstation, sleep, shutdown)
    post_action = result.get("post_action")
    if post_action:
        try:
            if post_action == "lock":
                system_actions.lock_workstation()
            elif post_action == "shutdown":
                system_actions.shutdown(seconds=0)
            elif post_action == "lock_and_shutdown":
                system_actions.lock_workstation()
                system_actions.shutdown(seconds=1)
            elif post_action == "restart":
                system_actions.restart(seconds=1)
            elif post_action == "sleep":
                system_actions.sleep()
            elif post_action == "self_refresh":
                system_actions.self_refresh()
            elif post_action == "toggle_antigravity_mode":
                await broadcast_ws("config_updated", config_manager.config)
        except Exception as e:
            print(f"[Telegram Command Post-Action Error]: {e}")

    await broadcast_ws("remote_command", {
        "source": source,
        "command": command or ("Image Attachment" if image_path else ""),
        "response": result.get("response"),
        "audio_b64": result.get("audio_b64")
    })
    return result

telegram_bridge.set_command_handler(on_telegram_command)

async def on_antigravity_completed(full_content: str, preview: str, step_index: int = -1):
    print(f"[ATLAS] Antigravity generation complete (Step {step_index}): {preview}")
    cfg = config_manager.config
    preview_clean = preview or "Antigravity task completed successfully."
    text_msg = f"Boss, Antigravity has completed generation: {preview_clean[:90]}"
    audio_b64 = None
    if cfg.get("voice_output", True):
        try:
            tts_cfg = cfg.get("tts", {})
            audio_b64 = await tts_service.synthesize_to_base64(
                text=text_msg,
                voice=tts_cfg.get("voice", "en-US-ChristopherNeural"),
                rate=tts_cfg.get("rate", "+0%"),
                pitch=tts_cfg.get("pitch", "+0Hz")
            )
        except Exception as e:
            print(f"TTS synthesis error for Antigravity completion: {e}")

    await broadcast_ws("antigravity_completed", {
        "message": text_msg,
        "preview": preview_clean,
        "full_content": full_content,
        "step_index": step_index,
        "audio_b64": audio_b64
    })

    # Dispatch full completion response to Telegram
    if telegram_bridge.is_running and telegram_bridge.bot_app:
        try:
            tg_cfg = config_manager.get("telegram", {})
            chat_id = tg_cfg.get("allowed_chat_id") or telegram_bridge.last_chat_id
            if chat_id:
                header = f"🛰️ *Antigravity Completed Task* (Step {step_index})\n\n" if step_index >= 0 else "🛰️ *Antigravity Completed Task*\n\n"
                full_body = full_content.strip() if full_content else preview_clean
                formatted = header + full_body
                chunks = TelegramBridge._chunk_text(formatted)
                for chunk in chunks:
                    try:
                        await telegram_bridge.bot_app.bot.send_message(
                            chat_id=chat_id,
                            text=chunk,
                            parse_mode="Markdown"
                        )
                    except Exception:
                        try:
                            await telegram_bridge.bot_app.bot.send_message(
                                chat_id=chat_id,
                                text=chunk,
                                parse_mode=None
                            )
                        except Exception as ex:
                            print(f"[Telegram Notification Error]: {ex}")

                # Send spoken completion audio to Telegram
                if audio_b64:
                    try:
                        audio_bytes = base64.b64decode(audio_b64)
                        voice_bio = io.BytesIO(audio_bytes)
                        voice_bio.name = "atlas_completion.mp3"
                        await telegram_bridge.bot_app.bot.send_voice(chat_id=chat_id, voice=voice_bio)
                    except Exception as ex:
                        print(f"[Telegram Voice Notification Error]: {ex}")
        except Exception as e:
            print(f"[Telegram Completion Dispatch Error]: {e}")

antigravity_watcher.on_completion_callback = on_antigravity_completed

def launch_app_window(url: str = "http://127.0.0.1:8000"):
    """Launch in standalone application window mode using Chrome or Edge, or system default browser."""
    # Put Chrome first as Chrome is the user's default browser (ProgId: ChromeHTML)
    browser_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]

    for p in browser_candidates:
        if os.path.exists(p):
            try:
                # App mode opens an instant frameless native desktop application window
                subprocess.Popen([p, f"--app={url}"])
                return
            except Exception as e:
                print(f"Error launching {p} --app: {e}")

    try:
        if hasattr(os, "startfile"):
            os.startfile(url)
        else:
            webbrowser.open(url)
    except Exception as e:
        print(f"Fallback browser error: {e}")

@app.on_event("startup")
async def startup_event():
    # Pre-warm Resemblyzer voice encoder with dummy forward pass for sub-25ms inference
    asyncio.create_task(asyncio.to_thread(voice_biometrics.warmup))

    # Start Antigravity real-time transcript watcher
    asyncio.create_task(antigravity_watcher.start())

    # Start Telegram if enabled
    tg_cfg = config_manager.get("telegram", {})
    if tg_cfg.get("enabled", False) and tg_cfg.get("token"):
        asyncio.create_task(telegram_bridge.start(
            token=tg_cfg.get("token"),
            allowed_chat_id=tg_cfg.get("allowed_chat_id")
        ))
    
    # Do not auto-seed sample emails (user requested clean real mailbox)
    # asyncio.create_task(seed_sample_emails_if_empty(force=False))

    # Auto launch desktop window
    launch_app_window("http://127.0.0.1:8000")

@app.on_event("shutdown")
async def shutdown_event():
    await antigravity_watcher.stop()
    await telegram_bridge.stop()

# --- REST Endpoints ---

@app.post("/api/system/restart")
async def restart_system():
    system_actions.self_refresh()
    return {"status": "restarting"}

@app.get("/api/config")
async def get_config():
    return config_manager.config.copy()

@app.post("/api/config")
async def update_config(payload: Dict[str, Any]):
    success = config_manager.save(payload)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save configuration.")
    await broadcast_ws("config_updated", config_manager.config)
    
    tg_cfg = config_manager.get("telegram", {})
    if tg_cfg.get("enabled", False) and tg_cfg.get("token"):
        asyncio.create_task(telegram_bridge.start(tg_cfg["token"], tg_cfg.get("allowed_chat_id")))
    else:
        asyncio.create_task(telegram_bridge.stop())

    if config_manager.get("telegram_queue_access", False):
        telegram_bridge.notify_queue()

    has_llm, llm_msg = mia_agent.check_llm_status()
    await broadcast_ws("mia_status_changed", {"has_llm": has_llm, "message": llm_msg})

    # Sync MIA configuration to Cloud MongoDB Atlas
    mia_storage.sync_config_to_cloud(config_manager.config.get("mia", {}))

    return {"status": "ok", "config": config_manager.config}

@app.get("/api/telegram/queue")
async def get_telegram_queue():
    return {
        "queue_access": config_manager.get("telegram_queue_access", False),
        "pending_count": db_manager.get_pending_telegram_queue_count(),
        "items": db_manager.get_telegram_queue(limit=30)
    }

@app.get("/api/logs")
async def get_logs(limit: int = 50, offset: int = 0, status: str = None):
    logs = db_manager.get_logs(limit=limit, offset=offset, status_filter=status)
    return {"logs": logs}

@app.delete("/api/logs")
async def clear_logs():
    db_manager.clear_logs()
    return {"status": "ok", "message": "Audit logs cleared."}

@app.get("/api/voices")
async def get_voices():
    voices = await tts_service.list_voices()
    return {"voices": voices}

@app.post("/api/test-voice")
async def test_voice(payload: Dict[str, Any]):
    voice = payload.get("voice", "en-US-ChristopherNeural")
    sample_text = payload.get("text", "Greetings. I am ATLAS 2.0, ready for your commands.")
    rate = payload.get("rate", "+0%")
    pitch = payload.get("pitch", "+0Hz")
    audio_b64 = await tts_service.synthesize_to_base64(sample_text, voice=voice, rate=rate, pitch=pitch)
    return {"audio_b64": audio_b64}

@app.post("/api/test-llm")
async def test_llm(payload: Dict[str, Any]):
    provider = payload.get("provider", "gemini")
    success, msg = await llm_hub.test_connection(provider, payload)
    return {"success": success, "message": msg}

@app.post("/api/test-telegram")
async def test_telegram(payload: Dict[str, Any]):
    token = payload.get("token", "")
    success, msg = await telegram_bridge.test_token(token)
    return {"success": success, "message": msg}

@app.get("/api/biometrics/status")
def biometrics_status():
    enrolled = voice_biometrics.is_enrolled()
    return {
        "enrolled": enrolled,
        "threshold": config_manager.get("biometrics.similarity_threshold", 0.72),
        "enabled": config_manager.get("biometrics.enabled", False)
    }

# Synchronous endpoints for CPU-bound Resemblyzer inference to run in FastAPI's internal threadpool
@app.post("/api/biometrics/enroll")
async def enroll_voice(files: List[UploadFile] = File(...)):
    wav_samples = []
    for file in files:
        content = await file.read()
        wav = voice_biometrics.audio_bytes_to_wav(content)
        if wav is not None and len(wav) >= 8000:
            wav_samples.append(wav)
            
    if not wav_samples:
        return JSONResponse(status_code=400, content={"success": False, "message": "Could not decode audio samples. Please ensure speech is audible and record for at least 1-2 seconds."})

    success, message = voice_biometrics.enroll_samples(wav_samples)
    if success:
        config_manager.update("biometrics.enrolled", True)
        config_manager.update("biometrics.enabled", True)
        await broadcast_ws("config_updated", config_manager.config)
    return {"success": success, "message": message}

@app.post("/api/biometrics/test")
async def test_voice_biometrics(file: UploadFile = File(...)):
    if not voice_biometrics.is_enrolled():
        return {
            "success": False,
            "is_enrolled": False,
            "message": "No voice profile enrolled yet. Please record and enroll 1 to 3 samples above first."
        }

    content = await file.read()
    wav = voice_biometrics.audio_bytes_to_wav(content)
    if wav is None:
        return JSONResponse(status_code=400, content={"success": False, "message": "Could not decode audio clip."})

    threshold = float(config_manager.get("biometrics.similarity_threshold", 0.72))
    is_match, similarity = voice_biometrics.verify_audio(wav, threshold=threshold)

    status_text = "AUTHORIZED OWNER" if is_match else "VOICE MISMATCH"
    msg = f"{status_text}: {int(similarity * 100)}% similarity ({'>=' if is_match else '<'} {int(threshold * 100)}% threshold)"

    return {
        "success": True,
        "is_enrolled": True,
        "is_match": is_match,
        "similarity": similarity,
        "threshold": threshold,
        "message": msg
    }

@app.delete("/api/biometrics/profile")
async def delete_voice_profile():
    voice_biometrics.delete_profile()
    config_manager.update("biometrics.enrolled", False)
    config_manager.update("biometrics.enabled", False)
    await broadcast_ws("config_updated", config_manager.config)
    return {"success": True, "message": "Voice profile successfully removed. You can now record new samples."}

# --- MIA (Mail Intelligence Assistant) Endpoints ---

@app.get("/api/mia/status")
async def get_mia_status():
    has_llm, llm_msg = mia_agent.check_llm_status()
    stats = mia_storage.get_stats()
    mia_cfg = config_manager.get("mia", {})
    return {
        "enabled": mia_cfg.get("enabled", True),
        "has_llm": has_llm,
        "llm_message": llm_msg,
        "provider": mia_cfg.get("provider", "gemini"),
        "model": mia_cfg.get("model", ""),
        "summary_hours": mia_cfg.get("summary_hours", 2),
        "high_confidence": mia_cfg.get("high_confidence", 0.90),
        "min_confidence": mia_cfg.get("min_confidence", 0.65),
        "margin_delta": mia_cfg.get("margin_delta", 0.08),
        "mongodb_uri": mia_cfg.get("mongodb_uri", ""),
        "mongodb_db": mia_cfg.get("mongodb_db", "atlas_mia"),
        "stats": stats
    }

@app.post("/api/mia/seed")
async def seed_mia(payload: Dict[str, Any] = None):
    force = bool((payload or {}).get("force", False))
    stats = await seed_sample_emails_if_empty(force=force)
    return {"status": "ok", "stats": stats}

@app.post("/api/mia/ingest")
async def ingest_email_api(payload: Dict[str, Any]):
    if not payload.get("email_id"):
        payload["email_id"] = f"email-api-{int(time.time())}"
    record = await email_ingestion_service.ingest_email(payload)
    return {"status": "ok", "email": record}

@app.post("/api/mia/query")
async def query_mia_api(payload: Dict[str, Any]):
    cmd = payload.get("command", "")
    res = await mia_agent.execute(cmd)
    return res

@app.post("/api/mia/test-mongodb")
async def test_mongodb_endpoint(payload: Dict[str, Any]):
    uri = payload.get("uri", "")
    success, msg = mia_storage.test_mongodb(uri)
    if success:
        config_manager.update("mia.mongodb_uri", uri)
        mia_storage.sync_config_to_cloud(config_manager.config.get("mia", {}))
    return {"success": success, "message": msg}

@app.post("/api/mia/test-llm")
async def test_mia_llm(payload: Dict[str, Any]):
    provider = payload.get("provider", "gemini")
    success, msg = await llm_hub.test_connection(provider, payload)
    return {"success": success, "message": msg}

# --- WebSocket Channel ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    has_llm, llm_msg = mia_agent.check_llm_status()
    await websocket.send_text(json.dumps({
        "event": "connected",
        "data": {
            "config": config_manager.config,
            "biometrics_enrolled": voice_biometrics.is_enrolled(),
            "mia_has_llm": has_llm,
            "mia_llm_message": llm_msg
        }
    }))
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                action = msg.get("action")
                
                if action == "execute_command":
                    text = msg.get("text", "")
                    audio_b64 = msg.get("audio_b64")
                    image_b64 = msg.get("image_b64")
                    audio_wav = None
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        audio_wav = voice_biometrics.audio_bytes_to_wav(audio_bytes)

                    image_path = None
                    if image_b64:
                        try:
                            if "," in image_b64:
                                image_b64 = image_b64.split(",", 1)[1]
                            img_data = base64.b64decode(image_b64)
                            uploads_dir = Path(__file__).resolve().parent.parent / "data" / "uploads"
                            uploads_dir.mkdir(parents=True, exist_ok=True)
                            image_path = str(uploads_dir / f"chat_img_{int(time.time())}_{uuid.uuid4().hex[:6]}.png")
                            with open(image_path, "wb") as f_img:
                                f_img.write(img_data)
                        except Exception as e_img:
                            print(f"[Chat Image Save Error]: {e_img}")

                    result = await atlas_engine.execute_command(
                        command_text=text,
                        source=msg.get("source", "voice"),
                        audio_wav=audio_wav,
                        image_path=image_path
                    )
                    if result.get("post_action") == "toggle_antigravity_mode":
                        await broadcast_ws("config_updated", config_manager.config)

                    await websocket.send_text(json.dumps({
                        "event": "command_result",
                        "data": result
                    }))

                elif action == "execute_post_action":
                    post_action = msg.get("post_action")
                    if post_action == "lock":
                        system_actions.lock_workstation()
                    elif post_action == "shutdown":
                        system_actions.shutdown(seconds=0)
                    elif post_action == "lock_and_shutdown":
                        system_actions.lock_workstation()
                        system_actions.shutdown(seconds=1)
                    elif post_action == "restart":
                        system_actions.restart(seconds=1)
                    elif post_action == "sleep":
                        system_actions.sleep()
                    elif post_action == "self_refresh":
                        system_actions.self_refresh()
                    elif post_action == "toggle_antigravity_mode":
                        await broadcast_ws("config_updated", config_manager.config)

                elif action == "toggle_setting":
                    key = msg.get("key")
                    val = msg.get("value")
                    if key:
                        config_manager.update(key, val)
                        await broadcast_ws("config_updated", config_manager.config)
                        if key == "telegram_queue_access" and val:
                            telegram_bridge.notify_queue()

                elif action == "set_state":
                    new_state = msg.get("state", "idle")
                    detail = msg.get("detail", "")
                    await broadcast_ws("state_change", {"state": new_state, "detail": detail})

            except Exception as e:
                print(f"WS message handling error: {e}")
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)

# Mount frontend files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
async def root():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "ATLAS 2.0 Backend Online"}
