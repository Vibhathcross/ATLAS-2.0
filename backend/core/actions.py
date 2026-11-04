"""
System Actions & Automation Engine for ATLAS 2.0.
Provides high-performance, non-blocking execution of OS automation,
application launching, window management, and Antigravity relaying.
"""

import os
import re
import time
import ctypes
import winreg
import webbrowser
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

import psutil
import pyautogui

# ============================================================================
# CONSTANTS & CONFIGURATION MAPS
# ============================================================================

# Common web destinations mapped to verified HTTPS endpoints
WEB_SITES: Dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://www.github.com",
    "chatgpt": "https://chatgpt.com",
    "openai": "https://chatgpt.com",
    "gmail": "https://mail.google.com",
    "whatsapp": "https://web.whatsapp.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "linkedin": "https://www.linkedin.com",
    "netflix": "https://www.netflix.com",
    "instagram": "https://www.instagram.com",
    "amazon": "https://www.amazon.com",
    "wikipedia": "https://www.wikipedia.org",
    "facebook": "https://www.facebook.com",
}

# Windows URI protocol handlers for zero-latency WinRT application launching
URI_PROTOCOLS: Dict[str, str] = {
    "settings": "ms-settings:",
    "windows settings": "ms-settings:",
    "calculator": "calculator:",
    "calc": "calculator:",
    "spotify": "spotify:",
    "camera": "microsoft.windows.camera:",
    "photos": "ms-photos:",
    "store": "ms-windows-store:",
    "windows store": "ms-windows-store:",
    "mail": "mailto:",
    "email": "mailto:",
    "maps": "bingmaps:",
    "terminal": "wt:",
    "windows terminal": "wt:",
}

# Common application aliases mapped to target executable basenames
APP_ALIASES: Dict[str, str] = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "browser": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "code": "code",
    "vs code": "code",
    "visual studio code": "code",
    "vscode": "code",
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "cmd": "cmd",
    "command prompt": "cmd",
    "terminal": "wt",
    "windows terminal": "wt",
    "powershell": "powershell",
    "spotify": "spotify",
    "file explorer": "explorer",
    "files": "explorer",
    "explorer": "explorer",
    "task manager": "taskmgr",
    "paint": "mspaint",
    "word": "winword",
    "microsoft word": "winword",
    "excel": "excel",
    "microsoft excel": "excel",
    "powerpoint": "powerpnt",
    "discord": "discord",
    "slack": "slack",
    "steam": "steam",
}

# Target process names for clean application termination
PROCESS_MAP: Dict[str, List[str]] = {
    "chrome": ["chrome.exe"],
    "google chrome": ["chrome.exe"],
    "browser": ["chrome.exe", "msedge.exe"],
    "edge": ["msedge.exe"],
    "microsoft edge": ["msedge.exe"],
    "code": ["code.exe"],
    "vs code": ["code.exe"],
    "visual studio code": ["code.exe"],
    "notepad": ["notepad.exe"],
    "calculator": ["CalculatorApp.exe", "calc.exe"],
    "calc": ["CalculatorApp.exe", "calc.exe"],
    "spotify": ["Spotify.exe"],
    "paint": ["mspaint.exe"],
    "terminal": ["WindowsTerminal.exe", "wt.exe"],
    "cmd": ["cmd.exe"],
    "command prompt": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "word": ["WINWORD.EXE"],
    "excel": ["EXCEL.EXE"],
    "task manager": ["Taskmgr.exe"],
}

# Direct keywords for single-word execution in awake mode
DIRECT_KEYWORDS: Dict[str, str] = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "browser": "chrome",
    "edge": "edge",
    "microsoft edge": "edge",
    "notepad": "notepad",
    "calculator": "calculator",
    "calc": "calculator",
    "youtube": "youtube",
    "github": "github",
    "chatgpt": "chatgpt",
    "gmail": "gmail",
    "whatsapp": "whatsapp",
    "spotify": "spotify",
    "settings": "settings",
    "file explorer": "file explorer",
    "task manager": "task manager",
    "paint": "paint",
    "vs code": "vs code",
    "code": "code",
    "terminal": "terminal",
    "cmd": "cmd",
}

# Pre-compiled regular expressions for sub-millisecond pattern matching
RE_PREFIX_FILLER = re.compile(r"^(?:please\s+|can you\s+|open\s+up\s+|start\s+up\s+)", re.IGNORECASE)
RE_SUFFIX_FILLER = re.compile(r"\s+(?:please|for me|now|app|application|website|site|tab|page)$", re.IGNORECASE)
RE_CLOSE_PREFIX_FILLER = re.compile(r"^(?:please\s+|can you\s+|close\s+down\s+|shut\s+down\s+)", re.IGNORECASE)

RE_DICTATE = re.compile(r"^(?:dictate to agent|tell agent|send to antigravity|ask antigravity|prompt agent|type in antigravity)\s+(.+)$", re.IGNORECASE)
RE_LOCK_SHUTDOWN = re.compile(r"\b(?:lock(?:\s+(?:the\s+)?(?:screen|computer|workstation|pc))?\s+and\s+(?:shut\s*down|power\s*off)|(?:shut\s*down|power\s*off)\s+and\s+lock(?:\s+(?:the\s+)?(?:screen|computer|workstation|pc))?)\b", re.IGNORECASE)
RE_LOCK = re.compile(r"\b(?:lock(?:\s+(?:the\s+)?(?:screen|computer|workstation|pc|display))?|lock\s*down)\b", re.IGNORECASE)
RE_SHUTDOWN = re.compile(r"\b(?:shut\s*down(?:\s+(?:the\s+)?(?:system|computer|pc))?|power\s*off)\b", re.IGNORECASE)
RE_CANCEL_SHUTDOWN = re.compile(r"\b(?:cancel shut ?down|abort shut ?down)\b", re.IGNORECASE)
RE_RESTART = re.compile(r"\b(?:restart|reboot)(?:\s+(?:the\s+)?(?:system|computer|pc))?\b", re.IGNORECASE)
RE_SLEEP = re.compile(r"\b(?:sleep computer|go to sleep|put pc to sleep)\b", re.IGNORECASE)
RE_STOP = re.compile(r"^\b(?:stop|be quiet|shut up|cancel|hush|silence)\b$", re.IGNORECASE)
RE_CLEAR_DESKTOP = re.compile(r"\b(?:clear all apps|close all apps|clear screen|minimize all|hide windows)\b", re.IGNORECASE)
RE_SHOW_DESKTOP = re.compile(r"\b(?:show desktop|minimize windows)\b", re.IGNORECASE)
RE_VOL_UP = re.compile(r"\b(?:volume up|increase volume|louder)\b", re.IGNORECASE)
RE_VOL_DOWN = re.compile(r"\b(?:volume down|decrease volume|lower volume|quieter)\b", re.IGNORECASE)
RE_VOL_MUTE = re.compile(r"\b(?:mute|unmute)\b", re.IGNORECASE)
RE_SYS_STATUS = re.compile(r"\b(?:system status|system health|cpu usage|ram usage|battery status)\b", re.IGNORECASE)
RE_FULLSCREEN = re.compile(r"\b(?:full\s*screen|enter full\s*screen|exit full\s*screen|maximize window|toggle full\s*screen)\b", re.IGNORECASE)
RE_AUTOKEYBOARD = re.compile(r"^(?:autokeyboard|press\s+keys?|press|hit|hotkey|click\s+keys?|click|tap|strike)\s+(.+)$", re.IGNORECASE)
RE_RAW_HOTKEY = re.compile(r"^(?:(?:ctrl|control|alt|alternate|shift|win|windows|cmd|super)\s*[\+\-\s]\s*)+[a-zA-Z0-9_\-\+]+$", re.IGNORECASE)
RE_STANDALONE_KEY = re.compile(r"^(?:f[1-9]|f1[0-2]|enter|return|esc|escape|tab|space|spacebar|backspace|delete|del|insert|ins|home|end|pageup|pgup|pagedown|pgdn|up|down|left|right|capslock|numlock|scrolllock|printscreen|prtsc|prtscr|alt|ctrl|shift|win|windows)$", re.IGNORECASE)
RE_TYPE_TEXT = re.compile(r"^(?:type|autotype|write|keyboard\s+type)\s+(.+)$", re.IGNORECASE)
RE_SELF_REFRESH = re.compile(r"^\b(?:self\s*refresh|restart\s+atlas|reload\s+atlas|refresh\s+atlas)\b$", re.IGNORECASE)
RE_TOGGLE_ANTI = re.compile(
    r"^(?:(?:#|hash\s+|hashtag\s+)?anti(?:gravity)?(?:\s+mode)?|"
    r"(?:toggle|switch|turn\s+(?:on|off)|enable|disable)\s+anti(?:gravity)?(?:\s+mode)?)$",
    re.IGNORECASE
)
RE_OPEN = re.compile(r"^(?:can you\s+)?(?:please\s+)?(?:open|launch|start|run|go to)\s+(?:up\s+)?([a-zA-Z0-9_\-\. ]+?)(?:\s+(?:please|for me|now|app|website|page|tab))*$", re.IGNORECASE)
RE_CLOSE = re.compile(r"^(?:can you\s+)?(?:please\s+)?(?:close|exit|terminate|kill|shut down)\s+(?:up\s+)?([a-zA-Z0-9_\-\. ]+?)(?:\s+(?:please|for me|now|app))*$", re.IGNORECASE)

# Fast in-memory cache for resolved Windows App Paths
_APP_PATH_CACHE: Dict[str, Optional[str]] = {}


# ============================================================================
# SYSTEM ACTIONS CLASS
# ============================================================================

class SystemActions:
    """Windows system and desktop automation capabilities."""

    @staticmethod
    def find_windows_app_path(app_name: str) -> Optional[str]:
        """Look up Windows Registry App Paths for registered executables with caching."""
        clean = app_name.strip().lower()
        if clean in _APP_PATH_CACHE:
            return _APP_PATH_CACHE[clean]

        targets = [clean]
        if not clean.endswith(".exe"):
            targets.append(f"{clean}.exe")

        for name in targets:
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(root, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}") as key:
                        path = winreg.QueryValue(key, None)
                        if path and os.path.exists(path):
                            _APP_PATH_CACHE[clean] = path
                            return path
                except Exception:
                    pass

        _APP_PATH_CACHE[clean] = None
        return None

    @staticmethod
    def shutdown(seconds: int = 5) -> str:
        subprocess.run(["shutdown", "/s", "/t", str(seconds)], check=False)
        return f"Shutting down the system in {seconds} seconds."

    @staticmethod
    def cancel_shutdown() -> str:
        subprocess.run(["shutdown", "/a"], check=False)
        return "System shutdown has been cancelled."

    @staticmethod
    def restart(seconds: int = 5) -> str:
        subprocess.run(["shutdown", "/r", "/t", str(seconds)], check=False)
        return f"Restarting the computer in {seconds} seconds."

    @staticmethod
    def lock_workstation() -> str:
        ctypes.windll.user32.LockWorkStation()
        return "Workstation locked."

    @staticmethod
    def sleep() -> str:
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=False)
        return "Putting system to sleep."

    @staticmethod
    def minimize_all() -> str:
        pyautogui.hotkey('win', 'd')
        return "Minimized all active windows."

    @staticmethod
    def clear_all_apps() -> str:
        """Minimizes windows and cleans desktop space."""
        pyautogui.hotkey('win', 'd')
        return "Desktop cleared and all background application windows minimized."

    @classmethod
    def open_app(cls, app_name: str) -> str:
        """Launches desktop applications, protocol schemes, or websites with zero-flicker execution."""
        clean = app_name.strip().lower()
        clean = RE_PREFIX_FILLER.sub("", clean)
        clean = RE_SUFFIX_FILLER.sub("", clean).strip()

        # 1. Direct Web URLs
        if clean in WEB_SITES:
            url = WEB_SITES[clean]
            try:
                os.startfile(url)
                return f"Opening {clean.capitalize()}."
            except Exception:
                webbrowser.open(url)
                return f"Opening {clean.capitalize()}."

        # 2. Windows URI Protocols (Calculator, Settings, Spotify, etc.)
        if clean in URI_PROTOCOLS:
            try:
                os.startfile(URI_PROTOCOLS[clean])
                return f"Launching {app_name.capitalize()}."
            except Exception:
                pass

        # 3. Known Application Aliases
        target_name = APP_ALIASES.get(clean, clean)

        # 4. Windows App Paths Registry
        reg_path = cls.find_windows_app_path(target_name)
        if reg_path:
            try:
                os.startfile(reg_path)
                return f"Launching {app_name}."
            except Exception:
                pass

        # 5. Common System Executables
        system_paths = [
            f"C:\\Windows\\System32\\{target_name}.exe",
            f"C:\\Windows\\{target_name}.exe",
            f"C:\\Program Files\\Google\\Chrome\\Application\\{target_name}.exe",
            f"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\{target_name}.exe",
        ]
        for sp in system_paths:
            if os.path.exists(sp):
                try:
                    os.startfile(sp)
                    return f"Launching {app_name}."
                except Exception:
                    pass

        # 6. Direct Win32 ShellExecute
        try:
            os.startfile(target_name)
            return f"Launching {app_name}."
        except Exception:
            pass

        # 7. Subprocess fallback with hidden window flags
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.Popen([target_name], shell=True, startupinfo=startupinfo)
            return f"Launching {app_name}."
        except Exception:
            return f"Could not launch {app_name}. Please verify the application is installed."

    @staticmethod
    def close_app(app_name: str) -> str:
        """Terminates running instances of an application cleanly via psutil."""
        clean = app_name.strip().lower()
        clean = RE_CLOSE_PREFIX_FILLER.sub("", clean)
        clean = RE_SUFFIX_FILLER.sub("", clean).strip()

        targets = [p.lower() for p in PROCESS_MAP.get(clean, [f"{clean}.exe"])]
        killed = 0
        for proc in psutil.process_iter(['name']):
            try:
                pname = proc.info.get('name')
                if pname and pname.lower() in targets:
                    proc.terminate()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if killed > 0:
            return f"Closed {app_name}."
        return f"No active window or process found for {app_name}."

    @staticmethod
    def volume_up(presses: int = 5) -> str:
        for _ in range(presses):
            pyautogui.press('volumeup')
        return "Volume increased."

    @staticmethod
    def volume_down(presses: int = 5) -> str:
        for _ in range(presses):
            pyautogui.press('volumedown')
        return "Volume decreased."

    @staticmethod
    def volume_mute() -> str:
        pyautogui.press('volumemute')
        return "Volume muted/unmuted."

    @staticmethod
    def get_system_status() -> Dict[str, Any]:
        """Collects live performance telemetry from system sensors."""
        cpu_pct = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        battery = psutil.sensors_battery()

        return {
            "cpu_percent": cpu_pct,
            "ram_used_gb": round(ram.used / (1024**3), 2),
            "ram_total_gb": round(ram.total / (1024**3), 2),
            "ram_percent": ram.percent,
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "battery_percent": battery.percent if battery else None,
            "power_plugged": battery.power_plugged if battery else None
        }

    @staticmethod
    def press_keys(keys_expr: str) -> Tuple[bool, str]:
        """
        Presses any key or simultaneous combination of keys (up to 10 keys).
        Supports:
          - Single key presses (e.g. 'enter', 'esc', 'space', 'f5', 'a', 'tab')
          - Simultaneous combinations (e.g. 'ctrl+shift+esc', 'win+d', 'alt+f4', 'ctrl+c')
        Uses the high-performance 'keyboard' engine with ctypes Windows keybd_event & PyAutoGUI fallback.
        """
        raw_parts = [p.strip().lower() for p in re.split(r"[\s,+]|\band\b|\bplus\b", keys_expr) if p.strip()]
        if not raw_parts:
            return False, "No keys specified to press."

        if len(raw_parts) > 10:
            return False, "AutoKeyboard limit exceeded: at most 10 keys can be pressed together."

        KEY_NORM_MAP = {
            "win": "win", "windows": "win", "super": "win", "cmd": "win", "meta": "win", "winleft": "win",
            "ctrl": "ctrl", "control": "ctrl",
            "alt": "alt", "alternate": "alt", "option": "alt",
            "shift": "shift",
            "esc": "esc", "escape": "esc",
            "enter": "enter", "return": "enter",
            "space": "space", "spacebar": "space",
            "tab": "tab",
            "backspace": "backspace", "bksp": "backspace",
            "delete": "delete", "del": "delete",
            "insert": "insert", "ins": "insert",
            "home": "home", "end": "end",
            "pageup": "pageup", "pgup": "pageup",
            "pagedown": "pagedown", "pgdn": "pagedown",
            "up": "up", "down": "down", "left": "left", "right": "right",
            "capslock": "capslock", "caps": "capslock",
            "numlock": "numlock",
            "scrolllock": "scrolllock",
            "printscreen": "printscreen", "prtscr": "printscreen", "prtsc": "printscreen",
            "volumeup": "volume up", "volumedown": "volume down", "volumemute": "volume mute",
        }

        # VK Map for ctypes Windows native fallback
        VK_MAP = {
            "win": 0x5B, "ctrl": 0x11, "alt": 0x12, "shift": 0x10,
            "esc": 0x1B, "enter": 0x0D, "space": 0x20, "tab": 0x09,
            "backspace": 0x08, "delete": 0x2E, "insert": 0x2D,
            "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
            "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
            "capslock": 0x14, "numlock": 0x90, "scrolllock": 0x91,
            "printscreen": 0x2C, "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
            "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
            "f11": 0x7A, "f12": 0x7B
        }

        normalized_keys = [KEY_NORM_MAP.get(p, p) for p in raw_parts]
        keys_display = " + ".join(normalized_keys).upper()

        # Dedicated Windows Toggle Desktop hook
        if normalized_keys in (["win", "d"], ["windows", "d"]):
            try:
                import win32com.client
                win32com.client.Dispatch("Shell.Application").ToggleDesktop()
                return True, "AutoKeyboard: Pressed WIN + D (Toggled Desktop)."
            except Exception:
                pass

        # Dedicated Windows Close Active Window hook (Alt+F4)
        if normalized_keys in (["alt", "f4"], ["f4", "alt"]):
            try:
                # Post WM_CLOSE to active foreground window
                u32 = ctypes.windll.user32
                hwnd = u32.GetForegroundWindow()
                if hwnd:
                    u32.PostMessageW(hwnd, 0x0010, 0, 0) # WM_CLOSE
            except Exception:
                pass
            try:
                import keyboard
                keyboard.send("alt+f4")
            except Exception:
                pass
            return True, "AutoKeyboard: Pressed ALT + F4 (Closed active window)."

        # Engine 1: Native Windows Win32 keybd_event with hardware scan-codes & 50ms hold
        try:
            u32 = ctypes.windll.user32
            KEYEVENTF_KEYUP = 0x0002
            KEYEVENTF_EXTENDEDKEY = 0x0001
            EXTENDED_VKS = {0x5B, 0x5C, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x24, 0x23, 0x21, 0x22, 0x2C, 0x90, 0x5D}

            vk_items = []
            for k in normalized_keys:
                if k in VK_MAP:
                    vk = VK_MAP[k]
                elif len(k) == 1 and k.isalnum():
                    vk = ord(k.upper())
                else:
                    vk = None
                
                if vk is not None:
                    scan = u32.MapVirtualKeyW(vk, 0)
                    flags = KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else 0
                    vk_items.append((vk, scan, flags))

            if vk_items and len(vk_items) == len(normalized_keys):
                # 1. Key down in forward order
                for vk, scan, flags in vk_items:
                    u32.keybd_event(vk, scan, flags, 0)
                time.sleep(0.05)
                # 2. Key up in reverse order
                for vk, scan, flags in reversed(vk_items):
                    u32.keybd_event(vk, scan, flags | KEYEVENTF_KEYUP, 0)

                # Send auxiliary event via keyboard package to cover non-win32 listeners
                try:
                    import keyboard
                    keyboard.send("+".join(normalized_keys))
                except Exception:
                    pass

                return True, f"AutoKeyboard: Pressed {keys_display}."
        except Exception as win_err:
            print(f"[AutoKeyboard] Native win32 notice: {win_err}. Falling back to keyboard library...")

        # Engine 2: Dedicated Python 'keyboard' automation library
        try:
            import keyboard
            combo = "+".join(normalized_keys)
            keyboard.send(combo)
            return True, f"AutoKeyboard: Pressed {keys_display}."
        except Exception as kb_err:
            print(f"[AutoKeyboard] keyboard library notice: {kb_err}. Falling back to PyAutoGUI...")

        # Engine 3: PyAutoGUI fallback
        try:
            old_failsafe = pyautogui.FAILSAFE
            pyautogui.FAILSAFE = False
            pyautogui.hotkey(*normalized_keys)
            pyautogui.FAILSAFE = old_failsafe
            return True, f"AutoKeyboard: Pressed {keys_display}."
        except Exception as e:
            return False, f"AutoKeyboard error: {str(e)}"

    @classmethod
    def type_text(cls, text: str) -> Tuple[bool, str]:
        """Types text keystroke-by-keystroke using hardware keyboard emulation."""
        clean = text.strip()
        if not clean:
            return False, "No text provided to type."
        try:
            import keyboard
            keyboard.write(clean, delay=0.01)
            return True, f"AutoKeyboard: Typed '{clean}'."
        except Exception:
            try:
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.write(clean, interval=0.01)
                return True, f"AutoKeyboard: Typed '{clean}'."
            except Exception as e:
                return False, f"AutoKeyboard type error: {e}"

    @staticmethod
    def self_refresh() -> None:
        """Restarts the ATLAS 2.0 application in a detached process."""
        base_dir = Path(__file__).resolve().parent.parent.parent
        bat_script = base_dir / "run_atlas.bat"

        # Spawn detached PowerShell starter that waits 1.2s and launches ATLAS batch runner
        cmd = f'powershell -Command "Start-Sleep -Milliseconds 1200; Start-Process -FilePath \'{bat_script}\'"'
        subprocess.Popen(cmd, shell=True, creationflags=0x08000000)

        def delayed_exit():
            import time
            time.sleep(0.8)
            os._exit(0)
        import threading
        threading.Thread(target=delayed_exit, daemon=True).start()

    @staticmethod
    def toggle_antigravity_mode() -> Tuple[bool, str]:
        """Toggles Antigravity Mode state on/off in runtime config."""
        from backend.config import config_manager
        current = config_manager.get("antigravity_mode", False)
        new_state = not current
        config_manager.update("antigravity_mode", new_state)
        status_str = "activated" if new_state else "deactivated"
        detail = "Direct agent relay is now online." if new_state else "Native routing restored."
        return new_state, f"Antigravity mode {status_str}, Boss. {detail}"

    @classmethod
    def match_predefined_command(cls, text: str) -> Tuple[bool, str, Any, Any]:
        """
        Pattern matches common voice/text commands using pre-compiled regex.
        Returns: (is_matched, action_name, result_message, post_action)
        """
        cleaned = text.strip().lower()

        # Toggle Antigravity Mode Command: "#anti" / "#antigravity" / "toggle antigravity mode"
        if RE_TOGGLE_ANTI.match(cleaned):
            new_state, msg = cls.toggle_antigravity_mode()
            return True, "toggle_antigravity_mode", msg, "toggle_antigravity_mode"

        # Raw Hotkey shortcut: e.g. "alt+f4", "ctrl+shift+esc", "win+d", "ctrl+c"
        if RE_RAW_HOTKEY.match(cleaned):
            success, msg = cls.press_keys(cleaned)
            return True, "autokeyboard", msg, None

        # Standalone Key shortcut: e.g. "f5", "f11", "enter", "esc", "tab", "space", "alt"
        if RE_STANDALONE_KEY.match(cleaned):
            success, msg = cls.press_keys(cleaned)
            return True, "autokeyboard", msg, None

        # AutoKeyboard Command: "autokeyboard <keys>" or "press keys <keys>" or "hotkey <keys>"
        auto_match = RE_AUTOKEYBOARD.search(cleaned)
        if auto_match:
            keys_expr = auto_match.group(1).strip()
            success, msg = cls.press_keys(keys_expr)
            return True, "autokeyboard", msg, None

        # Type Text Command: "type <text>" or "autotype <text>" or "write <text>"
        type_match = RE_TYPE_TEXT.match(cleaned)
        if type_match:
            text_to_type = type_match.group(1).strip()
            success, msg = cls.type_text(text_to_type)
            return True, "autotype", msg, None

        # SelfRefresh Command: "selfrefresh" / "restart atlas" / "reload atlas"
        if RE_SELF_REFRESH.search(cleaned):
            return True, "self_refresh", "Restarting ATLAS 2.0 with all updated features. Standing by, Boss.", "self_refresh"

        # 1. Antigravity Agent Dictation
        dictate_match = RE_DICTATE.search(cleaned)
        if dictate_match:
            prompt_text = dictate_match.group(1).strip()
            from backend.core.antigravity_bridge import antigravity_bridge
            relayed, msg = antigravity_bridge.send_prompt(prompt_text)
            return True, "antigravity_relay", msg, None

        # 2. Combined Lock and Shutdown (executed strictly after TTS playback completes)
        if RE_LOCK_SHUTDOWN.search(cleaned):
            return True, "lock_and_shutdown", "Locking the workstation and shutting down the system. Goodbye, Boss.", "lock_and_shutdown"

        # 3. Workstation Lock
        if RE_LOCK.search(cleaned):
            return True, "lock", "Locking the workstation now. Goodbye, Boss.", "lock"

        # 4. System Shutdown / Abort
        if RE_SHUTDOWN.search(cleaned):
            return True, "shutdown", "Shutting down the system. Powering down now.", "shutdown"
        if RE_CANCEL_SHUTDOWN.search(cleaned):
            return True, "cancel_shutdown", cls.cancel_shutdown(), None

        # 5. Restart & Sleep
        if RE_RESTART.search(cleaned):
            return True, "restart", "Restarting the computer. See you soon, Boss.", "restart"
        if RE_SLEEP.search(cleaned):
            return True, "sleep", "Putting the system to sleep now.", "sleep"

        # 6. Stop Speaking / Interruption
        if RE_STOP.search(cleaned):
            return True, "stop_speaking", "Understood. Standing by.", None

        # 7. Desktop & Window Management
        if RE_CLEAR_DESKTOP.search(cleaned):
            return True, "clear_all_apps", cls.clear_all_apps(), None
        if RE_SHOW_DESKTOP.search(cleaned):
            return True, "minimize_all", cls.minimize_all(), None

        # 8. Audio Volume Control
        if RE_VOL_UP.search(cleaned):
            return True, "volume_up", cls.volume_up(), None
        if RE_VOL_DOWN.search(cleaned):
            return True, "volume_down", cls.volume_down(), None
        if RE_VOL_MUTE.search(cleaned):
            return True, "volume_mute", cls.volume_mute(), None

        # 9. Telemetry & System Status
        if RE_SYS_STATUS.search(cleaned):
            status = cls.get_system_status()
            summary = f"CPU is at {status['cpu_percent']}%, RAM usage is {status['ram_percent']}% ({status['ram_used_gb']} of {status['ram_total_gb']} GB)."
            return True, "system_status", summary, None

        # 10. Full Screen Mode Toggle
        if RE_FULLSCREEN.search(cleaned):
            return True, "toggle_fullscreen", "Toggling full screen mode.", "toggle_fullscreen"

        # 10. Open Application or Website
        open_match = RE_OPEN.search(cleaned)
        if open_match:
            app_target = open_match.group(1).strip()
            if app_target and app_target not in ["the door", "router"]:
                return True, "open_app", cls.open_app(app_target), None

        # 11. Standalone Direct App/Website Name (e.g. "chrome", "notepad", "calculator")
        if cleaned in DIRECT_KEYWORDS:
            return True, "open_app", cls.open_app(DIRECT_KEYWORDS[cleaned]), None

        # 12. Close Application
        close_match = RE_CLOSE.search(cleaned)
        if close_match:
            app_target = close_match.group(1).strip()
            if app_target not in ["all", "all apps", "everything", "the computer", "the pc", "the system"]:
                return True, "close_app", cls.close_app(app_target), None

        return False, "", None, None


system_actions = SystemActions()
