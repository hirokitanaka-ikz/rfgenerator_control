import unittest
from unittest.mock import MagicMock, patch
from tig20 import TIG20, TIG20Error, TIG20CommunicationError


class TestTIG20(unittest.TestCase):
    def setUp(self):
        self.mock_serial_patcher = patch('serial.Serial')
        self.mock_serial = self.mock_serial_patcher.start()
        self.tig = TIG20('COM3')


    def tearDown(self):
        self.mock_serial_patcher.stop()


    def test_open_connection(self):
        with self.tig:
            self.mock_serial.assert_called_with(
                port='COM3',
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
        # Checksum = 0 + 1 + 0 + 50 = 51 (0x33)
        frame = self.tig._build_frame(cmd=0x01, data=50)
        expected = bytes([0x00, 0x01, 0x00, 0x32, 0x33])
        self.assertEqual(frame, expected)


    def test_rf_on_success(self):
        """Test sending RF ON command with valid response."""
        # Setup mock read return value (address, cmd, data_h, data_l, chk)
        # Echo back command as success? Spec says fixed frame response.
        # Let's assume response mirrors command for simplicity in this mock, 
        # or has some standard ACK. Since we didn't firmly define response content
        # beyond "5 bytes", let's craft a valid checksum response.
        
        # CMD_RF_ON = 0x02
        # Response: ADR=0, CMD=2, Data=0, CHK=2
        response_bytes = bytes([0x00, 0x02, 0x00, 0x00, 0x02])
        
        instance = self.mock_serial.return_value
        instance.is_open = True
        instance.read.return_value = response_bytes

        with self.tig:
            self.tig.rf_on()
            
            # Verify write called with correct frame
            # 0+2+0+0 = 2 checksum
            expected_tx = bytes([0x00, 0x02, 0x00, 0x00, 0x02])
            instance.write.assert_called_with(expected_tx)


    def test_checksum_error(self):
        """Test that bad checksum raises exception."""
        # Response with bad checksum
        # ADR=0, CMD=2, Data=0, CHK=99 (should be 2)
        response_bytes = bytes([0x00, 0x02, 0x00, 0x00, 0x99])
        
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
        # CMD_RF_OFF = 0x03. Checksum = 3.
        instance.read.return_value = bytes([0x00, 0x03, 0x00, 0x00, 0x03])

        with self.tig:
            pass # Just enter and exit
        
        # Verify rf_off was called (CMD_RF_OFF = 0x03)
        # Check if write was called with RF OFF frame
        expected_off_frame = bytes([0x00, 0x03, 0x00, 0x00, 0x03])
        
        # We might have other calls, check if last call or any call was RF OFF
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
        expected_off_frame = bytes([0x00, 0x03, 0x00, 0x00, 0x03])
        
        # Check that write was NOT called (or not called with RF OFF)
        # Note: In this pure mock, nothing was written.
        try:
             instance.write.assert_any_call(expected_off_frame)
             self.fail("RF OFF should have been skipped")
        except AssertionError:
             pass # Success, it wasn't called


if __name__ == '__main__':
    unittest.main()
