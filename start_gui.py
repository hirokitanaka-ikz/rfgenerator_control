from PyQt6.QtWidgets import QApplication
import sys
from tig20_widget import TIG20Widget

def main():
    app = QApplication(sys.argv)
    
    # Create the widget and show it as a top-level window
    widget = TIG20Widget()
    widget.setWindowTitle("TIG 20 Control Panel")
    widget.resize(500, 300)
    widget.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
