"""Convert a coach workout design into a Garmin Connect structured workout.

Design JSON (produced by the coach under a strict schema) uses athlete-friendly
units: paces as seconds-per-km, heart rate as bpm, durations as seconds or
meters. Garmin's wire format wants speeds in m/s (targetValueOne = LOW speed =
slowest pace, targetValueTwo = HIGH speed = fastest pace) and custom bpm
ranges on a heart.rate.zone target.

Nothing here talks to the network — push happens through GarminClient so the
API layer controls when a write to the user's Garmin account is allowed.
"""
from garminconnect.workout import (
    ConditionType, ExecutableStep, RepeatGroup, RunningWorkout, StepType,
    TargetType, WorkoutSegment,
)

_STEP_TYPES = {
    "warmup":   {"stepTypeId": StepType.WARMUP,   "stepTypeKey": "warmup"},
    "cooldown": {"stepTypeId": StepType.COOLDOWN, "stepTypeKey": "cooldown"},
    "interval": {"stepTypeId": StepType.INTERVAL, "stepTypeKey": "interval"},
    "recovery": {"stepTypeId": StepType.RECOVERY, "stepTypeKey": "recovery"},
    "rest":     {"stepTypeId": StepType.REST,     "stepTypeKey": "rest"},
}

_END = {
    "time":     {"conditionTypeId": ConditionType.TIME, "conditionTypeKey": "time",
                 "displayable": True},
    "distance": {"conditionTypeId": ConditionType.DISTANCE,
                 "conditionTypeKey": "distance", "displayable": True},
}

_NO_TARGET = {"workoutTargetTypeId": TargetType.NO_TARGET,
              "workoutTargetTypeKey": "no.target"}


def pace_to_mps(sec_per_km):
    """270 sec/km (4:30/km) -> 3.7037 m/s."""
    return 1000.0 / float(sec_per_km)


def _target(step):
    """Garmin target dict + custom range values for one design step."""
    t = step.get("target_type") or "none"
    lo, hi = step.get("target_min"), step.get("target_max")
    if t == "pace" and lo and hi:
        # design: target_min = FASTEST (lowest sec/km), target_max = SLOWEST.
        # Garmin speed zone: valueOne = low speed (slowest), valueTwo = high.
        return ({"workoutTargetTypeId": TargetType.SPEED,
                 "workoutTargetTypeKey": "speed.zone"},
                pace_to_mps(max(lo, hi)), pace_to_mps(min(lo, hi)))
    if t == "heart_rate" and lo and hi:
        return ({"workoutTargetTypeId": TargetType.HEART_RATE,
                 "workoutTargetTypeKey": "heart.rate.zone"},
                float(min(lo, hi)), float(max(lo, hi)))
    return (_NO_TARGET, None, None)


def _step(design_step, order):
    target, v1, v2 = _target(design_step)
    kind = design_step.get("kind", "interval")
    return ExecutableStep(
        stepOrder=order,
        description=(design_step.get("description") or "")[:512] or None,
        stepType=_STEP_TYPES.get(kind, _STEP_TYPES["interval"]),
        endCondition=_END.get(design_step.get("duration_type", "time"), _END["time"]),
        endConditionValue=float(design_step.get("duration_value") or 0),
        targetType=target,
        targetValueOne=v1,
        targetValueTwo=v2,
    )


def design_to_garmin(design):
    """Coach design dict -> RunningWorkout ready for upload_running_workout."""
    steps, order = [], 1
    for s in design.get("steps") or []:
        if s.get("kind") == "repeat":
            children = []
            for child in s.get("steps") or []:
                order += 1
                children.append(_step(child, order))
            steps.append(RepeatGroup(
                stepOrder=order - len(children),
                stepType={"stepTypeId": StepType.REPEAT, "stepTypeKey": "repeat"},
                numberOfIterations=int(s.get("count") or 1),
                endCondition={"conditionTypeId": ConditionType.ITERATIONS,
                              "conditionTypeKey": "iterations",
                              "displayable": False},
                endConditionValue=float(s.get("count") or 1),
                workoutSteps=children,
            ))
            order += 1
        else:
            steps.append(_step(s, order))
            order += 1
    total_s = _estimate_seconds(design)
    return RunningWorkout(
        workoutName=(design.get("name") or "Coach workout")[:100],
        description=(design.get("rationale") or "")[:1024] or None,
        estimatedDurationInSecs=total_s,
        workoutSegments=[WorkoutSegment(
            segmentOrder=1,
            sportType={"sportTypeId": 1, "sportTypeKey": "running"},
            workoutSteps=steps,
        )],
    )


def _estimate_seconds(design):
    """Rough duration estimate for Garmin's metadata (time steps only;
    distance steps assumed at 6:00/km)."""
    def step_s(s):
        v = float(s.get("duration_value") or 0)
        return v if s.get("duration_type") == "time" else v * 0.36
    total = 0.0
    for s in design.get("steps") or []:
        if s.get("kind") == "repeat":
            total += int(s.get("count") or 1) * sum(step_s(c) for c in s.get("steps") or [])
        else:
            total += step_s(s)
    return int(total) or None
