import pyvisa

################### User/Experimenter Settings ###################
drain_source_instrum_address = 'GPIB1::24::INSTR'
gate_source_instrum_address = 'GPIB1::25::INSTR'
bulk_source_instrum_address = 'GPIB1::23::INSTR'
sourc_sub_instrum_address = 'GPIB1::22::INSTR'
DAQ_mux_ds_top_address = 'USB0::0x05E6::0x6510::04510741::INSTR'
DAQ_mux_gs_bottom_address = 'USB0::0x05E6::0x6510::04505354::INSTR'
##################################################################
rm = pyvisa.ResourceManager()
print("Available VISA resources:", rm.list_resources())

#---------------------------------------------------------------------------------
# Open each resource (instrument) and configure termination for SCPI vs. non-SCPI
#---------------------------------------------------------------------------------
drain_source_instrum = rm.open_resource(drain_source_instrum_address, read_termination='\r', write_termination='\r')
gate_source_instrum = rm.open_resource(gate_source_instrum_address, read_termination='\r', write_termination='\r')
bulk_source_instrum = rm.open_resource(bulk_source_instrum_address, read_termination='\r', write_termination='\r')
sourc_sub_instrum = rm.open_resource(sourc_sub_instrum_address, read_termination='\r', write_termination='\r')
DAQ_mux_ds_top = rm.open_resource(DAQ_mux_ds_top_address, read_termination='\n', write_termination='\n')
DAQ_mux_gs_bottom = rm.open_resource(DAQ_mux_gs_bottom_address, read_termination='\n', write_termination='\n')

gate_source_instrum.timeout = 5000
drain_source_instrum.timeout = 5000
bulk_source_instrum.timeout = 5000
sourc_sub_instrum.timeout = 5000

# Two DAQ/MUX instruments (assuming SCPI‐based control)
DAQ_mux_ds_top    = rm.open_resource(DAQ_mux_ds_top_address,
                                     read_termination='\n',
                                     write_termination='\n')
DAQ_mux_gs_bottom = rm.open_resource(DAQ_mux_gs_bottom_address,
                                     read_termination='\n',
                                     write_termination='\n')

#------------------------
# ---------------------------------------------------------
# 1) Reset and set all SMUs to 0 V, then turn outputs OFF.
#---------------------------------------------------------------------------------

# Keithley 2410 & 2400 (SCPI)
for instr in [drain_source_instrum, gate_source_instrum,bulk_source_instrum,sourc_sub_instrum]:
    instr.write(":SOUR:VOLT 0")     # Set source to 0 V
    instr.write(":OUTP OFF")        # Turn output off

#---------------------------------------------------------------------------------
# 2) Open ALL channels on the MUX instruments.
#---------------------------------------------------------------------------------
#   This dis connects every channel, ensuring no forced connections remain.
DAQ_mux_ds_top.write("ROUT:OPEN:ALL")
DAQ_mux_gs_bottom.write("ROUT:OPEN:ALL")

print("\nAll SMU voltages set to 0 V, outputs turned off.")
print("All MUX channels opened (disconnected).")
print("Shutdown/reset complete.")