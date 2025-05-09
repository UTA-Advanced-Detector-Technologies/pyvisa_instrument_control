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
    transfer_char_set1 = processed_data.get(fet_type, {}).get('Primary sweep: Vgs', {})
    transfer_char = processed_data.get(fet_type, {}).get('Primary sweep: Vds', {})

    transfer_char_set1_vdrain_source = transfer_char_set1.get("Vd", [])
    transfer_char_set1_vgate_source = transfer_char_set1.get("Vg", [])

    transfer_char_vdrain_source = transfer_char.get("Vd", [])
    transfer_char_vgate_source = transfer_char.get("Vg", [])

    return (
        (transfer_char_set1_vdrain_source, transfer_char_set1_vgate_source),
        (transfer_char_vdrain_source, transfer_char_vgate_source)
    )

def configure_instr(sourcing_voltage,
                    instr,
                    current_compliance=1,
                    voltage_compliance=27,
                    ascii_command_flavor='SCPI',
                    wire_mode=2,
                    current_range=0.1,
                    disable_front_panel=True,
                    curr_range_hard_set=False,
                    voltage_range=20,
                    non_SCPI_curr_range=8):
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
            instr.write(f"L{current_compliance},{non_SCPI_curr_range}X")
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
        elif ascii_command_flavor == 'non-SCPI':
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
        elif ascii_command_flavor == 'non-SCPI':
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
        drain_source_instr,
        gate_source_instr,
        curr_compliance=0.01,
        live_plot=True,
        drain_curr_range=0.01,
        settle_delay=0.05,
):
    """
    Sweeps the 'variable' voltage while holding the other nodes constant.
    Now in addition to measuring currents and voltages

    The returned data tuple now contains 15 elements:
      (Vd_src, Vg_src, Vb_src, Vsub_src, Id, Ib, Isub, Ig, Vd_meas, Vb_meas, Vsub_meas, Vg_meas, TempA, TempB, Elapsed_time)
    """
    # --- Prepare live plot with an extra temperature subplot if requested ---
    if live_plot:
        plt.ion()  # interactive mode
        # Create a figure with 5 rows; rows 0-3 are for currents/voltages and row 4 is for temperature.
        fig_all = plt.figure(figsize=(10, 10))
        gs = gridspec.GridSpec(2, 1, height_ratios=[1, 1])
        # Rows for currents and voltages:
        ax0_left = fig_all.add_subplot(gs[0])
        ax1_left = fig_all.add_subplot(gs[1])


        # Set labels for current plots (left column)
        ax0_left.set_ylabel("Drain I (A)")
        ax1_left.set_ylabel("Gate I (A)")
        ax1_left.set_xlabel(f"{variable} (V)")

        # Create line objects:
        line_drain_source_i, = ax0_left.plot([], [], 'b-o', markersize=4, label='Drain Current')
        line_gate_source_i, = ax1_left.plot([], [], 'g-o', markersize=4, label='Gate Current')

        fig_all.suptitle(
            f"{variable} Sweep with Fixed {fixed} = {fixed_voltage} V "
            ,
            fontsize=12
        )
        fig_all.tight_layout()
        fig_all.show()

    # Prepare arrays for final data and for live plotting:
    data = []
    plotting_voltages = []  # x-axis for the sweep
    plotting_drain_source_currents = []
    plotting_gate_source_currents = []
    plotting_drain_source_voltages = []
    plotting_gate_source_voltages = []

    time.sleep(0.5)
    # Set the "fixed" node:
    if fixed == 'Vd':
        set_voltage(fixed_voltage, drain_source_instr, ascii_command_flavor='non-SCPI')
    elif fixed == 'Vg':
        set_voltage(fixed_voltage, gate_source_instr, ascii_command_flavor='non-SCPI')
    else:
        print("Warning: 'fixed' should be 'Vd' or 'Vg' in this example code.")

    time.sleep(0.5)
    # Initialize the "variable" node to 0 V:
    if variable == 'Vd':
        set_voltage(0, drain_source_instr, ascii_command_flavor='non-SCPI')
    elif variable == 'Vg':
        set_voltage(0, gate_source_instr, ascii_command_flavor='non-SCPI')
    else:
        print("Warning: 'variable' should be 'Vd' or 'Vg' in this example code.")

    for v_value in sweep_voltages:
        # Update the "variable" voltage:
        if variable == 'Vd':
            set_voltage(v_value, drain_source_instr, ascii_command_flavor='non-SCPI')
        else:  # variable == 'Vg'
            set_voltage(v_value, gate_source_instr, ascii_command_flavor='non-SCPI')
        time.sleep(settle_delay)

        # Measure currents and voltages:
        d_v, d_i = measure_iv(drain_source_instr, ascii_command_flavor='non-SCPI')
        g_v, g_i = measure_iv(gate_source_instr, ascii_command_flavor='non-SCPI')

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


        data.append((
            Vd_src, Vg_src,   # Source voltages
            d_i, g_i  # Measured currents
        ))

        # --- Update live plots (if enabled) ---
        if live_plot:
            plotting_voltages.append(v_value)
            plotting_drain_source_currents.append(d_i)
            plotting_gate_source_currents.append(g_i)
            plotting_drain_source_voltages.append(d_v if d_v is not None else 0)
            plotting_gate_source_voltages.append(g_v if g_v is not None else 0)

            # Update current and voltage lines:
            line_drain_source_i.set_data(plotting_voltages, plotting_drain_source_currents)
            line_gate_source_i.set_data(plotting_voltages, plotting_gate_source_currents)

            # Rescale current and voltage axes:
            for ax in [ax0_left, ax1_left]:
                ax.relim()
                ax.autoscale_view()

            fig_all.canvas.draw()
            fig_all.canvas.flush_events()

    time.sleep(0.5) #if you go to fast the older smus give an out of range error, so just keep this in there

    # Return SMU outputs to 0 V:
    set_voltage(0, drain_source_instr, ascii_command_flavor='non-SCPI')
    set_voltage(0, gate_source_instr, ascii_command_flavor='non-SCPI')
    time.sleep(0.5)
    if live_plot:
        plt.close(fig_all)

    return data


# -----------------------------------------------------------------------------------------------------------------------
#                                              MAIN MEASUREMENT SCRIPT
# -----------------------------------------------------------------------------------------------------------------------

data_folder = 'Data/coldish_newwires_05-09-2025'
bias_json_file = "sweep_bias_instructions_v3.json"
live_plotting = True
disable_front_panel = False
curr_compliance = 0.5  # A
drain_curr_range = 0.5  # A
settle_delay = 0
drain_instr_wire_mode = 2
gate_instr_wire_mode = 2

rm = pyvisa.ResourceManager()

print("Available VISA resources:", rm.list_resources())

drain_source_instrum_address = 'GPIB0::15::INSTR'
gate_source_instrum_address = 'GPIB0::11::INSTR'

drain_source_instrum = rm.open_resource(drain_source_instrum_address, read_termination='\r', write_termination='\r')
gate_source_instrum = rm.open_resource(gate_source_instrum_address, read_termination='\r', write_termination='\r')

gate_source_instrum.timeout = 50000
drain_source_instrum.timeout = 50000

configure_instr(0,
                drain_source_instrum,
                current_compliance=curr_compliance,
                ascii_command_flavor='non-SCPI',
                wire_mode=drain_instr_wire_mode,
                disable_front_panel=disable_front_panel,
                curr_range_hard_set = False,
                current_range = 0.5,
                non_SCPI_curr_range=5
                )

configure_instr(0,
                gate_source_instrum,
                current_compliance=curr_compliance,
                ascii_command_flavor='non-SCPI',
                wire_mode=gate_instr_wire_mode,
                disable_front_panel=disable_front_panel,
                non_SCPI_curr_range=10)


transistor_key='nmos_FET_len_100_wid_100' #give it a name for the data saving folder. needs to have nmos or pmos in name


print(f"\nConfiguring transistor: {transistor_key}")

flavor = 'LV'

if 'pmos' in transistor_key:
    fet_type = "PMOS"
elif 'nmos' in transistor_key:
    fet_type = "NMOS"
else:
    print('Invalid FET type in transistor_key.')


os.makedirs(data_folder, exist_ok=True)
os.makedirs(f'{data_folder}/{flavor}', exist_ok=True)

bias_instructions = load_bias_instructions(fet_type, bias_json_file)
flavor_index = {"LV": 0}[flavor]


# Extract relevant bias sets
gate_source_voltages_transfer_char = bias_instructions[0][1][flavor_index]
drain_source_voltages_transfer_char = bias_instructions[0][0][flavor_index]

drain_source_voltages_output_char = bias_instructions[1][0][flavor_index]
gate_source_voltages_output_char = bias_instructions[1][1][flavor_index]

start_time = time.time()
os.makedirs(f'{data_folder}/{flavor}/{transistor_key}', exist_ok=True)

##################################   Transfer Char (Set 1)   #############################
for drain_source_voltage in drain_source_voltages_transfer_char:
    transfer_char_data = voltage_sweep_three_instruments(
        fixed='Vd',
        variable='Vg',
        sweep_voltages=gate_source_voltages_transfer_char,
        fixed_voltage=drain_source_voltage,
        drain_source_instr=drain_source_instrum,
        gate_source_instr=gate_source_instrum,
        live_plot=live_plotting,
        curr_compliance=curr_compliance,
        drain_curr_range=drain_curr_range,
        settle_delay=settle_delay
    )
    drain_source_voltage_str = str(drain_source_voltage).replace('.', 'p')

    # Define the CSV file path
    csv_filename = f'idvg_Vd{drain_source_voltage_str}.csv'
    csv_path = os.path.join(data_folder, flavor, transistor_key, 'mystic_format', csv_filename)

    # Ensure the directory exists
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    # Extract relevant columns
    Vd_src = [row[0] for row in transfer_char_data]
    Vg_src = [row[1] for row in transfer_char_data]
    Id = [row[2] for row in transfer_char_data]

    # Open the CSV file for writing
    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Write the constant voltage section
        writer.writerow(['#Constant Voltage'])
        writer.writerow(['VD', Vd_src[0]])  # First value of Vd_src
        writer.writerow(['VS', '0'])  # VS set to 0

        # Write the data header
        writer.writerow(['#Data'])
        writer.writerow(['VG', 'ID'])

        # Write the data rows
        for vg, id_val in zip(Vg_src, Id):
            writer.writerow([vg, id_val])

    np.savetxt(
        f'{data_folder}/{flavor}/{transistor_key}/idvg_Vd{drain_source_voltage_str}.csv',
        transfer_char_data,
        delimiter=',',
        header='Vd_src, Vg_src, Id, Ig',
        comments=''
    )
    set_voltage(0, drain_source_instrum, ascii_command_flavor = 'non-SCPI') #letting transistor cool btwn measurements
    set_voltage(0, gate_source_instrum, ascii_command_flavor = 'non-SCPI')
    time.sleep(1)

#################################### Output Characteristics #######################################
for gate_source_voltage in gate_source_voltages_output_char:
    output_char_data = voltage_sweep_three_instruments(
        fixed='Vg',
        variable='Vd',
        sweep_voltages=drain_source_voltages_output_char,
        fixed_voltage=gate_source_voltage,
        drain_source_instr=drain_source_instrum,
        gate_source_instr=gate_source_instrum,
        live_plot=live_plotting,
        curr_compliance=curr_compliance,
        drain_curr_range=drain_curr_range,
        settle_delay=settle_delay
    )

    gate_source_voltage_str = str(gate_source_voltage).replace('.', 'p')

    # Define the CSV file path
    csv_filename = f'idvd_Vg{gate_source_voltage_str}.csv'
    csv_path = os.path.join(data_folder, flavor, transistor_key, 'mystic_format', csv_filename)

    # Ensure the directory exists
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    # Extract relevant columns
    Vd_src = [row[0] for row in output_char_data]
    Vg_src = [row[1] for row in output_char_data]
    Id = [row[2] for row in output_char_data]

    # Open the CSV file for writing
    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Write the constant voltage section
        writer.writerow(['#Constant Voltage'])
        writer.writerow(['VG', Vg_src[0]])  # First value of Vd_src
        writer.writerow(['VS', '0'])  # VS set to 0

        # Write the data header
        writer.writerow(['#Data'])
        writer.writerow(['VD', 'ID'])

        # Write the data rows
        for vd, id_val in zip(Vd_src, Id):
            writer.writerow([vd, id_val])

    # Saving 4 columns again
    np.savetxt(
        f'{data_folder}/{flavor}/{transistor_key}/idvd_Vg{gate_source_voltage_str}.csv',
        output_char_data,
        delimiter=',',
        header='Vd_src, Vg_src, Id, Ig',
        comments=''
    )



#be sure all voltages are set to zero
set_voltage(0, gate_source_instrum, ascii_command_flavor = 'non-SCPI')
set_voltage(0, drain_source_instrum, ascii_command_flavor = 'non-SCPI')

end_time = time.time()
elapsed_time = end_time - start_time
minutes = int(elapsed_time // 60)
seconds = elapsed_time % 60
print(f"Transistor Characterization completed in {minutes} minutes {seconds:.2f} seconds.")
