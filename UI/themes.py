# Preset themes list (Unfinished)
from PyQt6.QtGui import QPalette, QColor

THEMES = {
    "Dark": {
        "highlight": "#8088F8",         # Used for text highlight
        "outline": "#8088F8",           # Dropbox outline and box_selected (UNUSED ATM)
        "interior": "#181818",          # Widget interior (Scroll area, dropbox interior)
        "text_main": "#E4EEEE",         # Used with all non-header text
        "text_header": "#B8BCC4",       # Used with header text
        "box_border": "#484848",        # Used only with palette box borders
        "background": "#222222",        # Window background
        "fusion_base": "#1C1C1C",       # Inner (Textbox, Scrollbar, Asset Tree)
        "fusion_button": "#343434",     # Tab and buttons (Maybe split these off?)

        # Additional styling colors (add to all palettes)
        "bg_selected": "#545767",
        "separator": "#686C74",
    },
    "Light": {
        "highlight": "#5058C0",
        "outline": "#5058C0",
        "interior": "#F8F8F8",
        "text_main": "#101828",
        "text_header": "#586068",
        "box_border": "#989898",
        "background": "#EAEAEA",
        "fusion_base": "#FFFFFF",
        "fusion_button": "#DCE0E4",

        # Additional styling colors (add to all palettes)
        "bg_selected": "#545767",
        "separator": "#686C74",
    },
    "Ash": {
        "highlight": "#A6ACFF",
        "outline": "#A6ACFF",
        "interior": "#383A3E",
        "text_main": "#F2F3F5",
        "text_header": "#C3C6DD",
        "box_border": "#686C74",
        "background": "#404146",
        "fusion_base": "#383A3E",
        "fusion_button": "#4D5056",

        # Additional styling colors (add to all palettes)
        "bg_selected": "#545767",
        "separator": "#686C74",
    },
    "SSRG": {
        "highlight": "#3266D1",
        "outline": "#3266D1",
        "interior": "#F0F7FC",
        "text_main": "#031971",
        "text_header": "#062E82",
        "box_border": "#686C74",
        "background": "#E7E7FF",
        "fusion_base": "#F5F8FB",
        "fusion_button": "#DDF0FC",

        # Additional styling colors (add to all palettes)
        "bg_selected": "#545767",
        "separator": "#686C74",
    },
    "Sonic Retro": {
        "highlight": "#3266D1",
        "outline": "#CFDF00",
        "interior": "#181818",
        "text_main": "#E4EEEE",
        "text_header": "#CFDF00",
        "box_border": "#484848",
        "background": "#181818",
        "fusion_base": "#1C1C1C",
        "fusion_button": "#303018",

        # Additional styling colors (add to all palettes)
        "bg_selected": "#545767",
        "separator": "#686C74",
    },
    "Frost Mint": {
        "highlight": "#7FCAB2",
        "outline": "#48AD8B",
        "interior": "#F8FAFC",
        "text_main": "#102818",
        "text_header": "#2D9C7B",
        "box_border": "#989898",
        "background": "#F6FCFB",
        "fusion_base": "#FFFFFF",
        "fusion_button": "#DEF4ED",

        # Additional styling colors (add to all palettes)
        "bg_selected": "#545767",
        "separator": "#686C74",
    },
}

# Reverse lookup themes dict
THEME_BY_ID = {id(v): k for k, v in THEMES.items()}

def apply_theme(app, *, set_theme=None):
    """
    Change the color theme used in the app.

    Returns theme name for the button in the tab bar.
    """
    # Simply advance to the next theme in the list
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
    palette.setColor(QPalette.ColorRole.Window, QColor(theme["background"]))        # Window background
    palette.setColor(QPalette.ColorRole.WindowText, QColor(theme["text_main"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(theme["fusion_base"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(theme["text_main"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(theme["fusion_button"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme["text_main"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(theme["highlight"]))
    app.setPalette(palette)

    # QWidget#interior: This will change the BG of the palette window to match lineedit
    QSS = f"""
            QLabel#headerLabel {{
                color: {theme["text_header"]};
                font-size: 18px;
                font-weight: bold;
            }}

            QLabel#infoLabel {{
                color: {theme["text_header"]};
                font-size: 14px;
                font-weight: bold;
            }}
            
            QWidget#interior {{
                background-color: {theme["interior"]};
            }}

            QLabel#dropZone {{
                font-size: 16px;
                font-weight: bold;
                color: {theme["text_header"]};
                border: 2px dashed {theme["highlight"]};
                border-radius: 8px;
                background-color: {theme["interior"]};
            }}

            QGroupBox#ControlsGroup {{
                background-color: transparent;
            }}
        """
    app.setStyleSheet(QSS)

    # Return formatted theme name to app window
    return theme_name
