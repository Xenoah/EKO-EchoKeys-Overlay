import sys
import threading
import time
from dataclasses import dataclass, field
from typing import List, Set

from PySide6.QtCore import Qt, QTimer, QPoint, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QPushButton,
    QSizePolicy,
)

import keyboard  # グローバルキーフック


# ==== 表示する1件分（1コンボ）の情報 ====

@dataclass
class KeyCap:
    text: str
    created_at: float = field(default_factory=time.time)


# ==== 移動ボタン ====

class MoveButton(QPushButton):
    def __init__(self, window: "KeyOverlayWindow"):
        super().__init__("⤧")
        self.window = window
        self.setFixedSize(24, 24)
        self.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: rgba(255, 255, 255, 40);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 150);
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 80);
            }
        """)
        self.setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)
            self.window.start_move(event.globalPos())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.window.update_move(event.globalPos())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.OpenHandCursor)
            self.window.end_move()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


# ==== リサイズボタン（縦横） ====

class ResizeButton(QPushButton):
    def __init__(self, window: "KeyOverlayWindow"):
        super().__init__("↕↔")
        self.window = window
        self.setFixedSize(24, 24)
        self.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: rgba(255, 255, 255, 40);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 150);
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 80);
            }
        """)
        self.setCursor(Qt.SizeFDiagCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window.start_resize(event.globalPos())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.window.update_resize(event.globalPos())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window.end_resize()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


# ==== メインのオーバーレイウィンドウ ====

class KeyOverlayWindow(QWidget):
    key_received = Signal(str)  # スレッド間転送

    def __init__(self):
        super().__init__()

        # 状態
        self.keycaps: List[KeyCap] = []
        self.display_lifetime = 10.0
        self._max_history = 10
        self.number_merge_timeout = 0.8

        # 高さ固定
        self.history_row_height = 28
        self.latest_row_height = self.history_row_height * 2

        # ドラッグ
        self._dragging = False
        self._drag_offset = QPoint()

        # リサイズ
        self._resizing = False
        self._resize_start_pos = QPoint()
        self._resize_start_width = 0
        self._resize_start_height = 0
        self._min_width = 200
        self._min_height = 160

        # ウィンドウ設定
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # 初期位置
        screen = QGuiApplication.primaryScreen().geometry()
        w, h = 420, 300
        x = (screen.width() - w) // 2
        y = screen.height() - h - 60
        self.setGeometry(x, y, w, h)

        # ----------------------------------------------------
        # レイアウト
        # ----------------------------------------------------
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 6)
        outer.setSpacing(2)

        # --- 上：操作ボタン行 ---
        btns = QHBoxLayout()
        btns.setContentsMargins(0, 0, 0, 0)
        btns.setSpacing(4)

        self.move_btn = MoveButton(self)
        self.resize_btn = ResizeButton(self)

        self.exit_btn = QPushButton("X")
        self.exit_btn.setFixedSize(24, 24)
        self.exit_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: rgba(255, 70, 70, 200);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 180);
            }
            QPushButton:hover {
                background-color: rgba(255, 120, 120, 240);
            }
        """)
        self.exit_btn.clicked.connect(QApplication.instance().quit)

        btns.addWidget(self.move_btn)
        btns.addWidget(self.resize_btn)
        btns.addWidget(self.exit_btn)
        btns.addStretch()

        # --- 下：キー履歴 ---
        self.history_layout = QVBoxLayout()
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(0)

        history_container = QWidget()
        history_container.setLayout(self.history_layout)
        history_container.setAttribute(Qt.WA_TranslucentBackground, True)

        outer.addLayout(btns)
        outer.addWidget(history_container, 1)

        # 背景
        self.setStyleSheet("""
            QWidget#KeyOverlayRoot {
                background-color: rgba(20, 20, 20, 160);
                border-radius: 10px;
            }
        """)
        self.setObjectName("KeyOverlayRoot")

        # 古いログ削除タイマー
        self.cleanup_timer = QTimer()
        self.cleanup_timer.setInterval(100)
        self.cleanup_timer.timeout.connect(self.cleanup_old_keys)
        self.cleanup_timer.start()

        self.key_received.connect(self.on_key_received)

    # ----------------------------------------------------
    # 移動
    # ----------------------------------------------------

    def start_move(self, gpos):
        self._dragging = True
        self._drag_offset = gpos - self.frameGeometry().topLeft()

    def update_move(self, gpos):
        if self._dragging:
            self.move(gpos - self._drag_offset)

    def end_move(self):
        self._dragging = False

    # ----------------------------------------------------
    # リサイズ（縦横）
    # ----------------------------------------------------

    def start_resize(self, gpos):
        self._resizing = True
        self._resize_start_pos = gpos
        self._resize_start_width = self.width()
        self._resize_start_height = self.height()

    def update_resize(self, gpos):
        if not self._resizing:
            return
        dx = gpos.x() - self._resize_start_pos.x()
        dy = gpos.y() - self._resize_start_pos.y()

        w = max(self._min_width, self._resize_start_width + dx)
        h = max(self._min_height, self._resize_start_height + dy)

        self.setGeometry(self.x(), self.y(), w, h)

    def end_resize(self):
        self._resizing = False

    # ----------------------------------------------------
    # キー入力
    # ----------------------------------------------------

    @Slot(str)
    def on_key_received(self, text):
        self.add_key(text)

    def add_key(self, text):
        if not text:
            return

        now = time.time()

        # 数字連結
        if text.isdigit() and self.keycaps:
            last = self.keycaps[-1]
            if last.text.isdigit() and (now - last.created_at) < self.number_merge_timeout:
                last.text += text
                last.created_at = now
                self.refresh_view()
                return

        self.keycaps.append(KeyCap(text=text, created_at=now))

        if len(self.keycaps) > self._max_history:
            self.keycaps = self.keycaps[-self._max_history:]

        self.refresh_view()

    # ----------------------------------------------------
    # 古いの消す
    # ----------------------------------------------------

    def cleanup_old_keys(self):
        now = time.time()
        before = len(self.keycaps)
        self.keycaps = [kc for kc in self.keycaps if (now - kc.created_at) <= self.display_lifetime]
        if len(self.keycaps) != before:
            self.refresh_view()

    # ----------------------------------------------------
    # 表示更新（枠くっつける・上詰め）
    # ----------------------------------------------------

    def refresh_view(self):
        # 全消去
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self.keycaps:
            return

        # 最新が一番上
        for idx, kc in enumerate(reversed(self.keycaps)):
            is_latest = (idx == 0)

            lbl = QLabel(kc.text)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            if is_latest:
                lbl.setFixedHeight(self.latest_row_height)
                lbl.setStyleSheet("""
                    QLabel {
                        color: white;
                        background-color: rgba(80, 160, 255, 230);
                        border: 2px solid rgba(255,255,255,220);
                        border-radius: 6px;
                        padding: 2px 8px;
                        font-size: 15pt;
                        font-weight: bold;
                        qproperty-alignment: 'AlignCenter';
                    }
                """)
            else:
                lbl.setFixedHeight(self.history_row_height)
                lbl.setStyleSheet("""
                    QLabel {
                        color: white;
                        background-color: rgba(40,40,40,220);
                        border: 2px solid rgba(255,255,255,100);
                        border-radius: 6px;
                        padding: 2px 8px;
                        font-size: 13pt;
                        qproperty-alignment: 'AlignCenter';
                    }
                """)

            row = QWidget()
            rlay = QHBoxLayout()
            rlay.setContentsMargins(0, 0, 0, 0)
            rlay.setSpacing(0)
            rlay.addWidget(lbl)
            row.setLayout(rlay)
            row.setAttribute(Qt.WA_TranslucentBackground, True)

            self.history_layout.addWidget(row)

        self.update()

    # ----------------------------------------------------
    # ウィンドウ本体の移動
    # ----------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_move(event.globalPos())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and (event.buttons() & Qt.LeftButton):
            self.update_move(event.globalPos())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.end_move()
            event.accept()


# ==== キー名 → 表示名 ====

def normalize_key_name(name: str) -> str:
    if not name:
        return ""

    name = name.lower()

    special = {
        "space": "Space",
        "enter": "Enter",
        "tab": "Tab",
        "esc": "Esc",
        "up": "↑",
        "down": "↓",
        "left": "←",
        "right": "→",
        "delete": "Del",
        "backspace": "BS",
        "shift": "Shift",
        "ctrl": "Ctrl",
        "alt": "Alt",
        "left windows": "Win",
        "right windows": "Win",
    }

    if name in special:
        return special[name]

    if len(name) == 1:
        return name.upper()

    if name.startswith("f") and name[1:].isdigit():
        return name.upper()

    return name


# ==== キーフック ====

def start_key_listener(window: KeyOverlayWindow):

    MOD_KEYS = {"ctrl", "shift", "alt"}
    pressed_mod = set()

    def on_event(event):
        try:
            name = event.name
            if not name:
                return

            low = name.lower()

            if event.event_type == "down":
                if low in MOD_KEYS:
                    pressed_mod.add(low)
                    return

                # コンボ構築
                label = normalize_key_name(name)
                mods = [normalize_key_name(m) for m in ["ctrl", "shift", "alt"] if m in pressed_mod]
                combo = " + ".join(mods + [label])
                window.key_received.emit(combo)

            elif event.event_type == "up":
                if low in pressed_mod:
                    pressed_mod.remove(low)

        except:
            pass

    keyboard.hook(on_event)
    keyboard.wait()


# ==== エントリーポイント ====

def main():
    app = QApplication(sys.argv)
    win = KeyOverlayWindow()
    win.show()

    t = threading.Thread(target=start_key_listener, args=(win,), daemon=True)
    t.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
