"""
Real-time Antigravity Transcript Watcher for ATLAS 2.0.
Hybrid watcher utilizing Windows kernel events and low-overhead periodic polling
to detect sub-second agent generation completions and notify the user immediately.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional, Callable, Awaitable

import watchfiles


class AntigravityWatcher:
    """Real-time transcript watcher that monitors Antigravity agent execution and completions."""

    def __init__(self, on_completion_callback: Optional[Callable[[str], Awaitable[None]]] = None):
        self.brain_dir = Path.home() / ".gemini" / "antigravity" / "brain"
        self.on_completion_callback = on_completion_callback
        self.running = False
        self._watch_task: Optional[asyncio.Task] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._current_file: Optional[Path] = None
        self._last_file_pos = 0
        self._is_generating = False
        self._last_notified_step = -1
        self._lock = asyncio.Lock()

    def find_latest_transcript(self) -> Optional[Path]:
        """Discovers the most recently modified transcript.jsonl across all brain session directories."""
        if not self.brain_dir.exists():
            return None
        try:
            transcripts = list(self.brain_dir.glob("*/.system_generated/logs/transcript.jsonl"))
            if not transcripts:
                return None
            return max(transcripts, key=lambda p: p.stat().st_mtime)
        except Exception as e:
            print(f"[Antigravity Watcher] Discovery error: {e}")
            return None

    def _init_file_tracking(self, file_path: Path):
        """Initializes tracking pointers at the end of the current transcript file."""
        self._current_file = file_path
        self._last_notified_step = -1
        try:
            self._last_file_pos = file_path.stat().st_size
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                for l in reversed(lines[-30:]):
                    try:
                        d = json.loads(l)
                        if "step_index" in d and d["step_index"] is not None:
                            self._last_notified_step = max(self._last_notified_step, int(d["step_index"]))
                    except Exception:
                        pass
        except Exception:
            self._last_file_pos = 0
            self._last_notified_step = -1

    async def start(self):
        """Starts both kernel watcher and polling tasks."""
        if self.running:
            return
        self.running = True

        latest_file = self.find_latest_transcript()
        if latest_file and latest_file.exists():
            self._init_file_tracking(latest_file)

        self._watch_task = asyncio.create_task(self._watch_loop())
        self._poll_task = asyncio.create_task(self._poll_loop())
        print("[Antigravity Watcher] Real-time Hybrid Transcript Watcher active.")

    async def stop(self):
        """Stops the watcher tasks gracefully."""
        self.running = False
        for task in (self._watch_task, self._poll_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._watch_task = None
        self._poll_task = None

    async def _poll_loop(self):
        """Fallback polling loop to guarantee updates even if Windows file events are delayed."""
        while self.running:
            try:
                await asyncio.sleep(0.5)
                latest_file = self.find_latest_transcript()
                if latest_file and latest_file.exists():
                    if self._current_file != latest_file:
                        self._init_file_tracking(latest_file)
                    await self._process_transcript_updates(latest_file)
            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(1.0)

    async def _watch_loop(self):
        """Kernel event watch loop."""
        while self.running:
            try:
                latest_file = self.find_latest_transcript()
                if not latest_file or not latest_file.exists():
                    await asyncio.sleep(1.0)
                    continue

                if self._current_file != latest_file:
                    self._init_file_tracking(latest_file)

                watch_dir = latest_file.parent

                async for changes in watchfiles.awatch(watch_dir):
                    if not self.running:
                        break

                    for _, path_str in changes:
                        if path_str.endswith("transcript.jsonl"):
                            await self._process_transcript_updates(Path(path_str))

                    new_latest = self.find_latest_transcript()
                    if new_latest and new_latest.parent != watch_dir:
                        self._init_file_tracking(new_latest)
                        break
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1.0)

    async def _process_transcript_updates(self, file_path: Path):
        async with self._lock:
            try:
                if not file_path.exists():
                    return

                current_size = file_path.stat().st_size
                if current_size < self._last_file_pos:
                    self._last_file_pos = 0

                if current_size == self._last_file_pos:
                    return

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(self._last_file_pos)
                    new_data = f.read()
                    self._last_file_pos = f.tell()

                for line in new_data.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        await self._handle_transcript_entry(entry)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[Antigravity Watcher Error] {e}")

    def _fetch_full_content(self, step_index: int) -> Optional[str]:
        """Fetches untruncated content from transcript_full.jsonl for the given step index."""
        if not self._current_file:
            return None
        full_file = self._current_file.parent / "transcript_full.jsonl"
        if not full_file.exists():
            return None
        try:
            with open(full_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in reversed(f.readlines()[-30:]):
                    try:
                        d = json.loads(line)
                        if d.get("step_index") == step_index and d.get("content"):
                            return d.get("content")
                    except Exception:
                        pass
        except Exception as e:
            print(f"[Antigravity Watcher] Error reading transcript_full: {e}")
        return None

    async def _handle_transcript_entry(self, entry: dict):
        src = entry.get("source")
        etype = entry.get("type")
        step_index = entry.get("step_index", -1)
        tool_calls = entry.get("tool_calls")
        content = entry.get("content")
        truncated = entry.get("truncated_fields", [])

        # 1. Detect start of user request or intermediate tool reasoning
        if src in ("USER_EXPLICIT", "USER_INPUT") or (src == "MODEL" and tool_calls):
            self._is_generating = True

        # 2. Detect completion: Final model response delivered with no active tool calls
        if (
            src == "MODEL"
            and etype == "PLANNER_RESPONSE"
            and entry.get("status") == "DONE"
            and not tool_calls
            and (content or "content" in truncated)
            and step_index > self._last_notified_step
        ):
            self._is_generating = False
            self._last_notified_step = step_index

            full_content = content or ""
            if (not full_content or "content" in truncated) and step_index >= 0:
                full_untruncated = self._fetch_full_content(step_index)
                if full_untruncated:
                    full_content = full_untruncated

            preview = ""
            if full_content:
                preview = full_content.strip().split("\n")[0][:120]
            else:
                preview = "Agent task finished successfully."

            print(f"[Antigravity Watcher] Generation completed (Step {step_index}): {preview}")
            if self.on_completion_callback:
                try:
                    await self.on_completion_callback(full_content, preview, step_index)
                except Exception as e:
                    print(f"Error in completion callback: {e}")


antigravity_watcher = AntigravityWatcher()
