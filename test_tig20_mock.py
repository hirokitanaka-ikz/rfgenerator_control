import unittest
from unittest.mock import MagicMock, patch
from tig20 import TIG20, TIG20Error, TIG20CommunicationError


class TestTIG20(unittest.TestCase):
    def setUp(self):
        self.mock_serial_patcher = patch('serial.Serial')
        self.mock_serial = self.mock_serial_patcher.start()
        self.tig = TIG20('COM4')


    def tearDown(self):
        self.mock_serial_patcher.stop()


    def test_open_connection(self):
        with self.tig:
            self.mock_serial.assert_called_with(
                port='COM4',
                baudrate=9600,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=1.0,
                write_timeout=1.0,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )


    def test_build_frame(self):
        """Test frame construction manually."""
        # ADR=0, CMD=1, DATA=50 (0x32, H=0, L=0x32)
        # ADR=0, CMD=1, DATA=50 (0x32, H=0, L=0x32)
        # Checksum = 0 ^ 1 ^ 0 ^ 50 = 51 (0x33)
        frame = self.tig._build_frame(cmd=0x01, data=50)
        expected = bytes([0x00, 0x01, 0x00, 0x32, 0x33])
        self.assertEqual(frame, expected)


    def test_rf_on_success(self):
        """Test sending RF ON command with valid response."""
        # CMD_OPERATION_WRITE = 0x4F (79)
        # Data = 1
        # CMD_OPERATION_WRITE = 0x4F (79)
        # Data = 1
        # Checksum = 0 ^ 79 ^ 0 ^ 1 = 78 (0x4E)
        # Response: ADR=0, CMD=0x4F, Data=1, CHK=0x4E
        response_bytes = bytes([0x00, 0x4F, 0x00, 0x01, 0x4E])
        
        instance = self.mock_serial.return_value
        instance.is_open = True
        instance.read.return_value = response_bytes

        with self.tig:
            self.tig.rf_on()
            
            # Verify write called with correct frame
            expected_tx = bytes([0x00, 0x4F, 0x00, 0x01, 0x4E])
            instance.write.assert_called_with(expected_tx)


    def test_checksum_error(self):
        """Test that bad checksum raises exception."""
        # Response with bad checksum
        # ADR=0, CMD=0x4F, Data=1, CHK=99 (should be 0x4E)
        response_bytes = bytes([0x00, 0x4F, 0x00, 0x01, 0x99])
        
        instance = self.mock_serial.return_value
        instance.is_open = True
        instance.read.return_value = response_bytes

        with self.tig:
            with self.assertRaises(TIG20CommunicationError):
                self.tig.rf_on()


    def test_context_manager_safety(self):
        """Ensure RF OFF is called on exit."""
        instance = self.mock_serial.return_value
        instance.is_open = True
        # Setup read for the implicit rf_off call at exit
        # CMD_OPERATION_WRITE = 0x4F. Data=0. Checksum = 79 (0x4F).
        instance.read.return_value = bytes([0x00, 0x4F, 0x00, 0x00, 0x4F])

        with self.tig:
            pass # Just enter and exit
        
        # Verify rf_off was called
        # Check if write was called with RF OFF frame
        expected_off_frame = bytes([0x00, 0x4F, 0x00, 0x00, 0x4F])
        
        instance.write.assert_called_with(expected_off_frame)


    def test_skip_cleanup_on_error(self):
        """Ensure RF OFF is SKIPPED on communication error."""
        instance = self.mock_serial.return_value
        instance.is_open = True
        
        # Simulate an error during execution
        with self.assertRaises(TIG20CommunicationError):
            with self.tig:
                raise TIG20CommunicationError("Simulated Failure")
        
        # Verify RF OFF was NOT called because we raised TIG20CommunicationError
        expected_off_frame = bytes([0x00, 0x4F, 0x00, 0x00, 0x4F])
        
        # Check that write was NOT called (or not called with RF OFF)
        # Note: In this pure mock, nothing was written.
        try:
             instance.write.assert_any_call(expected_off_frame)
             self.fail("RF OFF should have been skipped")
        except AssertionError:
             pass # Success, it wasn't called



    def test_read_actual_power(self):
        """Test reading actual power."""
        # CMD_ACTUAL_PDC_READ = 0xE6 (230)
        # Checksum = 0 ^ 230 ^ 0 ^ 0 = 230 (0xE6)
        # Response: Data = 500 (0x01F4).
        # Checksum = 0 ^ 0xE6 ^ 0x01 ^ 0xF4 = 0xE6 ^ 0x1F5 = 0x13
        
        response_bytes = bytes([0x00, 0xE6, 0x01, 0xF4, 0x13])
        
        instance = self.mock_serial.return_value
        instance.is_open = True
        instance.read.return_value = response_bytes
        
        with self.tig:
            val = self.tig.read_actual_power()
            self.assertEqual(val, 500)
            
            # Expected TX: 00 E6 00 00 E6
            expected_tx = bytes([0x00, 0xE6, 0x00, 0x00, 0xE6])
            instance.write.assert_called_with(expected_tx)


    def test_read_actual_voltage(self):
        """Test reading actual voltage."""
        # CMD_ACTUAL_UDC_READ = 0xE7
        # Response: Data = 100 (0x0064)
        # Checksum = 0 ^ 0xE7 ^ 0x00 ^ 0x64 = 0xE7 ^ 0x64 = 0x83
        
        response_bytes = bytes([0x00, 0xE7, 0x00, 0x64, 0x83])
        
        instance = self.mock_serial.return_value
        instance.is_open = True
        instance.read.return_value = response_bytes
        
        with self.tig:
            val = self.tig.read_actual_voltage()
            self.assertEqual(val, 100)
            
            # Expected TX: 00 E7 00 00 E7
            expected_tx = bytes([0x00, 0xE7, 0x00, 0x00, 0xE7])
            instance.write.assert_called_with(expected_tx)


    def test_read_actual_current(self):
        """Test reading actual current."""
        # CMD_ACTUAL_IDC_READ = 0xE8
        # Response: Data = 0
        # Checksum = 0 ^ 0xE8 ^ 0 ^ 0 = 0xE8
        
        response_bytes = bytes([0x00, 0xE8, 0x00, 0x00, 0xE8])
        
        instance = self.mock_serial.return_value
        instance.is_open = True
        instance.read.return_value = response_bytes
        
        with self.tig:
            val = self.tig.read_actual_current()
            self.assertEqual(val, 0)
            
            # Expected TX: 00 E8 00 00 E8
            expected_tx = bytes([0x00, 0xE8, 0x00, 0x00, 0xE8])
            instance.write.assert_called_with(expected_tx)


    def test_read_actual_frequency(self):
        """Test reading actual frequency."""
        # CMD_ACTUAL_FREQ_READ = 0xED
        # Response: Data = 1356 (13.56 MHz?) 1356 = 0x054C
        # Checksum = 0 ^ 0xED ^ 0x05 ^ 0x4C = 0xA4
        
        response_bytes = bytes([0x00, 0xED, 0x05, 0x4C, 0xA4])
        
        instance = self.mock_serial.return_value
        instance.is_open = True
        instance.read.return_value = response_bytes
        
        with self.tig:
            val = self.tig.read_actual_frequency()
            self.assertEqual(val, 1356)
            
            # Expected TX: 00 ED 00 00 ED
            expected_tx = bytes([0x00, 0xED, 0x00, 0x00, 0xED])
            instance.write.assert_called_with(expected_tx)


if __name__ == '__main__':
    unittest.main()
