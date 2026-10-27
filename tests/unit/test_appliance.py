"""Tests for power-based cycle detection."""

from datetime import datetime, timedelta, timezone
import unittest

from custom_components.appliance_cycle_monitor.appliance import (
    ApplianceCycleDetector,
    BinaryActivityDetector,
    CycleEvent,
    CycleThresholds,
    CycleTransition,
)


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


class ApplianceCycleDetectorTests(unittest.TestCase):
    def test_default_start_requires_fifteen_seconds(self) -> None:
        detector = ApplianceCycleDetector()

        self.assertEqual(detector.observe_power("5", "W", START), [])
        self.assertEqual(
            detector.advance_time(START + timedelta(seconds=14)), []
        )
        self.assertEqual(
            detector.advance_time(START + timedelta(seconds=15)),
            [CycleEvent(CycleTransition.STARTED, START + timedelta(seconds=15))],
        )
        self.assertTrue(detector.is_running)

    def test_start_candidate_is_cancelled_at_start_threshold(self) -> None:
        detector = ApplianceCycleDetector()
        detector.observe_power(5, "W", START)
        detector.observe_power(4, "W", START + timedelta(seconds=10))

        self.assertEqual(
            detector.advance_time(START + timedelta(seconds=30)), []
        )
        self.assertFalse(detector.is_running)

    def test_finish_candidate_is_cancelled_above_finish_threshold(self) -> None:
        detector = ApplianceCycleDetector()
        detector.observe_power(5, "W", START)
        detector.advance_time(START + timedelta(seconds=15))
        detector.observe_power(0.5, "W", START + timedelta(seconds=20))
        detector.observe_power(1, "W", START + timedelta(seconds=50))

        self.assertEqual(
            detector.advance_time(START + timedelta(minutes=3)), []
        )
        self.assertTrue(detector.is_running)

    def test_default_finish_requires_one_minute_below_threshold(self) -> None:
        detector = ApplianceCycleDetector()
        detector.observe_power(5, "W", START)
        detector.advance_time(START + timedelta(seconds=15))
        detector.observe_power(0.5, "W", START + timedelta(seconds=20))

        self.assertEqual(
            detector.advance_time(START + timedelta(seconds=79)), []
        )
        finished_at = START + timedelta(seconds=80)
        self.assertEqual(
            detector.advance_time(finished_at),
            [
                CycleEvent(
                    CycleTransition.FINISHED,
                    finished_at,
                    timedelta(seconds=65),
                )
            ],
        )
        self.assertFalse(detector.is_running)
        self.assertEqual(detector.last_cycle_duration, timedelta(seconds=65))

    def test_kilowatts_are_normalized_to_watts(self) -> None:
        detector = ApplianceCycleDetector()

        detector.observe_power(0.005, "kW", START)

        self.assertEqual(detector.power_w, 5)
        self.assertEqual(detector.next_deadline, START + timedelta(seconds=15))

    def test_invalid_reading_clears_candidate_but_keeps_active_cycle(self) -> None:
        detector = ApplianceCycleDetector()
        detector.observe_power(5, "W", START)
        detector.advance_time(START + timedelta(seconds=15))
        detector.observe_power(0.5, "W", START + timedelta(seconds=20))

        self.assertEqual(
            detector.observe_power("unavailable", "W", START + timedelta(seconds=30)),
            [],
        )
        self.assertTrue(detector.is_running)
        self.assertIsNone(detector.next_deadline)

    def test_invalid_units_and_values_are_ignored(self) -> None:
        for value, unit in (
            (5, None),
            (5, "mW"),
            (float("nan"), "W"),
            (float("inf"), "W"),
            (-1, "W"),
            ("invalid", "W"),
            (True, "W"),
        ):
            with self.subTest(value=value, unit=unit):
                detector = ApplianceCycleDetector()
                self.assertEqual(detector.observe_power(value, unit, START), [])
                self.assertIsNone(detector.power_w)
                self.assertIsNone(detector.next_deadline)

    def test_switch_off_finishes_active_cycle_immediately(self) -> None:
        detector = ApplianceCycleDetector()
        detector.observe_power(5, "W", START)
        detector.advance_time(START + timedelta(seconds=15))
        switched_off_at = START + timedelta(seconds=20)

        self.assertEqual(
            detector.finish_by_switch(switched_off_at),
            CycleEvent(
                CycleTransition.FINISHED,
                switched_off_at,
                timedelta(seconds=5),
            ),
        )
        self.assertIsNone(detector.finish_by_switch(switched_off_at))

    def test_detector_state_round_trips_with_pending_finish(self) -> None:
        detector = ApplianceCycleDetector()
        detector.observe_power(5, "W", START)
        detector.advance_time(START + timedelta(seconds=15))
        detector.observe_power(0.5, "W", START + timedelta(seconds=20))
        restored = ApplianceCycleDetector()

        restored.restore_state(detector.export_state())

        self.assertTrue(restored.is_running)
        self.assertEqual(restored.cycle_started_at, START + timedelta(seconds=15))
        self.assertEqual(
            restored.next_deadline,
            START + timedelta(seconds=80),
        )
        self.assertEqual(restored.power_w, 0.5)

    def test_restored_candidate_keeps_its_original_deadline(self) -> None:
        detector = ApplianceCycleDetector()
        detector.observe_power(5, "W", START)
        restored = ApplianceCycleDetector()
        restored.restore_state(detector.export_state())

        self.assertEqual(
            restored.next_deadline,
            START + timedelta(seconds=15),
        )
        self.assertEqual(
            restored.advance_time(START + timedelta(seconds=15)),
            [CycleEvent(CycleTransition.STARTED, START + timedelta(seconds=15))],
        )

    def test_reconcile_unavailable_preserves_restored_candidate(self) -> None:
        detector = ApplianceCycleDetector()
        detector.observe_power(5, "W", START)
        restored = ApplianceCycleDetector()
        restored.restore_state(detector.export_state())

        self.assertEqual(
            restored.reconcile_power(None, None, START + timedelta(minutes=1)), []
        )
        self.assertEqual(restored.next_deadline, START + timedelta(seconds=15))
        self.assertFalse(restored.is_running)

    def test_reconcile_clears_candidates_contradicted_by_current_power(self) -> None:
        detector = ApplianceCycleDetector()
        detector.observe_power(5, "W", START)
        self.assertEqual(detector.reconcile_power(4, "W", START), [])
        self.assertIsNone(detector.next_deadline)

        detector.observe_power(5, "W", START)
        detector.advance_time(START + timedelta(seconds=15))
        detector.observe_power(0.5, "W", START + timedelta(seconds=20))
        self.assertEqual(
            detector.reconcile_power(1, "W", START + timedelta(seconds=30)), []
        )
        self.assertIsNone(detector.next_deadline)

    def test_corrupt_state_is_rejected(self) -> None:
        detector = ApplianceCycleDetector()

        with self.assertRaises(ValueError):
            detector.restore_state({"cycle_started_at": "not-a-timestamp"})

    def test_invalid_restored_values_are_rejected(self) -> None:
        invalid_states = (
            {"power_w": True},
            {"cycle_started_at": "2026-01-01T00:00:00"},
            {"last_cycle_duration_seconds": -1},
            {
                "cycle_started_at": START.isoformat(),
                "start_candidate_at": START.isoformat(),
            },
            {"finish_candidate_at": START.isoformat()},
        )
        for state in invalid_states:
            with self.subTest(state=state), self.assertRaises(ValueError):
                ApplianceCycleDetector().restore_state(state)

    def test_invalid_thresholds_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CycleThresholds(start_power_w=1, finish_power_w=1)
        with self.assertRaises(ValueError):
            CycleThresholds(start_duration=timedelta(seconds=-1))


class BinaryActivityDetectorTests(unittest.TestCase):
    def test_on_and_off_emit_immediate_activity_events(self) -> None:
        detector = BinaryActivityDetector()

        self.assertEqual(
            detector.observe_state("on", START),
            [CycleEvent(CycleTransition.STARTED, START)],
        )
        finished_at = START + timedelta(minutes=5)
        self.assertEqual(
            detector.observe_state("off", finished_at),
            [
                CycleEvent(
                    CycleTransition.FINISHED,
                    finished_at,
                    timedelta(minutes=5),
                )
            ],
        )
        self.assertFalse(detector.is_running)

    def test_unavailable_state_does_not_finish_active_period(self) -> None:
        detector = BinaryActivityDetector()
        detector.observe_state("on", START)

        self.assertEqual(detector.observe_state("unavailable", START), [])
        self.assertTrue(detector.is_running)
        self.assertFalse(detector.available)

    def test_state_round_trips(self) -> None:
        detector = BinaryActivityDetector()
        detector.observe_state("on", START)
        restored = BinaryActivityDetector()

        restored.restore_state(detector.export_state())

        self.assertTrue(restored.is_running)
        self.assertEqual(restored.cycle_started_at, START)
        self.assertFalse(restored.available)

    def test_idle_and_unavailable_states_do_not_emit_transitions(self) -> None:
        detector = BinaryActivityDetector()

        self.assertEqual(detector.reconcile_state(None, START), [])
        self.assertFalse(detector.available)
        self.assertEqual(detector.observe_state("off", START), [])
        self.assertTrue(detector.available)
        self.assertEqual(detector.advance_time(START + timedelta(minutes=1)), [])
        self.assertIsNone(detector.finish_by_switch(START))

    def test_invalid_restored_duration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BinaryActivityDetector().restore_state(
                {"last_cycle_duration_seconds": float("nan")}
            )


if __name__ == "__main__":
    unittest.main()