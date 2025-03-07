import pyvisa
import time
import numpy as np
import os
import json
import matplotlib.pyplot as plt

#-------------------------------------------------------Definitions-----------------------------------------------------
def load_sweep_bias_instructions_from_json(input_file):
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
        print(f"Processed data successfully loaded from {input_file}")
        return data  #return the dictionary containing the processed data
    except Exception as e:
        print(f"Failed to load processed data from {input_file}. Error: {e}")
        return None

def configure_instr(sourcing_voltage, instr, current_compliance = 0.01, voltage_compliance = 26,
                    ascii_command_flavor = 'SCPI', wire_mode = 2):
    try:
        if ascii_command_flavor == 'SCPI':
            instr.write('*RST')  # Reset the instrument
            if wire_mode == 2:
                instr.write(":SYST:RSEN OFF")
            elif wire_mode == 4:
                instr.write(":SYST:RSEN ON")
            else:
                print('Invalid wire_mode passed, please pass 2 or 4')
            instr.write(':SOUR:FUNC VOLT')  # Set source function to voltage
            instr.write(':SOUR:VOLT:MODE FIXED')  # Fixed voltage mode
            instr.write(f':SENS:VOLT:PROT {voltage_compliance}')  # Set voltage compliance to 26 volts
            instr.write(f':SOUR:VOLT {sourcing_voltage}')  # Set sourcing voltage
            instr.write(':SENS:FUNC "CURR"')  # Set sense function to current
            instr.write(f':SENS:CURR:PROT {current_compliance}')  # Set current compliance limit
            instr.write(':SENS:AVER:COUN 4')  # Set averaging count to 4
            instr.write(':SENS:AVER:TCON REP')  # Typically 'REP' for repeating type averaging
            instr.write(':SENS:AVER:STAT ON')  # Enable averaging
            instr.write(':OUTP ON')  # Turn on output
        elif ascii_command_flavor == 'non-SCPI':
            instr.write("F0,0X")  # select v-source and measure I DC
            instr.write(f'B{sourcing_voltage},0,0X')  # set source to voltage value
            instr.write(f"L{current_compliance},0X")  # set current compliance and select auto measuring range (select using 0 from manual)
            instr.write("P2X")  # set to get the average of 4 measurements on the smu
            instr.write("R1X")  # enable triggers
            instr.write('H0X')  # trigger (t0 output the voltage)
            instr.write("N1X")  # send from standby to output
        else:
            raise ValueError(
                "Invalid ascii_command_flavor: Please do \'non-SCPI\' for the keithley 236/237/238 series or \'SCPI\' for the newer instruments")
    except ValueError as e:
        print(e)


def measure_current(instr, ascii_command_flavor='SCPI'):
    """
    Measure current using the specified instrument.

    Parameters:
    - instr: The instrument communication object (e.g., VISA resource).
    - ascii_command_flavor (str): 'SCPI' for SCPI-compliant instruments or 'non-SCPI' for others.

    Returns:
    - float: The measured current, or None if an error occurs.
    """
    try:
        if ascii_command_flavor.upper() == 'SCPI':
            # Single query to trigger measurement and get the response
            response = instr.query(":READ?")
            # Assuming the current is the second value in a comma-separated string
            current = float(response.strip().split(',')[1])

        elif ascii_command_flavor.lower() == 'non-scpi':
            # Combine multiple commands into one to reduce I/O overhead
            commands = "O1X;G4,2,0X;H0X;"
            instr.write(commands)
            # Query the response in a single operation
            response = instr.query("X")
            current = float(response.strip())

        else:
            raise ValueError(
                "Invalid ascii_command_flavor: Use 'non-SCPI' for Keithley 236/237/238 series or 'SCPI' for newer instruments."
            )

        return current

    except IndexError:
        print("Unexpected response format:", response)
    except ValueError as ve:
        print("Value conversion error:", ve)
    except Exception as e:
        print("Error measuring current:", e)

    return None

def voltage_sweep_three_instruments(fixed, variable, sweep_voltages, fixed_voltage, body_voltage, ds_instr, gs_instr, bs_instr, curr_compliance = 0.01, live_plot = True):

    if live_plot:
        # Enable interactive mode for live plotting
        plt.ion()

        # Create a figure with three subplots, one for each current
        fig, axs = plt.subplots(3, 1, figsize=(8, 8), sharex=True)

        # Create separate line objects for each current on its respective subplot
        line_d, = axs[0].plot([], [], 'b-o', markersize=4, label='Drain Current')
        line_b, = axs[1].plot([], [], 'r-o', markersize=4, label='Body Current')
        line_g, = axs[2].plot([], [], 'g-o', markersize=4, label='Gate Current')

        # Set titles and labels
        fig.suptitle(f"{variable} Sweep with Fixed {fixed} = {fixed_voltage}V Vb = {body_voltage}V")
        axs[2].set_xlabel(f"{variable} (V)")
        axs[0].set_ylabel("Drain I (A)")
        axs[1].set_ylabel("Body I (A)")
        axs[2].set_ylabel("Gate I (A)")

        axs[0].legend(loc='upper left')
        axs[1].legend(loc='upper left')
        axs[2].legend(loc='upper left')

        plt.tight_layout()
        plt.show(block=False)

    try:
        fixed_v_instr_wire_mode = None
        sweep_v_instr_wire_mode = None
        if 'Vd' in fixed and 'Vg' in variable:
            fixed_v_instr = ds_instr
            sweep_v_instr = gs_instr
            fixed_v_instr_wire_mode = 4
            sweep_v_instr_wire_mode = 2
        elif 'Vg' in fixed and 'Vd' in variable:
            fixed_v_instr = gs_instr
            sweep_v_instr = ds_instr
            fixed_v_instr_wire_mode = 2
            sweep_v_instr_wire_mode = 4
        else:
            raise ValueError(
                "Invalid configuration: Please do 'Vg' and 'Vd' for 'fixed' and 'variable' values.")
    except ValueError as e:
        print(e)

    data = []
    plotting_voltages = []
    plotting_d_currents = []
    plotting_b_currents = []
    plotting_g_currents = []

    #configure everything
    configure_instr(body_voltage, bs_instr, current_compliance=curr_compliance,
                    ascii_command_flavor='non-SCPI')  # Body voltage
    configure_instr(fixed_voltage, fixed_v_instr, current_compliance=curr_compliance,
                    ascii_command_flavor='SCPI', wire_mode=fixed_v_instr_wire_mode)  # Fixed voltage
    configure_instr(0, sweep_v_instr, current_compliance=curr_compliance,
                    ascii_command_flavor='SCPI', wire_mode=sweep_v_instr_wire_mode)  # Start sweep at 0 V

    for v_value in sweep_voltages:
        sweep_v_instr.write(f":SOUR:VOLT:LEV {v_value}")  # Update sweep voltage

        # Measure currents
        d_current = measure_current(ds_instr, ascii_command_flavor='SCPI')
        b_current = measure_current(bs_instr, ascii_command_flavor='non-SCPI')
        g_current = measure_current(gs_instr, ascii_command_flavor='SCPI')

        data.append((fixed_voltage, v_value, body_voltage, d_current, b_current, g_current))

        if live_plot:
            # Append the new data
            plotting_voltages.append(v_value)
            plotting_d_currents.append(d_current)
            plotting_b_currents.append(b_current)
            plotting_g_currents.append(g_current)

            # Update each line object with new data
            line_d.set_data(plotting_voltages, plotting_d_currents)
            line_b.set_data(plotting_voltages, plotting_b_currents)
            line_g.set_data(plotting_voltages, plotting_g_currents)

            # Adjust axes for new data
            for ax in axs:
                ax.relim()
                ax.autoscale_view()

            fig.canvas.draw()
            fig.canvas.flush_events()

    # Close the figure after the measurement is complete
    if live_plot:
        plt.close(fig)

    # Turn off outputs after measurement
    sweep_v_instr.write(':OUTP OFF')
    fixed_v_instr.write(':OUTP OFF')
    bs_instr.write("N0X")  # send from output to standby
    return data

def characterize_transistor( fixed, variable, sweep_voltages, fixed_voltage, body_voltage, ds_instr, gs_instr, bs_instr, live_plotting):
    data = voltage_sweep_three_instruments(fixed, variable, sweep_voltages, fixed_voltage, body_voltage, ds_instr, gs_instr, bs_instr, live_plot=live_plotting)
    return data

def load_mux_instructions(json_file="mux_instructions.json"):
    with open(json_file, "r") as f:
        mux_data = json.load(f)
    return mux_data

def load_bias_instructions(fet_type = "NMOS"):
    try:
        if "NMOS" not in fet_type and "PMOS" not in fet_type:
            raise ValueError("Please pass \"NMOS\" or \"PMOS\" as fet_type")
    except ValueError as e:
        print(e)

    input_json_path = "sweep_bias_instructions.json"

    # first run 01_save_mux_bias_instructions.py. Then this code will work
    # Load the instructions
    processed_data = load_sweep_bias_instructions_from_json(input_json_path)

    # ------grab nmos instructions-----
    transfer_char_set1 = processed_data.get(fet_type, {}).get('Primary sweep: Vgs Set 1', {})
    transfer_char_set2 = processed_data.get(fet_type, {}).get('Primary sweep: Vgs Set 2', {})
    transfer_char = processed_data.get(fet_type, {}).get('Primary sweep: Vds', {})

    transfer_char_set1_vs = transfer_char_set1.get("Vs", [])
    transfer_char_set1_vb = transfer_char_set1.get("Vb", [])
    transfer_char_set1_vd = transfer_char_set1.get("Vd", [])
    transfer_char_set1_vg = transfer_char_set1.get("Vg", [])

    transfer_char_set2_vs = transfer_char_set2.get("Vs", [])
    transfer_char_set2_vb = transfer_char_set2.get("Vb", [])
    transfer_char_set2_vd = transfer_char_set2.get("Vd", [])
    transfer_char_set2_vg = transfer_char_set2.get("Vg", [])

    transfer_char_vs = transfer_char.get("Vs", [])
    transfer_char_vb = transfer_char.get("Vb", [])
    transfer_char_vd = transfer_char.get("Vd", [])
    transfer_char_vg = transfer_char.get("Vg", [])

    return (
        (transfer_char_set1_vs, transfer_char_set1_vb, transfer_char_set1_vd, transfer_char_set1_vg),
        (transfer_char_set2_vs, transfer_char_set2_vb, transfer_char_set2_vd, transfer_char_set2_vg),
        (transfer_char_vs, transfer_char_vb, transfer_char_vd, transfer_char_vg)
    )
    

#-----------------------------------------------------Take some measurements--------------------------------------------
#set these values or make sure they are correct for your experiment
data_folder = 'Data'
mux_json_file= "mux_instructions_by_transistor_4wire_drain.json"
live_plotting = True

# Initialize VISA resource manager
rm = pyvisa.ResourceManager()

#should print something like this, find your instruments ('GPIB0::24::INSTR', 'GPIB0::25::INSTR', 'TCPIP0::192.168.1.100::INSTR')
print(rm.list_resources())

# Replace with your actual VISA addresses
keithley2410_address = 'GPIB1::5::INSTR'
keithley2400_address = 'GPIB1::22::INSTR'
keithley237_bottom_address = 'GPIB1::15::INSTR'
keithley237_top_address = 'GPIB1::11::INSTR'
DAQ_mux_ds_top_address = 'USB0::0x05E6::0x6510::04510741::INSTR'
DAQ_mux_gs_bottom_address = 'USB0::0x05E6::0x6510::04505354::INSTR'

# Open sessions
keithley2410 = rm.open_resource(keithley2410_address, read_termination='\r', write_termination='\r')
keithley2400 = rm.open_resource(keithley2400_address, read_termination='\r', write_termination='\r')
keithley237_bottom = rm.open_resource(keithley237_bottom_address, read_termination='\r', write_termination='\r')
keithley237_top = rm.open_resource(keithley237_top_address, read_termination='\r', write_termination='\r')
DAQ_mux_ds_top = rm.open_resource(DAQ_mux_ds_top_address, read_termination='\n', write_termination='\n')
DAQ_mux_gs_bottom = rm.open_resource(DAQ_mux_gs_bottom_address, read_termination='\n', write_termination='\n')

keithley2410.timeout = 5000
keithley2400.timeout = 5000
# if you get errors you can use something like these lines to query:
#error = keithley2400.query('SYST:ERR?')
#print(f'Keithley 2400 Error Status: {error}')

# Set the instruments for gate-source, drain-source, body-source
ds_instr= keithley2400
gs_instr = keithley2410
bs_instr = keithley237_bottom
substrate_instr = keithley237_top

# #set the 4th smu to some voltage for the substrate potentially (not using for now)
# substrate_voltage = 0
# configure_instr(substrate_voltage, substrate_instr, current_compliance=0.01,
#                     ascii_command_flavor='non-SCPI')

mux_data = load_mux_instructions(mux_json_file)
for transistor_key, mux_dict in mux_data.items():
    #for testing purposes
    if 'nmos' in transistor_key:
        print('nmos, continuing')
        continue

    # transistor_key looks like "pmos25_FET1"
    print(f"\nConfiguring transistor: {transistor_key}")

    #grab the flavor info from the transistor_key
    flavor=None
    if '25' in transistor_key:
        flavor = 'HV'
    else:
        print('please configure for MV and LV')
        break
    # grab the fet type info from the transistor_key
    if 'pmos' in transistor_key:
        fet_type = "PMOS"
    elif 'nmos' in transistor_key:
        fet_type = "NMOS"
    else:
        print('invalid fet type')
        break

    os.makedirs(data_folder, exist_ok=True)
    os.makedirs(f'{data_folder}/{flavor}', exist_ok=True)

    # loaded in format instructions[instruction set][node biases][transistor flavor]
    # transistor flavors are [0]=LV [1]=MV [2]=HV
    bias_instructions = load_bias_instructions(fet_type)

    try:
        flavor_index = {"LV": 0, "MV": 1, "HV": 2}[flavor]
    except KeyError:
        print("Invalid flavor, please pass LV, MV, or HV")

    # transfer char set 1
    gate_voltages_transfer_char_s1 = bias_instructions[1][3][
        flavor_index]  # 0 for the first instruction set, 3 for the gate voltage vals, 2 for the HV devices
    drain_voltages_transfer_char_s1 = bias_instructions[0][2][flavor_index]
    body_voltages_transfer_char_s1 = bias_instructions[0][1][flavor_index]

    # transfer char set 2
    gate_voltages_transfer_char_s2 = bias_instructions[1][3][flavor_index]
    drain_voltages_transfer_char_s2 = bias_instructions[1][2][flavor_index]
    body_voltages_transfer_char_s2 = bias_instructions[1][1][flavor_index]

    # output char
    drain_voltages_output_char = bias_instructions[1][2][flavor_index]
    gate_voltages_output_char = bias_instructions[1][3][flavor_index]
    body_voltages_output_char = bias_instructions[1][1][flavor_index]

    DAQ_mux_ds_top.write('ROUTe:OPEN:ALL') #open everything to start
    DAQ_mux_gs_bottom.write('ROUTe:OPEN:ALL')  # open everything to start

    DAQ_mux_ds_top.write(':FUNC "VOLT:DC"')  # Configure DC voltage mode
    DAQ_mux_gs_bottom.write(':FUNC "VOLT:DC"')  # Configure DC voltage mode

    #two vs 4 wire measurements on the mux are automatically configured based on if
    # you have both the force and sense channels open, so no additional configuration for the mux is needed

    # mux_dict is something like: { "Mux1": [...], "Mux2": [...] }
    for mux_name, mux_instructions in mux_dict.items():
        print(f"  → Setting up {mux_name}")
        for instruc in mux_instructions:
            # instr has keys like:
            # {
            #   "raw_string": "P1016_pmos25_FET3_CH7_BiasDS_Force",
            #   "transistor_type": "pmos25",
            #   "fet": 3,
            #   "channel": 7,
            #   "bias_type": "DS",
            #   "operation": "Force"
            # }
            channel_idx = instruc["channel"]
            bias_type = instruc["bias_type"]
            operation = instruc["operation"]  # "Force", "Sense", or None (GS)

            # Map "channel_idx" to the actual 7703 switch channel
            keithley_channel = 100 + channel_idx

            if "DS" in bias_type: #look at top daq
                # Close the channel:
                DAQ_mux_ds_top.write(f"ROUT:CLOS (@{keithley_channel})")
                print(f"    Closed channel {keithley_channel} "
                  f"(bias={bias_type}, operation={operation}) in top DAQ/MUX for DS")
            elif "GS" in bias_type: #look at bottom daq
                # Close the channel:
                DAQ_mux_gs_bottom.write(f"ROUT:CLOS (@{keithley_channel})")
                print(f"    Closed channel {keithley_channel} "
                  f"(bias={bias_type}, operation={operation}) in bottom DAQ/MUX for GS")
            else:
                print('Invalid bias terminals, not GS or DS')

    start_time = time.time()
    os.makedirs(f'{data_folder}/{flavor}/{transistor_key}', exist_ok=True)

    '''# transfer characteristics set 1
    for vb in body_voltages_transfer_char_s1:
        for drain_voltage in drain_voltages_transfer_char_s1:
            transfer_char_data = characterize_transistor('Vd', 'Vg', gate_voltages_transfer_char_s1,
                                                         drain_voltage, vb, ds_instr, gs_instr, bs_instr, live_plotting)
            drain_voltage_str = str(drain_voltage).replace('.', 'p')
            body_voltage_str = str(vb).replace('.', 'p')
            np.savetxt(f'{data_folder}/{flavor}/{transistor_key}/idvg_Vd{drain_voltage_str}_Vb{body_voltage_str}.csv', transfer_char_data,
                       delimiter=',', header='V_drain,V_gate,V_body,I_drain,I_body,I_gate')
    '''
    # transfer characteristics set 2
    sweep=[]
    n=0
    for i in range(0, round(0.6/0.01)):
        sweep.append(n)
        n-=0.01

    for vb in [0]:
        for drain_voltage in [-0.02,-0.03,-0.04]:
            transfer_char_data = characterize_transistor('Vd', 'Vg',sweep,
                                                         drain_voltage, vb, ds_instr,
                                                         gs_instr, bs_instr, live_plotting)
            drain_voltage_str = str(drain_voltage).replace('.', 'p')
            body_voltage_str = str(vb).replace('.', 'p')
            np.savetxt(f'{data_folder}/{flavor}/{transistor_key}/idvg_Vd{drain_voltage_str}_Vb{body_voltage_str}.csv', transfer_char_data,
                       delimiter=',', header='V_drain,V_gate,V_body,I_drain,I_body,I_gate')

    # output characteristics
    for vb in [0]:
        for gate_voltage in [-0.02,-0.03,-0.04, -0.6]:
            output_char_data = characterize_transistor('Vg', 'Vd', sweep,
                                                       gate_voltage,vb, ds_instr, gs_instr, bs_instr, live_plotting)
            gate_voltage_str = str(gate_voltage).replace('.', 'p')
            body_voltage_str = str(vb).replace('.', 'p')
            np.savetxt(f'{data_folder}/{flavor}/{transistor_key}/idvd_Vg{gate_voltage_str}_Vb{body_voltage_str}.csv', output_char_data,
                       delimiter=',', header='V_gate,V_drain,V_body,I_drain,I_body,I_gate')

    end_time = time.time()
    elapsed_time = end_time - start_time
    minutes = int(elapsed_time // 60)
    seconds = elapsed_time % 60
    print(f"Transistor Characterization completed in {minutes} minutes {seconds:.2f} seconds.")

