import serial
import logging


# --- Constants & Placeholders ---
# IMPORTANT: Update these values from the hardware manual!
CMD_SET_POWER = 0x01  # Placeholder
CMD_RF_ON = 0x02      # Placeholder
CMD_RF_OFF = 0x03     # Placeholder
CMD_GET_STATUS = 0x04 # Placeholder
CMD_GET_POWER = 0x05  # Placeholder

# Response validation
ACK = 0x06 # Placeholder for Acknowledge if applicable, though spec says fixed frame response

# BAUDRATE
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


    def set_power(self, power_percent: int):
        """Set RF output power in watts."""
        self.logger.info(f"Setting power to {power_percent}%")
        # Assuming data bytes correspond to watts directly
        self._send_command(CMD_SET_POWER, power_percent)


    def get_power(self) -> int:
        """Read back measured RF output power."""
        resp = self._send_command(CMD_GET_POWER)
        return resp['data']


    def rf_on(self):
        """Enable RF output."""
        self.logger.info("Turning RF ON")
        self._send_command(CMD_RF_ON)


    def rf_off(self):
        """Disable RF output."""
        self.logger.info("Turning RF OFF")
        # We try to send command, but if communication is broken, we can't do much more.
        try:
            self._send_command(CMD_RF_OFF)
        except TIG20Error as e:
            self.logger.error(f"Failed to send RF OFF command: {e}")
            raise


    def get_status(self) -> dict:
        """
        Query operating status.
        Returns dict with status flags.
        """
        resp = self._send_command(CMD_GET_STATUS)
        data = resp['data']
        
        # Decoding depends on specific bit definitions in manual.
        # Placeholder implementation:
        return {
            'rf_on': bool(data & 0x01),
            'error': bool(data & 0x02),
            'interlock': bool(data & 0x04)
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
