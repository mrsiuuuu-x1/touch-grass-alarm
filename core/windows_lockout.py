import ctypes
import ctypes.wintypes
import winreg
import threading
import sys
from typing import Optional

# Admin Check
def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def relaunch_as_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit(0)

# Win32 helpers
_user32 = ctypes.windll.user32
def _block_input(block: bool):
    try:
        _user32.BlockInput(ctypes.c_bool(block))
    except Exception:
        pass

def _set_task_manager_disabled(disabled: bool):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path,
            0, winreg.KEY_SET_VALUE
        )
        if disabled:
            winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
        else:
            try:
                winreg.DeleteValue(key, "DisableTaskMgr")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception:
        pass

def _set_window_topmost(hwnd: int, topmost: bool):
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    flag = HWND_TOPMOST if topmost else HWND_NOTOPMOST
    try:
        _user32.SetWindowPos(hwnd, flag, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    except Exception:
        pass

# Lockout Manager
class WindowsLockout:
    def __init__(self):
        self._engaged = False
        self._hwnd = None
        self._keepalive_t = None
    
    AUTO_RELEASE_SECONDS = 30

    def engage(self, hwnd: int):
        if self._engaged:
            return
        
        self._hwnd = hwnd
        self._engaged = True

        _block_input(True)
        _set_task_manager_disabled(True)
        _set_window_topmost(hwnd, True)

        self._keepalive_t = threading.Thread(target=self._keepalive_t, daemon=True)
        self._keepalive_t.start()

        # safety - auto release
        self._safety_t = threading.Timer(self.AUTO_RELEASE_SECONDS, self._safety_release)
        self._safety_t.daemon = True
        self._safety_t.start()

    def release(self):
        self._engaged = False

        # cancel safety timer
        if hasattr(self, '_safety_t') and self._safety_t:
            self._safety_t.cancel()

        _block_input(False)
        _set_task_manager_disabled(False)
        
        if self._hwnd:
            _set_window_topmost(self._hwnd, False)
            self._hwnd = None
    
    def _keepalive(self):
        import time
        while self._engaged:
            _block_input(True)
            if self._hwnd:
                _set_window_topmost(self._hwnd, True)
            time.sleep(0.5)
    
    @property
    def engaged(self) -> bool:
        return self._engaged
    
# Safety net
def emergency_released():
    _block_input(False)
    _set_task_manager_disabled(False)