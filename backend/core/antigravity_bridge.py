import time
import os
import io
import json
import ctypes
import subprocess
from pathlib import Path
from typing import Tuple, Optional
import psutil

try:
    import win32clipboard
    from PIL import Image
    CLIPBOARD_IMAGE_AVAILABLE = True
except ImportError:
    CLIPBOARD_IMAGE_AVAILABLE = False


def copy_image_to_clipboard(image_path: str) -> bool:
    """Copies an image to the Windows clipboard in CF_DIB format."""
    if not CLIPBOARD_IMAGE_AVAILABLE or not os.path.exists(image_path):
        return False
    try:
        image = Image.open(image_path)
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # Strip 14-byte BMP header for DIB
        output.close()

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            return True
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        print(f"[Antigravity Bridge] Error copying image to clipboard: {e}")
        return False


class AntigravityBridge:
    """Controls Antigravity communication: delivers prompts and images in the background without stealing focus."""

    def __init__(self):
        self.brain_dir = Path.home() / ".gemini" / "antigravity" / "brain"
        self.agentapi_path = Path.home() / ".gemini" / "antigravity" / "bin" / "agentapi.bat"
        local_app = os.environ.get("LOCALAPPDATA", "")
        self.ls_exe = Path(local_app) / "Programs" / "Antigravity" / "resources" / "bin" / "language_server.exe"

    def get_latest_conversation_id(self) -> Optional[str]:
        """Discovers the active conversation ID from the most recently modified transcript."""
        if not self.brain_dir.exists():
            return None
        try:
            transcripts = list(self.brain_dir.glob("*/.system_generated/logs/transcript.jsonl"))
            if not transcripts:
                return None
            latest = max(transcripts, key=lambda p: p.stat().st_mtime)
            # path is brain/<conv_id>/.system_generated/logs/transcript.jsonl
            # parent: logs, parent.parent: .system_generated, parent.parent.parent: <conv_id>
            return latest.parent.parent.parent.name
        except Exception as e:
            print(f"[Antigravity Bridge] Error finding conversation ID: {e}")
            return None

    def send_via_agentapi(self, prompt_text: str, force_send_now: bool = False, image_path: Optional[str] = None) -> Tuple[bool, str]:
        """Dispatches prompt directly into Antigravity conversation silently in the background."""
        conv_id = self.get_latest_conversation_id()
        if not conv_id:
            return False, "Could not determine active Antigravity conversation."

        # Format prompt with image attachment reference if provided
        final_prompt = prompt_text
        if image_path and os.path.exists(image_path):
            norm_path = os.path.abspath(image_path).replace("\\", "/")
            img_header = f"[Attached Image: file:///{norm_path}]\nLocal Path: {norm_path}\n"
            if final_prompt:
                final_prompt = f"{img_header}\n{final_prompt}"
            else:
                final_prompt = f"{img_header}\nPlease inspect and analyze the attached image, Boss."

        title = "SEND_NOW_ATLAS_COMMAND" if force_send_now else "ATLAS_COMMAND"

        if self.ls_exe.exists():
            exec_args = [str(self.ls_exe), "agentapi", "send-message", f"--title={title}", conv_id, final_prompt]
        elif self.agentapi_path.exists():
            exec_args = [str(self.agentapi_path), "send-message", f"--title={title}", conv_id, final_prompt]
        else:
            return False, "Neither language_server.exe nor agentapi.bat found"

        try:
            env = os.environ.copy()
            cache_file = Path(__file__).resolve().parent.parent.parent / "data" / "antigravity_env.json"
            if cache_file.exists():
                try:
                    cached = json.loads(cache_file.read_text(encoding="utf-8"))
                    for k, v in cached.items():
                        if v:
                            env[k] = str(v)
                except Exception:
                    pass

            # Dynamic auto-discovery: inspect running language_server.exe for live port and csrf_token
            for p in psutil.process_iter(['name', 'pid', 'cmdline']):
                try:
                    pname = p.info.get('name') or ''
                    if 'language_server' in pname.lower():
                        cmdline = " ".join(p.info.get('cmdline') or [])
                        import re
                        token_match = re.search(r'--csrf_token\s+([a-f0-9\-]+)', cmdline)
                        if token_match:
                            env['ANTIGRAVITY_CSRF_TOKEN'] = token_match.group(1)
                        for conn in p.net_connections(kind='inet'):
                            if conn.status == 'LISTEN':
                                env['ANTIGRAVITY_LS_ADDRESS'] = f"localhost:{conn.laddr.port}"
                                break
                        break
                except Exception:
                    pass

            # Run completely in the background without opening any command window
            CREATE_NO_WINDOW = 0x08000000
            res = subprocess.run(
                exec_args,
                capture_output=True,
                text=True,
                env=env,
                creationflags=CREATE_NO_WINDOW,
                timeout=10
            )

            if res.returncode == 0:
                print(f"[Antigravity Bridge] Background dispatch to conversation {conv_id} successful (force={force_send_now}).")
                prefix = "Force dispatched in Send Now mode: " if force_send_now else ""
                return True, f"{prefix}Prompt redirected in background to Antigravity."
            else:
                err_msg = res.stderr.strip() or res.stdout.strip()
                print(f"[Antigravity Bridge] agentapi error: {err_msg}")
                return False, f"agentapi error: {err_msg}"
        except Exception as e:
            print(f"[Antigravity Bridge] Failed agentapi execution: {e}")
            return False, str(e)

    @staticmethod
    def _attach_to_desktop():
        """Ensure calling thread has access to interactive desktop winsta0\\default."""
        try:
            u32 = ctypes.windll.user32
            hw = u32.OpenWindowStationW('winsta0', False, 0x10000000)
            if hw:
                u32.SetProcessWindowStation(hw)
                hd = u32.OpenDesktopW('default', 0, False, 0x10000000)
                if hd:
                    u32.SetThreadDesktop(hd)
        except Exception:
            pass

    @classmethod
    def find_antigravity_window(cls) -> Optional[int]:
        """Finds the main visible window handle for Antigravity."""
        cls._attach_to_desktop()
        u32 = ctypes.windll.user32

        pids = set()
        for p in psutil.process_iter(['name', 'pid']):
            try:
                name = p.info.get('name')
                if name and 'antigravity' in name.lower():
                    pids.add(p.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if not pids:
            return None

        found_hwnd = None
        def enum_cb(h, _):
            nonlocal found_hwnd
            try:
                if u32.IsWindowVisible(h):
                    pid = ctypes.c_ulong()
                    u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                    if pid.value in pids and u32.GetWindowTextLengthW(h) > 0:
                        found_hwnd = h
                        return False
            except Exception:
                pass
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        try:
            u32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        except Exception:
            pass

        return found_hwnd

    def send_via_ui_fallback(self, prompt_text: str, force_send_now: bool = False, image_path: Optional[str] = None) -> Tuple[bool, str]:
        """Fallback typing/pasting into UI while immediately restoring previous window focus."""
        import pyautogui
        import pyperclip

        hwnd = self.find_antigravity_window()
        if not hwnd:
            return False, "Could not locate active Antigravity window."

        u32 = ctypes.windll.user32
        prev_hwnd = u32.GetForegroundWindow()

        try:
            u32.ShowWindow(hwnd, 9)
            time.sleep(0.04)
            u32.SetForegroundWindow(hwnd)
            time.sleep(0.08)

            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.08)

            # Paste image from clipboard if available
            if image_path and os.path.exists(image_path):
                copied = copy_image_to_clipboard(image_path)
                if copied:
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.12)

            final_text = prompt_text
            if image_path and os.path.exists(image_path) and not final_text:
                final_text = f"Analyze attached image: {os.path.abspath(image_path)}"

            if final_text:
                pyperclip.copy(final_text)
                time.sleep(0.04)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.06)

            # In Antigravity/VS Code, Alt+Enter forces "Send Now" without queuing
            if force_send_now:
                try:
                    import keyboard
                    keyboard.send('alt+enter')
                except Exception:
                    pyautogui.hotkey('alt', 'enter')
                time.sleep(0.04)
                pyautogui.press('enter')
            else:
                pyautogui.press('enter')

            # Immediately restore previous focus to avoid interrupting user workflow
            if prev_hwnd and prev_hwnd != hwnd:
                time.sleep(0.05)
                u32.SetForegroundWindow(prev_hwnd)

            prefix = "Force dispatched in Send Now mode: " if force_send_now else ""
            return True, f"{prefix}Prompt redirected."
        except Exception as e:
            if prev_hwnd and prev_hwnd != hwnd:
                try:
                    u32.SetForegroundWindow(prev_hwnd)
                except Exception:
                    pass
            return False, f"Failed to type prompt into Antigravity: {str(e)}"

    def send_prompt(self, prompt_text: str, force_send_now: bool = False, image_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        Main entry point for dispatching prompts and images to Antigravity.
        Supports:
          - Regular prompts
          - Force Send Now mode (bypasses task queue)
          - Image attachments
        Prioritizes silent background dispatch (0 window popups, 0 focus changes).
        Falls back to UI injection with immediate focus restoration.
        """
        clean_prompt = prompt_text.strip()
        if not clean_prompt and not image_path:
            return False, "Prompt is empty."

        # 1. Primary method: Background direct API dispatch (zero focus interruption)
        success, msg = self.send_via_agentapi(clean_prompt, force_send_now=force_send_now, image_path=image_path)
        if success:
            return True, msg

        # 2. Secondary fallback: UI injection with focus restoration
        return self.send_via_ui_fallback(clean_prompt, force_send_now=force_send_now, image_path=image_path)

    def send_image(self, image_path: str, caption: str = "", force_send_now: bool = False) -> Tuple[bool, str]:
        """Dispatches an image attachment and caption to Antigravity."""
        return self.send_prompt(caption, force_send_now=force_send_now, image_path=image_path)

antigravity_bridge = AntigravityBridge()
