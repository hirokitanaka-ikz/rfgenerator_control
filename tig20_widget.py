import sys
from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout, 
    QLabel, QComboBox, QPushButton, QDoubleSpinBox, 
    QProgressBar, QMessageBox, QGridLayout
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtSerialPort import QSerialPortInfo
import logging

# Ensure we can import tig20 from the same directory or path
try:
    from tig20 import TIG20, TIG20Error
except ImportError:
    # Fallback if running standalone and tig20 is in the same dir
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from tig20 import TIG20, TIG20Error

class TIG20Widget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("TIG 20 Control", parent)
        self.tig20 = None
        self.is_connected = False
        
        # Setup logging
        self.logger = logging.getLogger("TIG20Widget")
        if not self.logger.handlers:
             logging.basicConfig(level=logging.INFO)

        self._init_ui()
        self._setup_connections()

        # Timer for polling status
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_status)
        self.poll_interval = 500 # ms

    def _init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # --- Connection Section ---
        conn_layout = QHBoxLayout()
        
        self.combo_ports = QComboBox()
        self.btn_refresh_ports = QPushButton("↻")
        self.btn_refresh_ports.setFixedWidth(30)
        self.btn_refresh_ports.setToolTip("Refresh COM Ports")
        
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setCheckable(True)

        conn_layout.addWidget(QLabel("Port:"))
        conn_layout.addWidget(self.combo_ports)
        conn_layout.addWidget(self.btn_refresh_ports)
        conn_layout.addWidget(self.btn_connect)
        
        layout.addLayout(conn_layout)

        # --- Controls Section ---
        controls_layout = QGridLayout()
        
        # RF On/Off
        self.btn_rf = QPushButton("RF ON/OFF")
        self.btn_rf.setCheckable(True)
        self.btn_rf.setStyleSheet("QPushButton:checked { background-color: green; color: white; }")
        self.lbl_rf_status = QLabel("OFF")
        self.lbl_rf_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_rf_status.setStyleSheet("background-color: grey; color: white; border-radius: 5px; padding: 2px;")
        
        controls_layout.addWidget(QLabel("RF Output:"), 0, 0)
        controls_layout.addWidget(self.btn_rf, 0, 1)
        controls_layout.addWidget(self.lbl_rf_status, 0, 2)

        # Control Mode
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["UDC", "IDC", "PDC"])
        
        controls_layout.addWidget(QLabel("Mode:"), 1, 0)
        controls_layout.addWidget(self.combo_mode, 1, 1, 1, 2)

        # Setpoint
        self.spin_setpoint = QDoubleSpinBox()
        self.spin_setpoint.setRange(0.0, 100.0)
        self.spin_setpoint.setSingleStep(0.1)
        self.spin_setpoint.setSuffix(" %")
        self.btn_set_setpoint = QPushButton("Set") # Explicit set button often better for serial devices
        
        controls_layout.addWidget(QLabel("Setpoint:"), 2, 0)
        controls_layout.addWidget(self.spin_setpoint, 2, 1)
        controls_layout.addWidget(self.btn_set_setpoint, 2, 2)
        
        layout.addLayout(controls_layout)

        # --- Monitor Section (Bars) ---
        # Note: These show LIMITS/SETPOINTS because actual values aren't readable via protocol
        
        self.bar_udc = self._create_bar("UDC Limit")
        layout.addLayout(self.bar_udc['layout'])
        
        self.bar_idc = self._create_bar("IDC Limit")
        layout.addLayout(self.bar_idc['layout'])
        
        self.bar_pdc = self._create_bar("PDC Limit")
        layout.addLayout(self.bar_pdc['layout'])

        self._refresh_ports()
        self._update_ui_state(False)

    def _create_bar(self, label_text):
        container = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(60)
        
        bar = QProgressBar()
        bar.setRange(0, 1000) # Internal 0-1000 permille
        bar.setTextVisible(False)
        
        num_label = QLabel("0.0 %")
        num_label.setFixedWidth(50)
        num_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        container.addWidget(label)
        container.addWidget(bar)
        container.addWidget(num_label)
        
        return {'layout': container, 'bar': bar, 'label': num_label}

    def _setup_connections(self):
        self.btn_refresh_ports.clicked.connect(self._refresh_ports)
        self.btn_connect.clicked.connect(self._toggle_connection)
        
        self.btn_rf.clicked.connect(self._toggle_rf)
        self.combo_mode.currentIndexChanged.connect(self._change_mode)
        self.btn_set_setpoint.clicked.connect(self._write_setpoint)
        # Also write setpoint on spinbox editingFinished? Maybe too frequent. Keep button for now.
        
    def _refresh_ports(self):
        current = self.combo_ports.currentText()
        self.combo_ports.clear()
        ports = QSerialPortInfo.availablePorts()
        for p in ports:
            self.combo_ports.addItem(p.portName())
        
        if current:
            index = self.combo_ports.findText(current)
            if index >= 0:
                self.combo_ports.setCurrentIndex(index)

    def _toggle_connection(self):
        if not self.is_connected:
            self._connect()
        else:
            self._disconnect()

    def _connect(self):
        port = self.combo_ports.currentText()
        if not port:
            return
            
        try:
            self.tig20 = TIG20(port=port)
            self.tig20.open()
            self.is_connected = True
            self.btn_connect.setText("Disconnect")
            self.btn_connect.setChecked(True)
            self._update_ui_state(True)
            self.timer.start(self.poll_interval)
            self.logger.info(f"Connected to {port}")
            
            # Initial read of values
            self._initial_read()
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            QMessageBox.critical(self, "Connection Error", f"Could not connect to {port}:\n{str(e)}")
            self.btn_connect.setChecked(False)

    def _disconnect(self):
        self.timer.stop()
        if self.tig20:
            try:
                self.tig20.close()
            except:
                pass
            self.tig20 = None
            
        self.is_connected = False
        self.btn_connect.setText("Connect")
        self.btn_connect.setChecked(False)
        self._update_ui_state(False)
        self.logger.info("Disconnected")

    def _update_ui_state(self, enabled):
        self.btn_rf.setEnabled(enabled)
        self.combo_mode.setEnabled(enabled)
        self.spin_setpoint.setEnabled(enabled)
        self.btn_set_setpoint.setEnabled(enabled)
        
        if not enabled:
            self.lbl_rf_status.setText("OFF")
            self.lbl_rf_status.setStyleSheet("background-color: grey; color: white; border-radius: 5px; padding: 2px;")
            self.btn_rf.setChecked(False)

    def _initial_read(self):
        # Read all limits and mode once efficiently
        if not self.tig20: return
        
        try:
            # Mode
            mode = self.tig20.get_control_mode_setting()
            self.combo_mode.blockSignals(True)
            if mode in [0, 1, 2]:
                self.combo_mode.setCurrentIndex(mode)
            self.combo_mode.blockSignals(False)

            # Setpoint
            sp = self.tig20.read_setpoint()
            self.spin_setpoint.setValue(sp / 10.0)

            # Limits
            self._update_bar_value(self.bar_udc, self.tig20.read_limit_voltage())
            self._update_bar_value(self.bar_idc, self.tig20.read_limit_current())
            self._update_bar_value(self.bar_pdc, self.tig20.read_limit_power())
            
        except Exception as e:
            self.logger.error(f"Initial read failed: {e}")

    def _poll_status(self):
        if not self.tig20: return
        
        try:
            status = self.tig20.get_status()
            
            # Update RF LED
            rf_on = not status['contactor_on'] # Wait, protocol says Bit 0: 0=Off, 1=On?
            # Re-checking tig20.py: 
            # Bit 0: 0=Schütz off (contactor), 1=on. 
            # Ideally this means RF is potentially active if contactor is ON.
            # But there is also Operation Write 0/1. 
            # Let's rely on 'contactor_on' as the feedback for "HV On" usually.
            
            is_on = status['contactor_on']
            text = "ON" if is_on else "OFF"
            color = "red" if is_on else "grey" # Red is usually HV ON danger
            self.lbl_rf_status.setText(text)
            self.lbl_rf_status.setStyleSheet(f"background-color: {color}; color: white; border-radius: 5px; padding: 2px;")
            
            # Sync button state if changed externally?
            # self.btn_rf.setChecked(is_on) # Optional: might interfere with user interaction
            
            # We could also poll setpoints/limits occasionally, but maybe overkill?
            # Protocol doesn't give actual values in status, only flags.
            
        except Exception as e:
            self.logger.error(f"Poll status error: {e}")
            # If excessive errors, maybe disconnect?

    def _toggle_rf(self):
        if not self.tig20: return
        
        want_on = self.btn_rf.isChecked()
        try:
            if want_on:
                self.tig20.rf_on()
            else:
                self.tig20.rf_off()
        except Exception as e:
            self.logger.error(f"RF Toggle error: {e}")
            # Revert button state if failed
            self.btn_rf.setChecked(not want_on)

    def _change_mode(self, index):
        if not self.tig20: return
        try:
            self.tig20.set_control_mode(index)
        except Exception as e:
            self.logger.error(f"Set Mode error: {e}")

    def _write_setpoint(self):
        if not self.tig20: return
        val = self.spin_setpoint.value()
        permille = int(val * 10)
        try:
            self.tig20.write_setpoint(permille)
        except Exception as e:
            self.logger.error(f"Write setpoint error: {e}")

    def _update_bar_value(self, bar_dict, permille):
        bar_dict['bar'].setValue(permille)
        bar_dict['label'].setText(f"{permille/10.0:.1f} %")


if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = TIG20Widget()
    window.show()
    sys.exit(app.exec())
