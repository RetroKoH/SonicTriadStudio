# Preset themes list (Unfinished)
from PyQt6.QtGui import QPalette, QColor

THEMES = {
    "dark": {
        "primary": "#8088F8",           # ONLY used for dropbox outline (merge with box_selected)
        "bg_dark": "#181818",           # Unknown where this is used (merge with fusion_base)
        "bg_medium": "#242424",         # ONLY used for dropbox interior (merge w/ color used for widget interior)
        "bg_light": "#303030",          # Unknown where this is used
        "text_main": "#E4EEEE",         # Used with all non-header text
        "text_muted": "#B8BCC4",        # Used with header text
        "border": "#484848",            # Used only with palette box borders
        "box_selected": "#FFFFFF",      # Used for pal selection outline
        "fusion_window": "#222222",     # Window background (and widget interior; Split this off)
        "fusion_base": "#181818",       # Inner (Textbox, Scrollbar)
        "fusion_button": "#343434",     # Tab

        # Additional styling colors (add to all palettes)
        "text_heading": "#CDD0FF",
        "bg_selected": "#545767",
        "separator": "#686C74",
    },
    "light": {
        "primary": "#5058C8",
        "bg_dark": "#E0E0E0",
        "bg_medium": "#E8E8E8",
        "bg_light": "#F8F8F8",
        "text_main": "#101828",
        "text_muted": "#586068",
        "border": "#C8C8C8",
        "box_selected": "#5058C8",
        "fusion_window": "#F0F0F0",     # Window background
        "fusion_base": "#FFFFFF",       # Inner (Textbox, Scrollbar)
        "fusion_button": "#DCE0E4",     # Tab

        # Additional styling colors (add to all palettes)
        "text_heading": "#CDD0FF",
        "bg_selected": "#545767",
        "separator": "#686C74",
    },
    "ash": {
        "primary": "#A6ACFF",
        "bg_dark": "#383A3E",
        "bg_medium": "#494C52",
        "bg_light": "#55585F",
        "text_main": "#F2F3F5",
        "text_muted": "#C3C6CD",
        "border": "#686C74",
        "box_selected": "#A6ACFF",
        "fusion_window": "#414348",
        "fusion_base": "#383A3E",
        "fusion_button": "#4D5057",

        # Additional styling colors (add to all palettes)
        "text_heading": "#CDD0FF",
        "bg_selected": "#545767",
        "separator": "#686C74",
    },
}

# Reverse lookup themes dict
THEME_BY_ID = {id(v): k for k, v in THEMES.items()}

def apply_theme(app, *, set_theme=None):
    if set_theme is None:
        # Get list of theme names
        theme_names = list(THEMES)

        # Get the name of the current theme (Default: dark)
        current_name = THEME_BY_ID.get(id(app.active_theme), "dark")

        # Get both the current and next theme's index
        current_index = theme_names.index(current_name)
        next_index = (current_index + 1) % len(theme_names)

        # Get the name of the next theme to be loaded
        theme_name = theme_names[next_index]

    else:
        # Get the name of the given theme to be loaded
        theme_name = set_theme

    # Get color data (dict) of the theme to be loaded
    theme = THEMES[theme_name]

    # Global theme token
    app.active_theme = theme

    # Assign standard colors
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(theme["fusion_window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(theme["text_main"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(theme["fusion_base"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(theme["text_main"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(theme["fusion_button"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme["text_main"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(theme["primary"]))
    app.setPalette(palette)

    # The last item that uses bg_light should use a new intermediary color
    QSS = f"""
            QLabel#headerLabel {{
                color: {theme["text_muted"]};
                font-size: 18px;
                font-weight: bold;
            }}

            QLabel#infoLabel {{
                color: {theme["text_muted"]};
                font-size: 14px;
                font-weight: bold;
            }}

            QLabel#dropZone {{
                font-size: 16px;
                font-weight: bold;
                color: {theme["text_muted"]};
                border: 2px dashed {theme["primary"]};
                border-radius: 8px;
                background-color: {theme["bg_medium"]};
            }}

            QGroupBox#ControlsGroup {{
                background-color: transparent;
            }}
        """
    app.setStyleSheet(QSS)

    # Return formatted theme name to app window
    return theme_name.replace("_", " ").title()
