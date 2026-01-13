import logging
import time
from tig20 import TIG20, TIG20Error

# Configure logging to see communication details
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    # Update COM port as needed
    PORT = 'COM4' 

    tig = TIG20(PORT)

    try:
        print(f"Connecting to TIG 20 on {PORT}...")
        print("Note: If the device is not responding, this may take a few seconds to timeout.")
        
        # Manual connection
        tig.open()
            
        # 1. Check status
        status = tig.get_status()
        print(f"Initial Status: {status}")

        if status['error']:
            print("Error detected! Aborting.")
            return

        # 2. Set Setpoint (Power/Voltage/Current depending on mode)
        # Assuming we are in a mode where setpoint means power (permille)
        # 50 Watts -> If max is 1000W, 50 permille? Or is permille 0-100%?
        # Protocol says 0...1000 permille.
        target_setpoint = 50 
        print(f"Writing setpoint to {target_setpoint} (permille)...")
        tig.write_setpoint(target_setpoint)

        # 3. Enable RF
        print("Turning RF ON...")
        tig.rf_on()
        
        # 4. Monitor Loop
        for i in range(5):
            time.sleep(1)
            actual_setpoint = tig.read_setpoint()
            # Also read actual power limit if desired
            # p_limit = tig.read_limit_power()
            print(f"[{i+1}/5] Read Setpoint: {actual_setpoint}")
        
        print("Finished sequence.")

    except TIG20Error as e:
        print(f"Communication Error: {e}")
    except Exception as e:
        print(f"Unexpected Error: {e}")
    finally:
        # CRITICAL: Always close the connection in finally block.
        # This ensures RF is turned OFF (if not skipped by error logic) and port is closed.
        if tig:
            print("Closing connection...")
            # Note: You might want to call rf_off() explicitly here if you are not relying
            # on the smart cleanup logic that was inside __exit__. 
            # But close() itself purely closes the port in the new logic.
            # To be safe in manual mode, we should try to turn RF off if possible.
            try:
                tig.rf_off()
            except:
                pass # Ignore errors during cleanup
            
            tig.close()

if __name__ == "__main__":
    main()
