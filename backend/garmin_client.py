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


def _primary_device_value(device_map):
    """Garmin nests several training metrics under a {deviceId: {...}} map.
    Return the primary device's value (else the first), or {} if none."""
    if not isinstance(device_map, dict) or not device_map:
        return {}
    for v in device_map.values():
        if isinstance(v, dict) and v.get("primaryTrainingDevice"):
            return v
    return next(iter(device_map.values()), {}) or {}


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
        intensity = self._safe(lambda: api.get_intensity_minutes_data(date_str), {}) or {}
        resp = self._safe(lambda: api.get_respiration_data(date_str), {}) or {}
        tstat = self._safe(lambda: api.get_training_status(date_str), {}) or {}

        sdto = (sleep or {}).get("dailySleepDTO", {}) or {}
        hrv_sum = (hrv or {}).get("hrvSummary", {}) if hrv else {}
        tr0 = tr[0] if isinstance(tr, list) and tr else {}
        maxgen = {}
        if isinstance(maxmet, list) and maxmet:
            maxgen = (maxmet[0] or {}).get("generic", {}) or {}
        elif isinstance(maxmet, dict):
            maxgen = maxmet.get("generic", {}) or {}

        ts_data = _primary_device_value(
            (tstat.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData") or {})
        acute = ts_data.get("acuteTrainingLoadDTO", {}) or {}
        load_bal = _primary_device_value(
            (tstat.get("mostRecentTrainingLoadBalance") or {}).get("metricsTrainingLoadBalanceDTOMap") or {})
        scores = sdto.get("sleepScores") or {}
        sleep_need = sdto.get("sleepNeed") or {}

        metrics = {
            "hrv_last_night": hrv_sum.get("lastNightAvg"),
            "hrv_status": hrv_sum.get("status"),
            "rhr": summary.get("restingHeartRate"),
            "sleep_score": (scores.get("overall") or {}).get("value"),
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
            # v2 expansion
            "floors_ascended": summary.get("floorsAscended"),
            "intensity_moderate": summary.get("moderateIntensityMinutes"),
            "intensity_vigorous": summary.get("vigorousIntensityMinutes"),
            "intensity_weekly_total": intensity.get("weeklyTotal"),
            "intensity_weekly_goal": intensity.get("weekGoal"),
            "highly_active_s": summary.get("highlyActiveSeconds"),
            "active_s": summary.get("activeSeconds"),
            "sedentary_s": summary.get("sedentarySeconds"),
            "active_calories": summary.get("activeKilocalories"),
            "resting_calories": summary.get("bmrKilocalories"),
            "distance_m": summary.get("totalDistanceMeters"),
            "resp_waking": resp.get("avgWakingRespirationValue"),
            "resp_sleep": resp.get("avgSleepRespirationValue"),
            "sleep_need_actual": sleep_need.get("actual"),
            "sleep_need_baseline": sleep_need.get("baseline"),
            "sleep_deep_score": (scores.get("deep") or {}).get("value"),
            "sleep_rem_score": (scores.get("rem") or {}).get("value"),
            "sleep_light_score": (scores.get("light") or {}).get("value"),
            "sleep_restlessness_score": (scores.get("restlessness") or {}).get("value"),
            "awake_count": sdto.get("awakeCount"),
            "training_status_label": ts_data.get("trainingStatusFeedbackPhrase"),
            "acwr_ratio": acute.get("dailyAcuteChronicWorkloadRatio"),
            "acute_load": acute.get("dailyTrainingLoadAcute"),
            "chronic_load": acute.get("dailyTrainingLoadChronic"),
            "load_aerobic_low": load_bal.get("monthlyLoadAerobicLow"),
            "load_aerobic_high": load_bal.get("monthlyLoadAerobicHigh"),
            "load_anaerobic": load_bal.get("monthlyLoadAnaerobic"),
            "tr_sleep_factor": tr0.get("sleepScoreFactorPercent"),
            "tr_recovery_factor": tr0.get("recoveryTimeFactorPercent"),
            "tr_acwr_factor": tr0.get("acwrFactorPercent"),
            "tr_hrv_factor": tr0.get("hrvFactorPercent"),
            "tr_stress_factor": tr0.get("stressHistoryFactorPercent"),
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

    def fetch_performance(self, date_str):
        """VO2max, fitness age, race predictions, endurance, acclimation."""
        self._fetch_errors = 0
        api = self.api
        tstat = self._safe(lambda: api.get_training_status(date_str), {}) or {}
        v2 = tstat.get("mostRecentVO2Max") or {}
        generic = v2.get("generic") or {}
        accl = v2.get("heatAltitudeAcclimation") or {}
        maxmet = self._safe(lambda: api.get_max_metrics(date_str), None)
        mg = {}
        if isinstance(maxmet, list) and maxmet:
            mg = (maxmet[0] or {}).get("generic", {}) or {}
        race = self._safe(lambda: api.get_race_predictions(), {}) or {}
        endur = self._safe(lambda: api.get_endurance_score(date_str), {}) or {}
        return {
            "vo2max": generic.get("vo2MaxValue") or mg.get("vo2MaxValue"),
            "vo2max_cycling": (v2.get("cycling") or {}).get("vo2MaxValue"),
            "fitness_age": generic.get("fitnessAge") or mg.get("fitnessAge"),
            "race_5k": race.get("time5K"), "race_10k": race.get("time10K"),
            "race_hm": race.get("timeHalfMarathon"), "race_marathon": race.get("timeMarathon"),
            "endurance_score": endur.get("overallScore"),
            "endurance_class": endur.get("classification"),
            "heat_acclimation": accl.get("heatAcclimationPercentage"),
            "altitude_acclimation": accl.get("altitudeAcclimation"),
        }

    def fetch_personal_records(self):
        self._fetch_errors = 0
        api = self.api
        raw = self._safe(lambda: api.get_personal_record(), []) or []
        out = []
        for r in raw:
            r = r or {}
            out.append({
                "id": r.get("id"), "type_id": r.get("typeId"), "value": r.get("value"),
                "activity_id": r.get("activityId"), "activity_name": r.get("activityName"),
                "start_time": (r.get("prStartTimeGmtFormatted")
                               or r.get("activityStartDateTimeLocalFormatted")),
            })
        return out

    def fetch_intraday(self, date_str):
        """All-day curves: HR, stress, body battery, overnight HRV readings."""
        self._fetch_errors = 0
        api = self.api
        hr = self._safe(lambda: api.get_heart_rates(date_str), {}) or {}
        stress = self._safe(lambda: api.get_stress_data(date_str), {}) or {}
        bb = self._safe(lambda: api.get_body_battery(date_str), []) or []
        hrv = self._safe(lambda: api.get_hrv_data(date_str), {}) or {}
        bb0 = bb[0] if isinstance(bb, list) and bb else {}
        return {
            "hr": hr.get("heartRateValues"),
            "stress": stress.get("stressValuesArray"),
            "body_battery": bb0.get("bodyBatteryValuesArray"),
            "hrv": hrv.get("hrvReadings"),
        }

    def fetch_activity_detail(self, activity_id, maxpoly=2000):
        """Route polyline, splits, HR-zone distribution, weather for one activity."""
        self._fetch_errors = 0
        api = self.api
        det = self._safe(lambda: api.get_activity_details(activity_id, maxpoly=maxpoly), {}) or {}
        geo = det.get("geoPolylineDTO", {}) or {}
        splits = self._safe(lambda: api.get_activity_splits(activity_id), {}) or {}
        zones = self._safe(lambda: api.get_activity_hr_in_timezones(activity_id), []) or []
        weather = self._safe(lambda: api.get_activity_weather(activity_id), None)
        summary = {k: geo.get(k) for k in
                   ("minLat", "maxLat", "minLon", "maxLon", "startPoint", "endPoint")}
        return {
            "polyline": geo.get("polyline"),
            "splits": splits.get("lapDTOs"),
            "hr_zones": zones if isinstance(zones, list) else None,
            "weather": weather,
            "summary": summary,
        }
