import pyvisa
import time
import matplotlib.pyplot as plt
import csv
import datetime
import os

# Enable interactive mode for live plotting
plt.ion()

# Initialize PyVISA and connect to the instrument
rm = pyvisa.ResourceManager()

# List connected instruments
print("Connected Instruments:", rm.list_resources())

# Replace with your actual resource address
# Example for GPIB: 'GPIB::24::INSTR'
# Example for USB: 'USB::0x05E6::0x2408::043241234::INSTR'
keithley_6430 = rm.open_resource('ASRL3::INSTR', read_termination='\r', write_termination='\r')
rigol_dp832 = rm.open_resource('USB0::0x1AB1::0x0E11::DP8C233003503::INSTR', read_termination='\n', write_termination='\n')

time.sleep(0.05)

# Verify connection
keithley_6430.write("*IDN?")
response = keithley_6430.read()
print("Successful connection with 2400 Instrument:", response)

rigol_dp832.write("*IDN?")
response = rigol_dp832.read()
print("Successful connection with DP832 Instrument:", response)

time.sleep(0.05)

# Reset the instrument to default settings
keithley_6430.write("*RST")

time.sleep(0.05)
keithley_6430.write("*CLS")  # Clear status and error queues


def initialize_rigol_dp832():
    """
    Initialize the Rigol DP832 by configuring Channel 1 as a voltage source with 0 A current limit.
    """
    # Select Channel 1
    rigol_dp832.write("INST CH1")
    time.sleep(0.1)  # Short delay to ensure channel selection

    # Reset the channel to default settings
    rigol_dp832.write("*RST")
    time.sleep(0.1)

    # Set voltage to 0 V initially
    rigol_dp832.write("VOLT 0")
    time.sleep(0.1)

    # **Set current limit to 0 A**
    # Note: Rigol DP832 may not accept 0 A as a valid current limit.
    # If it rejects, set to the minimum allowed current (e.g., 0.001 A).
    try:
        rigol_dp832.write("CURR 0")
        print("Rigol DP832 Channel 1 set to 0 A current limit.")
    except pyvisa.errors.VisaIOError:
        # If 0 A is not allowed, set to the minimal current
        rigol_dp832.write("CURR 0.001")
        print("Rigol DP832 Channel 1 current limit set to 0.001 A (minimum allowed).")

    # Turn off the output initially
    rigol_dp832.write("OUTP OFF")
    print("Rigol DP832 Channel 1 initialized for voltage sourcing with 0 A current limit.")


def set_rigol_voltage(channel, voltage):
    """
    Sets the voltage on the specified channel of Rigol DP832.

    Args:
        channel (str): Channel identifier, e.g., 'CH1'.
        voltage (float): Desired voltage in volts.
    """
    rigol_dp832.write(f"INST {channel}")
    rigol_dp832.write(f"VOLT {voltage}")
    print(f"Rigol DP832 {channel} set to {voltage} V.")

def initialize_source():
    """
    Initialize the Keithley 2400 by setting source voltage and configuring current measurement.
    Prints the configured source values.
    """
    keithley_6430.write(":SOUR:FUNC VOLT")  # Set to voltage source mode
    keithley_6430.write(":SOUR:VOLT:LEV 0")  # Initialize voltage level to 0 V
    keithley_6430.write(":SOUR:CURR:LEV 0")  # Initialize current level to 0 A
    keithley_6430.write(":OUTP OFF")  # Ensure output is off initially

    # Configure measurement functions
    keithley_6430.write(":SENS:FUNC 'CURR'")  # Set measurement to current
    keithley_6430.write(":SENS:CURR:PROT 0.001")  # Set current protection to 1 mA (adjust as needed)

    # Configure auto-ranging (optional)
    keithley_6430.write(":SENS:VOLT:DC:RANGE:AUTO ON")
    keithley_6430.write(":SENS:CURR:DC:RANGE:AUTO ON")

    print("Instrument initialized for voltage sourcing and current measurement.")

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

def read_current():
    """
    Reads the current measurement from the Keithley 2400.
    Returns:
        float: Current in amperes
    """
    # Trigger a single measurement
    current = keithley_6430.query(":READ?")

    try:
        # The response might contain multiple values; extract current
        # Typically, response format: <voltage>,<current>,<other_values>
        values = current.strip().split(',')
        if len(values) >= 2:
            current_read = float(values[1])
            return current_read
        else:
            print("Unexpected response format:", current)
            return None
    except ValueError:
        print("Error parsing current value:", current)
        return None

def save_sweep_data(sweep_data, filename=None, Vg = None, Vd = None):
    """
    Saves the IV sweep data to a CSV file.

    Args:
        sweep_data (list of tuples): Each tuple contains (Voltage, Current)
        filename (str, optional): The filename for the CSV file. If not provided, a timestamped filename is generated.
    """
    if not filename:
        data_folder = 'Data'
        os.makedirs(data_folder, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        filename = f"{data_folder}/iv_sweep_Vg{Vg}_Vd{Vd}_{timestamp}.csv"

    try:
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Voltage (V)', 'Current (A)'])  # Header
            writer.writerows(sweep_data)
        print(f"Data successfully saved to {filename}")
    except Exception as e:
        print(f"Failed to save data to {filename}: {e}")


def perform_iv_sweep(V_start, V_stop, V_step, V_rigol, settle_time=0.1):
    """
    Performs a voltage sweep from V_start to V_stop in steps of V_step.
    Measures current at each voltage step and updates the plot in real-time.

    Args:
        V_start (float): Starting voltage in volts.
        V_stop (float): Stopping voltage in volts.
        V_step (float): Voltage step in volts.
        settle_time (float): Time to wait after setting voltage before measurement (in seconds).

    Returns:
        list of tuples: Each tuple contains (Voltage, Current)
    """
    sweep_data = []
    V = V_start
    direction = 1 if V_step > 0 else -1

    print(f"Starting IV sweep from {V_start} V to {V_stop} V with step {V_step} V")

    # Initialize the plot
    fig, ax = plt.subplots(figsize=(8, 6))
    line, = ax.plot([], [], 'b-o', markersize=4)
    ax.set_title("IV Curve")
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("Current (A)")
    plt.tight_layout()
    plt.show()

    voltages = []
    currents = []

    print(f"Setting Rigol DP832 Channel 1 to {V_rigol} V")
    # Set Rigol DP832's Channel 1 voltage and turn it on
    set_rigol_voltage("CH1", V_rigol)
    rigol_dp832.write("OUTP ON")  # Turn on Channel 1

    while (V <= V_stop and direction == 1) or (V >= V_stop and direction == -1):
        # Set the source voltage
        keithley_6430.write(f":SOUR:VOLT:LEV {V}")

        # Turn on the output
        keithley_6430.write(":OUTP ON")

        # Wait for the instrument to settle
        time.sleep(settle_time)

        # Read the current
        current = read_current()

        # Record the data
        if current is not None:
            sweep_data.append((V, current))
            voltages.append(V)
            currents.append(current)

        # Update the plot
        line.set_data(voltages, currents)
        ax.relim()            # Recompute the limits
        ax.autoscale_view()   # Autoscale the view
        fig.canvas.draw()
        fig.canvas.flush_events()

        # Turn off the output before next step to prevent overshoot (optional)
        # keithley_6430.write(":OUTP OFF")

        # Increment the voltage
        V += V_step

    # Reset to 0V and turn off output after sweep
    keithley_6430.write(":SOUR:VOLT:LEV 0")
    keithley_6430.write(":OUTP OFF")

    # Turn off Rigol DP832's Channel 1
    rigol_dp832.write("OUTP OFF")
    print("Rigol DP832 Channel 1 turned off.")
    print("IV sweep completed.")

    plt.ioff()  # Turn off interactive mode
    plt.show()  # Keep the plot open after the sweep

    return sweep_data


def plot_iv_curve(sweep_data):
    """
    Plots the IV curve from the sweep data.

    Args:
        sweep_data (list of tuples): Each tuple contains (Voltage, Current)
    """
    voltages, currents = zip(*sweep_data)
    plt.figure(figsize=(8, 6))
    plt.plot(voltages, currents, 'b-o', markersize=4)
    plt.title("IV Curve")
    plt.xlabel("Voltage (V)")
    plt.ylabel("Current (A)")
    plt.tight_layout()
    plt.show()

configure(keithley_6430, mode='V,I')

# Initialize the source settings
initialize_source()

# Initialize Rigol DP832's Channel 1
initialize_rigol_dp832()

# Define sweep parameters
V_start = 0        # Starting voltage in V
V_stop = 1         # Stopping voltage in V
V_step = 0.1      # Voltage step in V
settle_time = 0.5  # Settling time in seconds
V_rigol = 0.3

# Perform the IV sweep with live plotting
sweep_data = perform_iv_sweep(V_start, V_stop, V_step, V_rigol,  settle_time)

# Save the sweep data to a CSV file
save_sweep_data(sweep_data, Vg=None, Vd=V_rigol)

# Close the instrument connection
keithley_6430.close()
rm.close()
print("Instrument connection closed.")
