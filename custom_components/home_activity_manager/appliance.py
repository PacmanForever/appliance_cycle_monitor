"""Power-based appliance cycle detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import math
from typing import Any


@dataclass(frozen=True, slots=True)
class CycleThresholds:
    """Power thresholds and confirmation durations for one appliance."""

    start_power_w: float = 4.0
    start_duration: timedelta = timedelta(seconds=15)
    finish_power_w: float = 1.0
    finish_duration: timedelta = timedelta(seconds=60)

    def __post_init__(self) -> None:
        """Reject invalid thresholds and durations."""
        if (
            not math.isfinite(self.start_power_w)
            or not math.isfinite(self.finish_power_w)
            or self.finish_power_w < 0
            or self.start_power_w <= self.finish_power_w
        ):
            raise ValueError("Power thresholds must satisfy 0 <= finish < start")
        if self.start_duration < timedelta(0) or self.finish_duration < timedelta(0):
            raise ValueError("Confirmation durations cannot be negative")


class CycleTransition(str, Enum):
    """Transitions emitted by the detector."""

    STARTED = "started"
    FINISHED = "finished"


@dataclass(frozen=True, slots=True)
class CycleEvent:
    """A confirmed cycle transition."""

    transition: CycleTransition
    occurred_at: datetime
    duration: timedelta | None = None


class ApplianceCycleDetector:
    """Track one appliance cycle from power readings and elapsed time."""

    def __init__(self, thresholds: CycleThresholds | None = None) -> None:
        """Create a detector with the default or provided thresholds."""
        self.thresholds = thresholds or CycleThresholds()
        self.power_w: float | None = None
        self.cycle_started_at: datetime | None = None
        self.last_cycle_duration: timedelta | None = None
        self._start_candidate_at: datetime | None = None
        self._finish_candidate_at: datetime | None = None

    @property
    def is_running(self) -> bool:
        """Return whether a cycle is active."""
        return self.cycle_started_at is not None

    @property
    def next_deadline(self) -> datetime | None:
        """Return the next hysteresis deadline for the runtime to schedule."""
        if self._start_candidate_at is not None:
            return self._start_candidate_at + self.thresholds.start_duration
        if self._finish_candidate_at is not None:
            return self._finish_candidate_at + self.thresholds.finish_duration
        return None

    def observe_power(
        self, value: object, unit: str | None, at: datetime
    ) -> list[CycleEvent]:
        """Apply a power reading, ignoring invalid readings without ending a cycle."""
        watts = self.to_watts(value, unit)
        if watts is None:
            self.power_w = None
            self._clear_candidates()
            return []

        events = self.advance_time(at)
        self.power_w = watts

        if self.is_running:
            if watts < self.thresholds.finish_power_w:
                if self._finish_candidate_at is None:
                    self._finish_candidate_at = at
            else:
                self._finish_candidate_at = None
        elif watts > self.thresholds.start_power_w:
            if self._start_candidate_at is None:
                self._start_candidate_at = at
        else:
            self._start_candidate_at = None

        events.extend(self.advance_time(at))
        return events

    def reconcile_power(
        self, value: object, unit: str | None, at: datetime
    ) -> list[CycleEvent]:
        """Reconcile restored candidates against the input's current state."""
        watts = self.to_watts(value, unit)
        if watts is None:
            self.power_w = None
            return []
        if self._start_candidate_at is not None and watts <= self.thresholds.start_power_w:
            self._start_candidate_at = None
        if self._finish_candidate_at is not None and watts >= self.thresholds.finish_power_w:
            self._finish_candidate_at = None
        return self.observe_power(value, unit, at)

    def advance_time(self, at: datetime) -> list[CycleEvent]:
        """Confirm a candidate whose threshold has remained satisfied to its deadline."""
        if self._start_candidate_at is not None:
            deadline = self._start_candidate_at + self.thresholds.start_duration
            if at >= deadline:
                self.cycle_started_at = deadline
                self._start_candidate_at = None
                return [CycleEvent(CycleTransition.STARTED, deadline)]

        if self._finish_candidate_at is not None:
            deadline = self._finish_candidate_at + self.thresholds.finish_duration
            if at >= deadline:
                return [self._finish_cycle(deadline)]

        return []

    def finish_by_switch(self, at: datetime) -> CycleEvent | None:
        """Finish an active cycle immediately when its configured plug turns off."""
        self._start_candidate_at = None
        if not self.is_running:
            return None
        return self._finish_cycle(at)

    def export_state(self) -> dict[str, Any]:
        """Return JSON-compatible state for persistent storage."""
        return {
            "power_w": self.power_w,
            "cycle_started_at": self._format_datetime(self.cycle_started_at),
            "last_cycle_duration_seconds": (
                self.last_cycle_duration.total_seconds()
                if self.last_cycle_duration is not None
                else None
            ),
            "start_candidate_at": self._format_datetime(self._start_candidate_at),
            "finish_candidate_at": self._format_datetime(self._finish_candidate_at),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore detector state from a previously exported mapping."""
        self.power_w = self._parse_power(state.get("power_w"))
        self.cycle_started_at = self._parse_datetime(state.get("cycle_started_at"))
        self._start_candidate_at = self._parse_datetime(
            state.get("start_candidate_at")
        )
        self._finish_candidate_at = self._parse_datetime(
            state.get("finish_candidate_at")
        )

        duration_seconds = state.get("last_cycle_duration_seconds")
        if duration_seconds is None:
            self.last_cycle_duration = None
        else:
            duration = float(duration_seconds)
            if not math.isfinite(duration) or duration < 0:
                raise ValueError("Invalid stored cycle duration")
            self.last_cycle_duration = timedelta(seconds=duration)

        if self.cycle_started_at is not None and self._start_candidate_at is not None:
            raise ValueError("Stored state cannot have a running and start candidate")
        if not self.is_running and self._finish_candidate_at is not None:
            raise ValueError("Stored state cannot have a finish candidate while idle")

    @staticmethod
    def _format_datetime(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Invalid stored timestamp")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("Stored timestamps must include a timezone")
        return parsed

    @staticmethod
    def _parse_power(value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("Invalid stored power")
        power = float(value)
        if not math.isfinite(power) or power < 0:
            raise ValueError("Invalid stored power")
        return power

    def _finish_cycle(self, at: datetime) -> CycleEvent:
        started_at = self.cycle_started_at
        assert started_at is not None
        duration = max(at - started_at, timedelta(0))
        self.cycle_started_at = None
        self.last_cycle_duration = duration
        self._finish_candidate_at = None
        return CycleEvent(CycleTransition.FINISHED, at, duration)

    def _clear_candidates(self) -> None:
        self._start_candidate_at = None
        self._finish_candidate_at = None

    @staticmethod
    def to_watts(value: object, unit: str | None) -> float | None:
        if isinstance(value, bool) or unit is None:
            return None
        try:
            numeric_value = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(numeric_value) or numeric_value < 0:
            return None

        normalized_unit = unit.strip().casefold()
        if normalized_unit == "w":
            return numeric_value
        if normalized_unit == "kw":
            return numeric_value * 1000
        return None


class BinaryActivityDetector:
    """Track activity from a binary sensor that is on while an appliance runs."""

    def __init__(self) -> None:
        self.power_w: float | None = None
        self.cycle_started_at: datetime | None = None
        self.last_cycle_duration: timedelta | None = None
        self.available = False

    @property
    def is_running(self) -> bool:
        return self.cycle_started_at is not None

    @property
    def next_deadline(self) -> datetime | None:
        return None

    def observe_state(self, value: str | None, at: datetime) -> list[CycleEvent]:
        if value not in ("on", "off"):
            self.available = False
            return []
        self.available = True
        if value == "on" and not self.is_running:
            self.cycle_started_at = at
            return [CycleEvent(CycleTransition.STARTED, at)]
        if value == "off" and self.is_running:
            return [self._finish_cycle(at)]
        return []

    def reconcile_state(self, value: str | None, at: datetime) -> list[CycleEvent]:
        if value not in ("on", "off"):
            self.available = False
            return []
        return self.observe_state(value, at)

    def advance_time(self, at: datetime) -> list[CycleEvent]:
        return []

    def finish_by_switch(self, at: datetime) -> CycleEvent | None:
        if not self.is_running:
            return None
        return self._finish_cycle(at)

    def export_state(self) -> dict[str, Any]:
        return {
            "power_w": None,
            "cycle_started_at": ApplianceCycleDetector._format_datetime(
                self.cycle_started_at
            ),
            "last_cycle_duration_seconds": (
                self.last_cycle_duration.total_seconds()
                if self.last_cycle_duration is not None
                else None
            ),
            "start_candidate_at": None,
            "finish_candidate_at": None,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self.cycle_started_at = ApplianceCycleDetector._parse_datetime(
            state.get("cycle_started_at")
        )
        self.power_w = None
        self.available = False
        duration_seconds = state.get("last_cycle_duration_seconds")
        if duration_seconds is None:
            self.last_cycle_duration = None
            return
        duration = float(duration_seconds)
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("Invalid stored activity duration")
        self.last_cycle_duration = timedelta(seconds=duration)

    def _finish_cycle(self, at: datetime) -> CycleEvent:
        started_at = self.cycle_started_at
        assert started_at is not None
        duration = max(at - started_at, timedelta(0))
        self.cycle_started_at = None
        self.last_cycle_duration = duration
        return CycleEvent(CycleTransition.FINISHED, at, duration)