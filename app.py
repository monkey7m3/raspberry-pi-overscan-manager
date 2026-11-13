"""GTK3 interface for Raspberry Pi Overscan Manager."""
import subprocess
from pathlib import Path
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from backend import EDGES, discover, load_settings, save_settings, validate_margins

class Window(Gtk.Window):
    def __init__(self):
        super().__init__(title="Raspberry Pi Overscan Manager")
        self.set_default_size(610, 400)
        self.set_border_width(18)
        self.connect("destroy", Gtk.main_quit)
        self.outputs = discover()
        self.settings = load_settings()
        self.spins = {}
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(box)
        title = Gtk.Label(label="Display margin adjustment", xalign=0)
        title.get_style_context().add_class("title")
        box.pack_start(title, False, False, 0)
        note = Gtk.Label(label="Reboot-based KMS changes only; live preview and automatic rollback are not implemented.", xalign=0)
        note.set_line_wrap(True)
        box.pack_start(note, False, False, 0)
        self.selector = Gtk.ComboBoxText()
        box.pack_start(self.selector, False, False, 0)
        self.selector.connect("changed", self.changed)
        grid = Gtk.Grid(column_spacing=14, row_spacing=10)
        box.pack_start(grid, False, False, 0)
        for index, edge in enumerate(EDGES):
            grid.attach(Gtk.Label(label=edge.title(), xalign=0), 0, index, 1, 1)
            spin = Gtk.SpinButton.new_with_range(0, 100, 1)
            grid.attach(spin, 1, index, 1, 1)
            self.spins[edge] = spin
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        box.pack_start(self.status, False, False, 0)
        actions = Gtk.Box(spacing=8)
        box.pack_end(actions, False, False, 0)
        self.save = Gtk.Button(label="Save draft")
        self.save.connect("clicked", self.save_draft)
        actions.pack_start(self.save, False, False, 0)
        self.apply = Gtk.Button(label="Apply at next reboot…")
        self.apply.connect("clicked", self.apply_boot)
        actions.pack_start(self.apply, False, False, 0)
        diagnostic = Gtk.Button(label="Export diagnostics…")
        diagnostic.connect("clicked", self.export_diagnostics)
        actions.pack_start(diagnostic, False, False, 0)
        probe = Gtk.Button(label="Probe live access…")
        probe.connect("clicked", self.export_live_probe)
        actions.pack_start(probe, False, False, 0)
        audit = Gtk.Button(label="Export boot audit…")
        audit.connect("clicked", self.export_boot_audit)
        actions.pack_start(audit, False, False, 0)
        refresh = Gtk.Button(label="Refresh")
        refresh.connect("clicked", self.refresh)
        actions.pack_start(refresh, False, False, 0)
        self.refresh()

    def selected(self):
        index = self.selector.get_active()
        return self.outputs[index] if 0 <= index < len(self.outputs) else None

    def changed(self, *_):
        output = self.selected()
        if output is None:
            return
        margins = output["margins"]
        supported = len(margins) == 4
        saved = self.settings.get(output["name"], {})
        for edge in EDGES:
            spin = self.spins[edge]
            if supported:
                prop = margins[edge]
                spin.set_range(prop.low, prop.high)
                spin.set_value(saved.get(edge, prop.value))
            spin.set_sensitive(supported)
        self.save.set_sensitive(supported)
        self.apply.set_sensitive(supported)
        self.status.set_text(
            "Four independent KMS margins found. Applying changes requires a reboot."
            if supported else "This connector does not expose all four DRM/KMS margin properties."
        )

    def values(self):
        return validate_margins(
            {edge: self.spins[edge].get_value_as_int() for edge in EDGES},
            self.selected()["margins"]
        )

    def save_draft(self, *_):
        output = self.selected()
        if output is not None:
            self.settings[output["name"]] = self.values()
            save_settings(self.settings)
            self.status.set_text("Draft saved locally. Display settings unchanged.")

    def message(self, text, kind=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK):
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0, message_type=kind, buttons=buttons, text=text
        )
        response = dialog.run()
        dialog.destroy()
        return response

    def apply_boot(self, *_):
        output = self.selected()
        if not output or len(output["margins"]) != 4:
            return
        values = self.values()
        detail = ", ".join(f"{e}={values[e]}" for e in EDGES)
        response = self.message(
            f"Apply boot margins for {output['name']}?\n\n{detail}\n\n"
            "This modifies /boot/firmware/cmdline.txt with administrator authorization "
            "and makes a backup. A reboot is required. There is no automatic rollback, "
            "and a compositor may override the margins.",
            Gtk.MessageType.QUESTION, Gtk.ButtonsType.OK_CANCEL
        )
        if response != Gtk.ResponseType.OK:
            return
        cmd = [
            "pkexec", "/usr/bin/python3",
            "/usr/lib/raspberry-pi-overscan-manager/boot_helper.py",
            "--connector", output["name"],
        ]
        for e in EDGES:
            cmd += ["--" + e, str(values[e])]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.message(str(exc), Gtk.MessageType.ERROR)
            return
        if result.returncode != 0:
            self.message(
                result.stderr or result.stdout or "Authorization cancelled",
                Gtk.MessageType.ERROR
            )
            return
        self.save_draft()
        self.message("Boot configuration updated. Reboot to test.\n" + result.stdout)

    def export_diagnostics(self, *_):
        dialog = Gtk.FileChooserDialog(
            title="Save read-only display diagnostics", transient_for=self,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )
        dialog.set_current_name("overscan-diagnostics.json")
        dialog.set_do_overwrite_confirmation(True)
        response = dialog.run()
        filename = dialog.get_filename() if response == Gtk.ResponseType.OK else None
        dialog.destroy()
        if not filename:
            return
        try:
            from diagnostics import gather
            import json
            Path(filename).write_text(json.dumps(gather(), indent=2) + "\n")
            self.message("Read-only diagnostics saved to:\n" + filename)
        except (OSError, ValueError) as exc:
            self.message(str(exc), Gtk.MessageType.ERROR)

    def export_live_probe(self, *_):
        import json
        from live_probe import gather
        dialog = Gtk.FileChooserDialog(
            title="Save read-only live access probe", transient_for=self,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )
        dialog.set_current_name("overscan-live-probe.json")
        dialog.set_do_overwrite_confirmation(True)
        response = dialog.run()
        filename = dialog.get_filename() if response == Gtk.ResponseType.OK else None
        dialog.destroy()
        if filename:
            try:
                Path(filename).write_text(json.dumps(gather(), indent=2) + "\n")
                self.message("Read-only probe saved to:\n" + filename)
            except OSError as exc:
                self.message(str(exc), Gtk.MessageType.ERROR)

    def export_boot_audit(self, *_):
        import json
        from boot_audit import gather
        dialog = Gtk.FileChooserDialog(
            title="Save read-only boot margin audit", transient_for=self,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )
        dialog.set_current_name("overscan-boot-audit.json")
        dialog.set_do_overwrite_confirmation(True)
        response = dialog.run()
        filename = dialog.get_filename() if response == Gtk.ResponseType.OK else None
        dialog.destroy()
        if filename:
            try:
                Path(filename).write_text(json.dumps(gather(), indent=2) + "\n")
                self.message("Read-only boot audit saved to:\n" + filename)
            except OSError as exc:
                self.message(str(exc), Gtk.MessageType.ERROR)

    def refresh(self, *_):
        self.outputs = discover()
        self.selector.remove_all()
        for output in self.outputs:
            suffix = "" if len(output["margins"]) == 4 else " (unsupported)"
            self.selector.append_text(output["name"] + suffix)
        if self.outputs:
            self.selector.set_active(0)
        else:
            self.status.set_text("No connected DRM outputs detected.")
            self.save.set_sensitive(False)
            self.apply.set_sensitive(False)

if __name__ == "__main__":
    Window().show_all()
    Gtk.main()
