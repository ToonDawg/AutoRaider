from datetime import datetime, timedelta
import threading
from typing import TYPE_CHECKING, Dict, List, Optional, TypedDict
import json

class TaskScheduler:
    def __init__(self, py_auto_raid, logger):
        self.logger = logger
        self.logger.info("Initializing TaskScheduler")
        self.py_auto_raid = py_auto_raid
        self.schedules: List[Schedule] = []
        saved_schedules = self.py_auto_raid.config_handler.read_setting('Schedules', None, fallback={})
        self.schedules = Schedule.parse_schedules(saved_schedules)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.logger.info("TaskScheduler initialized with %d schedules", len(self.schedules))

    def _run_loop(self) -> None:
        """Main scheduling loop that executes tasks at their scheduled times."""
        self.logger.info("Entering TaskScheduler run loop")
        while not self._stop_event.is_set():
            now = datetime.now()
            current_hour, current_minute = now.hour, now.minute
            with self._lock:
                for schedule in self.schedules:
                    if schedule['enabled']:
                        try:
                            hour, minute = map(int, schedule['schedule'].split(':'))
                            if hour == current_hour and minute == current_minute:
                                self.logger.info("Executing scheduled task: %s", schedule['name'])
                                self._execute_task(schedule['name'])
                        except ValueError as e:
                            self.logger.error("Invalid time format for schedule '%s': %s", schedule['schedule'], e)
            self._stop_event.wait(60)

    def add_schedule(self, task_name: str, schedule_time: str) -> None:
        """Add a new scheduled task with HH:MM time format."""
        self.logger.info("Adding schedule: %s at %s", task_name, schedule_time)
        with self._lock:
            if not any(s['name'] == task_name for s in self.schedules):
                schedule_id = max((s['id'] for s in self.schedules), default=0) + 1
                new_schedule: Schedule = {
                    'id': schedule_id,
                    'name': task_name,
                    'schedule': schedule_time,
                    'enabled': True
                }
                self.schedules.append(new_schedule)
                self.py_auto_raid.config_handler.update_setting(
                    'Schedules', 
                    str(schedule_id),
                    json.dumps(new_schedule)
                )
                self.logger.info("Schedule added: %s", new_schedule)
                self._restart_loop_if_needed()

    def remove_schedule(self, schedule_id: int) -> None:
        """Remove a task from the scheduler by ID."""
        self.logger.info("Removing schedule with ID: %d", schedule_id)
        with self._lock:
            self.schedules = [s for s in self.schedules if s['id'] != schedule_id]
            self.py_auto_raid.config_handler.remove_setting('Schedules', str(schedule_id))

    def toggle_schedule(self, schedule_id: int, enabled: bool) -> None:
        """Enable/disable a scheduled task by ID."""
        self.logger.info("Toggling schedule ID %d to %s", schedule_id, enabled)
        with self._lock:
            for schedule in self.schedules:
                if schedule['id'] == schedule_id:
                    schedule['enabled'] = enabled
                    self.py_auto_raid.config_handler.update_setting(
                        'Schedules', 
                        str(schedule_id),
                        json.dumps(schedule)
                    )
                    self.logger.info("Schedule ID %d toggled to %s", schedule_id, enabled)
                    break

    def start(self) -> None:
        """Start the scheduler thread."""
        self.logger.info("Starting TaskScheduler thread")
        if not self._thread or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            self.logger.info("TaskScheduler thread started")

    def stop(self) -> None:
        """Stop the scheduler thread gracefully."""
        self.logger.info("Stopping TaskScheduler thread")
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            self.logger.info("TaskScheduler thread stopped")

    def _execute_task(self, task_name: str) -> None:
        """Execute the actual task using the py_auto_raid system."""
        self.logger.info("Executing task: %s", task_name)
        try:
            self.py_auto_raid.make_sure_raid_is_open()
            
            # Run the task and wait for completion
            self.py_auto_raid.run_task(task_name, self.py_auto_raid.close_raid)
            
            # Close Raid after task completes
            self.logger.info("Task completed, closing Raid...")
        except Exception as e:
            self.logger.error(f"Error during task execution: {e}")
            # Try to close Raid even if task failed
            try:
                self.py_auto_raid.close_raid()
            except Exception as close_error:
                self.logger.error(f"Error closing Raid after task failure: {close_error}")
                

    def _restart_loop_if_needed(self) -> None:
        """Restart the scheduler loop if it's not running."""
        if not self._thread or not self._thread.is_alive():
            self.logger.info("Restarting TaskScheduler loop")
            self.start()


class Schedule(TypedDict):
    id: int
    name: str
    schedule: str  # Format: HH:MM
    enabled: bool

    @staticmethod
    def parse_schedules(saved_schedules: Dict[str, str]) -> List["Schedule"]:
        """Parse saved schedules from a dictionary."""
        schedules = []
        for schedule_id, schedule_str in saved_schedules.items():
            try:
                schedule = json.loads(schedule_str)
                schedules.append({
                    "id": int(schedule_id),
                    "name": schedule["name"],
                    "schedule": schedule["schedule"],
                    "enabled": bool(schedule["enabled"])
                })
            except json.JSONDecodeError as json_error:
                try:
                    schedule = eval(schedule_str)
                    schedules.append({
                        "id": int(schedule_id),
                        "name": schedule["name"],
                        "schedule": schedule["schedule"],
                        "enabled": bool(schedule["enabled"])
                    })
                except Exception as eval_error:
                    print(f"ERROR: Failed to parse schedule ID {schedule_id}: {json_error} and {eval_error}")
        return schedules
