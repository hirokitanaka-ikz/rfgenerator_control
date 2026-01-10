import serial
import logging


# --- Constants ---
# Command Codes
CMD_SETPOINT_WRITE = 0x43
CMD_SETPOINT_READ = 0xC3
CMD_LIMIT_UDC_WRITE = 0x44
CMD_LIMIT_UDC_READ = 0xC4
CMD_LIMIT_IDC_WRITE = 0x45
CMD_LIMIT_IDC_READ = 0xC5
CMD_LIMIT_PDC_WRITE = 0x46
CMD_LIMIT_PDC_READ = 0xC6
CMD_MODE_WRITE = 0x4D
CMD_MODE_READ = 0xCD
CMD_OPERATION_WRITE = 0x4F
CMD_OPERATION_READ = 0xCF
CMD_RESET_ERROR = 0x51
CMD_GET_STATUS = 0xE1

# Constants
BAUDRATE = 9600


class TIG20Error(Exception):
    """Base exception for TIG 20 errors."""
    pass


class TIG20CommunicationError(TIG20Error):
    """Raised when serial communication fails or checksum mismatches."""
    pass


class TIG20:
    """
    Control class for TRUMPF / Hüttinger TIG 20 RF power supply via RS-232.
    """

    def __init__(self, port: str, baudrate: int = BAUDRATE, address: int = 0x00, timeout: float = 1.0):
        """
        Initialize the TIG 20 controller.

        Args:
            port: Serial port name (e.g., 'COM3' or '/dev/ttyUSB0').
            baudrate: Baud rate (default 9600).
            address: Device address (default 0x00).
            timeout: Read timeout in seconds (default 1.0).
        """
        self.port = port
        self.baudrate = baudrate
        self.address = address
        self.timeout = timeout
        self.ser = None
        self.logger = logging.getLogger(__name__)


    def open(self):
        """Open the serial connection manually."""
        if self.ser is None:
            try:
                self.ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=self.timeout,
                    write_timeout=self.timeout, # Prevent write from blocking indefinitely
                    xonxoff=False,
                    rtscts=False,
                    dsrdtr=False
                )
                self.logger.info(f"Connected to TIG 20 on {self.port}")
            except serial.SerialException as e:
                self.logger.error(f"Failed to open serial port {self.port}: {e}")
                raise TIG20Error(f"Could not open port {self.port}") from e


    def close(self):
        """Close the serial connection manually."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None
            self.logger.info("Disconnected from TIG 20")


    def _build_frame(self, cmd: int, data: int) -> bytes:
        """
        Construct a 5-byte command frame.
        Byte 1: Address
        Byte 2: Command
        Byte 3: Data High
        Byte 4: Data Low
        Byte 5: Checksum
        """
        data_h = (data >> 8) & 0xFF
        data_l = data & 0xFF
        
        checksum = (self.address + cmd + data_h + data_l) & 0xFF
        
        frame = bytearray([self.address, cmd, data_h, data_l, checksum])
        return bytes(frame)


    def _send_frame(self, frame: bytes):
        """Transmit a frame via serial."""
        if not self.ser or not self.ser.is_open:
            raise TIG20Error("Serial port not open")
        
        self.logger.debug(f"TX: {frame.hex()}")
        try:
            self.ser.write(frame)
        except serial.SerialTimeoutException as e:
            self.logger.error(f"Write timeout: {e}")
            raise TIG20CommunicationError("Write timeout") from e


    def _read_frame(self) -> dict:
        """
        Read and parse a response frame (fixed 5 bytes).
        Returns:
            dict containing address, command, data, and checksum_ok status.
        """
        if not self.ser or not self.ser.is_open:
            raise TIG20Error("Serial port not open")

        response = self.ser.read(5)
        if len(response) != 5:
            self.logger.error(f"Timeout or incomplete read. Received: {response.hex()}")
            raise TIG20CommunicationError("Timeout waiting for response")

        self.logger.debug(f"RX: {response.hex()}")

        addr = response[0]
        cmd = response[1]
        data_h = response[2]
        data_l = response[3]
        chk_rx = response[4]

        data = (data_h << 8) | data_l
        chk_calc = (addr + cmd + data_h + data_l) & 0xFF
        
        checksum_ok = (chk_rx == chk_calc)

        if not checksum_ok:
             self.logger.error(f"Checksum mismatch! RX: {chk_rx:02X}, Calc: {chk_calc:02X}")
             # Depending on strategy, might raise here or let caller handle.
             # Spec says 'Retry' for checksum mismatch, so we might want to raise a specific error
             # that allows the caller to retry.
             raise TIG20CommunicationError("Checksum mismatch")

        return {
            'address': addr,
            'command': cmd,
            'data': data,
            'checksum_ok': checksum_ok
        }


    def _send_command(self, cmd: int, data: int = 0) -> dict:
        """Helper to build, send, and read response."""
        frame = self._build_frame(cmd, data)
        self._send_frame(frame)
        return self._read_frame()


    def write_setpoint(self, permille: int):
        """
        Write Setpoint (U/I/P depending on mode).
        Range: 0 ... 1000 (representing 0.0% to 100.0%)
        """
        if not (0 <= permille <= 1000):
            raise ValueError("Setpoint must be between 0 and 1000")
        self.logger.info(f"Writing setpoint: {permille}")
        self._send_command(CMD_SETPOINT_WRITE, permille)

    def read_setpoint(self) -> int:
        """Read current Setpoint (0 ... 1000)."""
        resp = self._send_command(CMD_SETPOINT_READ)
        return resp['data']

    def write_limit_voltage(self, permille: int):
        """Write UDC (voltage) limit (0 ... 1000)."""
        if not (0 <= permille <= 1000):
            raise ValueError("Limit must be between 0 and 1000")
        self.logger.info(f"Writing UDC limit: {permille}")
        self._send_command(CMD_LIMIT_UDC_WRITE, permille)

    def read_limit_voltage(self) -> int:
        """Read UDC (voltage) limit (0 ... 1000)."""
        resp = self._send_command(CMD_LIMIT_UDC_READ)
        return resp['data']

    def write_limit_current(self, permille: int):
        """Write IDC (current) limit (0 ... 1000)."""
        if not (0 <= permille <= 1000):
            raise ValueError("Limit must be between 0 and 1000")
        self.logger.info(f"Writing IDC limit: {permille}")
        self._send_command(CMD_LIMIT_IDC_WRITE, permille)

    def read_limit_current(self) -> int:
        """Read IDC (current) limit (0 ... 1000)."""
        resp = self._send_command(CMD_LIMIT_IDC_READ)
        return resp['data']

    def write_limit_power(self, permille: int):
        """Write PDC (power) limit (0 ... 1000)."""
        if not (0 <= permille <= 1000):
            raise ValueError("Limit must be between 0 and 1000")
        self.logger.info(f"Writing PDC limit: {permille}")
        self._send_command(CMD_LIMIT_PDC_WRITE, permille)

    def read_limit_power(self) -> int:
        """Read PDC (power) limit (0 ... 1000)."""
        resp = self._send_command(CMD_LIMIT_PDC_READ)
        return resp['data']

    def set_control_mode(self, mode: int):
        """
        Set Generator control mode.
        0 = UDC
        1 = IDC
        2 = PDC
        """
        if mode not in [0, 1, 2]:
            raise ValueError("Mode must be 0 (UDC), 1 (IDC), or 2 (PDC)")
        self.logger.info(f"Setting control mode to {mode}")
        self._send_command(CMD_MODE_WRITE, mode)

    def get_control_mode_setting(self) -> int:
        """
        Read Generator control mode setting.
        Returns: 0 (UDC), 1 (IDC), or 2 (PDC)
        """
        resp = self._send_command(CMD_MODE_READ)
        return resp['data']

    def reset_error(self):
        """Send Reset Error command."""
        self.logger.info("Resetting error")
        self._send_command(CMD_RESET_ERROR, 1)

    def rf_on(self):
        """Enable RF output (Operation ON)."""
        self.logger.info("Turning RF ON")
        self._send_command(CMD_OPERATION_WRITE, 1)

    def rf_off(self):
        """Disable RF output (Operation OFF)."""
        self.logger.info("Turning RF OFF")
        # We try to send command, but if communication is broken, we can't do much more.
        try:
            self._send_command(CMD_OPERATION_WRITE, 0)
        except TIG20Error as e:
            self.logger.error(f"Failed to send RF OFF command: {e}")
            raise

    def is_rf_on_set(self) -> bool:
        """Check if RF Operation is set to ON."""
        resp = self._send_command(CMD_OPERATION_READ)
        return resp['data'] == 1

    def get_status(self) -> dict:
        """
        Query operating status.
        Returns dict with status flags detailed in protocol.
        """
        resp = self._send_command(CMD_GET_STATUS)
        data = resp['data']
        
        # High byte: Bits 8-15
        high_byte = (data >> 8) & 0xFF
        # Low byte: Bits 0-7
        low_byte = data & 0xFF

        # Parse High Byte
        # Bit 7: Setpoint: 0=internal, 1=external
        setpoint_external = bool(high_byte & 0x80)
        # Bit 6: Circuit: 0=not ready, 1=ready
        circuit_ready = bool(high_byte & 0x40)
        # Bit 4: Frequency limit: 0=off, 1=on
        freq_limit_active = bool(high_byte & 0x10)
        # Bit 3: PE limit: 0=off, 1=on
        pe_limit_active = bool(high_byte & 0x08)
        
        # Bits 0-2: Remote control
        rc_bits = high_byte & 0x07
        remote_control = "unknown"
        if rc_bits == 0: remote_control = "free"
        elif rc_bits == 1: remote_control = "internal"
        elif rc_bits == 2: remote_control = "AD_interface"
        elif rc_bits == 3: remote_control = "RS232"
        elif rc_bits == 4: remote_control = "RS485"
        elif rc_bits == 5: remote_control = "Profibus"

        # Parse Low Byte
        # Bits 5-7: Control mode active
        cm_bits = (low_byte >> 5) & 0x07
        control_mode_active = "unknown"
        if cm_bits == 0: control_mode_active = "UDC"
        elif cm_bits == 1: control_mode_active = "IDC"
        elif cm_bits == 2: control_mode_active = "PDC"
        
        # Bit 1: 0=Tastung on (sampling), 1=off
        sampling_off = bool(low_byte & 0x02)
        # Bit 0: 0=Schütz off (contactor), 1=on
        contactor_on = bool(low_byte & 0x01)

        return {
            'setpoint_external': setpoint_external,
            'circuit_ready': circuit_ready,
            'freq_limit_active': freq_limit_active,
            'pe_limit_active': pe_limit_active,
            'remote_control': remote_control,
            'control_mode_active': control_mode_active,
            'sampling_off': sampling_off,
            'contactor_on': contactor_on,
            # Raw data for debug if needed
            'raw_status_code': data
        }

    def emergency_off(self):
        """Force RF OFF and close connection."""
        self.logger.critical("EMERGENCY OFF TRIGGERED")
        try:
            self.rf_off()
        except:
            pass
        finally:
            self.close()


    def __enter__(self):
        self.open()
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        # If we are exiting due to a communication error (Timeout, etc.),
        # sending RF OFF is futile and will only cause another timeout.
        is_comm_error = isinstance(exc_val, (TIG20CommunicationError, serial.SerialTimeoutException))
        
        if not is_comm_error:
            try:
                self.rf_off()
            except:
                pass
        else:
            self.logger.warning("Skipping RF OFF commands due to communication error.")
            
        self.close()
