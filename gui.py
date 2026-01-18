# -*- coding: utf-8 -*-
import os
import sys
import math
import shutil
import requests
import weakref
from functools import partial
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QMessageBox,
    QFileDialog, QListWidget, QListWidgetItem,
    QVBoxLayout, QMenu, QAction
)
from PyQt5.QtGui import QMovie, QPixmap, QIcon
from PyQt5.QtCore import Qt, QPoint, QUrl, QBuffer, QByteArray, QSize
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class ExitButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__("結束程式", parent)
        self.clicked.connect(self.exit_app)
    def exit_app(self):
        QApplication.quit()

class ImportButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__("導入素材", parent)
        self.clicked.connect(self.import_asset)
    def import_asset(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "選擇素材", "", "所有素材 (*.gif *.png *.jpg *.jpeg *.bmp *.mp4)"
        )
        if not file_path:
            return
        filename = os.path.basename(file_path)
        dest_path = os.path.join("assets", filename)
        if not os.path.exists("assets"):
            os.makedirs("assets")
        shutil.copy(file_path, dest_path)
        add_asset(dest_path, 100, 100, self.parent())
        for widget in self.parent().children():
            if isinstance(widget, AssetLibrary):
                widget.refresh()

class DraggableVideo(QWidget):
    def __init__(self, video_path, x, y, parent=None):
        super().__init__(parent)
        self.offset = QPoint()
        self.setGeometry(x, y, 320, 240)

        self.video_widget = QVideoWidget(self)
        self.video_widget.setGeometry(0, 0, 320, 240)

        self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.player.setVideoOutput(self.video_widget)
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(video_path)))
        self.player.play()

        self.show()

    def mousePressEvent(self, event):
        self.offset = event.pos()

    def mouseMoveEvent(self, event):
        self.move(self.mapToParent(event.pos() - self.offset))

class AnimatedWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Animated Desktop")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.show()

class GifMenuButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__("新增 GIF", parent)
        self.clicked.connect(self.show_menu)
        self._preview_refs = []
        self._preview_map = {}  # id(preview) → movie

    def show_menu(self):
        menu = QMenu(self)
        for file in sorted(os.listdir("assets")):
            if file.lower().endswith(".gif"):
                path = os.path.join("assets", file)
                sub_menu = QMenu(file, self)

                preview_action = QAction("預覽", self)
                preview_action.triggered.connect(self.make_preview_lambda(path))
                sub_menu.addAction(preview_action)

                add_action = QAction("加入畫面", self)
                add_action.triggered.connect(self.make_add_lambda(path))
                sub_menu.addAction(add_action)

                delete_action = QAction("刪除", self)
                delete_action.triggered.connect(self.make_delete_lambda(path))
                sub_menu.addAction(delete_action)

                menu.addMenu(sub_menu)

        menu.exec_(self.mapToGlobal(self.rect().bottomLeft()))

    def make_preview_lambda(self, path):
        return lambda checked=False: self.preview_gif(path)

    def make_add_lambda(self, path):
        return lambda checked=False: self.add_gif(path)

    def make_delete_lambda(self, path):
        return lambda checked=False: self.delete_gif(path)

    def preview_gif(self, path):
        try:
            if not os.path.exists(path):
                QMessageBox.warning(self, "檔案不存在", f"找不到檔案：{path}")
                return

            movie = QMovie(path)
            movie.setCacheMode(QMovie.CacheAll)

            if not movie.isValid():
                QMessageBox.warning(self, "預覽失敗", f"無法載入 GIF：{os.path.basename(path)}")
                return

            preview = GifPreviewWindow(movie, on_close=self.cleanup_preview_refs)
            preview.setWindowTitle(os.path.basename(path))
            preview.setWindowFlags(Qt.Window)
            preview.setAttribute(Qt.WA_DeleteOnClose)
            preview.resize(300, 300)
            preview.setScaledContents(True)
            preview.setMovie(movie)
            preview.show()
            movie.start()

            self._preview_refs.append(preview)
            self._preview_map[id(preview)] = movie

            preview.destroyed.connect(lambda: self.cleanup_preview_refs(id(preview)))

        except Exception as e:
            QMessageBox.critical(self, "預覽錯誤", f"發生錯誤：{e}")

    def cleanup_preview_refs(self, preview_id):
        self._preview_map.pop(preview_id, None)
        self._preview_refs = [p for p in self._preview_refs if id(p) != preview_id]

    def add_gif(self, path):
        add_animation(path, 100, 100, self.parent())

    def delete_gif(self, path):
        reply = QMessageBox.question(
            self, "確認刪除", f"確定要刪除：{os.path.basename(path)} 嗎？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                os.remove(path)
                print("已刪除：", path)
            except Exception as e:
                print("刪除失敗：", e)

            for widget in self.parent().children():
                if isinstance(widget, AssetLibrary):
                    widget.refresh()

class GifLabel(QLabel):
    def __init__(self, movie, parent=None):
        super().__init__(parent)
        self.setMovie(movie)
        self.setScaledContents(True)
        self.resize(movie.currentImage().size())
        movie.start()

class GifPreviewWindow(QLabel):
    def __init__(self, movie, on_close=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.movie = movie
        self.on_close = on_close

    def closeEvent(self, event):
        self.movie.stop()
        if self.on_close:
            self.on_close(id(self))
        super().closeEvent(event)

class ImageLabel(QLabel):
    def __init__(self, image_path="", parent=None, movie_buffer=None):
        super().__init__(parent)
        self.image_path = image_path
        self.offset = None

        if movie_buffer:
            self.movie = QMovie()
            self.movie.setDevice(movie_buffer)
            self.setMovie(self.movie)
            self.setScaledContents(True)
            self.movie.start()
            self.movie.frameChanged.connect(self.adjust_size_from_movie)

        elif image_path:
            if image_path.lower().endswith(".gif"):
                self.movie = QMovie(image_path)
                if self.movie.isValid():
                    self.setMovie(self.movie)
                    self.setScaledContents(True)
                    self.movie.start()
                    self.movie.frameChanged.connect(self.adjust_size_from_movie)
                else:
                    self.setText("GIF 無效")
                    self.resize(200, 200)
            else:
                pixmap = QPixmap(resource_path("assets/example.gif"))
                self.setPixmap(pixmap)
                self.setScaledContents(True)
                self.resize(pixmap.size())

        else:
            self.setText("無圖片來源")
            self.resize(200, 200)

    def adjust_size_from_movie(self):
        if self.movie and self.movie.isValid():
            self.resize(self.movie.frameRect().size())
        self.movie.frameChanged.disconnect(self.adjust_size_from_movie)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if self.offset and event.buttons() & Qt.LeftButton:
            self.move(self.mapToParent(event.pos() - self.offset))

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        delete_action = QAction("刪除影像", self)
        delete_action.triggered.connect(self.delete_image)
        menu.addAction(delete_action)
        menu.exec_(event.globalPos())

    def delete_image(self):
        if hasattr(self, "movie") and self.movie:
            self.movie.stop()
            self.setMovie(None)

        if self.image_path and os.path.exists(self.image_path):
            try:
                os.remove(self.image_path)
            except Exception as e:
                print("刪除失敗：", e)

        self.deleteLater()
class ResizableDraggableImageLabel(ImageLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setScaledContents(True)
        self.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._resize_margin = 30
        self._resizing = False
        self._dragging = False
        self._resize_zone_active = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control and not event.isAutoRepeat():
            self.setStyleSheet("border: 5px dashed gray")

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control and not event.isAutoRepeat():
            self.setStyleSheet("")

    def _resize_zone(self, pos):
        dx = pos.x() - self.width()
        dy = pos.y() - 0
        distance = math.hypot(dx, dy)
        if distance < self._resize_margin:
            return "top_right"
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            zone = self._resize_zone(event.pos())
            if zone == "top_right":
                self._resizing = True
                self._dragging = False
                self._resize_zone_active = zone
                self._start_size = self.size()
                self._start_pos = event.pos()
                self._start_bottom_y = self.y() + self.height()
            else:
                self._dragging = True
                self._drag_offset = event.pos()
                self._resizing = False
                self._resize_zone_active = None

    def mouseMoveEvent(self, event):
        if self._resizing and self._resize_zone_active == "top_right":
            aspect_ratio = self._start_size.width() / self._start_size.height()

            dx = event.pos().x() - self._start_pos.x()
            dy = self._start_pos.y() - event.pos().y()

            if abs(dx) > abs(dy):
                new_width = self._start_size.width() + dx
                new_height = new_width / aspect_ratio
            else:
                new_height = self._start_size.height() + dy
                new_width = new_height * aspect_ratio

            min_size = 50
            max_size = 2000
            new_width = int(max(min_size, min(max_size, new_width)))
            new_height = int(max(min_size, min(max_size, new_height)))

            new_y = self._start_bottom_y - new_height
            new_x = self.x()

            self.move(new_x, new_y)
            self.resize(int(new_width), int(new_height))

        elif self._dragging:
            new_pos = self.mapToParent(event.pos() - self._drag_offset)
            self.move(new_pos)

        else:
            zone = self._resize_zone(event.pos())
            if zone == "top_right":
                self.setCursor(Qt.SizeBDiagCursor)
            else:
                self.setCursor(Qt.OpenHandCursor)

    def mouseReleaseEvent(self, event):
        self._resizing = False
        self._dragging = False
        self._resize_zone_active = None
        self.setCursor(Qt.ArrowCursor)

class AssetLibrary(QWidget):
    def __init__(self, asset_folder, parent=None):
        super().__init__(parent)
        self.setWindowTitle("assets")
        self.setGeometry(1, 1, 1, 1)

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(100, 100))

        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        self.setLayout(layout)

        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.list_widget.itemClicked.connect(self.asset_selected)

        self.load_assets(asset_folder)

    def refresh(self):
        self.load_assets("assets")

    def get_preview_pixmap(self, path):
        full_path = resource_path(path)
        try:
            if full_path.lower().endswith(".gif"):
                movie = QMovie(full_path)
                if movie.isValid():
                    movie.jumpToFrame(0)
                    return movie.currentPixmap()
            elif full_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                return QPixmap(full_path)
            elif full_path.lower().endswith(".mp4"):
                return QPixmap(resource_path("icons/video_icon.png"))
        except Exception as e:
            print("預覽載入失敗：", e)
        return QPixmap()

    def load_assets(self, folder):
        self.list_widget.clear()
        folder = resource_path(folder)  # ✅ 加入這行

        for file in sorted(os.listdir(folder)):
            path = os.path.join(folder, file)
            ext = os.path.splitext(file)[1].lower()
            if ext in (".gif", ".png", ".jpg", ".jpeg", ".bmp", ".mp4"):
                item = QListWidgetItem(file)
                item.setData(Qt.UserRole, path)

                pixmap = self.get_preview_pixmap(path)
                if not pixmap.isNull():
                    icon = QIcon(pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    item.setIcon(icon)
                    item.setToolTip(f"{file}\n尺寸：{pixmap.width()}x{pixmap.height()}")

                self.list_widget.addItem(item)

    def asset_selected(self, item):
        path = item.data(Qt.UserRole)
        add_asset(path, 100, 100, self.parent())

    def show_context_menu(self, pos):
        list_pos = self.list_widget.mapFrom(self, pos)
        item = self.list_widget.itemAt(list_pos)

        if item:
            path = item.data(Qt.UserRole)
            print("右鍵點擊素材：", os.path.basename(path))

            menu = QMenu(self)
            delete_action = QAction("刪除素材", self)
            delete_action.triggered.connect(lambda: self.delete_asset(item))
            menu.addAction(delete_action)
            menu.exec_(self.list_widget.mapToGlobal(list_pos))
        else:
            print("右鍵點擊空白區域")

    def delete_asset(self, item):
        path = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "確認刪除", f"確定要刪除素材：{os.path.basename(path)} 嗎？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print("刪除失敗：", e)
            self.list_widget.takeItem(self.list_widget.row(item))
def select_animation():
    file_path, _ = QFileDialog.getOpenFileName(
        None, "選擇動畫素材", "", "GIF Files (*.gif);;MP4 Files (*.mp4)"
    )
    return file_path

def add_asset(path, x, y, parent):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gif":
        add_animation(path, x, y, parent)
    elif ext in (".png", ".jpg", ".jpeg", ".bmp"):
        add_image(path, x, y, parent)
    elif ext == ".mp4":
        add_video(path, x, y, parent)

def add_animation(path, x, y, parent):
    label = ResizableDraggableImageLabel(path, parent)
    label.move(x, y)
    label.show()

def add_image(path, x, y, parent):
    full_path = resource_path(path)
    label = ImageLabel(full_path, parent)
    pixmap = QPixmap(full_path)

    if pixmap.isNull():
        print("圖片載入失敗：", full_path)
        return

    scaled = pixmap.scaled(600, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    label.setPixmap(scaled)
    label.setFixedSize(scaled.size())
    label.move(x, y)
    label.show()

def add_video(path, x, y, parent):
    video = DraggableVideo(path, x, y, parent)
    video.show()

def add_online_gif(url, x, y, parent):
    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            print("GIF 載入失敗：", url)
            return

        gif_data = QByteArray(response.content)
        buffer = QBuffer()
        buffer.setData(gif_data)
        buffer.open(QBuffer.ReadOnly)

        label = ImageLabel("", parent, movie_buffer=buffer)
        label.move(x, y)
        label.show()
    except Exception as e:
        print("線上 GIF 載入錯誤：", e)