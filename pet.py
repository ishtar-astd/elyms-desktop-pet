import math
import sys
from pathlib import Path

from PyQt5.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QCursor, QFont, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QApplication, QMenu, QMessageBox, QWidget

from chat_window import ChatWindow


class ElymsPet(QWidget):
    CALL_SECONDS = 2.7
    SIZES = (('小', 155), ('中', 220), ('大', 300))

    def __init__(self, image):
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle('曳尔沐桌宠')
        self.setCursor(Qt.OpenHandCursor)
        self.image = image
        self.press_point = None
        self.dragging = False
        self.call_started = -self.CALL_SECONDS
        self.chat_window = None
        self.clock = QElapsedTimer()
        self.clock.start()
        self.set_pet_height(220)
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 24, area.bottom() - self.height() - 16)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(33)

    def set_pet_height(self, height):
        old_corner = self.geometry().bottomRight()
        self.pet_height = height
        self.pet_width = round(self.image.width() * height / self.image.height())
        self.sprite = self.image.scaledToHeight(height * 2, Qt.SmoothTransformation)
        self.setFixedSize(max(170, self.pet_width + 34), height + 61)
        if self.isVisible():
            screen = QApplication.screenAt(old_corner) or QApplication.primaryScreen()
            area = screen.availableGeometry()
            x = max(area.left(), min(old_corner.x() - self.width() + 1, area.right() - self.width() + 1))
            y = max(area.top(), min(old_corner.y() - self.height() + 1, area.bottom() - self.height() + 1))
            self.move(x, y)

    def paintEvent(self, event):
        now = self.clock.elapsed() / 1000
        elapsed = now - self.call_started
        bob = 0 if self.dragging else 1.7 * math.sin(now * 2.5)
        angle = 0
        if elapsed < 0.7 and not self.dragging:
            phase = elapsed / 0.7
            bob -= 11 * math.sin(phase * math.pi)
            angle = 4 * math.sin(phase * math.tau * 2) * (1 - phase)

        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        painter.save()
        painter.translate(self.width() / 2, 48 + self.pet_height + bob)
        painter.rotate(angle)
        target = QRectF(-self.pet_width / 2, -self.pet_height, self.pet_width, self.pet_height)
        painter.drawPixmap(target, self.sprite, QRectF(self.sprite.rect()))
        painter.restore()
        if elapsed < self.CALL_SECONDS:
            self.paint_call(painter, elapsed)
        painter.end()

    def paint_call(self, painter, elapsed):
        painter.setOpacity(min(1.0, elapsed / 0.14, (self.CALL_SECONDS - elapsed) / 0.32))
        bubble = QRectF((self.width() - 148) / 2, 5, 148, 32)
        painter.setPen(QPen(QColor('#6865a6'), 1.5))
        painter.setBrush(QColor('#f2edff'))
        painter.drawRoundedRect(bubble, 14, 14)

        painter.setPen(QColor('#352d67'))
        font = QFont(painter.font())
        font.setPixelSize(14)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        caption = '曳尔沐来电…' if elapsed < 0.82 else '接通！我到啦'
        painter.drawText(bubble.adjusted(25, 0, -6, 0), Qt.AlignCenter, caption)

        painter.setPen(Qt.NoPen)
        for index in range(3):
            height = 4 + index * 3
            active = index <= int(elapsed * 8) % 3 or elapsed >= 0.82
            painter.setBrush(QColor('#6a61c6' if active else '#cfc5ec'))
            bar = QRectF(bubble.left() + 11 + index * 5, 27 - height, 3, height)
            painter.drawRoundedRect(bar, 1, 1)

        if elapsed < 1.0:
            painter.setOpacity(math.sin(elapsed * math.pi))
            pen = QPen(QColor('#a393fb'), 2.0)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            x = self.width() - 22
            y = 92 - 15 * elapsed
            painter.drawLine(QPointF(x - 5, y), QPointF(x + 5, y))
            painter.drawLine(QPointF(x, y - 5), QPointF(x, y + 5))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.press_point = event.globalPos()
            self.press_window = self.pos()
            self.dragging = False
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.press_point is None:
            return
        delta = event.globalPos() - self.press_point
        if self.dragging or delta.manhattanLength() >= QApplication.startDragDistance():
            self.dragging = True
            self.move(self.press_window + delta)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self.press_point is None:
            return
        if not self.dragging:
            self.play_call()
        self.press_point = None
        self.dragging = False
        self.setCursor(Qt.OpenHandCursor)

    def play_call(self):
        self.call_started = self.clock.elapsed() / 1000

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.open_chat()

    def open_chat(self):
        if self.chat_window is None:
            self.chat_window = ChatWindow(self.play_call)
            QApplication.instance().aboutToQuit.connect(self.chat_window.close)
        self.chat_window.show()
        self.chat_window.raise_()
        self.chat_window.activateWindow()
        self.chat_window.entry.setFocus()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction('和曳尔沐聊天', self.open_chat)
        menu.addSeparator()
        size_menu = menu.addMenu('大小')
        for label, height in self.SIZES:
            action = size_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(height == self.pet_height)
            action.triggered.connect(lambda checked=False, h=height: self.set_pet_height(h))
        menu.addSeparator()
        menu.addAction('退出桌宠', QApplication.instance().quit)
        menu.exec_(event.globalPos())
        menu.deleteLater()


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    app.setApplicationName('Elyms Desktop Pet')
    app.setQuitOnLastWindowClosed(False)
    image = QPixmap(str(Path(__file__).with_name('elyms.png')))
    if image.isNull():
        QMessageBox.critical(None, '曳尔沐桌宠', '无法读取 elyms.png，请完整解压后再启动。')
        return 1
    pet = ElymsPet(image)
    pet.show()
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())
