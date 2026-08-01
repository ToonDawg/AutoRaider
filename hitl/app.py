"""CustomTkinter crash-dump viewer and crop tool.

Imported only by ``python -m hitl``. Tests never import this module — the
pure logic lives in hitl.repair, and this Python may not even have _tkinter.

Written against the CustomTkinter 6 API. Smoke-test on a machine with
python-tk installed before trusting the window; see Ticket 3 Windows
follow-ups.
"""

from __future__ import annotations

import json
import logging
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

from engine.dump import DUMPS_DIR
from hitl.repair import RepairError, crop_target, load_dump, rewrite_target

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "assets"
DYNAMIC_DIR = ASSETS_DIR / "dynamic"
EXPECTED_SIZE = (900, 600)


def _list_dumps(dumps_dir: Path) -> list[Path]:
    """Return dump JSON paths newest-first. A missing PNG is still listed —
    selecting it shows an error rather than crashing the whole window.
    """
    if not dumps_dir.is_dir():
        return []
    return sorted(dumps_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def _dump_label(json_path: Path) -> str:
    try:
        context = json.loads(json_path.read_text(encoding="utf-8"))
        stamp = context.get("timestamp", json_path.stem)
        name = context.get("sequence_name", "?")
        node = context.get("failed_node", "?")
        return f"{stamp}  |  {name}  |  {node}"
    except Exception:
        return f"{json_path.stem}  |  (unreadable)"


class HitlApp(ctk.CTk):
    def __init__(self, dumps_dir: Path = DUMPS_DIR) -> None:
        super().__init__()
        self.dumps_dir = Path(dumps_dir)
        self.title("AutoRaider HITL — crash dump repair")
        self.geometry("1280x780")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._dump = None
        self._photo: ImageTk.PhotoImage | None = None
        self._target_photo: ImageTk.PhotoImage | None = None
        self._drag_start: tuple[int, int] | None = None
        self._rect_id: int | None = None
        self._selection: tuple[int, int, int, int] | None = None  # l,t,w,h

        self._build()
        self.refresh_dumps()

    def _build(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, width=340)
        left.grid(row=0, column=0, sticky="nsw", padx=(8, 4), pady=8)
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Crash dumps", font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=8, pady=(8, 4)
        )
        self.dump_list = ctk.CTkScrollableFrame(left, width=320, height=400)
        self.dump_list.pack(fill="both", expand=True, padx=4, pady=4)
        self._list_widgets: list = []

        ctk.CTkButton(left, text="Refresh", command=self.refresh_dumps).pack(
            fill="x", padx=8, pady=4
        )

        self.context_box = ctk.CTkTextbox(left, height=180, wrap="word")
        self.context_box.pack(fill="x", padx=8, pady=8)
        self.context_box.insert("1.0", "Select a dump to inspect.")
        self.context_box.configure(state="disabled")

        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(right, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        self.coords_label = ctk.CTkLabel(
            toolbar, text="selection: (none)", anchor="w"
        )
        self.coords_label.pack(side="left", padx=4)
        self.size_warning = ctk.CTkLabel(
            toolbar, text="", text_color="#F0A020", anchor="w"
        )
        self.size_warning.pack(side="left", padx=12)
        ctk.CTkButton(toolbar, text="Save Target", command=self.save_target, width=120).pack(
            side="right", padx=4
        )

        # Native tk Canvas: CustomTkinter has no canvas with drag selection.
        # Coordinates are image pixels because we display at 1:1 — never scale.
        canvas_frame = ctk.CTkFrame(right)
        canvas_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_frame, bg="#1a1a1a", highlightthickness=0)
        self.h_scroll = tk.Scrollbar(
            canvas_frame, orient="horizontal", command=self.canvas.xview
        )
        self.v_scroll = tk.Scrollbar(
            canvas_frame, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(
            xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        target_frame = ctk.CTkFrame(right, height=120)
        target_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=4)
        ctk.CTkLabel(target_frame, text="Current target template:").pack(
            side="left", padx=8
        )
        self.target_label = ctk.CTkLabel(target_frame, text="(none)")
        self.target_label.pack(side="left", padx=8)
        self.target_image_label = ctk.CTkLabel(target_frame, text="")
        self.target_image_label.pack(side="right", padx=8, pady=4)

        self.status = ctk.CTkLabel(right, text="", anchor="w")
        self.status.grid(row=3, column=0, sticky="ew", padx=8, pady=4)

    def refresh_dumps(self) -> None:
        for widget in self._list_widgets:
            widget.destroy()
        self._list_widgets.clear()

        dumps = _list_dumps(self.dumps_dir)
        if not dumps:
            empty = ctk.CTkLabel(
                self.dump_list, text=f"No dumps in {self.dumps_dir}"
            )
            empty.pack(anchor="w", padx=4, pady=4)
            self._list_widgets.append(empty)
            return

        for path in dumps:
            button = ctk.CTkButton(
                self.dump_list,
                text=_dump_label(path),
                anchor="w",
                command=lambda p=path: self.select_dump(p),
            )
            button.pack(fill="x", padx=2, pady=2)
            self._list_widgets.append(button)

    def select_dump(self, json_path: Path) -> None:
        self._selection = None
        self._drag_start = None
        self._clear_rect()
        self.coords_label.configure(text="selection: (none)")
        self.size_warning.configure(text="")

        try:
            dump = load_dump(json_path)
        except RepairError as exc:
            self._dump = None
            self.canvas.delete("all")
            self._set_context(f"Error loading {json_path.name}:\n{exc}")
            self.status.configure(text=str(exc))
            self._show_target(None)
            return

        self._dump = dump
        self._show_screenshot(dump.png_path)
        self._show_context(dump)
        self._show_target(dump.target)
        self.status.configure(text=f"Loaded {dump.json_path.name}")

    def _set_context(self, text: str) -> None:
        self.context_box.configure(state="normal")
        self.context_box.delete("1.0", "end")
        self.context_box.insert("1.0", text)
        self.context_box.configure(state="disabled")

    def _show_context(self, dump) -> None:
        ctx = dump.context
        lines = [
            f"failed_node: {ctx.get('failed_node')}",
            f"action:      {ctx.get('action')}",
            f"target:      {ctx.get('target')}",
            f"note:        {ctx.get('note')}",
            f"outcome:     {ctx.get('outcome')}",
            f"steps:       {ctx.get('steps')}",
            f"config:      {ctx.get('config_path')}",
            f"visited:     {' -> '.join(ctx.get('visited') or [])}",
        ]
        self._set_context("\n".join(lines))

    def _show_screenshot(self, png_path: Path) -> None:
        image = Image.open(png_path)
        width, height = image.size
        if (width, height) != EXPECTED_SIZE:
            self.size_warning.configure(
                text=f"WARNING: dump is {width}x{height}, expected 900x600 — "
                "still showing 1:1, never scaled"
            )
        # 1:1 — canvas coordinates are image coordinates. Do not scale.
        self._photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self.canvas.configure(scrollregion=(0, 0, width, height))

    def _show_target(self, target: str | None) -> None:
        self._target_photo = None
        if not target:
            self.target_label.configure(text="(none)")
            self.target_image_label.configure(image="", text="")
            return
        path = ASSETS_DIR / target
        self.target_label.configure(text=target)
        if not path.is_file():
            self.target_image_label.configure(image="", text="(file missing)")
            return
        try:
            image = Image.open(path)
            self._target_photo = ImageTk.PhotoImage(image)
            self.target_image_label.configure(image=self._target_photo, text="")
        except Exception as exc:
            self.target_image_label.configure(image="", text=f"(unreadable: {exc})")

    def _canvas_xy(self, event) -> tuple[int, int]:
        return (
            int(self.canvas.canvasx(event.x)),
            int(self.canvas.canvasy(event.y)),
        )

    def _on_press(self, event) -> None:
        if self._dump is None:
            return
        self._drag_start = self._canvas_xy(event)
        self._clear_rect()

    def _on_drag(self, event) -> None:
        if self._drag_start is None:
            return
        x0, y0 = self._drag_start
        x1, y1 = self._canvas_xy(event)
        self._clear_rect()
        self._rect_id = self.canvas.create_rectangle(
            x0, y0, x1, y1, outline="#00E5FF", width=2
        )
        left, top = min(x0, x1), min(y0, y1)
        width, height = abs(x1 - x0), abs(y1 - y0)
        self._selection = (left, top, width, height)
        self.coords_label.configure(
            text=f"selection: left={left} top={top} width={width} height={height}"
        )

    def _on_release(self, event) -> None:
        self._on_drag(event)
        self._drag_start = None

    def _clear_rect(self) -> None:
        if self._rect_id is not None:
            self.canvas.delete(self._rect_id)
            self._rect_id = None

    def save_target(self) -> None:
        if self._dump is None:
            messagebox.showerror("No dump", "Select a dump first.")
            return
        if self._selection is None:
            messagebox.showerror("No selection", "Click-drag a rectangle on the screenshot.")
            return

        try:
            crop_path = crop_target(
                self._dump.png_path,
                self._selection,
                self._dump.failed_node,
                DYNAMIC_DIR,
            )
            new_target = f"dynamic/{crop_path.name}"
            config_path = Path(self._dump.config_path)
            if not config_path.is_file():
                # Dump may record a relative path; resolve against the repo root.
                config_path = REPO_ROOT / self._dump.config_path
            old = rewrite_target(
                config_path,
                self._dump.failed_node,
                new_target,
                assets_dir=ASSETS_DIR,
            )
        except RepairError as exc:
            messagebox.showerror("Repair failed", str(exc))
            self.status.configure(text=str(exc))
            return

        msg = (
            f"Saved {crop_path.name} and rewrote {config_path}:\n"
            f"  {old!r} -> {new_target!r}\n"
            f"Review with: git diff {config_path}"
        )
        self.status.configure(text=msg)
        messagebox.showinfo("Repair applied", msg)
        self._show_target(new_target)


def main(dumps_dir: Path = DUMPS_DIR) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    app = HitlApp(dumps_dir=dumps_dir)
    app.mainloop()
