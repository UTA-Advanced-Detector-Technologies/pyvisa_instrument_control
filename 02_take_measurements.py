import pyvisa
import time
import numpy as np
import os
import json
import csv
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec


# -----------------------------------------------------------------------------------------------------------------------
#                                                 HELPER FUNCTIONS
# -----------------------------------------------------------------------------------------------------------------------
def remove_greater_than_20(lst):
    return [item for item in lst if not (isinstance(item, (int, float)) and abs(item) > 20)]

def drange(start, stop, step):
    """Returns a list of decimal numbers for increment or decrement values"""
    result = []
    intermediate_voltage = float(start)
    if step>0:
        while intermediate_voltage < stop:
            result.append(round(intermediate_voltage,1))
            intermediate_voltage+=step
    elif step<0:
        while intermediate_voltage > stop:
            result.append(round(intermediate_voltage,1))
            intermediate_voltage += step
    else:
        return []

    return result

def plot_data(Vd_meas_list, Id_meas_list, Vds_list, save_path):
    """Generates and saves plots for Id_meas vs. Vd_meas and Id_meas vs. Vds."""

    if not os.path.exists(save_path):
        os.makedirs(save_path)  # Create directory if it doesn't exist

    if Vd_meas_list is not None and Id_meas_list is not None and Vds_list is not None:
        # Plot Id_meas vs Vd_meas
        plt.figure(figsize=(8, 6))
        plt.plot(Vd_meas_list, Id_meas_list, marker='o', linestyle='-', color='b', label="Id_meas vs Vd_meas")
        plt.xlabel("Vd_meas (V)")
        plt.ylabel("Id_meas (A)")
        plt.title("Id_meas vs Vd_meas")
        plt.legend()
        plt.grid(True)
        plt.savefig(f"{save_path}Id_meas_vs_Vd_meas.png", dpi=300)  # Save plot
        plt.show()

        # Plot Id_meas vs Vds
        plt.figure(figsize=(8, 6))
        plt.plot(Vds_list, Id_meas_list, marker='s', linestyle='-', color='r', label="Id_meas vs Vds")
        plt.xlabel("Vds (V)")
        plt.ylabel("Id_meas (A)")
        plt.title("Id_meas vs Vds")
        plt.legend()
        plt.grid(True)
        plt.savefig(f"{save_path}Id_meas_vs_Vds.png", dpi=300)  # Save plot
        plt.show()

def load_mux_instructions(json_file="mux_instructions.json"):
    """
    Loads multiplexer configuration instructions from a JSON file.
    """
    with open(json_file, "r") as f:
        mux_data = json.load(f)
    return mux_data

def load_sweep_bias_instructions_from_json(input_file):
    """
    Loads and returns sweep/bias instructions from a JSON file.
    """
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
        print(f"Processed data successfully loaded from {input_file}")
        return data
    except Exception as e:
        print(f"Failed to load processed data from {input_file}. Error: {e}")
        return None

def insert_evenly_spaced_points_partial(lst, start, stop, num_points):
    if num_points < 1:
        raise ValueError("Number of points to add must be at least 1.")

    new_list = []
    for i in range(len(lst) - 1):
        current = lst[i]
        next_val = lst[i + 1]
        new_list.append(current)

        sorted_pair = sorted([current, next_val])
        lower_val, upper_val = sorted_pair[0], sorted_pair[1]
        lower_overlap = max(lower_val, start)
        upper_overlap = min(upper_val, stop)

        if lower_overlap < upper_overlap:
            step = (upper_overlap - lower_overlap) / (num_points + 1)
            ascending_subsegment = (current < next_val)
            inserted_points = []
            for n in range(1, num_points + 1):
                new_point = lower_overlap + step * n
                inserted_points.append(new_point)
            if not ascending_subsegment:
                inserted_points.reverse()
            new_list.extend(inserted_points)

    new_list.append(lst[-1])
    new_list = [round(n, 3) for n in new_list]
    return new_list


def apply_log_spacing_after_changepoint(values, changepoint_value):
    all_negative = all(v < 0 for v in values)
    if all_negative:
        pos_values = [-v for v in values]
        cp_val = -changepoint_value
    else:
        pos_values = values[:]
        cp_val = changepoint_value

    try:
        cp_index = pos_values.index(cp_val)
    except ValueError:
        raise ValueError(
            f"The changepoint_value={changepoint_value} (or {cp_val} if flipped) was not found in the input list."
        )

    output = pos_values[:cp_index + 1]
    n_points_to_fill = len(pos_values) - (cp_index + 1)
    if n_points_to_fill <= 0:
        final_output = output
    else:
        start_val = pos_values[cp_index]
        end_val = pos_values[-1]
        if start_val <= 0 or end_val <= 0:
            raise ValueError("Cannot create log spacing with non-positive start or end value.")
        n_log_points = n_points_to_fill + 1
        log_spaced = np.logspace(np.log10(start_val),
                                 np.log10(end_val),
                                 n_log_points + 1)
        new_segment = log_spaced[1:n_log_points + 1]
        final_output = output + list(new_segment)

    if all_negative:
        final_output = [-v for v in final_output]
    final_output = [round(f, 3) for f in final_output]
    return final_output


def load_bias_instructions(fet_type="NMOS", input_json_path = 'sweep_bias_instructions_v3.json'):
    """
    Loads pre-defined bias/sweep instructions from JSON for NMOS or PMOS.
    """
    try:
        if "NMOS" not in fet_type and "PMOS" not in fet_type:
            raise ValueError("Please pass \"NMOS\" or \"PMOS\" as fet_type")
    except ValueError as e:
        print(e)

    processed_data = load_sweep_bias_instructions_from_json(input_json_path)
    if not processed_data:
        print("No data loaded from JSON. Check file and path.")
        return (None, None, None)

    # Extract relevant sections
    transfer_char_set1 = processed_data.get(fet_type, {}).get('Primary sweep: Vgs Set 1', {})
    transfer_char_set2 = processed_data.get(fet_type, {}).get('Primary sweep: Vgs Set 2', {})
    transfer_char = processed_data.get(fet_type, {}).get('Primary sweep: Vds', {})

    transfer_char_set1_vsource_sub = transfer_char_set1.get("Vsource_sub", [])
    transfer_char_set1_vbulk_sourc = transfer_char_set1.get("Vbulk_source", [])
    transfer_char_set1_vdrain_source = transfer_char_set1.get("Vdrain_source", [])
    transfer_char_set1_vgate_source = transfer_char_set1.get("Vgate_source", [])

    transfer_char_set2_vsource_sub = transfer_char_set2.get("Vsource_sub", [])
    transfer_char_set2_vbulk_sourc = transfer_char_set2.get("Vbulk_source", [])
    transfer_char_set2_vdrain_source = transfer_char_set2.get("Vdrain_source", [])
    transfer_char_set2_vgate_source = transfer_char_set2.get("Vgate_source", [])

    transfer_char_vsource_sub = transfer_char.get("Vsource_sub", [])
    transfer_char_vbulk_sourc = transfer_char.get("Vbulk_source", [])
    transfer_char_vdrain_source = transfer_char.get("Vdrain_source", [])
    transfer_char_vgate_source = transfer_char.get("Vgate_source", [])

    return (
        (transfer_char_set1_vsource_sub, transfer_char_set1_vbulk_sourc, transfer_char_set1_vdrain_source, transfer_char_set1_vgate_source),
        (transfer_char_set2_vsource_sub, transfer_char_set2_vbulk_sourc, transfer_char_set2_vdrain_source, transfer_char_set2_vgate_source),
        (transfer_char_vsource_sub, transfer_char_vbulk_sourc, transfer_char_vdrain_source, transfer_char_vgate_source)
    )


def read_temperature(lakeshore, channel='A'):
    """
    Query the Lakeshore controller for the temperature on the specified channel.
    """
    response = lakeshore.query(f'KRDG? {channel}')
    return float(response.strip())


def configure_instr(sourcing_voltage,
                    instr,
                    current_compliance=0.105,
                    voltage_compliance=27,
                    ascii_command_flavor='SCPI',
                    wire_mode=2,
                    current_range=0.001,
                    disable_front_panel=True,
                    curr_range_hard_set=False,
                    voltage_range=20):
    try:
        if ascii_command_flavor == 'SCPI':
            instr.write('*RST')
            if disable_front_panel:
                instr.write(":DISP:ENAB OFF")
            if wire_mode == 2:
                instr.write(":SYST:RSEN OFF")
            elif wire_mode == 4:
                instr.write(":SYST:RSEN ON")
            else:
                print('Invalid wire_mode passed, please pass 2 or 4')
            instr.write(':SOUR:FUNC VOLT')
            instr.write(':SOUR:VOLT:RANG:AUTO ON')
            #instr.write(':SOUR:VOLT:MODE FIXED')
            #instr.write(f':SOUR:VOLT:RANG {voltage_range}')
            instr.write(f':SENS:VOLT:PROT {voltage_compliance}')
            instr.write(f':SOUR:VOLT {sourcing_voltage}')
            instr.write(':SENS:FUNC "CURR"')
            instr.write(f':SENS:CURR:PROT {current_compliance}')
            if curr_range_hard_set:
                instr.write(':SENS:CURR:RANG:AUTO OFF')
                instr.write(f':SENS:CURR:RANG {current_range}')
            else:
                instr.write(':SENS:CURR:RANG:AUTO ON')
            instr.write(':SENS:AVER:COUN 4')
            instr.write(':SENS:AVER:TCON REP')
            instr.write(':SENS:AVER:STAT ON')
            instr.write(':OUTP ON')
        elif ascii_command_flavor == 'non-SCPI':
            instr.write("F0,0X")
            instr.write(f'B{sourcing_voltage},0,0X')
            instr.write(f"L{current_compliance},5X")
            instr.write("P2X")
            instr.write("R1X")
            instr.write('H0X')
            instr.write("N1X")
        else:
            raise ValueError("Invalid ascii_command_flavor: Use 'non-SCPI' or 'SCPI'.")
    except ValueError as e:
        print(e)


def set_voltage(sourcing_voltage, instr, ascii_command_flavor='SCPI'):
    try:
        if ascii_command_flavor == 'SCPI':
            instr.write(f':SOUR:VOLT {sourcing_voltage}')
        elif ascii_command_flavor == 'non-SCPI':
            instr.write(f'B{sourcing_voltage},0,0X')
        else:
            raise ValueError("Invalid ascii_command_flavor: Use 'non-SCPI' or 'SCPI'.")
    except ValueError as e:
        print(e)


def measure_iv(instr, ascii_command_flavor='SCPI'):
    try:
        if ascii_command_flavor.upper() == 'SCPI':
            response = instr.query(":READ?")
            data = response.strip().split(',')
            voltage = float(data[0])
            current = float(data[1])
            return (voltage, current)
        elif ascii_command_flavor.lower() == 'non-scpi':
            commands = "O1X;G4,2,0X;H0X;"
            instr.write(commands)
            response = instr.query("X")
            current = float(response.strip())
            return (None, current)
        else:
            raise ValueError("Invalid ascii_command_flavor.")
    except Exception as e:
        print("Error in measure_iv:", e)
        return (None, None)


def measure_current(instr, ascii_command_flavor='SCPI'):
    try:
        if ascii_command_flavor.upper() == 'SCPI':
            response = instr.query(":READ?")
            current = float(response.strip().split(',')[1])
        elif ascii_command_flavor.lower() == 'non-scpi':
            commands = "O1X;G4,2,0X;H0X;"
            instr.write(commands)
            response = instr.query("X")
            current = float(response.strip())
        else:
            raise ValueError("Invalid ascii_command_flavor.")
        return current
    except IndexError:
        print("Unexpected response format:", response)
    except ValueError as ve:
        print("Value conversion error:", ve)
    except Exception as e:
        print("Error measuring current:", e)
    return None


# -----------------------------------------------------------------------------------------------------------------------
#                           UPDATED VOLTAGE SWEEP FUNCTION (NOW WITH TEMPERATURE)
# -----------------------------------------------------------------------------------------------------------------------
def voltage_sweep_three_instruments(
        fixed,
        variable,
        sweep_voltages,
        fixed_voltage,
        bulk_source_voltage,
        source_substrate_voltage,
        drain_source_instr,
        gate_source_instr,
        bulk_source_instr,
        source_sub_instrum,
        curr_compliance=0.01,
        live_plot=True,
        drain_curr_range=0.01,
        settle_delay=0.05,
        lakeshore=None,  # <-- new parameter for temperature instrument
        start_global=None  # <-- new parameter: reference time (e.g., time.time() before sweep)
):
    """
    Sweeps the 'variable' voltage while holding the other nodes constant.
    Now in addition to measuring currents and voltages, if a Lakeshore instrument and start_global
    time are provided, it also reads temperature (from channels A and B) and records elapsed time.

    The returned data tuple now contains 15 elements:
      (Vd_src, Vg_src, Vb_src, Vsub_src, Id, Ib, Isub, Ig, Vd_meas, Vb_meas, Vsub_meas, Vg_meas, TempA, TempB, Elapsed_time)
    """
    # --- Prepare live plot with an extra temperature subplot if requested ---
    if live_plot:
        plt.ion()  # interactive mode
        # Create a figure with 5 rows; rows 0-3 are for currents/voltages and row 4 is for temperature.
        fig_all = plt.figure(figsize=(10, 10))
        gs = gridspec.GridSpec(5, 2, height_ratios=[1, 1, 1, 1, 1])
        # Rows for currents and voltages:
        ax0_left = fig_all.add_subplot(gs[0, 0])
        ax0_right = fig_all.add_subplot(gs[0, 1])
        ax1_left = fig_all.add_subplot(gs[1, 0])
        ax1_right = fig_all.add_subplot(gs[1, 1])
        ax2_left = fig_all.add_subplot(gs[2, 0])
        ax2_right = fig_all.add_subplot(gs[2, 1])
        ax3_left = fig_all.add_subplot(gs[3, 0])
        ax3_right = fig_all.add_subplot(gs[3, 1])
        # Temperature subplot (spanning both columns):
        ax_temp = fig_all.add_subplot(gs[4, :])

        # Set labels for current plots (left column)
        ax0_left.set_ylabel("Drain I (A)")
        ax1_left.set_ylabel("Bulk I (A)")
        ax2_left.set_ylabel("Substrate I (A)")
        ax3_left.set_ylabel("Gate I (A)")
        ax3_left.set_xlabel(f"{variable} (V)")
        # Set labels for voltage plots (right column)
        ax0_right.set_ylabel("Drain V (V)")
        ax1_right.set_ylabel("Bulk V (V)")
        ax2_right.set_ylabel("Substrate V (V)")
        ax3_right.set_ylabel("Gate V (V)")
        ax3_right.set_xlabel(f"{variable} (V)")
        # Temperature plot labels
        ax_temp.set_xlabel("Time (s)")
        ax_temp.set_ylabel("Temperature (K)")

        # Create line objects:
        line_drain_source_i, = ax0_left.plot([], [], 'b-o', markersize=4, label='Drain Current')
        line_bulk_source_i, = ax1_left.plot([], [], 'r-o', markersize=4, label='Bulk Current')
        line_source_sub_i, = ax2_left.plot([], [], 'r-o', markersize=4, label='Substrate Current')
        line_gate_source_i, = ax3_left.plot([], [], 'g-o', markersize=4, label='Gate Current')

        line_drain_source_v, = ax0_right.plot([], [], 'b-o', markersize=4, label='Drain Voltage')
        line_bulk_source_v, = ax1_right.plot([], [], 'r-o', markersize=4, label='Bulk Voltage')
        line_source_sub_v, = ax2_right.plot([], [], 'r-o', markersize=4, label='Substrate Voltage')
        line_gate_source_v, = ax3_right.plot([], [], 'g-o', markersize=4, label='Gate Voltage')

        # Temperature lines (for two channels)
        line_tempA, = ax_temp.plot([], [], 'm-', label='Temperature A')
        line_tempB, = ax_temp.plot([], [], 'c-', label='Temperature B')
        ax_temp.legend(loc='best')

        fig_all.suptitle(
            f"{variable} Sweep with Fixed {fixed} = {fixed_voltage} V, Vbulk_source = {bulk_source_voltage} V, "
            f"Vsource_sub = {source_substrate_voltage} V",
            fontsize=12
        )
        fig_all.tight_layout()
        fig_all.show()

    # Prepare arrays for final data and for live plotting:
    data = []
    plotting_voltages = []  # x-axis for the sweep
    plotting_drain_source_currents = []
    plotting_bulk_source_currents = []
    plotting_source_sub_currents = []
    plotting_gate_source_currents = []
    plotting_drain_source_voltages = []
    plotting_bulk_source_voltages = []
    plotting_source_sub_voltages = []
    plotting_gate_source_voltages = []
    # For temperature (if measured):
    plotting_time = []
    plotting_tempA = []
    plotting_tempB = []

    # Set body and substrate voltages:
    set_voltage(source_substrate_voltage, source_sub_instrum, ascii_command_flavor='SCPI')
    set_voltage(bulk_source_voltage, bulk_source_instr, ascii_command_flavor='SCPI')
    Vb_src = bulk_source_voltage
    Vsub_src = source_substrate_voltage

    # Set the "fixed" node:
    if fixed == 'Vd':
        set_voltage(fixed_voltage, drain_source_instr, ascii_command_flavor='SCPI')
    elif fixed == 'Vg':
        set_voltage(fixed_voltage, gate_source_instr, ascii_command_flavor='SCPI')
    else:
        print("Warning: 'fixed' should be 'Vd' or 'Vg' in this example code.")

    # Initialize the "variable" node to 0 V:
    if variable == 'Vd':
        set_voltage(0, drain_source_instr, ascii_command_flavor='SCPI')
    elif variable == 'Vg':
        set_voltage(0, gate_source_instr, ascii_command_flavor='SCPI')
    else:
        print("Warning: 'variable' should be 'Vd' or 'Vg' in this example code.")

    range_flip_voltage_done = False
    range_flip_current_done = False
    last_curr_val=0
    for v_value in sweep_voltages:
        # Update the "variable" voltage:
        if variable == 'Vd':
            drain_source_instr.write(f":SOUR:VOLT:LEV {v_value}")
        else:  # variable == 'Vg'
            gate_source_instr.write(f":SOUR:VOLT:LEV {v_value}")

        time.sleep(settle_delay)

        # Measure currents and voltages:
        d_v, d_i = measure_iv(drain_source_instr, ascii_command_flavor='SCPI')
        b_v, b_i = measure_iv(bulk_source_instr, ascii_command_flavor='SCPI')
        sub_v, sub_i = measure_iv(source_sub_instrum, ascii_command_flavor='SCPI')
        g_v, g_i = measure_iv(gate_source_instr, ascii_command_flavor='SCPI')
        if b_v is None:
            b_v = bulk_source_voltage
        # (If sub_v is None, you might want to set a default as needed)

        # Re-map fixed/variable source voltages:
        if fixed == 'Vd' and variable == 'Vg':
            Vd_src = fixed_voltage
            Vg_src = v_value
        elif fixed == 'Vg' and variable == 'Vd':
            Vg_src = fixed_voltage
            Vd_src = v_value
        else:
            Vd_src = 0
            Vg_src = 0

        # --- Measure temperature (if a Lakeshore and start time are provided) ---
        if lakeshore is not None and start_global is not None:
            try:
                tempA = read_temperature(lakeshore, channel='A')
                tempB = read_temperature(lakeshore, channel='B')
                elapsed_time = time.time() - start_global
            except Exception as e:
                print("Temperature measurement error:", e)
                tempA, tempB, elapsed_time = None, None, None
        else:
            tempA, tempB, elapsed_time = None, None, None

        # Append the measurement tuple (now 15 columns)
        data.append((
            Vd_src, Vg_src, Vb_src, Vsub_src,  # Source voltages
            d_i, b_i, sub_i, g_i,  # Measured currents
            d_v, b_v, sub_v, g_v,  # Measured voltages
            tempA, tempB, elapsed_time  # Temperature channels and elapsed time
        ))

        # --- Update live plots (if enabled) ---
        if live_plot:
            plotting_voltages.append(v_value)
            plotting_drain_source_currents.append(d_i)
            plotting_bulk_source_currents.append(b_i)
            plotting_source_sub_currents.append(sub_i)
            plotting_gate_source_currents.append(g_i)
            plotting_drain_source_voltages.append(d_v if d_v is not None else 0)
            plotting_bulk_source_voltages.append(b_v if b_v is not None else 0)
            plotting_source_sub_voltages.append(sub_v if sub_v is not None else 0)
            plotting_gate_source_voltages.append(g_v if g_v is not None else 0)

            # Update current and voltage lines:
            line_drain_source_i.set_data(plotting_voltages, plotting_drain_source_currents)
            line_bulk_source_i.set_data(plotting_voltages, plotting_bulk_source_currents)
            line_source_sub_i.set_data(plotting_voltages, plotting_source_sub_currents)
            line_gate_source_i.set_data(plotting_voltages, plotting_gate_source_currents)
            line_drain_source_v.set_data(plotting_voltages, plotting_drain_source_voltages)
            line_bulk_source_v.set_data(plotting_voltages, plotting_bulk_source_voltages)
            line_source_sub_v.set_data(plotting_voltages, plotting_source_sub_voltages)
            line_gate_source_v.set_data(plotting_voltages, plotting_gate_source_voltages)

            # Update temperature arrays if available:
            if elapsed_time is not None:
                plotting_time.append(elapsed_time)
                plotting_tempA.append(tempA)
                plotting_tempB.append(tempB)
                line_tempA.set_data(plotting_time, plotting_tempA)
                line_tempB.set_data(plotting_time, plotting_tempB)
                ax_temp.relim()
                ax_temp.autoscale_view()

            # Rescale current and voltage axes:
            for ax in [ax0_left, ax1_left, ax2_left, ax3_left, ax0_right, ax1_right, ax2_right, ax3_right]:
                ax.relim()
                ax.autoscale_view()

            fig_all.canvas.draw()
            fig_all.canvas.flush_events()

    # Return SMU outputs to 0 V:
    set_voltage(0, drain_source_instr, ascii_command_flavor='SCPI')
    set_voltage(0, gate_source_instr, ascii_command_flavor='SCPI')
    time.sleep(0.01)
    if live_plot:
        plt.close(fig_all)

    return data


# -----------------------------------------------------------------------------------------------------------------------
#                           SELF-HEATING TEST FUNCTION
# -----------------------------------------------------------------------------------------------------------------------


def self_heating_paused_measurements_test(Vds_set, Vgs, Vs, Vbs, num_measurements, measurement_interval, cooling_interval,
                                          drain_instr, gate_instr, bulk_instr, source_instr, start_global):
    """
    Performs a self-heating test by taking repeated single-point measurements.
    *Configured for output characteristics (idvd) only*

    For each measurement:
      Step 1. Set Vds and Vgs to fixed values.
      Step 2. Wait for 'measurement_interval' seconds.
      Step 3. Read IV data from the drain and gate instruments.
      Step 4. Read temperature from the Lakeshore instrument.
      Step 5. Record the data along with a timestamp.
      Step 6. Ramp the voltages back to 0 and wait for 'cooling_interval' seconds.
    """
    # array to hold data
    data = []

    for Vds in Vds_set:
        print(f"Taking self-heating measurement {num_measurements}/{num_measurements}...")
        #setting appropriate voltages
        set_voltage(Vs, source_instr)
        set_voltage(Vbs, bulk_instr)
        set_voltage(Vgs, gate_instr)
        set_voltage(Vds, drain_instr)

        # time.sleep(measurement_interval) #using SMU internal time delay

        d_v, d_i = measure_iv(drain_instr)
        g_v, g_i = measure_iv(gate_instr)
        s_v, s_i = measure_iv(source_instr)
        b_v, b_i = measure_iv(bulk_instr)
        #temp = read_temperature(lakeshore)

        # --- Measure temperature (if a Lakeshore and start time are provided) ---
        if lakeshore is not None and start_global is not None:
            try:
                tempA = read_temperature(lakeshore, channel='A')
                tempB = read_temperature(lakeshore, channel='B')
                elapsed_time = time.time() - start_global
            except Exception as e:
                print("Temperature measurement error:", e)
                tempA, tempB, elapsed_time = None, None, None
        else:
            tempA, tempB, elapsed_time = None, None, None

        # Append the measurement tuple (now 15 columns)
        data.append((
            Vds, Vgs, Vbs, Vs,  # Source voltages
            d_i, b_i, s_i, g_i,  # Measured currents
            d_v, b_v, s_v, g_v,  # Measured voltages
            tempA, tempB, elapsed_time  # Temperature channels and elapsed time
        ))

        print(f"Voltages \n Vds is {Vds} \n Vgs is {Vgs} \n Vs is {Vs} \n Vbs is {Vbs} \n Measurement taken.\n Now waiting for cooling interval...")

        # Setting voltages back to 0 for cooling
        # set_voltage(0, gate_instr) #For the new test, gate should be always ON.
        set_voltage(0, drain_instr)
        set_voltage(0, bulk_instr)
        # set_voltage(0, source_instr)

        time.sleep(cooling_interval) #voltages off for chosen cooling interval

    return data


# -----------------------------------------------------------------------------------------------------------------------
#                                              MAIN MEASUREMENT SCRIPT
# -----------------------------------------------------------------------------------------------------------------------

data_folder = 'Data/250K0_high_Vds_test2'
mux_json_file = "mux_instructions_by_transistor_4wire_drain.json"
bias_json_file = "sweep_bias_instructions_v3.json"
live_plotting = True
disable_front_panel = False
curr_compliance = 0.1  # A
drain_curr_range = 0.01  # A
settle_delay = 0
drain_instr_wire_mode = 4
gate_instr_wire_mode = 2

rm = pyvisa.ResourceManager()

print("Available VISA resources:", rm.list_resources())

drain_source_instrum_address = 'GPIB1::24::INSTR'
gate_source_instrum_address = 'GPIB1::25::INSTR'
bulk_source_instrum_address = 'GPIB1::23::INSTR'
sourc_sub_instrum_address = 'GPIB1::22::INSTR'
DAQ_mux_ds_top_address = 'USB0::0x05E6::0x6510::04510741::INSTR'
DAQ_mux_gs_bottom_address = 'USB0::0x05E6::0x6510::04505354::INSTR'

drain_source_instrum = rm.open_resource(drain_source_instrum_address, read_termination='\r', write_termination='\r')
gate_source_instrum = rm.open_resource(gate_source_instrum_address, read_termination='\r', write_termination='\r')
bulk_source_instrum = rm.open_resource(bulk_source_instrum_address, read_termination='\r', write_termination='\r')
sourc_sub_instrum = rm.open_resource(sourc_sub_instrum_address, read_termination='\r', write_termination='\r')
DAQ_mux_ds_top = rm.open_resource(DAQ_mux_ds_top_address, read_termination='\n', write_termination='\n')
DAQ_mux_gs_bottom = rm.open_resource(DAQ_mux_gs_bottom_address, read_termination='\n', write_termination='\n')

gate_source_instrum.timeout = 50000
drain_source_instrum.timeout = 50000
bulk_source_instrum.timeout = 50000
sourc_sub_instrum.timeout = 50000

# Open a Lakeshore instrument (for temperature)
lakeshore_addr = 'GPIB0::12::INSTR'
lakeshore = rm.open_resource(lakeshore_addr)
lakeshore.timeout = 50000

configure_instr(0,
                drain_source_instrum,
                current_compliance=curr_compliance,
                ascii_command_flavor='SCPI',
                wire_mode=drain_instr_wire_mode,
                disable_front_panel=disable_front_panel,
                curr_range_hard_set = False,
                current_range = 0.1
                )

configure_instr(0,
                gate_source_instrum,
                current_compliance=curr_compliance,
                ascii_command_flavor='SCPI',
                wire_mode=gate_instr_wire_mode,
                disable_front_panel=disable_front_panel)

configure_instr(0,
                bulk_source_instrum,
                current_compliance=curr_compliance,
                ascii_command_flavor='SCPI',
                wire_mode=gate_instr_wire_mode,
                disable_front_panel=disable_front_panel)

configure_instr(0,
                sourc_sub_instrum,
                current_compliance=curr_compliance,
                ascii_command_flavor='SCPI',
                wire_mode=gate_instr_wire_mode,
                disable_front_panel=disable_front_panel,
                curr_range_hard_set=True,
                current_range=0.01,
                voltage_range=200)

mux_data = load_mux_instructions(mux_json_file)

for transistor_key, mux_dict in mux_data.items():

    if 'nmos25_FET3' not in transistor_key:
        continue

    print(f"\nConfiguring transistor: {transistor_key}")

    flavor = None
    if '25' in transistor_key:
        flavor = 'HV'
    else:
        print('Please configure for MV and LV as needed.')
        break

    if 'pmos' in transistor_key:
        fet_type = "PMOS"
    elif 'nmos' in transistor_key:
        fet_type = "NMOS"
    else:
        print('Invalid FET type in transistor_key.')
        break

    os.makedirs(data_folder, exist_ok=True)
    os.makedirs(f'{data_folder}/{flavor}', exist_ok=True)

    bias_instructions = load_bias_instructions(fet_type, bias_json_file)

    try:
        flavor_index = {"LV": 0, "MV": 1, "HV": 2}[flavor]
    except KeyError:
        print("Invalid flavor, expected 'LV', 'MV', or 'HV'.")
        continue

    # Extract relevant bias sets
    gate_source_voltages_transfer_char_s1 = bias_instructions[0][3][flavor_index]
    drain_source_voltages_transfer_char_s1 = bias_instructions[0][2][flavor_index]
    bulk_source_voltages_transfer_char_s1 = bias_instructions[0][1][flavor_index]
    source_sub_voltages_transfer_char_s1 = bias_instructions[0][0][flavor_index]

    gate_source_voltages_transfer_char_s2 = bias_instructions[1][3][flavor_index]
    drain_source_voltages_transfer_char_s2 = bias_instructions[1][2][flavor_index]
    bulk_source_voltages_transfer_char_s2 = bias_instructions[1][1][flavor_index]
    source_sub_voltages_transfer_char_s2 = bias_instructions[1][0][flavor_index]

    drain_source_voltages_output_char = bias_instructions[2][2][flavor_index]
    gate_source_voltages_output_char = bias_instructions[2][3][flavor_index]
    bulk_source_voltages_output_char = bias_instructions[2][1][flavor_index]
    source_sub_voltages_output_char = bias_instructions[2][0][flavor_index]

    DAQ_mux_ds_top.write('ROUTe:OPEN:ALL')
    DAQ_mux_gs_bottom.write('ROUTe:OPEN:ALL')

    DAQ_mux_ds_top.write(':FUNC "VOLT:DC"')
    DAQ_mux_gs_bottom.write(':FUNC "VOLT:DC"')

    for mux_name, mux_instructions in mux_dict.items():
        print(f"  → Setting up {mux_name}")
        for instruc in mux_instructions:
            channel_idx = instruc["channel"]
            bias_type = instruc["bias_type"]
            operation = instruc["operation"]
            keithley_channel = 100 + channel_idx

            if "DS" in bias_type:
                DAQ_mux_ds_top.write(f"ROUT:CLOS (@{keithley_channel})")
                print(f"    Closed channel {keithley_channel} (bias={bias_type}, op={operation}) in top DS MUX.")
            elif "GS" in bias_type:
                DAQ_mux_gs_bottom.write(f"ROUT:CLOS (@{keithley_channel})")
                print(f"    Closed channel {keithley_channel} (bias={bias_type}, op={operation}) in bottom GS MUX.")
            else:
                print('    Invalid bias specification (not DS or GS), skipping.')

    start_time = time.time()
    os.makedirs(f'{data_folder}/{flavor}/{transistor_key}', exist_ok=True)

    # Configure the voltages for the source to substrate
    if 'pmos' in transistor_key:
        source_substrate_voltage_default = 25
    elif 'nmos' in transistor_key:
        source_substrate_voltage_default = 0
    else:
        print('pmos or nmos is not in transistor_key. Please update instructions to include this information')
        break

    # ##################################   Transfer Characterization (Set 1)   #############################
    # if 'pmos' in transistor_key:
    #     for body_source_voltage in bulk_source_voltages_transfer_char_s1:
    #         if body_source_voltage == 0:
    #             continue  # no need to redo Vb 0 measurements
    #
    #         for drain_source_voltage in drain_source_voltages_transfer_char_s1:
    #             transfer_char_data = voltage_sweep_three_instruments(
    #                 fixed='Vd',
    #                 variable='Vg',
    #                 sweep_voltages=gate_source_voltages_transfer_char_s1,
    #                 fixed_voltage=drain_source_voltage,
    #                 bulk_source_voltage=body_source_voltage,
    #                 source_substrate_voltage=source_substrate_voltage_default,
    #                 drain_source_instr=drain_source_instrum,
    #                 gate_source_instr=gate_source_instrum,
    #                 bulk_source_instr=bulk_source_instrum,
    #                 source_sub_instrum=sourc_sub_instrum,
    #                 live_plot=live_plotting,
    #                 curr_compliance=curr_compliance,
    #                 drain_curr_range=drain_curr_range,
    #                 settle_delay=settle_delay,
    #                 lakeshore=lakeshore,
    #                 start_global=start_time
    #             )
    #             drain_source_voltage_str = str(drain_source_voltage).replace('.', 'p')
    #             body_source_voltage_str = str(body_source_voltage).replace('.', 'p')
    #             source_sub_voltage_str = str(source_substrate_voltage_default).replace('.', 'p')
    #
    #             # Define the CSV file path
    #             csv_filename = f'idvg_Vd{drain_source_voltage_str}_Vb{body_source_voltage_str}_Vsub{source_sub_voltage_str}.csv'
    #             csv_path = os.path.join(data_folder, flavor, transistor_key, 'mystic_format', csv_filename)
    #
    #             # Ensure the directory exists
    #             os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    #             # Extract relevant columns
    #             Vd_src = [row[0] for row in transfer_char_data]
    #             Vg_src = [row[1] for row in transfer_char_data]
    #             body_source_voltage_src = [row[2] for row in transfer_char_data]
    #             Id = [row[4] for row in transfer_char_data]
    #
    #             # Open the CSV file for writing
    #             with open(csv_path, 'w', newline='') as csvfile:
    #                 writer = csv.writer(csvfile)
    #
    #                 # Write the constant voltage section
    #                 writer.writerow(['#Constant Voltage'])
    #                 writer.writerow(['VD', Vd_src[0]])  # First value of Vd_src
    #                 writer.writerow(['VS', '0'])  # VS set to 0
    #                 writer.writerow(['VB', body_source_voltage_src[0]])  # First value of body_source_voltage_src
    #                 writer.writerow(['VSUB', source_substrate_voltage_default])  # substrate_source_voltage set to 25 for pmos
    #
    #                 # Write the data header
    #                 writer.writerow(['#Data'])
    #                 writer.writerow(['VG', 'ID'])
    #
    #                 # Write the data rows
    #                 for vg, id_val in zip(Vg_src, Id):
    #                     writer.writerow([vg, id_val])
    #
    #             # Now saving 9 columns: (Vd_src, Vg_src, body_source_voltage_src, Id, Ib, Ig, Vd_meas, body_source_voltage_meas, Vg_meas)
    #             np.savetxt(
    #                 f'{data_folder}/{flavor}/{transistor_key}/idvg_Vd{drain_source_voltage_str}_Vb'
    #                 f'{body_source_voltage_str}_Vsub{source_sub_voltage_str}.csv',
    #                 transfer_char_data,
    #                 delimiter=',',
    #                 header='Vd_src, Vg_src, Vb_src, Vsub_src, Id, Ib, Isub, Ig, Vd_meas, Vb_meas, Vsub_meas, Vg_meas,'
    #                        'TempA,TempB,Elapsed_time',
    #                 comments=''
    #             )
    #
    # if 'nmos' in transistor_key:
    #     for source_sub_voltage in source_sub_voltages_transfer_char_s1:
    #         if source_sub_voltage == 0:
    #             continue  # no need to redo Vb 0 measurements
    #
    #         for drain_source_voltage in drain_source_voltages_transfer_char_s1:
    #             transfer_char_data = voltage_sweep_three_instruments(
    #                 fixed='Vd',
    #                 variable='Vg',
    #                 sweep_voltages=gate_source_voltages_transfer_char_s1,
    #                 fixed_voltage=drain_source_voltage,
    #                 bulk_source_voltage=bulk_source_voltages_transfer_char_s1[0],
    #                 source_substrate_voltage=source_sub_voltage,
    #                 drain_source_instr=drain_source_instrum,
    #                 gate_source_instr=gate_source_instrum,
    #                 bulk_source_instr=bulk_source_instrum,
    #                 source_sub_instrum=sourc_sub_instrum,
    #                 live_plot=live_plotting,
    #                 curr_compliance=curr_compliance,
    #                 drain_curr_range=drain_curr_range,
    #                 settle_delay=settle_delay,
    #                 lakeshore=lakeshore,
    #                 start_global=start_time
    #             )
    #             drain_source_voltage_str = str(drain_source_voltage).replace('.', 'p')
    #             body_source_voltage_str = str(bulk_source_voltages_transfer_char_s1[0]).replace('.', 'p') #body to source voltage
    #             source_sub_voltage_str = str(source_sub_voltage).replace('.', 'p')
    #
    #             # Define the CSV file path
    #             csv_filename = f'idvg_Vd{drain_source_voltage_str}_Vs{source_sub_voltage_str}_Vb{body_source_voltage_str}.csv' #body=bulk=sub
    #             csv_path = os.path.join(data_folder, flavor, transistor_key, 'mystic_format', csv_filename)
    #
    #             # Ensure the directory exists
    #             os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    #             # Extract relevant columns
    #             Vd_src = [row[0] for row in transfer_char_data]
    #             Vg_src = [row[1] for row in transfer_char_data]
    #             body_source_voltage_src = [row[3] for row in transfer_char_data] # sub to source voltage
    #             Id = [row[4] for row in transfer_char_data]
    #
    #             # Open the CSV file for writing
    #             with open(csv_path, 'w', newline='') as csvfile:
    #                 writer = csv.writer(csvfile)
    #
    #                 # Write the constant voltage section
    #                 writer.writerow(['#Constant Voltage'])
    #                 writer.writerow(['VD', Vd_src[0]])  # First value of Vd_src
    #                 writer.writerow(['VS', body_source_voltage_src[0]])  # VS set to mimic body bias
    #                 writer.writerow(['VB', source_substrate_voltage_default]) # substrate is effectively the body for nmos, set to 0
    #                 '''eliminated vsub for clearer implementation in Mystic -faith 2/19/25
    #                 writer.writerow(['VB', body_source_voltage_src[0]])  # First value of body_source_voltage_src
    #                 writer.writerow(['VSUB', source_substrate_voltage_default])  # substrate_source_voltage set to 0'''
    #
    #                 # Write the data header
    #                 writer.writerow(['#Data'])
    #                 writer.writerow(['VG', 'ID'])
    #
    #                 # Write the data rows
    #                 for vg, id_val in zip(Vg_src, Id):
    #                     writer.writerow([vg, id_val])
    #
    #             # Now saving 9 columns: (Vd_src, Vg_src, body_source_voltage_src, Id, Ib, Ig, Vd_meas, body_source_voltage_meas, Vg_meas)
    #             np.savetxt(
    #                 f'{data_folder}/{flavor}/{transistor_key}/idvg_Vd{drain_source_voltage_str}_Vb'
    #                 f'{body_source_voltage_str}_Vsub{source_sub_voltage_str}.csv',
    #                 transfer_char_data,
    #                 delimiter=',',
    #                 header='Vd_src, Vg_src, Vb_src, Vsub_src, Id, Ib, Isub, Ig, Vd_meas, Vb_meas, Vsub_meas, '
    #                        'Vg_meas,TempA,TempB,Elapsed_time',
    #                 comments=''
    #             )

    # ##################################   Transfer Char (Set 2)   #############################
    # for drain_source_voltage in drain_source_voltages_transfer_char_s2:
    #     if abs(drain_source_voltage) == 0.1 or abs(drain_source_voltage) == 25:
    #         transfer_char_data = voltage_sweep_three_instruments(
    #             fixed='Vd',
    #             variable='Vg',
    #             sweep_voltages=gate_source_voltages_transfer_char_s2,
    #             fixed_voltage=drain_source_voltage,
    #             bulk_source_voltage=bulk_source_voltages_transfer_char_s2[0],
    #             source_substrate_voltage=source_substrate_voltage_default,
    #             drain_source_instr=drain_source_instrum,
    #             gate_source_instr=gate_source_instrum,
    #             bulk_source_instr=bulk_source_instrum,
    #             source_sub_instrum=sourc_sub_instrum,
    #             live_plot=live_plotting,
    #             curr_compliance=curr_compliance,
    #             drain_curr_range=drain_curr_range,
    #             settle_delay=settle_delay,
    #             lakeshore=lakeshore,
    #             start_global=start_time
    #         )
    #         drain_source_voltage_str = str(drain_source_voltage).replace('.', 'p')
    #         body_source_voltage_str = str(bulk_source_voltages_transfer_char_s2[0]).replace('.', 'p')
    #         source_sub_voltage_str = str(source_substrate_voltage_default).replace('.', 'p')
    #
    #         # Define the CSV file path
    #         csv_filename = f'idvg_Vd{drain_source_voltage_str}_Vb{body_source_voltage_str}_Vsub{source_sub_voltage_str}.csv'
    #         csv_path = os.path.join(data_folder, flavor, transistor_key, 'mystic_format', csv_filename)
    #
    #         # Ensure the directory exists
    #         os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    #         # Extract relevant columns
    #         Vd_src = [row[0] for row in transfer_char_data]
    #         Vg_src = [row[1] for row in transfer_char_data]
    #         body_source_voltage_src = [row[2] for row in transfer_char_data]
    #         Id = [row[4] for row in transfer_char_data]
    #
    #         # Open the CSV file for writing
    #         with open(csv_path, 'w', newline='') as csvfile:
    #             writer = csv.writer(csvfile)
    #
    #             # Write the constant voltage section
    #             writer.writerow(['#Constant Voltage'])
    #             writer.writerow(['VD', Vd_src[0]])  # First value of Vd_src
    #             writer.writerow(['VS', '0'])  # VS set to 0
    #             writer.writerow(['VB', body_source_voltage_src[0]])  # First value of body_source_voltage_src
    #             if 'pmos' in transistor_key: #only include source to sub voltage for pmos
    #                 writer.writerow(['VSUB', source_substrate_voltage_default])
    #
    #             # Write the data header
    #             writer.writerow(['#Data'])
    #             writer.writerow(['VG', 'ID'])
    #
    #             # Write the data rows
    #             for vg, id_val in zip(Vg_src, Id):
    #                 writer.writerow([vg, id_val])
    #
    #         # Now saving 9 columns: (Vd_src, Vg_src, body_source_voltage_src, Id, Ib, Ig, Vd_meas, body_source_voltage_meas, Vg_meas)
    #         np.savetxt(
    #             f'{data_folder}/{flavor}/{transistor_key}/idvg_Vd{drain_source_voltage_str}_Vb{body_source_voltage_str}_Vsub{source_sub_voltage_str}.csv',
    #             transfer_char_data,
    #             delimiter=',',
    #             header='Vd_src, Vg_src, Vb_src,Vsub_src, Id, Ib, Isub, Ig, Vd_meas, Vb_meas, Vsub_meas, Vg_meas,TempA,TempB,Elapsed_time',
    #             comments=''
    #         )
    #         set_voltage(0, drain_source_instrum) #letting transistor cool btwn measurements
    #         set_voltage(0, bulk_source_instrum)
    #         set_voltage(0, gate_source_instrum)
    #         set_voltage(0, sourc_sub_instrum)
    #         time.sleep(60)

    #################################### Output Characteristics #######################################
    for gate_source_voltage in gate_source_voltages_output_char:
        if abs(gate_source_voltage)>20.5:
            output_char_data = voltage_sweep_three_instruments(
                fixed='Vg',
                variable='Vd',
                sweep_voltages=drain_source_voltages_output_char,
                fixed_voltage=gate_source_voltage,
                bulk_source_voltage=bulk_source_voltages_output_char[0],
                source_substrate_voltage=source_substrate_voltage_default,
                drain_source_instr=drain_source_instrum,
                gate_source_instr=gate_source_instrum,
                bulk_source_instr=bulk_source_instrum,
                source_sub_instrum=sourc_sub_instrum,
                live_plot=live_plotting,
                curr_compliance=curr_compliance,
                drain_curr_range=drain_curr_range,
                settle_delay=settle_delay,
                lakeshore=lakeshore,
                start_global=start_time
            )

            gate_source_voltage_str = str(gate_source_voltage).replace('.', 'p')
            body_source_voltage_str = str(bulk_source_voltages_output_char[0]).replace('.', 'p')
            source_sub_voltage_str = str(source_substrate_voltage_default).replace('.', 'p')

            # Define the CSV file path
            csv_filename = f'idvd_Vg{gate_source_voltage_str}_Vb{body_source_voltage_str}_Vsub{source_sub_voltage_str}.csv'
            csv_path = os.path.join(data_folder, flavor, transistor_key, 'mystic_format', csv_filename)

            # Ensure the directory exists
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            # Extract relevant columns
            Vd_src = [row[0] for row in output_char_data]
            Vg_src = [row[1] for row in output_char_data]
            body_source_voltage_src = [row[2] for row in output_char_data]
            Id = [row[4] for row in output_char_data]

            # Open the CSV file for writing
            with open(csv_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write the constant voltage section
                writer.writerow(['#Constant Voltage'])
                writer.writerow(['VG', Vg_src[0]])  # First value of Vd_src
                writer.writerow(['VS', '0'])  # VS set to 0
                writer.writerow(['VB', body_source_voltage_src[0]])  # First value of body_source_voltage_src
                if 'pmos' in transistor_key:
                    writer.writerow(['VSUB', source_substrate_voltage_default])  # substrate_source_voltage set to 0-nmos/25-pmos

                # Write the data header
                writer.writerow(['#Data'])
                writer.writerow(['VD', 'ID'])

                # Write the data rows
                for vd, id_val in zip(Vd_src, Id):
                    writer.writerow([vd, id_val])

            # Saving 9 columns again
            np.savetxt(
                f'{data_folder}/{flavor}/{transistor_key}/idvd_Vg{gate_source_voltage_str}_Vb{body_source_voltage_str}_Vsub'
                f'{source_sub_voltage_str}.csv',
                output_char_data,
                delimiter=',',
                header='Vd_src, Vg_src, Vb_src,Vsub_src, Id, Ib, Isub, Ig, Vd_meas, Vb_meas, Vsub_meas, Vg_meas,TempA,'
                       'TempB,Elapsed_time',
                comments=''
            )



    # ################################# Output Characteristics Backward ####################################
    # for gate_source_voltage in gate_source_voltages_output_char:
    #     drain_source_voltages_output_char_bkwd=drain_source_voltages_output_char[::-1]
    #     if abs(gate_source_voltage) > 20.5:
    #         output_char_data = voltage_sweep_three_instruments(
    #             fixed='Vg',
    #             variable='Vd',
    #             sweep_voltages=drain_source_voltages_output_char_bkwd,
    #             fixed_voltage=gate_source_voltage,
    #             bulk_source_voltage=bulk_source_voltages_output_char[0],
    #             source_substrate_voltage=source_substrate_voltage_default,
    #             drain_source_instr=drain_source_instrum,
    #             gate_source_instr=gate_source_instrum,
    #             bulk_source_instr=bulk_source_instrum,
    #             source_sub_instrum=sourc_sub_instrum,
    #             live_plot=live_plotting,
    #             curr_compliance=curr_compliance,
    #             drain_curr_range=drain_curr_range,
    #             settle_delay=settle_delay,
    #             lakeshore=lakeshore,
    #             start_global=start_time
    #         )
    #
    #         gate_source_voltage_str = str(gate_source_voltage).replace('.', 'p')
    #         body_source_voltage_str = str(bulk_source_voltages_output_char[0]).replace('.', 'p')
    #         source_sub_voltage_str = str(source_substrate_voltage_default).replace('.', 'p')
    #
    #         # Define the CSV file path
    #         csv_filename = f'idvd_Vg{gate_source_voltage_str}_Vb{body_source_voltage_str}_Vsub{source_sub_voltage_str}_backward.csv'
    #         csv_path = os.path.join(data_folder, flavor, transistor_key, 'mystic_format', csv_filename)
    #
    #         # Ensure the directory exists
    #         os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    #         # Extract relevant columns
    #         Vd_src = [row[0] for row in output_char_data]
    #         Vg_src = [row[1] for row in output_char_data]
    #         body_source_voltage_src = [row[2] for row in output_char_data]
    #         Id = [row[4] for row in output_char_data]
    #
    #         # Open the CSV file for writing
    #         with open(csv_path, 'w', newline='') as csvfile:
    #             writer = csv.writer(csvfile)
    #
    #             # Write the constant voltage section
    #             writer.writerow(['#Constant Voltage'])
    #             writer.writerow(['VG', Vg_src[0]])  # First value of Vd_src
    #             writer.writerow(['VS', '0'])  # VS set to 0
    #             writer.writerow(['VB', body_source_voltage_src[0]])  # First value of body_source_voltage_src
    #             if 'pmos' in transistor_key:
    #                 writer.writerow(
    #                     ['VSUB', source_substrate_voltage_default])  # substrate_source_voltage set to 0-nmos/25-pmos
    #
    #             # Write the data header
    #             writer.writerow(['#Data'])
    #             writer.writerow(['VD', 'ID'])
    #
    #             # Write the data rows
    #             for vd, id_val in zip(Vd_src, Id):
    #                 writer.writerow([vd, id_val])
    #
    #         # Saving 9 columns again
    #         np.savetxt(
    #             f'{data_folder}/{flavor}/{transistor_key}/idvd_Vg{gate_source_voltage_str}_Vb{body_source_voltage_str}_Vsub'
    #             f'{source_sub_voltage_str}_backward.csv',
    #             output_char_data,
    #             delimiter=',',
    #             header='Vd_src, Vg_src, Vb_src,Vsub_src, Id, Ib, Isub, Ig, Vd_meas, Vb_meas, Vsub_meas, Vg_meas,TempA,'
    #                    'TempB,Elapsed_time',
    #             comments=''
    #         )
    #
    #         set_voltage(0, gate_source_instrum)  # letting transistor cool btwn measurements
    #         set_voltage(0, drain_source_instrum)
    #         set_voltage(0, bulk_source_instrum)
    #         set_voltage(0, sourc_sub_instrum)
    #         time.sleep(120)



    # # Parameters for the self-heating test:
    # # doing entire sweep, resting for 2 mins in between
    # Vds_test = drange(-20,-25,-0.2)  # , i for i in range(21,25,1)]
    # # Fixed drain voltage starting from [5,10,15,20 to 25] (in V)
    # Vgs_test = -25
    # # Fixed gate voltage (in V)
    # num_measurements = 1  # Number of times you want to take the measurement
    # measurement_interval = 0  # seconds to wait after setting voltage before taking measurement
    # cooling_interval = 120  # seconds to wait after turning voltage off for cooling
    #
    # print("Starting self-heating test...")
    #
    # self_heating_paused_data = self_heating_paused_measurements_test(
    #     Vds_set=Vds_test,
    #     Vgs=Vgs_test,
    #     Vs=source_substrate_voltage_default,
    #     Vbs=bulk_source_voltages_output_char[0],
    #     num_measurements=num_measurements,
    #     measurement_interval=measurement_interval,
    #     cooling_interval=cooling_interval,
    #     drain_instr=drain_source_instrum,
    #     gate_instr=gate_source_instrum,
    #     bulk_instr=bulk_source_instrum,
    #     source_instr=sourc_sub_instrum,
    #     start_global=start_time)
    #
    # gate_source_voltage_str = str(Vgs_test).replace('.', 'p')
    # body_source_voltage_str = str(bulk_source_voltages_output_char[0]).replace('.', 'p')
    # source_sub_voltage_str = str(source_substrate_voltage_default).replace('.', 'p')
    #
    # # Extract relevant columns
    # Vd_src = [row[0] for row in self_heating_paused_data]
    # Vg_src = [row[1] for row in self_heating_paused_data]
    # body_source_voltage_src = [row[2] for row in self_heating_paused_data]
    # Id = [row[4] for row in self_heating_paused_data]
    #
    # # Saving 9 columns again
    # np.savetxt(
    #     f'{data_folder}/{flavor}/{transistor_key}/idvd_paused_meas_Vg{gate_source_voltage_str}_Vb{body_source_voltage_str}_Vsub'
    #     f'{source_sub_voltage_str}_Test2.csv',
    #     self_heating_paused_data,
    #     delimiter=',',
    #     header='Vd_src, Vg_src, Vb_src,Vsub_src, Id, Ib, Isub, Ig, Vd_meas, Vb_meas, Vsub_meas, Vg_meas,TempA,'
    #            'TempB,Elapsed_time',
    #     comments=''
    # )

    #be sure all voltages are set to zero
    set_voltage(0, gate_source_instrum)
    set_voltage(0, bulk_source_instrum)
    set_voltage(0, drain_source_instrum)
    set_voltage(0, sourc_sub_instrum)

    end_time = time.time()
    elapsed_time = end_time - start_time
    minutes = int(elapsed_time // 60)
    seconds = elapsed_time % 60
    print(f"Transistor Characterization completed in {minutes} minutes {seconds:.2f} seconds.")
