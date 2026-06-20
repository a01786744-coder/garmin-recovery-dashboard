"""Authenticated wrapper around the garminconnect library (v0.3.2).

Never logs or includes credential values in error messages. Tokens are
persisted to the tokenstore directory so only the first login needs
credentials/MFA; later runs resume silently.
"""
import logging
import os

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

log = logging.getLogger("garmin")


class GarminAuthError(Exception):
    pass


class GarminRateLimitError(Exception):
    pass


class GarminConnectionError(Exception):
    pass


class GarminMFARequired(Exception):
    """Raised by login() when the account needs an MFA code and no valid
    tokens exist. Carries client_state to pass to complete_mfa()."""
    def __init__(self, client_state):
        super().__init__("MFA code required to complete Garmin login")
        self.client_state = client_state


class GarminClient:
    def __init__(self, email, password, tokenstore):
        self._email = email
        self._password = password
        self._tokenstore = str(tokenstore)
        self._api = None

    def login(self):
        """Resume from the token store, or do a credential login.

        On a clean login (tokens loaded, or a non-MFA account), persists
        tokens and returns. If the account needs MFA and no valid tokens
        exist, raises GarminMFARequired carrying the client_state.
        """
        try:
            self._api = Garmin(self._email, self._password, return_on_mfa=True)
            needs_mfa, client_state = self._api.login(self._tokenstore)
        except GarminConnectAuthenticationError:
            raise GarminAuthError("Garmin authentication failed (check .env credentials)")
        except GarminConnectTooManyRequestsError:
            raise GarminRateLimitError("Garmin rate limit hit (HTTP 429)")
        except GarminConnectConnectionError:
            raise GarminConnectionError("Could not connect to Garmin Connect")
        if needs_mfa:
            raise GarminMFARequired(client_state)
        self._dump_tokens()

    def complete_mfa(self, client_state, code):
        """Finish an MFA login with the user-supplied code, then persist tokens."""
        try:
            self._api.resume_login(client_state, code)
        except GarminConnectAuthenticationError:
            raise GarminAuthError("Garmin MFA verification failed (wrong or expired code)")
        self._dump_tokens()

    def _dump_tokens(self):
        os.makedirs(self._tokenstore, exist_ok=True)
        try:
            self._api.client.dump(self._tokenstore)
        except Exception:
            log.warning("could not persist Garmin tokens")

    @property
    def api(self):
        if self._api is None:
            raise RuntimeError("login() must be called first")
        return self._api

    def _safe(self, fn, default=None):
        """Call a library getter; on any error return default (never raise),
        and record that an error occurred for last_fetch_had_errors."""
        try:
            return fn()
        except Exception as e:  # library raises varied types on missing data
            self._fetch_errors = getattr(self, "_fetch_errors", 0) + 1
            log.warning("metric fetch failed: %s", type(e).__name__)
            return default

    @property
    def last_fetch_had_errors(self):
        return getattr(self, "_fetch_errors", 0) > 0

    def fetch_baseline(self, date_str):
        """Lightweight pull for backfilling history cheaply: HRV + RHR only
        (2 calls), so a 30-day backfill stays within Garmin's rate limits."""
        self._fetch_errors = 0
        api = self.api
        summary = self._safe(lambda: api.get_user_summary(date_str), {}) or {}
        hrv = self._safe(lambda: api.get_hrv_data(date_str), None)
        hrv_sum = (hrv or {}).get("hrvSummary", {}) if hrv else {}
        return {
            "hrv_last_night": hrv_sum.get("lastNightAvg"),
            "hrv_status": hrv_sum.get("status"),
            "rhr": summary.get("restingHeartRate"),
        }

    def fetch_day(self, date_str):
        self._fetch_errors = 0
        api = self.api
        summary = self._safe(lambda: api.get_user_summary(date_str), {}) or {}
        sleep = self._safe(lambda: api.get_sleep_data(date_str), {}) or {}
        hrv = self._safe(lambda: api.get_hrv_data(date_str), None)
        tr = self._safe(lambda: api.get_training_readiness(date_str), []) or []
        maxmet = self._safe(lambda: api.get_max_metrics(date_str), None)

        sdto = (sleep or {}).get("dailySleepDTO", {}) or {}
        hrv_sum = (hrv or {}).get("hrvSummary", {}) if hrv else {}
        tr0 = tr[0] if isinstance(tr, list) and tr else {}
        maxgen = {}
        if isinstance(maxmet, list) and maxmet:
            maxgen = (maxmet[0] or {}).get("generic", {}) or {}
        elif isinstance(maxmet, dict):
            maxgen = maxmet.get("generic", {}) or {}

        metrics = {
            "hrv_last_night": hrv_sum.get("lastNightAvg"),
            "hrv_status": hrv_sum.get("status"),
            "rhr": summary.get("restingHeartRate"),
            "sleep_score": (sdto.get("sleepScores", {}) or {}).get("overall", {}).get("value"),
            "deep_sleep_s": sdto.get("deepSleepSeconds"),
            "light_sleep_s": sdto.get("lightSleepSeconds"),
            "rem_sleep_s": sdto.get("remSleepSeconds"),
            "awake_sleep_s": sdto.get("awakeSleepSeconds"),
            "steps": summary.get("totalSteps"),
            "calories": summary.get("totalKilocalories"),
            "body_battery": summary.get("bodyBatteryMostRecentValue"),
            "training_readiness_score": tr0.get("score"),
            "stress_avg": summary.get("averageStressLevel"),
            "vo2max": maxgen.get("vo2MaxValue"),
        }
        availability = {k: ("available" if v is not None else "unavailable")
                        for k, v in metrics.items()}
        return metrics, availability

    def fetch_activities(self, start_str, end_str):
        api = self.api
        raw = self._safe(lambda: api.get_activities_by_date(start_str, end_str), []) or []
        out = []
        for a in raw:
            a = a or {}
            out.append({
                "activity_id": a.get("activityId"),
                "date": (a.get("startTimeLocal") or "")[:10] or None,
                "type": (a.get("activityType", {}) or {}).get("typeKey"),
                "duration_s": a.get("duration"),
                "avg_hr": a.get("averageHR"),
                "max_hr": a.get("maxHR"),
                "training_load": a.get("activityTrainingLoad"),
                "aerobic_te": a.get("aerobicTrainingEffect"),
                "anaerobic_te": a.get("anaerobicTrainingEffect"),
            })
        return out
