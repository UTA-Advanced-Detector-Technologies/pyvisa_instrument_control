import pyvisa

################### User/Experimenter Settings ###################
drain_source_instrum_address = 'GPIB0::11::INSTR'
gate_source_instrum_address = 'GPIB0::15::INSTR'
##################################################################
rm = pyvisa.ResourceManager()
print("Available VISA resources:", rm.list_resources())

#---------------------------------------------------------------------------------
# Open each resource (instrument) and configure termination for SCPI vs. non-SCPI
#---------------------------------------------------------------------------------
drain_source_instrum = rm.open_resource(drain_source_instrum_address, read_termination='\r', write_termination='\r')
gate_source_instrum = rm.open_resource(gate_source_instrum_address, read_termination='\r', write_termination='\r')

gate_source_instrum.timeout = 5000
drain_source_instrum.timeout = 5000

# ---------------------------------------------------------
# 1) Reset and set all SMUs to 0 V, then turn outputs OFF.
#---------------------------------------------------------------------------------

# Keithley 2410 & 2400 (SCPI)
for instr in [drain_source_instrum, gate_source_instrum]:
    instr.write(f'B0,0,0X')     # Set source to 0 V
    instr.write("N0X")       # Turn output off

print("\nAll SMU voltages set to 0 V, outputs turned off.")
print("All MUX channels opened (disconnected).")
print("Shutdown/reset complete.")