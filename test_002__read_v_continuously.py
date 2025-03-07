import pyvisa
import time
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Initialize PyVISA and connect to the instrument
rm = pyvisa.ResourceManager()

# List connected instruments
print("Connected Instruments:", rm.list_resources())

# Replace with your actual resource address
keithley_6430 = rm.open_resource('ASRL3::INSTR', read_termination='\r', write_termination='\r')

# Verify connection
keithley_6430.write("*IDN?")
response = keithley_6430.read()
print("Successful connection with 2400 Instrument:", response)

time.sleep(0.1)
# Reset the instrument to default settings
keithley_6430.write("*RST")

time.sleep(0.1)
keithley_6430.write("*CLS")  # Clear status and error queues

def initialize_source():
    """
    Initialize the Keithley 2400 by setting source current and configuring voltage measurement.
    Prints the configured source values.
    """
    keithley_6430.write(":SOUR:FUNC VOLT")  # Set to voltage source mode
    keithley_6430.write(":SOUR:VOLT:LEV 0")  # Set voltage level to 0
    keithley_6430.write(":SOUR:CURR:LEV 0")  # Set current level to 0
    keithley_6430.write(":OUTP ON")  # Turn on output

    # Query and print source values
    voltage = keithley_6430.query(":SOUR:VOLT:LEV?")
    current = keithley_6430.query(":SOUR:CURR:LEV?")
    print(f"Source Voltage: {voltage.strip()} V")
    print(f"Source Current: {current.strip()} A")

def read_voltage():
    """
    Reads the voltage measurement from the Keithley 2400.
    Returns:
        float: The measured voltage in volts.
    """
    # Send the measurement command and get the response
    response = keithley_6430.query(":MEAS:VOLT?")
    # returns +0.000000E+00,-5.033000E-11,+9.910000E+37,+3.540547E+03,+2.048200E+04
    # corresponds to voltage reading, curent reading, resistance reading.. etc. nan or +9.91e37 is used for not used functions

    # Split the response by commas
    values = response.strip().split(',')

    # Ensure there are enough values returned
    if len(values) >= 1:
        # Extract the measured voltage (first value)
        voltage_read = float(values[0])
        # print("Measured voltage (v):", voltage_read)
        return voltage_read
    else:
        print("Unexpected response format:", response)
        return None

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

    if mode == 'V':
        _s.write(":SENS:FUNC 'VOLT'")
    elif mode == 'I':
        _s.write(":SENS:FUNC 'CURR'")
    elif mode == 'R':
        _s.write(":SENS:FUNC 'RES'")
    time.sleep(0.3)
    time.sleep(0.2)

# Initialize the source settings
initialize_source()

# Configure the instrument to measure voltage
configure(keithley_6430, mode='V')

# Real-time plotting setup
voltage_data = []
time_data = []

fig, ax = plt.subplots()
line, = ax.plot([], [], label="Measured Voltage (V)")
ax.set_xlim(0, 10)  # Initial x-axis limits; will adjust dynamically
ax.set_ylim(-1, 11)  # Adjust y-axis based on expected voltage range
ax.set_title("Real-Time Voltage Measurement")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Voltage (V)")
ax.legend()

start_time = time.time()

def update(frame):
    """Update function for the animation."""
    global voltage_data, time_data, start_time

    # Read the voltage
    voltage = read_voltage()
    if voltage is None:
        return line,

    elapsed_time = time.time() - start_time

    # Update data
    time_data.append(elapsed_time)
    voltage_data.append(voltage)

    # Dynamically adjust x-axis
    ax.set_xlim(0, max(time_data) + 1)

    x_min, x_max = ax.get_xlim()

    # Filter voltage_data to include only values within the visible x-axis range
    visible_data = [
        voltage_data[i] for i, t in enumerate(time_data) if x_min <= t <= x_max
    ]

    # Dynamically adjust y-axis based on the visible data
    if visible_data:  # Ensure there's visible data
        data_min = min(visible_data)
        data_max = max(visible_data)

        # Ensure a small range for close or identical points
        if data_min == data_max:
            padding = abs(data_min) * 0.1 if data_min != 0 else 0.1
            ax.set_ylim(data_min - padding, data_max + padding)
        else:
            # Add 5% padding to the range
            padding = (data_max - data_min) * 0.05
            ax.set_ylim(data_min - padding, data_max + padding)
    # Update the plot
    line.set_data(time_data, voltage_data)
    return line,

# Animation
ani = FuncAnimation(fig, update, interval=500)  # Update every 500 ms

# Display the graph
plt.show()

# Close the instrument after the plot window is closed
#keithley_6430.write(":OUTP OFF")
keithley_6430.close()
rm.close()
