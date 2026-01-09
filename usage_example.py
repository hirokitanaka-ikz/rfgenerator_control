import logging
import time
from tig20 import TIG20, TIG20Error

# Configure logging to see communication details
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    # Update COM port as needed
    PORT = 'COM3' 

    try:
        print(f"Connecting to TIG 20 on {PORT}...")
        
        # Using context manager ensures RF is turned OFF upon exit
        with TIG20(PORT) as tig:
            
            # 1. Check status
            status = tig.get_status()
            print(f"Initial Status: {status}")

            if status['error']:
                print("Error detected! Aborting.")
                return

            # 2. Set Power
            target_power = 50 # Watts
            print(f"Setting power to {target_power} W...")
            tig.set_power(target_power)

            # 3. Enable RF
            print("Turning RF ON...")
            tig.rf_on()
            
            # 4. Monitor Loop
            for i in range(5):
                time.sleep(1)
                actual_power = tig.get_power()
                print(f"[{i+1}/5] Measured Power: {actual_power} W")
            
            # 5. Context manager will automatically call rf_off() and close() here
            print("Finished sequence. RF should turn off now.")

    except TIG20Error as e:
        print(f"Communication Error: {e}")
    except Exception as e:
        print(f"Unexpected Error: {e}")

if __name__ == "__main__":
    main()
