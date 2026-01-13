from tig20 import TIG20, TIG20Error
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    PORT = 'COM4'  # Update as needed

    tig = TIG20(PORT)

    try:
        print(f"Connecting to TIG 20 on {PORT}...")
        tig.open()
        status = tig.get_status()
        print(f"Status: {status}")

        tig.rf_on()
        tig.rf_off()
        
    except TIG20Error as e:
        print(f"Communication Error: {e}")
    finally:
        if tig:
            print("Closing connection...")
            tig.close()