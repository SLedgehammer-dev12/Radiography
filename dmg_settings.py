# -*- coding: utf-8 -*-
"""dmgbuild settings for Radiography"""

import os

APP_NAME = "Radiography"
VOLUME_NAME = "Radiography 1.1.0"
APP_PATH = os.path.abspath(os.path.join("dist", "Radiography.app"))

icon = os.path.abspath("app.icns")

window_rect = ((200, 200), (500, 400))

icon_locations = {
    APP_NAME: (140, 180),
    "Applications": (360, 180),
}

applications_aliases = True

format = "UDZO"
compression_level = 9

files = [APP_PATH]
symlinks = {"Applications": "/Applications"}
