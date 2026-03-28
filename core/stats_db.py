import json
import os
from datetime import date, timedelta
from typing import Optional

# Path setup
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_DATA_DIR = os.path.join(_ROOT, "data")
_STATS_FILE = os.path.join(_DATA_DIR, "stats.json")

# Default state
def _defaults() -> dict:
    return {
        "total_breaks": 0,
        "best_streak": 0,
        "current_streak": 0,
        "last_break_date": None,
        "sessions_today": 1,
        "sessions_date": str(date.today()),
    }

# StatsDB
class StatsDB:
    def __init__(self, path: str = _STATS_FILE):
        self.path = path
        self._data = _defaults()

    def load(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data = {**_defaults(), **saved}
            except (json.JSONDecodeError, OSError):
                self._data = _defaults()
        else:
            self._save()

        # reset sessions_today if it's new calendar day
        if self._data["sessions_date"] != str(date.today()):
            self._data["sessions_today"]  = 1
            self._data["sessions_date"]   = str(date.today())
            self._save()
        
    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data,f,indent=2)
    
    # Mutations
    def record_break(self):
        today = date.today()
        last_str = self._data.get("last_break_data")
        last_date = self.fromisoformat(last_str) if last_str else None

        self._data["total_breaks"] += 1

        if last_date is None:
            self._data["current_streak"] = 1
        elif last_date == today:
            pass        #Streak doesn't change - already broken
        elif last_date == today - timedelta(days=1):
            self._data["current_streak"] += 1
        else:
            self._data["current_streak"] = 1
        
        self._data["last_break_date"] = str(today)
        self._data["best_streak"] = max(
            self._data["best_streak"],
            self._data["current_streak"],
        )
        self._save()

    def increment_session(self):
        today = str(date.today())
        if self._data["sessions_date"] == today:
            self._data["sessions_today"] += 1
        else:
            self._data["sessions_today"] = 1
            self._data["sessions_date"] = today
        self._save()

    def check_streak_broken(self):
        last_str = self._data.get("last_break_date")
        if not last_str:
            return
        last_date = date.fromisoformat(last_str)
        today = date.today()
        if today - last_date > timedelta(days=1):
            self._data["current_streak"] = 0
            self._save()

    # Read
    def snapshot(self) -> dict:
        return {
            "total_breaks":   self._data["total_breaks"],
            "sessions_today": self._data["sessions_today"],
            "current_streak": self._data["current_streak"],
            "best_streak":    self._data["best_streak"],
        }
    
    # Convenience Properties
    @property
    def current_streak(self) -> int:
        return self._data["current_streak"]
    
    @property
    def best_streak(self) -> int:
        return self._data["best_streak"]
 
    @property
    def total_breaks(self) -> int:
        return self._data["total_breaks"]
 
    @property
    def sessions_today(self) -> int:
        return self._data["sessions_today"]
