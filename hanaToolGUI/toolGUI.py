from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QWidget, QPushButton, QFrame
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QPropertyAnimation, QRect

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Hana Food Distributor, Inc. Tool')
        self.setGeometry(300, 300, 1000, 800)

        # Main container widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.central_widget.setStyleSheet("background-color: #f5f5f5;")

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)

        # Hamburger Button
        self.hamburger_button = QPushButton("☰")
        self.hamburger_button.setFixedSize(50, 50)
        self.hamburger_button.setStyleSheet("""
            font-size: 50px;
            color: black;
            background-color: transparent;
            border: none;
        """)
        self.hamburger_button.setCursor(Qt.PointingHandCursor)
        self.hamburger_button.clicked.connect(self.toggle_sidebar)
        self.content_layout.addWidget(self.hamburger_button, alignment=Qt.AlignLeft)

        # Main Content (Logo area)
        header_layout = QHBoxLayout()

        logo = QLabel()
        pixmap = QPixmap("../images/hana_logo.png")
        pixmap = pixmap.scaledToHeight(500, Qt.SmoothTransformation)
        logo.setPixmap(pixmap)
        logo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        label = QLabel("HANA\nTOOL")
        label.setStyleSheet("color: #1d55b4; font-size: 90px; font-weight: 100;")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        header_layout.addWidget(logo)
        header_layout.addWidget(label)
        header_layout.setAlignment(Qt.AlignHCenter)

        self.content_layout.addLayout(header_layout)
        self.main_layout.addWidget(self.content)

        # Dimming Layer
        self.dimming_layer = QWidget(self.central_widget)
        self.dimming_layer.setGeometry(0, 0, 1000, 800)
        self.dimming_layer.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        self.dimming_layer.setVisible(False)
        self.dimming_layer.mousePressEvent = lambda event: self.toggle_sidebar()

        # Hamburger Menu/Sidebar
        self.sidebar = QFrame(self.central_widget)
        self.sidebar.setGeometry(-300, 0, 300, 800)
        self.sidebar.setStyleSheet("border: 1px solid #aaa;")
        self.sidebar.setVisible(False)
        sidebar_layout = QVBoxLayout(self.sidebar)

        # Close Button
        self.close_button = QPushButton("ㄨ")
        self.close_button.setFixedSize(40, 40)
        self.close_button.setStyleSheet("""
            font-size: 24px;
            color: black;
            background-color: transparent;
            border: none;
        """)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.clicked.connect(self.toggle_sidebar)

        sidebar_layout.addWidget(self.close_button, alignment=Qt.AlignRight)
        # tool1_button = QPushButton("Tool 1")
        # tool1_button.setCursor(Qt.PointingHandCursor)
        # tool1_button.clicked.connect(lambda: self.switch_to_tab(0)) 
        # sidebar_layout.addWidget(tool1_button)

        # Sidebar animation setup
        self.sidebar_animation = QPropertyAnimation(self.sidebar, b"geometry")
        self.sidebar_animation.setDuration(300)  
        self.sidebar_animation.finished.connect(self.hide_sidebar)

    def toggle_sidebar(self):
        if not self.sidebar.isVisible():
            self.sidebar.setVisible(True)
            self.dimming_layer.setVisible(True)

            self.sidebar_animation.stop()
            self.sidebar_animation.setStartValue(QRect(-300, 0, 300, 800))
            self.sidebar_animation.setEndValue(QRect(0, 0, 300, 800))
            self.sidebar_animation.start()
        
        # Reset after closed
        else:
            self.sidebar_animation.stop()
            self.sidebar_animation.setStartValue(QRect(0, 0, 300, 800))
            self.sidebar_animation.setEndValue(QRect(-300, 0, 300, 800))
            self.sidebar_animation.start()

    def hide_sidebar(self):
        # Only hide sidebar and dimming when it’s completely slid out
        if self.sidebar.geometry().x() == -300:
            self.sidebar.setVisible(False)
            self.dimming_layer.setVisible(False)
    
    def switch_to_tab(self, index):
        self.tab_widget.setCurrentIndex(index)
        self.toggle_sidebar()


app = QApplication([])
window = MainWindow()
window.show()
app.exec()
