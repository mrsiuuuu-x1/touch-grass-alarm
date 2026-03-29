import ctypes, winreg
ctypes.windll.user32.BlockInput(False)
key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
    r"Software\Microsoft\Windows\CurrentVersion\Policies\System",
    0, winreg.KEY_SET_VALUE)
winreg.DeleteValue(key, "DisableTaskMgr")