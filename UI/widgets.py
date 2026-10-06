import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt

def create_checkbox(
    text="", *, parent=None, checked=False, layout=None
):
    checkbox = QtW.QCheckBox(text, parent)

    if checked is not None:
        checkbox.setChecked(checked)

    if layout is not None:
        layout.addWidget(checkbox)

    return checkbox

def create_combobox(
    *, parent=None, max_width=300, fixed_height=25,
    tooltip="", items=None, on_index_changed=None, layout=None
):
    combo = QtW.QComboBox(parent)

    # None allows the layout to determine dimensions
    if max_width is not None:
        combo.setMaximumWidth(max_width)

    if fixed_height is not None:
        combo.setFixedHeight(fixed_height)

    combo.setSizePolicy(
        QtW.QSizePolicy.Policy.Preferred,   # Horizontal policy
        QtW.QSizePolicy.Policy.Fixed,       # Vertical policy
    )

    if tooltip:
        combo.setToolTip(tooltip)

    if items is not None:
        combo.addItems(items)

    if on_index_changed is not None:
        combo.currentIndexChanged.connect(on_index_changed)

    if layout is not None:
        layout.addWidget(combo, stretch=1)

    return combo

def create_label(
    text, *, parent=None, width=None, height=None,
    object_name=None, alignment=None, word_wrap=False,
    tooltip="", selectable=False, layout=None
):
    label = QtW.QLabel(text, parent)

    if object_name is not None:
        label.setObjectName(object_name)

    if alignment is not None:
        label.setAlignment(alignment)

    label.setWordWrap(word_wrap)

    if tooltip:
        label.setToolTip(tooltip)

    if width is not None:
        label.setFixedWidth(width)

    if height is not None:
        label.setFixedHeight(height)

    if selectable:
        label.setTextInteractionFlags(
            label.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

    if layout is not None:
        layout.addWidget(label)

    return label

def create_lineedit(
    text="", *, parent=None, placeholder="",
    max_length=None, read_only=False, enabled=True,
    tooltip="", width=None, height=None, alignment=None,
    validator=None, clear_button=False, on_text_changed=None,
    on_editing_finished=None, layout=None
):
    line_edit = QtW.QLineEdit(parent)

    if max_length is not None:
        line_edit.setMaxLength(max_length)

    # Lets individual editors supply input restrictions
    if validator is not None:
        line_edit.setValidator(validator)

    line_edit.setPlaceholderText(placeholder)
    line_edit.setReadOnly(read_only)
    line_edit.setEnabled(enabled)
    line_edit.setClearButtonEnabled(clear_button)

    if tooltip:
        line_edit.setToolTip(tooltip)

    if width is not None:
        line_edit.setFixedWidth(width)

    if height is not None:
        line_edit.setFixedHeight(height)

    if alignment is not None:
        line_edit.setAlignment(alignment)

    # Set initial text before connecting callbacks.
    line_edit.setText(text)

    if on_text_changed is not None:
        line_edit.textChanged.connect(on_text_changed)

    if on_editing_finished is not None:
        line_edit.editingFinished.connect(on_editing_finished)

    if layout is not None:
        layout.addWidget(line_edit)

    return line_edit

"""Theoretical search input (Asset Tree)

    # Might also use for Level Editor
        self.search_input = create_lineedit(
            placeholder="Search objects...",
            clear_button=True,
            on_text_changed=self.filter_objects,
            layout=toolbar_layout,
        )
"""

def create_pushbutton(
    text, *, parent=None, width=65, height=25,
    tooltip="", on_clicked=None, enabled=None,
    checkable=False, checked=False, layout=None
):
    button = QtW.QPushButton(text, parent)

    # None allows the layout to determine dimensions
    # This is not default and needs to be specified
    if width is not None:
        button.setFixedWidth(width)

    if height is not None:
        button.setFixedHeight(height)

    if tooltip:
        button.setToolTip(tooltip)

    if enabled is not None:
        button.setEnabled(enabled)

    if checkable is not None:
        button.setCheckable(checkable)

    if checkable:
        button.setChecked(checked)

    if on_clicked is not None:
        button.clicked.connect(on_clicked)

    if layout is not None:
        layout.addWidget(button)

    return button

def create_radiobutton(
    text, *, parent=None, checked=False, enabled=True,
    tooltip="", group=None, button_id=None, on_toggled=None,
    on_clicked=None, layout=None
):
    button = QtW.QRadioButton(text, parent)
    button.setEnabled(enabled)

    if tooltip:
        button.setToolTip(tooltip)

    if group is not None:
        if button_id is None:
            group.addButton(button)
        else:
            group.addButton(button, button_id)

    if layout is not None:
        layout.addWidget(button)

    # Set the initial state
    button.setChecked(checked)

    if on_toggled is not None:
        button.toggled.connect(on_toggled)

    if on_clicked is not None:
        button.clicked.connect(on_clicked)

    return button

def create_scrollarea(
    content, *, parent=None, resizable=True,
    frame_shape=QtW.QFrame.Shape.StyledPanel,
    vertical_policy=Qt.ScrollBarPolicy.ScrollBarAsNeeded,
    horizontal_policy=Qt.ScrollBarPolicy.ScrollBarAsNeeded,
    fill_background=None, tooltip="", layout=None
):
    scroll_area = QtW.QScrollArea(parent)

    scroll_area.setWidgetResizable(resizable)
    scroll_area.setFrameShape(frame_shape)
    scroll_area.setVerticalScrollBarPolicy(vertical_policy)
    scroll_area.setHorizontalScrollBarPolicy(horizontal_policy)

    if tooltip:
        scroll_area.setToolTip(tooltip)

    scroll_area.setWidget(content)

    # setWidget() enables automatic filling on the content widget,
    # so apply any explicit override afterward.
    if fill_background is not None:
        scroll_area.viewport().setAutoFillBackground(fill_background)
        content.setAutoFillBackground(fill_background)

    if layout is not None:
        layout.addWidget(scroll_area)

    return scroll_area

def create_separator(
    *, parent=None, orientation=Qt.Orientation.Horizontal,
    shadow=QtW.QFrame.Shadow.Sunken, spacing=8, layout=None
):
    separator = QtW.QFrame(parent)

    shape = (
        QtW.QFrame.Shape.HLine
        if orientation == Qt.Orientation.Horizontal
        else QtW.QFrame.Shape.VLine
    )

    separator.setFrameShape(shape)
    separator.setFrameShadow(shadow)

    if layout is not None:
        if spacing > 0:
            layout.addSpacing(spacing)

        layout.addWidget(separator)

        if spacing > 0:
            layout.addSpacing(spacing)

    return separator

def create_slider(
    *, parent=None, orientation=Qt.Orientation.Horizontal,
    minimum=0, maximum=100, value=0, single_step=1,
    page_step=10, tick_position=QtW.QSlider.TickPosition.NoTicks,
    tick_interval=0, tooltip="", enabled=True, tracking=True,
    on_value_changed=None, on_pressed=None, on_released=None, layout=None
):
    slider = QtW.QSlider(orientation, parent)

    slider.setRange(minimum, maximum)
    slider.setSingleStep(single_step)
    slider.setPageStep(page_step)
    slider.setTickPosition(tick_position)
    slider.setTickInterval(tick_interval)
    slider.setTracking(tracking)
    slider.setEnabled(enabled)

    if tooltip:
        slider.setToolTip(tooltip)

    # Set the initial value before connecting callbacks.
    slider.setValue(value)

    if on_value_changed is not None:
        slider.valueChanged.connect(on_value_changed)

    if on_pressed is not None:
        slider.sliderPressed.connect(on_pressed)

    if on_released is not None:
        slider.sliderReleased.connect(on_released)

    if layout is not None:
        layout.addWidget(slider)

    return slider

def create_spinbox(
    *, parent=None, minimum=0, maximum=99, value=0,
    single_step=1, display_base=10, prefix="", suffix="",
    tooltip="", width=None, height=None, alignment=None,
    enabled=True, read_only=False, wrapping=False,
    keyboard_tracking=True, on_value_changed=None,
    on_editing_finished=None, layout=None
):
    spinbox = QtW.QSpinBox(parent)

    spinbox.setRange(minimum, maximum)
    spinbox.setSingleStep(single_step)
    spinbox.setDisplayIntegerBase(display_base)
    spinbox.setPrefix(prefix)
    spinbox.setSuffix(suffix)
    spinbox.setEnabled(enabled)
    spinbox.setReadOnly(read_only)
    spinbox.setWrapping(wrapping)
    spinbox.setKeyboardTracking(keyboard_tracking)

    if tooltip:
        spinbox.setToolTip(tooltip)

    if width is not None:
        spinbox.setFixedWidth(width)

    if height is not None:
        spinbox.setFixedHeight(height)

    if alignment is not None:
        spinbox.setAlignment(alignment)

    # Set the initial value before connecting callbacks.
    spinbox.setValue(value)

    if on_value_changed is not None:
        spinbox.valueChanged.connect(on_value_changed)

    if on_editing_finished is not None:
        spinbox.editingFinished.connect(on_editing_finished)

    if layout is not None:
        layout.addWidget(spinbox)

    return spinbox

def create_splitter(
    widgets=(), *, parent=None, orientation=Qt.Orientation.Horizontal,
    children_collapsible=False, handle_width=8, sizes=None,
    stretch_factors=None, on_moved=None, layout=None
):
    splitter = QtW.QSplitter(orientation, parent)
    splitter.setChildrenCollapsible(children_collapsible)
    splitter.setHandleWidth(handle_width)

    for widget in widgets:
        splitter.addWidget(widget)

    # Apply these after adding the child widgets.
    if stretch_factors is not None:
        for index, factor in enumerate(stretch_factors):
            splitter.setStretchFactor(index, factor)

    if sizes is not None:
        splitter.setSizes(list(sizes))

    if on_moved is not None:
        splitter.splitterMoved.connect(on_moved)

    if layout is not None:
        layout.addWidget(splitter)

    return splitter

def create_toolbutton(
    text="", *, parent=None, icon=None, arrow_type=Qt.ArrowType.NoArrow,
    tool_button_style=Qt.ToolButtonStyle.ToolButtonTextOnly,
    auto_raise=True, checkable=False, checked=False,
    enabled=True, tooltip="", width=None, height=None,
    on_clicked=None, on_toggled=None, layout=None
):
    button = QtW.QToolButton(parent)
    button.setText(text)
    button.setToolButtonStyle(tool_button_style)
    button.setAutoRaise(auto_raise)
    button.setCheckable(checkable)
    button.setEnabled(enabled)

    if icon is not None:
        button.setIcon(icon)

    button.setArrowType(arrow_type)

    if tooltip:
        button.setToolTip(tooltip)

    if width is not None:
        button.setFixedWidth(width)

    if height is not None:
        button.setFixedHeight(height)

    # Set the initial state before connecting callbacks.
    if checkable:
        button.setChecked(checked)

    if on_clicked is not None:
        button.clicked.connect(on_clicked)

    if on_toggled is not None:
        button.toggled.connect(on_toggled)

    if layout is not None:
        layout.addWidget(button)

    return button
