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

time.sleep(0.05)

# Verify connection
keithley_6430.write("*IDN?")
response = keithley_6430.read()
print("Successful connection with 2400 Instrument:", response)

time.sleep(0.05)

# Reset the instrument to default settings
keithley_6430.write("*RST")

time.sleep(0.05)
keithley_6430.write("*CLS")  # Clear status and error queues


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

    # Set compliance limits (optional)
    # For example, limit voltage between -5V and +5V
    keithley_6430.write(":SENS:VOLT:DC:PROT:LOWER -5")
    keithley_6430.write(":SENS:VOLT:DC:PROT:UPPER 5")

    print("Instrument initialized for voltage sourcing and current measurement.")


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


def perform_iv_sweep(V_start, V_stop, V_step, settle_time=0.1):
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


# Initialize the source settings
initialize_source()

# Define sweep parameters
V_start = 0        # Starting voltage in V
V_stop = 1         # Stopping voltage in V
V_step = 0.1      # Voltage step in V
settle_time = 0.2  # Settling time in seconds

# Perform the IV sweep with live plotting
sweep_data = perform_iv_sweep(V_start, V_stop, V_step, settle_time)

# Save the sweep data to a CSV file
save_sweep_data(sweep_data)

# Optionally, plot the IV curve again after the sweep is completed
# This is useful if you prefer a static plot after the sweep
# plot_iv_curve(sweep_data)

# Close the instrument connection
keithley_6430.close()
rm.close()
print("Instrument connection closed.")
