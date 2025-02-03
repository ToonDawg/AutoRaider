from typing import TYPE_CHECKING
import customtkinter as ctk
import ast

if TYPE_CHECKING:
    from app.pyAutoRaid import AutoRaider
    from utils.config_handler import ConfigHandler

class SchedulingTab:
    """GUI class for scheduling tasks in a customtkinter application."""

    def __init__(self, parent, config_handler, py_auto_raid):
        """Initialize scheduling tab components and UI."""
        self.parent = parent
        self.config_handler: ConfigHandler = config_handler
        self.py_auto_raid: AutoRaider = py_auto_raid
        self.schedule_hour_var = ctk.StringVar(value="HH")
        self.schedule_minute_var = ctk.StringVar(value="MM")
        self.task_values = self.load_task_list()
        self.checkbox_vars = {}
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI layout and elements."""
        self.parent.grid_columnconfigure(0, weight=1)
        self.parent.grid_columnconfigure(1, weight=1)
        self.parent.grid_columnconfigure(2, weight=1)
        self.parent.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            self.parent, text="Task Scheduling", font=("Arial", 16, "bold")
        ).grid(row=0, column=0, columnspan=4, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(self.parent, text="Task").grid(
            row=1, column=0, padx=10, pady=10, sticky="w"
        )
        task_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        task_frame.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        task_frame.grid_columnconfigure(0, weight=1)

        self.schedule_task_menu = ctk.CTkOptionMenu(
            task_frame,
            values=self.task_values,
            command=self.task_selected
        )
        self.schedule_task_menu.grid(row=0, column=0, sticky="ew")

        refresh_button = ctk.CTkButton(
            task_frame,
            text="⟳",
            width=30,
            command=self.update_task_list
        )
        refresh_button.grid(row=0, column=1, padx=(5, 0))

        time_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        time_frame.grid(row=1, column=2, padx=10, pady=10, sticky="ew")

        self.schedule_hour_menu = ctk.CTkOptionMenu(
            time_frame,
            values=[f"{i:02}" for i in range(24)],
            variable=self.schedule_hour_var,
            width=40
        )
        self.schedule_hour_menu.pack(side="left", padx=5)

        self.schedule_minute_menu = ctk.CTkOptionMenu(
            time_frame,
            values=[f"{i:02}" for i in range(0, 60, 1)],
            variable=self.schedule_minute_var,
            width=40
        )
        self.schedule_minute_menu.pack(side="left", padx=5)

        button_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        button_frame.grid(row=1, column=3, padx=10, pady=10, sticky="ew")

        add_schedule_button = ctk.CTkButton(
            button_frame,
            text="Add",
            command=self.add_schedule,
            width=80
        )
        add_schedule_button.pack(side="left", padx=5)

        self.table_container = ctk.CTkFrame(self.parent)
        self.table_container.grid(
            row=3, column=0, columnspan=4, padx=10, pady=10, sticky="nsew"
        )
        self._populate_schedule_table()

    def load_task_list(self):
        """Load task list from config."""
        raw_items = self.config_handler.read_setting("SelectionItems", "items", fallback="[]")
        try:
            task_list = ast.literal_eval(raw_items)
            if not isinstance(task_list, list):
                raise ValueError("Parsed value is not a list")
        except (SyntaxError, ValueError) as e:
            self.py_auto_raid.logger.error(f"Failed to parse task list: {e}")
            task_list = []
        return ["Select"] + [task for task in task_list if task != "Select"]

    def task_selected(self, selected_task):
        """Handle task selection."""
        if selected_task == "Select":
            self.py_auto_raid.logger.info("No valid task selected.")
        else:
            self.py_auto_raid.logger.info(f"Selected task: {selected_task}")

    def add_schedule(self):
        """Add a new schedule."""
        task_name = self.schedule_task_menu.get()
        task_time = f"{self.schedule_hour_var.get()}:{self.schedule_minute_var.get()}"

        if task_name != "Select" and task_time != "HH:MM":
            schedule_id = max((s["id"] for s in self.py_auto_raid.scheduler.schedules), default=0) + 1
            new_schedule = {
                "id": schedule_id,
                "name": task_name,
                "schedule": task_time,
                "enabled": True
            }
            self.py_auto_raid.scheduler.schedules.append(new_schedule)
            self.save_schedules()
            self._populate_schedule_table()
            self.py_auto_raid.logger.info(f"Added schedule: {new_schedule}")
        else:
            self.py_auto_raid.logger.error("Invalid task or time for schedule.")

    def _populate_schedule_table(self):
        """Populate schedule table with current tasks."""
        for widget in self.table_container.winfo_children():
            widget.destroy()

        self.table_container.grid_columnconfigure(0, weight=2, minsize=200)
        self.table_container.grid_columnconfigure(1, weight=1, minsize=100)
        self.table_container.grid_columnconfigure(2, weight=1, minsize=80)
        self.table_container.grid_columnconfigure(3, weight=1, minsize=120)

        headers = ["Task Name", "Time", "Enabled", "Actions"]
        for col, header in enumerate(headers):
            ctk.CTkLabel(
                self.table_container,
                text=header,
                font=("Arial", 12, "bold")
            ).grid(row=0, column=col, padx=10, pady=5, sticky="nsew")

        for row_idx, schedule in enumerate(self.py_auto_raid.scheduler.schedules, start=1):
            schedule_id = schedule["id"]
            task_name = schedule["name"]
            task_schedule = schedule["schedule"]

            ctk.CTkLabel(self.table_container, text=task_name).grid(
                row=row_idx, column=0, padx=5, pady=5, sticky="nsew"
            )
            ctk.CTkLabel(self.table_container, text=task_schedule).grid(
                row=row_idx, column=1, padx=5, pady=5, sticky="nsew"
            )

            if schedule_id not in self.checkbox_vars:
                self.checkbox_vars[schedule_id] = ctk.BooleanVar()
            self.checkbox_vars[schedule_id].set(schedule["enabled"])
            status_checkbox = ctk.CTkCheckBox(
                self.table_container,
                text="",
                variable=self.checkbox_vars[schedule_id],
                command=lambda s_id=schedule_id: self.toggle_task_status(s_id)
            )
            status_checkbox.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")

            action_frame = ctk.CTkFrame(self.table_container, fg_color="transparent")
            action_frame.grid(row=row_idx, column=3, padx=5, pady=5, sticky="nsew")

            run_button = ctk.CTkButton(
                action_frame,
                text="Run",
                command=lambda t_name=task_name: self.py_auto_raid.run_task(t_name),
                width=60
            )
            run_button.pack(side="left", padx=2)

            delete_button = ctk.CTkButton(
                action_frame,
                text="Delete",
                command=lambda s_id=schedule_id: self.delete_task(s_id),
                width=60,
                fg_color="#ff4444",
                hover_color="#cc0000"
            )
            delete_button.pack(side="left", padx=2)

    def delete_task(self, schedule_id):
        """Delete a schedule by its ID."""
        self.py_auto_raid.scheduler.schedules = [
            s for s in self.py_auto_raid.scheduler.schedules if s["id"] != schedule_id
        ]
        if schedule_id in self.checkbox_vars:
            del self.checkbox_vars[schedule_id]
        self.save_schedules()
        self._populate_schedule_table()
        self.py_auto_raid.logger.info(f"Deleted schedule with ID: {schedule_id}")

    def toggle_task_status(self, schedule_id):
        """Toggle the enabled status of a task by its ID."""
        for schedule in self.py_auto_raid.scheduler.schedules:
            if schedule["id"] == schedule_id:
                schedule["enabled"] = not schedule["enabled"]
                break
        self.save_schedules()
        self._populate_schedule_table()

    def save_schedules(self):
        """Save current schedules to the configuration."""
        self.config_handler.clear_section("Schedules")
        for schedule in self.py_auto_raid.scheduler.schedules:
            self.config_handler.update_setting(
                "Schedules",
                str(schedule["id"]),
                {
                    "name": schedule["name"],
                    "schedule": schedule["schedule"],
                    "enabled": schedule["enabled"]
                }
            )
            
    def update_task_list(self):
        """Update the task list and refresh the dropdown menu."""
        self.task_values = self.load_task_list()
        self.schedule_task_menu.configure(values=self.task_values)
