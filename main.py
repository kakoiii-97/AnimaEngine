# -*- coding: utf-8 -*-
import sys
import os
import pygame
from PyQt5.QtWidgets import QApplication
from gui import (
    AnimatedWindow, ImportButton, AssetLibrary,
    add_animation, ImageLabel, GifMenuButton, ExitButton
)
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AnimatedWindow()
    window.show()

    asset_folder = resource_path("assets")
    library = AssetLibrary(asset_folder, parent=window)
    library.show()

    menu_button = GifMenuButton(window)
    menu_button.move(20, 20)
    menu_button.show()

    import_button = ImportButton(window)
    import_button.move(20, 60)
    import_button.show()

    exit_button = ExitButton(window)
    exit_button.move(20, 100)
    exit_button.show()

    image_path = resource_path("assets/img-resources.jpg")
    label = ImageLabel(image_path, parent=window)
    label.move(100, 100)
    label.show()

    sys.exit(app.exec_())