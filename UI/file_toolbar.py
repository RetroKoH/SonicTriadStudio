import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt

from UI.widgets import create_pushbutton

def create_file_toolbar(dropdown, unsaved_label, *, resource_name="file", unsaved_changes=False,
    on_new=None, on_load=None, on_save=None, on_save_as=None, on_remove=None, extra_widgets=()
):
    """
    Shared file toolbar constructor for all editors (Dropdown and file buttons).

    The reason this is a function, and CollapsiblePanel is a class, is because
    this is purely a constructor, whereas the panel is a collection that manages
    a state, and the ongoing behavior while in that state.

    Returns:
        QHBoxLayout (toolbar; Contains ComboBox and PushButtons)
    """
    toolbar = QtW.QHBoxLayout()
    toolbar.setSpacing(4)
    toolbar.setAlignment(Qt.AlignmentFlag.AlignLeft)

    # Asset Dropdown
    toolbar.addWidget(dropdown, stretch=1)

    # File Buttons
    button_specs = (
        ("New", f"Create a new {resource_name}", on_new),
        ("Load", f"Load {resource_name} data", on_load),
        ("Save", f"Save the current {resource_name}", on_save),
        ("Save As...", f"Save {resource_name} data to another file", on_save_as),
        ("Remove", f"Remove the current {resource_name} from the project", on_remove),
    )
    for text, tooltip, callback in button_specs:
        button = create_pushbutton(text, tooltip=tooltip, layout=toolbar)
        if callback is not None:
            button.clicked.connect(callback)

    # Unsaved Changes (dirty flag) label
    toolbar.addWidget(unsaved_label)
    unsaved_label.setVisible(unsaved_changes)

    # Extra widgets, if applicable (most likely a format/setting label)
    for index, widget in enumerate(extra_widgets):
        if index == 0:
            toolbar.addSpacing(12)
        toolbar.addWidget(widget)

    toolbar.addStretch()
    return toolbar