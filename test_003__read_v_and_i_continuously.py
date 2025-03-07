import pyvisa
import time
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Initialize PyVISA and connect to the instrument
rm = pyvisa.ResourceManager()

# List connected instruments
print("Connected Instruments:", rm.list_resources())

# Replace with your actual resource address
keithley_2400 = rm.open_resource('ASRL3::INSTR', read_termination='\r', write_termination='\r')

time.sleep(0.05)
# Verify connection
keithley_2400.write("*IDN?")
response = keithley_2400.read()
print("Successful connection with 2400 Instrument:", response)

time.sleep(0.05)
# Reset the instrument to default settings
keithley_2400.write("*RST")

time.sleep(0.05)
keithley_2400.write("*CLS")  # Clear status and error queues

def initialize_source():
    """
    Initialize the Keithley 2400 by setting source voltage and configuring current measurement.
    Prints the configured source values.
    """
    keithley_2400.write(":SOUR:FUNC VOLT")  # Set to voltage source mode
    keithley_2400.write(":SOUR:VOLT:LEV 0")  # Set voltage level to 0
    keithley_2400.write(":SOUR:CURR:LEV 0")  # Set current level to 0
    keithley_2400.write(":OUTP ON")  # Turn on output

    # Query and print source values
    voltage = keithley_2400.query(":SOUR:VOLT:LEV?")
    current = keithley_2400.query(":SOUR:CURR:LEV?")
    print(f"Source Voltage: {voltage.strip()} V")
    print(f"Source Current: {current.strip()} A")

def read_measurements():
    """
    Reads both voltage and current measurements from the Keithley 2400.
    Returns:
        tuple: (voltage in volts, current in amperes)
    """
    # Send the measurement command and get the response
    response = keithley_2400.query(":READ?")
    # Example response: +0.000000E+00,-5.033000E-11,+9.910000E+37,+3.540547E+03,+2.048200E+04
    # Corresponds to voltage, current, resistance, etc.

    # Split the response by commas
    values = response.strip().split(',')

    # Ensure there are enough values returned
    if len(values) >= 2:
        try:
            # Extract the measured voltage (first value) and current (second value)
            voltage_read = float(values[0])
            current_read = float(values[1])
            return voltage_read, current_read
        except ValueError:
            print("Error parsing measurement values:", values)
            return None, None
    else:
        print("Unexpected response format:", response)
        return None, None

def configure(_s, mode='', vRange=None, iRange=None, vLimits=None, iLimits=None):
    """
    Configures the measurement settings of the instrument.
    Definition is an adaptation from Yuan Mei's previous work
    """
    vRange = vRange
    iRange = iRange

    if vRange:
        _s.write(":SENS:VOLT:DC:RANGE {}".format(vRange))
    else:
        _s.write(":SENS:VOLT:DC:RANGE:AUTO ON")
    if iRange:
        _s.write(f":SENS:CURR:DC:RANGE {iRange}")
    else:
        _s.write(":SENS:CURR:DC:RANGE:AUTO ON")
    if vLimits:
        _s.write(f":SENS:VOLT:DC:PROT:LOWER {vLimits[0]}")
        _s.write(f":SENS:VOLT:DC:PROT:UPPER {vLimits[1]}")
    if iLimits:
        _s.write(f":SENS:CURR:DC:PROT:LOWER {iLimits[0]}")
        _s.write(f":SENS:CURR:DC:PROT:UPPER {iLimits[1]}")

    if mode == 'V,I':
        _s.write(":SENS:FUNC 'VOLT','CURR'")
    elif mode == 'V':
        _s.write(":SENS:FUNC 'VOLT'")
    elif mode == 'I':
        _s.write(":SENS:FUNC 'CURR'")
    elif mode == 'R':
        _s.write(":SENS:FUNC 'RES'")
    time.sleep(0.3)
    time.sleep(0.2)

# Initialize the source settings
initialize_source()

# Configure the instrument to measure both voltage and current
keithley_6430

# Real-time plotting setup
voltage_data = []
current_data = []
time_data = []

fig, ax1 = plt.subplots()
ax2 = ax1.twinx()  # Create a second y-axis for current

# Plot voltage on ax1
line1, = ax1.plot([], [], 'b-', label="Measured Voltage (V)")
ax1.set_xlabel("Time (s)")
ax1.set_ylabel("Voltage (V)", color='b')
ax1.tick_params(axis='y', labelcolor='b')

# Plot current on ax2
line2, = ax2.plot([], [], 'r-', label="Measured Current (A)")
ax2.set_ylabel("Current (A)", color='r')
ax2.tick_params(axis='y', labelcolor='r')

# Title and legends
plt.title("Real-Time Voltage and Current Measurement")
lines = [line1, line2]
labels = [line.get_label() for line in lines]
ax1.legend(lines, labels, loc='upper left')

start_time = time.time()

def update(frame):
    """Update function for the animation."""
    global voltage_data, current_data, time_data, start_time

    # Read the voltage and current
    voltage, current = read_measurements()
    if voltage is None or current is None:
        return lines

    elapsed_time = time.time() - start_time

    # Update data
    time_data.append(elapsed_time)
    voltage_data.append(voltage)
    current_data.append(current)

    # Dynamically adjust x-axis
    ax1.set_xlim(0, max(time_data) + 1)

    x_min, x_max = ax1.get_xlim()

    # Filter data to include only values within the visible x-axis range
    visible_indices = [i for i, t in enumerate(time_data) if x_min <= t <= x_max]
    visible_time = [time_data[i] for i in visible_indices]
    visible_voltage = [voltage_data[i] for i in visible_indices]
    visible_current = [current_data[i] for i in visible_indices]

    # Dynamically adjust y-axis for voltage
    if visible_voltage:
        v_min = min(visible_voltage)
        v_max = max(visible_voltage)
        if v_min == v_max:
            padding = abs(v_min) * 0.1 if v_min != 0 else 0.1
            ax1.set_ylim(v_min - padding, v_max + padding)
        else:
            v_padding = (v_max - v_min) * 0.05
            ax1.set_ylim(v_min - v_padding, v_max + v_padding)

    # Dynamically adjust y-axis for current
    if visible_current:
        i_min = min(visible_current)
        i_max = max(visible_current)
        if i_min == i_max:
            padding = abs(i_min) * 0.1 if i_min != 0 else 0.1
            ax2.set_ylim(i_min - padding, i_max + padding)
        else:
            i_padding = (i_max - i_min) * 0.05
            ax2.set_ylim(i_min - i_padding, i_max + i_padding)

    # Update the plot lines
    line1.set_data(visible_time, visible_voltage)
    line2.set_data(visible_time, visible_current)
    return lines

# Animation
ani = FuncAnimation(fig, update, interval=500)  # Update every 500 ms

# Display the graph
plt.show()

# Close the instrument after the plot window is closed
# Stop any ongoing operations
keithley_2400.write(":ABOR")
time.sleep(0.1)  # Allow time for the command to be processed

# Attempt to turn off the output
#keithley_2400.write("OUTP OFF")

#print("Successfully turned off the output.")

rm.close()
