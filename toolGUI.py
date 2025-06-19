from PySide6.QtCore import Qt, QRect, QPropertyAnimation
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame, QFileDialog, QLineEdit, QTextEdit
)
from PySide6.QtGui import QPixmap
import io, os, sys, asyncio

def get_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

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
        landing_layout = QHBoxLayout(self.landing_page)

        logo = QLabel()
        # Added data to .spec file
        pixmap = QPixmap(get_path("images/hana_logo.png"))
        pixmap = pixmap.scaledToHeight(500, Qt.SmoothTransformation)
        logo.setPixmap(pixmap)
        logo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        label = QLabel("HANA\nTOOL")
        label.setStyleSheet("color: #1d55b4; font-size: 90px; font-weight: 100;")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        landing_layout.addWidget(logo)
        landing_layout.addWidget(label)
        landing_layout.setAlignment(Qt.AlignCenter)

        self.stacked.addWidget(self.landing_page)

        # Dimming Layer
        self.dimming_layer = QWidget(self.central_widget)
        self.dimming_layer.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        self.dimming_layer.setVisible(False)
        self.dimming_layer.mousePressEvent = lambda event: self.toggle_sidebar()
        self.dimming_layer.setGeometry(self.central_widget.rect())

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

        # Tool Pages and Tabs Setup
        tool_names = ["Whole Foods Market", "Safeway", "Harris Teeter", "Giant Food"]
        # **Revisit for making the two giant versions
        script_names = ["wholefoods", "safewayv5", "htscraperv4", "giantscalev3"]
        self.tool_pages = []

        for idx, name in enumerate(tool_names):
            # Create page
            page = self.create_tool_page(tool_names[idx], script_names[idx])
            self.stacked.addWidget(page)
            self.tool_pages.append(page)

            # Create sidebar button
            button = self.create_tool_button(page, name)
            sidebar_layout.addWidget(button, alignment=Qt.AlignHCenter)

        # Sidebar animation setup
        self.sidebar_animation = QPropertyAnimation(self.sidebar, b"geometry")
        self.sidebar_animation.setDuration(300)
        self.sidebar_animation.finished.connect(self.hide_sidebar)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.dimming_layer.setGeometry(self.central_widget.rect())

    def create_tool_page(self, label_text, script):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        label = QLabel(label_text + "\nScrape Tool")
        label.setStyleSheet("font-size: 50px; color: #1d55b4; font-weight: 300;")
        label.setFixedHeight(150)
        label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        layout.addWidget(label)

        file_layout = QHBoxLayout()
        file_input = QLineEdit()
        file_input.setFixedWidth(0)
        file_input.setStyleSheet("color: black;")
        file_input.setFixedHeight(0)
        file_input.setReadOnly(True)

        file_drop = FileDropArea(file_input)

        file_layout.addWidget(file_drop, alignment=Qt.AlignVCenter)
        file_layout.addWidget(file_input, alignment=Qt.AlignTop | Qt.AlignHCenter)
        file_layout.setSpacing(10)
        file_layout.setContentsMargins(0, 0, 0, 0)

        layout.addLayout(file_layout)
        layout.setAlignment(file_layout, Qt.AlignTop | Qt.AlignHCenter)

        if (label_text == "Safeway" or label_text == "Giant Food"):
            button_row = QHBoxLayout()

            scrape_button = QPushButton("Get products and \nprices (Scrape)")
            scrape_button.setFixedSize(200, 80)
            scrape_button.setCursor(Qt.PointingHandCursor)
            scrape_button.setStyleSheet("background-color: #1d55b4; font-size: 18px; font-weight: 500; margin-top: 20px;")
            scrape_button.clicked.connect(lambda: self.run_script(script, file_input, output_display, choice=1))

            compare_button = QPushButton("Match UPCs and\nCompare Prices")
            compare_button.setFixedSize(200, 80)
            compare_button.setCursor(Qt.PointingHandCursor)
            compare_button.setStyleSheet("background-color: #1d55b4; font-size: 18px; font-weight: 500; margin-top: 20px;")
            compare_button.clicked.connect(lambda: self.run_script(script, file_input, output_display, choice=2))

            both_button = QPushButton("Scrape and \ncompare prices")
            both_button.setFixedSize(200, 80)
            both_button.setCursor(Qt.PointingHandCursor)
            both_button.setStyleSheet("background-color: #1d55b4; font-size: 18px; font-weight: 500; margin-top: 20px;")
            both_button.clicked.connect(lambda: self.run_script(script, file_input, output_display, choice=3))

            button_row.addWidget(scrape_button)
            button_row.addWidget(compare_button)
            button_row.addWidget(both_button)

            layout.addLayout(button_row)
        else: 
            run_button = QPushButton("Match UPCs and\nCompare Prices")
            run_button.setFixedSize(200, 80)
            run_button.setCursor(Qt.PointingHandCursor)
            run_button.setStyleSheet("background-color: #1d55b4; font-size: 18px; font-weight: 500; margin-top: 20px;")
            run_button.clicked.connect(lambda: self.run_script(script, file_input, output_display))
            
            layout.addWidget(run_button)
            layout.setAlignment(run_button, Qt.AlignTop | Qt.AlignHCenter)
        
        output_display = QTextEdit()
        output_display.setReadOnly(True)
        output_display.setFixedHeight(300)
        output_display.setStyleSheet("color: black;")
        layout.addWidget(output_display)
        page.output_display = output_display
        return page

    def browse_file(self, file_input):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Excel File", "", "Excel Files (*.xlsx *.xls)")
        if file_path:
            file_input.setText(file_path)

    def create_tool_button(self, page, button_text):
        button = QPushButton(button_text)
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedSize(250, 80)
        button.setStyleSheet("""
            background-color: #1d55b4;
            font-size: 24px;
            font-weight: 200;
        """)
        button.clicked.connect(lambda: self.switch_tabs(page))
        return button

    def run_script(self, script, file_input, output_display, choice=0):
        # Can't drag files with a path to messages b/c of security
        # Scraping will open a new Hana application... fix
        file_path = file_input.text().strip()
        if not file_path and choice != 1:
            output_display.setPlainText("Please select a file first.")
            return
        
        try:
            buffer = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = buffer
            
            try:
                if script == "giantscalev3":
                    from scraplingAdaptationHana.giant.giantscalev3 import main
                    asyncio.run(main(choice, SOURCE_DATA=file_path))
                elif script == "safewayv5":
                    from scraplingAdaptationHana.safeway.safewayv5 import main
                    asyncio.run(main(choice, input_file=file_path))
            finally:
                sys.stdout = old_stdout

            output_text = buffer.getvalue()
            output_display.setPlainText(output_text)
        
        except Exception as e:
            output_display.setPlainText("Failed to run the script: " + str(e))

    def toggle_sidebar(self):
        if not self.sidebar.isVisible():
            self.sidebar.setVisible(True)
            self.dimming_layer.setVisible(True)

            self.sidebar_animation.stop()
            self.sidebar_animation.setStartValue(QRect(-300, 0, 300, 800))
            self.sidebar_animation.setEndValue(QRect(0, 0, 300, 800))
            self.sidebar_animation.start()

        else:
            self.sidebar_animation.stop()
            self.sidebar_animation.setStartValue(QRect(0, 0, 300, 800))
            self.sidebar_animation.setEndValue(QRect(-300, 0, 300, 800))
            self.sidebar_animation.start()

    def hide_sidebar(self):
        if self.sidebar.geometry().x() == -300:
            self.sidebar.setVisible(False)
            self.dimming_layer.setVisible(False)

    def switch_tabs(self, page):
        self.stacked.setCurrentWidget(page)
        self.toggle_sidebar()

class FileDropArea(QLabel):
    def __init__(self, file_input):
        super().__init__("Drag and drop a price sheet here (.xlsx)... \n(Not required if only scraping)")
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #1d55b4;
                border-radius: 10px;
                min-height: 150px;
                min-width: 400px;
                font-size: 18px;
                background-color: #f0f0f0;
                color: #A9A9A9;
                qproperty-alignment: AlignCenter;
            }
        """)
        self.setAcceptDrops(True)
        self.file_input = file_input

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
                self.file_input.setText(file_path)
                self.setText(f"{os.path.basename(file_path)}\n\nFile ready!")
                self.setStyleSheet("""
                    QLabel {
                        border: 2px dashed #1d55b4;
                        border-radius: 10px;
                        min-height: 150px;
                        min-width: 400px;
                        font-size: 18px;
                        background-color: #f0f0f0;
                        color: black;
                        qproperty-alignment: AlignCenter;
                    }
                """)
            else:
                self.setText("Invalid file type. Please drop an Excel file.")
                self.setStyleSheet("""
                    QLabel {
                        border: 2px dashed #1d55b4;
                        border-radius: 10px;
                        min-height: 150px;
                        min-width: 400px;
                        font-size: 18px;
                        background-color: #f0f0f0;
                        color: black;
                        qproperty-alignment: AlignCenter;
                    }
                """)

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())