# RS232 communication protocol

## command
- HEX 43H, Setpoint (U/I/P) write, 0 ... 1000 ‰
- HEX C3H, Setpoint read, 0 ... 1000 ‰
- HEX 44H, UDC (voltage) limit value write, 0 ... 1000 ‰
- HEX C4H, UDC (voltaga) limit value read, 0 ... 1000 ‰
- HEX 45H, IDC (current) limit value write, 0 ... 1000 ‰
- HEX C5H, IDC (current) limit value read, 0 ... 1000 ‰
- HEX 46H, PDC (power) limit value write, 0 ... 1000 ‰
- HEX C6H, PDC (power) limit value read, 0 ... 1000 ‰
- HEX 4DH, Generator control mode write: 0=UDC, 1=IDC, 2=PDC
- HEX CDH, Generator control mode read: 0=UDC, 1=IDC, 2=PDC
- HEX 4FH: Generator operation status write: 0=off, 1=on
- HEX CFH: Generator operation status read: 0=off, 1=on
- HEX 51H, Reset error: 0=No Action, 1=Reset Error
- HEX E1H, Read status (see status byte below)
- HEX E3H, Number of error messages read
- HEX E4H, Error information (function number) read
- HEX E5H, Error information (error number) read
- HEX E6H, Actual PDC (power) value read: 0 ... 1000 ‰
- HEX E7H, Actual UDC (voltage) value read: 0 ... 1000 ‰
- HEX E8H, Actual IDC (current) value read: 0 ... 1000 ‰
- HEX EDH, Actual Frequency value read: 0...3000 [1/10 kHz]


## Status bytes
### High byte
- Bit 7: Setpoint (not active): 0=internal, 1=external
- Bit 6: Circuit: 0=not ready, 1=ready
- Bit 5: not used
- Bit 4: Frequency limit value (not active): 0=off, 1=on
- Bit 3: PE limit value (not active): 0=off, 1=on
- Bit 0...2: Remote control:
    Bit2=0, Bit1=0, Bit0=0: free
    Bit2=0, Bit1=0, Bit0=1: internal
    Bit2=0, Bit1=1, Bit0=0: A/D interface
    Bit2=0, Bit1=1, Bit0=1: RS232 interface
    Bit2=1, Bit1=0, Bit0=0: RS485 interface
    Bit2=1, Bit1=0, Bit0=1: Profibus interface

### Low byte
- Bit 5...7: Control mode
    Bit7=0, Bit6=0, Bit5=0: UDC control active
    Bit7=0, Bit6=0, Bit5=1: IDC control active
    Bit7=0, Bit6=1, Bit5=0: PDC control active
- Bit 4: not used
- Bit 3: not used
- Bit 2: not used
- Bit 1: 0=Tastung(sampling) on, 1=Tastung(sampling) off
- Bit 0: 0=Schütz(contactor) off, 1=Schütz(contactor) on


