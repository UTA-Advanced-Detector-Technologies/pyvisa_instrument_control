import pyvisa
import time
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

smu_type = 'keithley_237' # can be keithley_237, keithley_2400, etc or "Other"

# Initialize PyVISA and connect to the instrument
rm = pyvisa.ResourceManager()

#should print something like this, find your instruments ('GPIB0::24::INSTR', 'GPIB0::25::INSTR', 'TCPIP0::192.168.1.100::INSTR')
print(rm.list_resources())

#try /n rather than /r if this doesnt work
keithley_instrument = rm.open_resource('GPIB0::15::INSTR', read_termination='\r\n', write_termination='\r\n')  # Replace with actual resource address
keithley_instrument.write("*RST")
keithley_instrument.write("X")
response = keithley_instrument.read() #if this is \n it gives timeout error for 6430
print("Successful connection with Instrument:", response)

time.sleep(0.1)
# Reset the instrument to default settings
keithley_instrument.write("*RST")

time.sleep(0.1)
keithley_instrument.write("*CLS")  # Clear status and error queues
def convert_237_output_to_float(reading_line):
    parts = reading_line.split(',')
    measurement_str = parts[0][5:]  # extract "+1.000E-03"
    value = float(measurement_str)
    return value

def initialize_source():
    """
    Initialize the Keithley 2400 by setting source current and source voltage to zero.
    Prints the configured source values.
    """

    # Query and print source values
    if smu_type == 'keithley_237': #instruments from this era have a different set of commands
        # for the 237 the output is NSDCV+<voltage>,B<status>
        '''keithley_instrument.write('F0,1X')  # Set to voltage source mode (Function 0, Mode 1)
        keithley_instrument.write('V0X')  # Set voltage level to 0 V
        keithley_instrument.write('H0X')  # Turn on the high-voltage output
        voltage = keithley_instrument.query('U0X')  # Query the voltage reading

        keithley_instrument.write('I0X')  # Set current compliance to 0 A (adjust as needed)
        current = keithley_instrument.query('I0X')  # Query the current reading

        print(f"Source Voltage: {voltage} ")
        print(f"Source Current: {current} ")'''

        # Set measurement function to voltage
        keithley_instrument.write('F0X')
        # Set source function to voltage
        keithley_instrument.write('Z0X')
        # Set an appropriate voltage range (for example, R3 might be 10 V range)
        keithley_instrument.write('R3X')
        # Turn the output on
        keithley_instrument.write('O1X')
        # Set the source voltage to 0.0 V
        keithley_instrument.write('V0.0X')
        # Set trigger mode for a single measurement
        keithley_instrument.write('N0X')
        # Trigger the measurement
        keithley_instrument.write('X')
        # Read the measurement
        voltage_reading = keithley_instrument.read()

        # Set measurement function to current (F1 for current)
        keithley_instrument.write('F1X')
        # Set source function to current source mode (Z1 for current sourcing)
        keithley_instrument.write('Z1X')
        # Select a suitable current range. For example, R3X might be a certain current range.
        # Check the Keithley 237 manual for the exact current range settings.
        keithley_instrument.write('R3X')
        # Turn the output on
        keithley_instrument.write('O1X')
        # I<value>X sets the source current to <value> in Amps.
        keithley_instrument.write('I0.000X')  # sets 1 mA source current
        # Set trigger mode for a single measurement
        keithley_instrument.write('N0X')
        # Trigger the measurement
        keithley_instrument.write('X')
        # Read the measured current
        current_reading = keithley_instrument.read()

        print("Measured Current Reading:",convert_237_output_to_float(current_reading))
        print("Sourced Voltage Reading:", convert_237_output_to_float(voltage_reading))


    else:
        keithley_instrument.write(":SOUR:FUNC VOLT")  # Set to voltage source mode
        keithley_instrument.write(":SOUR:VOLT:LEV 0")  # Set voltage level to 0
        keithley_instrument.write(":SOUR:CURR:LEV 0")  # Set current level to 0
        keithley_instrument.write(":OUTP ON")  # Turn on output

        voltage = keithley_instrument.query(":SOUR:VOLT:LEV?")
        current = keithley_instrument.query(":SOUR:CURR:LEV?")

        print(f"Source Voltage: {voltage.strip()} V")
        print(f"Source Current: {current.strip()} A")


def read_current():
    """
    Reads the current measurement from the Keithley 2400.
    Returns:
        float: The measured current in amperes.
    """
    # Send the measurement command and get the response
    if smu_type == 'keithley_237':
        # Set trigger mode for a single measurement
        keithley_instrument.write('N0X')
        # Trigger the measurement
        keithley_instrument.write('X')
        # Read the measured current
        current_reading = keithley_instrument.read()

        # Split the response by commas
        current_read = convert_237_output_to_float(current_reading)
        return current_read
    else:
        response = keithley_instrument.query(":MEAS:CURR?")
        # returns +0.000000E+00,-5.033000E-11,+9.910000E+37,+3.540547E+03,+2.048200E+04
        # corresponds to voltage reading, curent reading, resistance reading.. etc. nan or +9.91e37 is used for not used functions

        # Split the response by commas
        values = response.strip().split(',')

        # Ensure there are enough values returned
        if len(values) >= 1:
            # Extract the measured current (second value)
            current_read = float(values[1])
            #print("Measured current (A):", current_read)
            return current_read
        else:
            print("Unexpected response format:", response)
            return None


def configure(_s, mode='', vRange=None, iRange=None, vLimits=None, iLimits=None):
    '''Definition is an adaptation from Yuan Mei's previous work'''
    vRange = vRange
    iRange = iRange

    if vRange:
        _s.write(":SENS:VOLT:DC:RANGE 20")
    else:
        _s.write(":SENS:VOLT:DC:RANGE:AUTO ON")
    if iRange:
        _s.write(f":SENS:CURR:DC:RANGE {iRange}")
    else:
        _s.write(":SENS:CURR:DC:RANGE:AUTO ON")
    if vLimits:
        _s.write(f":SENS:VOLT:DC:RANGE:AUTO:LLIMIT {vLimits[0]}")
        _s.write(f":SENS:VOLT:DC:RANGE:AUTO:ULIMIT {vLimits[1]}")
    if iLimits:
        _s.write(f":SENS:CURR:DC:RANGE:AUTO:LLIMIT {iLimits[0]}")
        _s.write(f":SENS:CURR:DC:RANGE:AUTO:ULIMIT {iLimits[1]}")

    if mode == 'V':
        mode = mode
        _s.write(":SENS:FUNC \"VOLT\"")
    elif mode == 'I':
        mode = mode
        _s.write(":SENS:FUNC \"CURR\"")
    elif mode == 'R':
        mode = mode
        _s.write(":SENS:FUNC \"RES\"")
    time.sleep(0.3)
    # self._s.write(":SYSTem:ZCHeck OFF")      #doesnt like this line, undef header.. hashed out for now
    # self._s.write(":INITiate:CONTinuous ON")
    time.sleep(0.2)


# Initialize the source settings
initialize_source()

# Real-time plotting setup
current_data = []
time_data = []

fig, ax = plt.subplots()
line, = ax.plot([], [], label="Drain Current (A)")
ax.set_xlim(0, 10)  # Adjust x-axis limits dynamically later
ax.set_ylim(-0.01, 0.01)  # Adjust y-axis as needed for your current range
ax.set_title("Real-Time Current Measurement")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Current (A)")
ax.legend()

start_time = time.time()

def update(frame):
    """Update function for the animation."""
    global current_data, time_data, start_time

    # Read the current
    current = read_current()
    elapsed_time = time.time() - start_time

    # Update data
    time_data.append(elapsed_time)
    current_data.append(current)

    # Dynamically adjust x-axis
    ax.set_xlim(0, max(time_data) + 1)

    x_min, x_max = ax.get_xlim()

    # Filter current_data to include only values within the visible x-axis range
    visible_data = [
        current_data[i] for i, t in enumerate(time_data) if x_min <= t <= x_max
    ]

    # Dynamically adjust y-axis based on the visible data
    if visible_data:  # Ensure there's visible data
        data_min = min(visible_data)
        data_max = max(visible_data)

        # Ensure a small range for close or identical points
        if data_min == data_max:
            padding = abs(data_min) * 0.1 if data_min != 0 else 0.01
            ax.set_ylim(data_min - padding, data_max + padding)
        else:
            # Add 5% padding to the range
            padding = (data_max - data_min) * 0.05
            ax.set_ylim(data_min - padding, data_max + padding)
    # Update the plot
    line.set_data(time_data, current_data)
    return line,

if smu_type != 'keithley_237':
    configure(keithley_instrument, mode='I')

# Animation
ani = FuncAnimation(fig, update, interval=500)  # Update every 500 ms

# Display the graph
plt.show()

# Close the instrument after the plot window is closed
if smu_type == 'keithley_237':
    keithley_instrument.write("N0X")
else:
    keithley_instrument.write(":OUTP OFF")

keithley_instrument.close()
