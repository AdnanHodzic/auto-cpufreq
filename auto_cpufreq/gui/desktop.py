"""Desktop integration shared by GTK dialogs and the main window.

Use the registered URI handler rather than assuming Nemo, Nautilus, Dolphin,
or another specific file manager. No privileged operations are performed.
"""
from pathlib import Path

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk


def open_containing_folder(parent, file_path, *, missing_hint=None):
    """Open a file's parent folder, reporting unsupported or missing paths.

    The optional hint provides contextual help (for instance, a debug log
    directory that has not yet been created).
    """
    directory = Path(file_path).expanduser().absolute().parent
    try:
        if not directory.is_dir():
            message = f"Directory does not exist: {directory}"
            if missing_hint:
                message += f"\n{missing_hint}"
            raise FileNotFoundError(message)
        if not Gtk.show_uri_on_window(
            parent, directory.as_uri(), Gdk.CURRENT_TIME
        ):
            raise OSError("No application could open the directory")
    except (OSError, GLib.Error) as error:
        dialog = Gtk.MessageDialog(
            transient_for=parent,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text="Unable to open folder",
        )
        dialog.format_secondary_text(str(error))
        dialog.set_destroy_with_parent(True)
        dialog.connect("response", lambda widget, _response: widget.destroy())
        dialog.show_all()
        return False
    return True
