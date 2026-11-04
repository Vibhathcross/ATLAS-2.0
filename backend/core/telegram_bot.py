"""
Telegram Remote Bridge for ATLAS 2.0.
Fully asynchronous, non-blocking polling, boot-up connection assurance,
and paced command queue dispatching.
"""

import asyncio
import time
from pathlib import Path
import httpx
from typing import Optional, Callable, Awaitable, Tuple, List, Dict, Any

from backend.config import config_manager
from backend.database import db_manager

TELEGRAM_MAX_MSG_LEN = 4000

class TelegramBridge:
    """
    Telegram remote control bridge for ATLAS 2.0.
    Features:
    - Guaranteed boot-up connectivity with self-healing background supervisor
    - Automatic reconnection on network recovery / sleep wake
    - Paced queue execution (30-second time gap between commands)
    - Persistent deduplication preventing repeated command execution
    """

    def __init__(self):
        self.bot_app = None
        self.is_running = False
        self.should_run = False
        self.token: Optional[str] = None
        self.allowed_chat_id: Optional[str] = None
        self.last_chat_id: Optional[str] = None
        self._command_handler: Optional[Callable[..., Awaitable[Any]]] = None
        self._start_lock = asyncio.Lock()
        self._supervisor_task: Optional[asyncio.Task] = None
        self._queue_worker_task: Optional[asyncio.Task] = None
        self._queue_event = asyncio.Event()

    def set_command_handler(self, handler: Callable[..., Awaitable[Any]]):
        """Handler signature: async (text: str, source: str, image_path: Optional[str]) -> result_data"""
        self._command_handler = handler

    def is_queue_access_enabled(self) -> bool:
        """Returns True if Message Queue Access toggle is ON."""
        return bool(config_manager.get("telegram_queue_access", False))

    def notify_queue(self):
        """Wakes up the queue worker immediately."""
        self._queue_event.set()

    @staticmethod
    async def test_token(token: str) -> Tuple[bool, str]:
        token = token.strip()
        if not token:
            return False, "Bot token cannot be empty."
        url = f"https://api.telegram.org/bot{token}/getMe"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    bot_name = data.get("result", {}).get("username", "UnknownBot")
                    first_name = data.get("result", {}).get("first_name", "ATLAS Bot")
                    return True, f"Connected to @{bot_name} ({first_name}) successfully!"
                else:
                    return False, f"Telegram API error ({resp.status_code}): {resp.text[:120]}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    @staticmethod
    def _chunk_text(text: str, max_size: int = TELEGRAM_MAX_MSG_LEN) -> List[str]:
        """Splits long responses into Telegram-compatible message chunks."""
        if len(text) <= max_size:
            return [text]
        chunks = []
        while text:
            if len(text) <= max_size:
                chunks.append(text)
                break
            # Find a convenient newline or space split point
            split_idx = text.rfind("\n", 0, max_size)
            if split_idx == -1 or split_idx < max_size // 2:
                split_idx = text.rfind(" ", 0, max_size)
            if split_idx == -1:
                split_idx = max_size
            chunks.append(text[:split_idx].strip())
            text = text[split_idx:].strip()
        return [c for c in chunks if c]

    async def _send_result_to_chat(self, chat_id: str, result_data: Any):
        """Dispatches response text and spoken voice audio to a Telegram chat."""
        if not self.bot_app or not self.bot_app.bot:
            return

        if isinstance(result_data, dict):
            text = result_data.get("response", "Command executed.")
            audio_b64 = result_data.get("audio_b64")
        else:
            text = str(result_data)
            audio_b64 = None

        chunks = self._chunk_text(text)
        for chunk in chunks:
            try:
                await self.bot_app.bot.send_message(chat_id=chat_id, text=chunk, parse_mode="Markdown")
            except Exception:
                try:
                    await self.bot_app.bot.send_message(chat_id=chat_id, text=chunk, parse_mode=None)
                except Exception as ex:
                    print(f"[Telegram Reply Text Error]: {ex}")

        # Send spoken neural voice audio clip directly on Telegram
        if audio_b64:
            try:
                import base64
                import io
                audio_bytes = base64.b64decode(audio_b64)
                voice_bio = io.BytesIO(audio_bytes)
                voice_bio.name = "atlas_voice.mp3"
                await self.bot_app.bot.send_voice(chat_id=chat_id, voice=voice_bio)
            except Exception as e:
                print(f"[Telegram Voice Reply Error]: {e}")

    async def _send_continuous_typing(self, chat_id: int, bot):
        """Maintains the typing indicator while long tasks execute."""
        try:
            while True:
                await bot.send_chat_action(chat_id=chat_id, action="typing")
                await asyncio.sleep(4.5)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def _queue_worker_loop(self):
        """
        Background worker that processes pending queued Telegram messages
        with a mandatory 30-second time gap between commands.
        Only runs when Message Queue Access toggle is switched ON.
        """
        print("[Telegram Queue] Worker loop initialized.")
        while self.is_running:
            try:
                # 1. Check if Message Queue Access toggle is active
                if not self.is_queue_access_enabled():
                    try:
                        await asyncio.wait_for(self._queue_event.wait(), timeout=3.0)
                        self._queue_event.clear()
                    except asyncio.TimeoutError:
                        pass
                    continue

                # 2. Retrieve next pending message from persistent SQLite queue (FIFO order)
                msg_item = db_manager.get_next_pending_telegram_message()
                if not msg_item:
                    try:
                        await asyncio.wait_for(self._queue_event.wait(), timeout=3.0)
                        self._queue_event.clear()
                    except asyncio.TimeoutError:
                        pass
                    continue

                queue_id = msg_item["id"]
                chat_id = str(msg_item["chat_id"])
                command_text = msg_item["command_text"]
                image_path = msg_item.get("image_path")

                # Mark status as processing so it is not picked up again
                db_manager.update_telegram_message_status(queue_id, "processing")
                print(f"[Telegram Queue] Executing queued item #{queue_id}: '{command_text}' (Chat: {chat_id})")

                typing_task = None
                if self.bot_app and self.bot_app.bot and chat_id:
                    try:
                        typing_task = asyncio.create_task(
                            self._send_continuous_typing(int(chat_id), self.bot_app.bot)
                        )
                    except Exception:
                        pass

                result_data = None
                try:
                    if self._command_handler:
                        result_data = await self._command_handler(command_text, "telegram", image_path)
                    else:
                        result_data = "ATLAS engine is currently offline."
                except Exception as ex:
                    result_data = f"Execution error: {str(ex)}"
                finally:
                    if typing_task:
                        typing_task.cancel()

                # Dispatch text and voice result back to user on Telegram
                if self.bot_app and self.bot_app.bot and chat_id:
                    await self._send_result_to_chat(chat_id, result_data)

                # Mark as completed in persistent database (prevents repeated processing forever)
                resp_str = result_data.get("response") if isinstance(result_data, dict) else str(result_data)
                db_manager.update_telegram_message_status(queue_id, "completed", response=resp_str)
                print(f"[Telegram Queue] Item #{queue_id} executed and marked completed.")

                # 3. Paced Execution: Check if there are more pending messages
                remaining = db_manager.get_pending_telegram_queue_count()
                if remaining > 0 and self.is_queue_access_enabled():
                    print(f"[Telegram Queue] {remaining} message(s) queued. Pacing next execution with 30-second time gap...")
                    for _ in range(30):
                        if not self.is_running or not self.is_queue_access_enabled():
                            print("[Telegram Queue] Queue Access toggled OFF or bridge stopped during 30s gap. Pausing queue.")
                            break
                        await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Telegram Queue Worker Loop Error]: {e}")
                await asyncio.sleep(3.0)

    async def _connection_supervisor(self):
        """
        Guarantees Telegram connectivity on boot-up and maintains it continuously.
        Automatically retries with exponential backoff on startup until network/DNS is ready,
        and automatically self-heals/reconnects if network disconnects or resumes from sleep.
        """
        print("[Telegram Supervisor] Connection supervisor started.")
        backoff = 2.0
        max_backoff = 15.0

        while self.should_run:
            try:
                # If not currently running/connected, attempt connection
                if not self.is_running or not self.bot_app:
                    print("[Telegram Supervisor] Checking network & establishing Telegram bridge connection...")
                    connected = await self._connect_bridge()
                    if connected:
                        backoff = 2.0
                        print("[Telegram Supervisor] Telegram connection successfully established and verified!")
                    else:
                        print(f"[Telegram Supervisor] Network/Telegram not ready yet on boot. Retrying in {backoff:.1f}s...")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 1.5, max_backoff)
                        continue

                # Once connected, run health checks periodically
                await asyncio.sleep(15.0)

                # Health Check: verify updater is active
                if self.is_running and self.bot_app:
                    updater_alive = (
                        self.bot_app.updater is not None and 
                        getattr(self.bot_app.updater, "running", False)
                    )
                    if not updater_alive:
                        print("[Telegram Supervisor] Polling loop was interrupted or dropped. Triggering auto-reconnect...")
                        await self._stop_internal()
                        await asyncio.sleep(2.0)
                        continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Telegram Supervisor] Notice: {e}")
                await asyncio.sleep(5.0)

        print("[Telegram Supervisor] Supervisor stopped.")

    async def _connect_bridge(self) -> bool:
        """Attempts to connect to Telegram with network validation."""
        if not self.token:
            return False

        # Pre-flight check: verify API server is reachable
        can_reach, test_msg = await self.test_token(self.token)
        if not can_reach:
            return False

        try:
            from telegram import Update
            from telegram.error import Conflict, NetworkError
            from telegram.request import HTTPXRequest
            from telegram.ext import (
                ApplicationBuilder,
                ContextTypes,
                CommandHandler,
                MessageHandler,
                filters
            )

            # Robust HTTPX configuration with generous timeouts
            tg_request = HTTPXRequest(
                connection_pool_size=8,
                connect_timeout=15.0,
                read_timeout=30.0,
                write_timeout=15.0,
                pool_timeout=10.0
            )

            builder = ApplicationBuilder().token(self.token).request(tg_request)
            builder.concurrent_updates(True)
            app = builder.build()

            async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
                if isinstance(context.error, Conflict):
                    print("[Telegram] Polling conflict detected (previous instance closing). Waiting 2s...")
                    await asyncio.sleep(2.0)
                    return
                elif isinstance(context.error, NetworkError):
                    print(f"[Telegram Network Notice]: {context.error}")
                    return
                print(f"[Telegram Error Handler]: {context.error}")

            app.add_error_handler(error_handler)

            def is_authorized(chat_id: str) -> bool:
                if not self.allowed_chat_id or not str(self.allowed_chat_id).strip():
                    return True
                return str(chat_id).strip() == str(self.allowed_chat_id).strip()

            async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
                chat_id = str(update.effective_chat.id)
                self.last_chat_id = chat_id
                if not is_authorized(chat_id):
                    await update.message.reply_text(
                        f"⚠️ Unauthorized access.\nYour Chat ID is `{chat_id}`.\n"
                        "Add this Chat ID to ATLAS Settings Whitelist to enable remote access.",
                        parse_mode="Markdown"
                    )
                    return

                db_manager.enqueue_telegram_message(
                    chat_id=chat_id,
                    message_id=update.message.message_id,
                    command_text="/start",
                    update_id=update.update_id,
                    status="completed",
                    response="Connected & Ready"
                )

                queue_status_text = "Active (30s time gap)" if self.is_queue_access_enabled() else "Paused (Turn ON 'Message Queue Access' in ATLAS)"

                await update.message.reply_text(
                    f"🛰️ *ATLAS 2.0 Remote Control Online*\n\n"
                    f"• *Status:* Connected & Ready\n"
                    f"• *Your Chat ID:* `{chat_id}`\n"
                    f"• *Message Queue:* {queue_status_text}\n\n"
                    f"Send any system command, prompt, or photo to control ATLAS remotely.\n"
                    f"Type /help to see all available commands.",
                    parse_mode="Markdown"
                )

            async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
                chat_id = str(update.effective_chat.id)
                self.last_chat_id = chat_id
                if not is_authorized(chat_id):
                    await update.message.reply_text("⚠️ Unauthorized.")
                    return

                db_manager.enqueue_telegram_message(
                    chat_id=chat_id,
                    message_id=update.message.message_id,
                    command_text="/help",
                    update_id=update.update_id,
                    status="completed",
                    response="Help reference displayed"
                )

                help_text = (
                    "🛠️ *ATLAS 2.0 Command Reference*\n\n"
                    "⚡ *Quick System Commands:*\n"
                    "• `/status` — CPU, RAM, battery, system status\n"
                    "• `/clear` — Minimize all windows (Show Desktop)\n"
                    "• `lock computer` — Lock Windows workstation\n"
                    "• `sleep` — Put computer into sleep mode\n"
                    "• `volume up` / `volume down` / `mute` — Volume controls\n"
                    "• `open <app>` — E.g., `open chrome`, `open notepad`, `open spotify`\n"
                    "• `close <app>` — Gracefully terminates target app\n"
                    "• `autokeyboard <keys>` — Press key combination up to 10 keys (e.g. `autokeyboard win+d`)\n"
                    "• `selfrefresh` — Restarts ATLAS 2.0 to reload new features\n\n"
                    "🧠 *AI & Antigravity Mode:*\n"
                    "• `#anti` — Toggles Antigravity Mode on/off\n"
                    "• `f:<command>` — Force Send Now directly to Antigravity\n"
                    "• *Images / Photos* — Send any photo/image to relay directly to Antigravity\n\n"
                    "⏱️ *Queue Access Mode:*\n"
                    "When Message Queue Access is switched ON in ATLAS, queued messages execute with a 30s gap one after another."
                )
                await update.message.reply_text(help_text, parse_mode="Markdown")

            async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
                chat_id = str(update.effective_chat.id)
                self.last_chat_id = chat_id
                if not is_authorized(chat_id):
                    await update.message.reply_text("⚠️ Unauthorized.")
                    return

                db_manager.enqueue_telegram_message(
                    chat_id=chat_id,
                    message_id=update.message.message_id,
                    command_text="system status",
                    update_id=update.update_id,
                    status="pending"
                )
                if self.is_queue_access_enabled():
                    self.notify_queue()
                else:
                    pending_count = db_manager.get_pending_telegram_queue_count()
                    await update.message.reply_text(
                        f"⏸️ *Command Queued (Queue Access is OFF)*\n"
                        f"• Command: `system status`\n"
                        f"• Queue Position: #{pending_count}\n\n"
                        f"Switch ON *Message Queue Access* in ATLAS to process queued commands.",
                        parse_mode="Markdown"
                    )

            async def handle_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
                chat_id = str(update.effective_chat.id)
                self.last_chat_id = chat_id
                if not is_authorized(chat_id):
                    await update.message.reply_text("⚠️ Unauthorized.")
                    return

                db_manager.enqueue_telegram_message(
                    chat_id=chat_id,
                    message_id=update.message.message_id,
                    command_text="clear all apps",
                    update_id=update.update_id,
                    status="pending"
                )
                if self.is_queue_access_enabled():
                    self.notify_queue()
                else:
                    pending_count = db_manager.get_pending_telegram_queue_count()
                    await update.message.reply_text(
                        f"⏸️ *Command Queued (Queue Access is OFF)*\n"
                        f"• Command: `clear all apps`\n"
                        f"• Queue Position: #{pending_count}\n\n"
                        f"Switch ON *Message Queue Access* in ATLAS to process queued commands.",
                        parse_mode="Markdown"
                    )

            async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if not update.message or not update.message.text:
                    return

                update_id = update.update_id
                chat_id = str(update.effective_chat.id)
                self.last_chat_id = chat_id

                if not is_authorized(chat_id):
                    await update.message.reply_text(
                        f"⚠️ Access denied. Chat ID `{chat_id}` is not whitelisted in ATLAS Settings.",
                        parse_mode="Markdown"
                    )
                    return

                # Prevent repeated execution of already processed updates
                if db_manager.is_telegram_update_processed(update_id):
                    print(f"[Telegram] Update {update_id} already executed. Skipping repeat execution.")
                    return

                command_text = update.message.text.strip()
                if not command_text:
                    return

                queue_id = db_manager.enqueue_telegram_message(
                    chat_id=chat_id,
                    message_id=update.message.message_id,
                    command_text=command_text,
                    update_id=update_id,
                    status="pending"
                )

                if not queue_id:
                    return

                if self.is_queue_access_enabled():
                    self.notify_queue()
                else:
                    msg_time = update.message.date.timestamp() if update.message.date else time.time()
                    if (time.time() - msg_time) < 60:
                        pending_count = db_manager.get_pending_telegram_queue_count()
                        await update.message.reply_text(
                            f"⏸️ *Command Queued (Queue Access is OFF)*\n"
                            f"• Command: `{command_text}`\n"
                            f"• Queue Position: #{pending_count}\n\n"
                            f"Switch ON *Message Queue Access* in ATLAS to process queued commands with a 30-second time gap.",
                            parse_mode="Markdown"
                        )

            async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if not update.message:
                    return

                update_id = update.update_id
                chat_id = str(update.effective_chat.id)
                self.last_chat_id = chat_id

                if not is_authorized(chat_id):
                    await update.message.reply_text(
                        f"⚠️ Access denied. Chat ID `{chat_id}` is not whitelisted in ATLAS Settings.",
                        parse_mode="Markdown"
                    )
                    return

                if db_manager.is_telegram_update_processed(update_id):
                    print(f"[Telegram] Photo update {update_id} already executed. Skipping repeat execution.")
                    return

                photo_obj = None
                if update.message.photo:
                    photo_obj = update.message.photo[-1]
                elif update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith("image/"):
                    photo_obj = update.message.document

                if not photo_obj:
                    await update.message.reply_text("Could not recognize image attachment.")
                    return

                tg_file = await photo_obj.get_file()
                uploads_dir = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
                uploads_dir.mkdir(parents=True, exist_ok=True)
                file_ext = ".jpg"
                if tg_file.file_path and "." in tg_file.file_path:
                    file_ext = "." + tg_file.file_path.split(".")[-1]
                saved_path = uploads_dir / f"tg_{int(time.time())}_{photo_obj.file_unique_id}{file_ext}"
                await tg_file.download_to_drive(str(saved_path))

                caption = (update.message.caption or "").strip()

                queue_id = db_manager.enqueue_telegram_message(
                    chat_id=chat_id,
                    message_id=update.message.message_id,
                    command_text=caption or "Image Attachment",
                    update_id=update_id,
                    image_path=str(saved_path),
                    status="pending"
                )

                if not queue_id:
                    return

                if self.is_queue_access_enabled():
                    await update.message.reply_text("🛰️ Image queued for Antigravity relay...")
                    self.notify_queue()
                else:
                    msg_time = update.message.date.timestamp() if update.message.date else time.time()
                    if (time.time() - msg_time) < 60:
                        pending_count = db_manager.get_pending_telegram_queue_count()
                        await update.message.reply_text(
                            f"⏸️ *Image Queued (Queue Access is OFF)*\n"
                            f"• Queue Position: #{pending_count}\n\n"
                            f"Switch ON *Message Queue Access* in ATLAS to process queued commands.",
                            parse_mode="Markdown"
                        )

            # Register handlers
            app.add_handler(CommandHandler("start", handle_start))
            app.add_handler(CommandHandler("help", handle_help))
            app.add_handler(CommandHandler("status", handle_status))
            app.add_handler(CommandHandler("clear", handle_clear))
            app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
            app.add_handler(MessageHandler(filters.PHOTO | (filters.Document.IMAGE & ~filters.COMMAND), handle_photo))

            # Initialize and start polling asynchronously with drop_pending_updates=False
            await app.initialize()
            await app.start()
            await app.updater.start_polling(
                drop_pending_updates=False,
                poll_interval=2.0,
                timeout=20,
                bootstrap_retries=-1
            )

            self.bot_app = app
            self.is_running = True

            # Start queue worker
            if not self._queue_worker_task or self._queue_worker_task.done():
                self._queue_worker_task = asyncio.create_task(self._queue_worker_loop())

            if self.is_queue_access_enabled():
                self.notify_queue()

            print("[Telegram] Asynchronous Telegram Bot bridge active and polling (Queue Pacing: Active).")
            return True

        except Exception as e:
            print(f"[Telegram Connection Attempt Error]: {e}")
            await self._stop_internal()
            return False

    async def start(self, token: str, allowed_chat_id: Optional[str] = None):
        """Starts the connection supervisor to guarantee connectivity on boot-up and continuously."""
        async with self._start_lock:
            token = token.strip()
            if not token:
                print("[Telegram] Token is empty; bridge not started.")
                return

            self.token = token
            self.allowed_chat_id = allowed_chat_id
            self.should_run = True

            # Cancel existing supervisor if running
            if self._supervisor_task and not self._supervisor_task.done():
                self._supervisor_task.cancel()
                try:
                    await self._supervisor_task
                except asyncio.CancelledError:
                    pass

            # Launch the self-healing connection supervisor
            self._supervisor_task = asyncio.create_task(self._connection_supervisor())

    async def _stop_internal(self):
        if self._queue_worker_task and not self._queue_worker_task.done():
            try:
                self._queue_worker_task.cancel()
            except Exception:
                pass
            self._queue_worker_task = None

        if self.bot_app and self.is_running:
            try:
                print("[Telegram] Stopping Telegram polling bridge...")
                if self.bot_app.updater and getattr(self.bot_app.updater, "running", False):
                    await self.bot_app.updater.stop()
                if getattr(self.bot_app, "running", False):
                    await self.bot_app.stop()
                await self.bot_app.shutdown()
                print("[Telegram] Telegram bridge stopped cleanly.")
            except Exception as e:
                print(f"[Telegram] Shutdown note: {e}")
            finally:
                self.bot_app = None
                self.is_running = False

    async def stop(self):
        """Stops the supervisor and the Telegram bridge."""
        async with self._start_lock:
            self.should_run = False
            if self._supervisor_task and not self._supervisor_task.done():
                self._supervisor_task.cancel()
                try:
                    await self._supervisor_task
                except asyncio.CancelledError:
                    pass
                self._supervisor_task = None
            await self._stop_internal()

telegram_bridge = TelegramBridge()
