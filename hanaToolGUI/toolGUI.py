from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QWidget, QPushButton, QFrame, QStackedWidget
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
        self.main_layout = QVBoxLayout(self.central_widget)

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
        self.main_layout.addWidget(self.content)

        # Make different pages
        self.stacked = QStackedWidget()
        self.main_layout.addWidget(self.stacked)

        # Landing page (Logo area)
        self.landing_page = QWidget()
        landing_layout = QHBoxLayout(self.landing_page)  # Change to horizontal layout

        logo = QLabel()
        pixmap = QPixmap("../images/hana_logo.png")
        pixmap = pixmap.scaledToHeight(500, Qt.SmoothTransformation)
        logo.setPixmap(pixmap)
        logo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        label = QLabel("HANA\nTOOL")
        label.setStyleSheet("color: #1d55b4; font-size: 90px; font-weight: 100;")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        landing_layout.addWidget(logo)
        landing_layout.addWidget(label)

        landing_layout.setAlignment(Qt.AlignCenter)  # Optional: centers the entire row

        self.stacked.addWidget(self.landing_page)

        # Tool 1 Page:
        self.tool1_page = QWidget()
        tool1_layout = QVBoxLayout(self.tool1_page)
        hello_label = QLabel("1")
        hello_label.setStyleSheet("font-size: 50px; color: #1d55b4;")
        hello_label.setAlignment(Qt.AlignCenter)
        tool1_layout.addWidget(hello_label)

        self.stacked.addWidget(self.tool1_page)

        # Tool 2 Page:
        self.tool2_page = QWidget()
        tool2_layout = QVBoxLayout(self.tool2_page)
        hello_label = QLabel("2")
        hello_label.setStyleSheet("font-size: 50px; color: #1d55b4;")
        hello_label.setAlignment(Qt.AlignCenter)
        tool2_layout.addWidget(hello_label)

        self.stacked.addWidget(self.tool2_page)

        # Tool 3 Page:
        self.tool3_page = QWidget()
        tool3_layout = QVBoxLayout(self.tool3_page)
        hello_label = QLabel("3")
        hello_label.setStyleSheet("font-size: 50px; color: #1d55b4;")
        hello_label.setAlignment(Qt.AlignCenter)
        tool3_layout.addWidget(hello_label)

        self.stacked.addWidget(self.tool3_page)

        # Tool 4 Page:
        self.tool4_page = QWidget()
        tool4_layout = QVBoxLayout(self.tool4_page)
        hello_label = QLabel("4")
        hello_label.setStyleSheet("font-size: 50px; color: #1d55b4;")
        hello_label.setAlignment(Qt.AlignCenter)
        tool4_layout.addWidget(hello_label)

        self.stacked.addWidget(self.tool4_page)

        # Tool 5 Page:
        self.tool5_page = QWidget()
        tool5_layout = QVBoxLayout(self.tool5_page)
        hello_label = QLabel("5")
        hello_label.setStyleSheet("font-size: 50px; color: #1d55b4;")
        hello_label.setAlignment(Qt.AlignCenter)
        tool5_layout.addWidget(hello_label)

        self.stacked.addWidget(self.tool5_page)

        # Dimming Layer
        self.dimming_layer = QWidget(self.central_widget)
        self.dimming_layer.setGeometry(0, 0, 1000, 800)
        self.dimming_layer.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        self.dimming_layer.setVisible(False)
        self.dimming_layer.mousePressEvent = lambda event: self.toggle_sidebar()

        # Sidebar Setup
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

        # Tool 1 Tab:
        tool1_button = QPushButton("Tool 1")
        tool1_button.setCursor(Qt.PointingHandCursor)
        tool1_button.setFixedSize(250, 80)
        tool1_button.setStyleSheet("""
            background-color: #1d55b4;
            font-size: 24px;
            font-weight: 100;
        """)
        tool1_button.clicked.connect(lambda: self.switch_tabs(self.tool1_page))
        sidebar_layout.addWidget(tool1_button, alignment=Qt.AlignHCenter)

        # Tool 2 Tab:
        tool2_button = QPushButton("Tool 2")
        tool2_button.setCursor(Qt.PointingHandCursor)
        tool2_button.setFixedSize(250, 80)
        tool2_button.setStyleSheet("""
            background-color: #1d55b4;
            font-size: 24px;
            font-weight: 100;
        """)
        tool2_button.clicked.connect(lambda: self.switch_tabs(self.tool2_page))
        sidebar_layout.addWidget(tool2_button, alignment=Qt.AlignHCenter)

        # # Tool 3 Tab:
        tool3_button = QPushButton("Tool 3")
        tool3_button.setCursor(Qt.PointingHandCursor)
        tool3_button.setFixedSize(250, 80)
        tool3_button.setStyleSheet("""
            background-color: #1d55b4;
            font-size: 24px;
            font-weight: 100;
        """)
        tool3_button.clicked.connect(lambda: self.switch_tabs(self.tool3_page))
        sidebar_layout.addWidget(tool3_button, alignment=Qt.AlignHCenter)

        # # Tool 4 Tab:
        tool4_button = QPushButton("Tool 4")
        tool4_button.setCursor(Qt.PointingHandCursor)
        tool4_button.setFixedSize(250, 80)
        tool4_button.setStyleSheet("""
            background-color: #1d55b4;
            font-size: 24px;
            font-weight: 100;
        """)
        tool4_button.clicked.connect(lambda: self.switch_tabs(self.tool4_page))
        sidebar_layout.addWidget(tool4_button, alignment=Qt.AlignHCenter)

        # # Tool 5 Tab:
        tool5_button = QPushButton("Tool 5")
        tool5_button.setCursor(Qt.PointingHandCursor)
        tool5_button.setFixedSize(250, 80)
        tool5_button.setStyleSheet("""
            background-color: #1d55b4;
            font-size: 24px;
            font-weight: 100;
        """)
        tool5_button.clicked.connect(lambda: self.switch_tabs(self.tool5_page))
        sidebar_layout.addWidget(tool5_button, alignment=Qt.AlignHCenter)

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
    
    def switch_tabs(self, page):
        self.stacked.setCurrentWidget(page)
        self.toggle_sidebar()

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())