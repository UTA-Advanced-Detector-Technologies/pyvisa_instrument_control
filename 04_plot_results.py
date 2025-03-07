import glob
import os
import pandas as pd
import matplotlib.pyplot as plt
import re
import json


def load_mux_instructions(json_file="mux_instructions.json"):
    with open(json_file, "r") as f:
        mux_data = json.load(f)
    return mux_data


flavor = "HV"
data_folder = 'Data'

# Create output directories for plots.
os.makedirs('archiv/test7_roomtemp_full/plot_all_biases', exist_ok=True)
os.makedirs(f'archiv/test7_roomtemp_full/plot_all_biases/{flavor}', exist_ok=True)

mux_json_file = "mux_instructions_by_transistor_4wire_drain.json"
mux_data = load_mux_instructions(mux_json_file)

# Regex patterns to extract numeric substrings from filenames.
vd_pattern = re.compile(r'Vd([0-9e\-\+p]+)')
vg_pattern = re.compile(r'Vg([0-9e\-\+p]+)')
vb_pattern = re.compile(r'Vb([0-9e\-\+p]+)')
vsub_pattern = re.compile(r'Vsub([0-9e\-\+p]+)')


def read_data(csv_path):
    """Read the CSV file into a DataFrame with consistent column names."""
    df = pd.read_csv(csv_path, header=None)
    df.columns = [
        'Vd_src', 'Vg_src', 'Vb_src', 'Vsub_src',
        'Id', 'Ib', 'Isub', 'Ig',
        'Vd_meas', 'Vb_meas', 'Vsub_meas', 'Vg_meas',
        'TempA', 'TempB', 'Elapsed_time'
    ]
    numeric_cols = [
        'Vd_src', 'Vg_src', 'Vb_src', 'Vsub_src',
        'Id', 'Ib', 'Isub', 'Ig',
        'Vd_meas', 'Vb_meas', 'Vsub_meas', 'Vg_meas',
        'TempA', 'TempB', 'Elapsed_time'
    ]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
    return df


def ensure_dir(path):
    """Ensure that the directory at `path` exists."""
    os.makedirs(path, exist_ok=True)
    return path


def is_vb_zero(filename, transistor_type=None):
    """
    Return True if the filename indicates that Vbulk_source is zero.
    For PFETs the function checks if the filename contains "Vb0_forward_vs_backward"
    (so that names like "Vbopo" are treated as nonzero).
    For NFETs (or if transistor_type is not "pfet"), the numeric extraction is used.
    """
    basename = os.path.basename(filename)
    if transistor_type and transistor_type.lower() == "pfet":
        if "Vb0_forward_vs_backward" in basename:
            return True
        else:
            return False
    else:
        vb_match = vb_pattern.search(basename)
        if not vb_match:
            return False
        vb_str = vb_match.group(1).replace('p', '.')
        try:
            vb_float = float(vb_str)
            return abs(vb_float) < 1e-14
        except ValueError:
            return False


###############################################################################
# NEW: Transfer characteristics for nonzero-bias files grouped by terminal
###############################################################################
def plot_transfer_grouped_by_terminal(idvg_files, out_dir, label_for_title="Nonzero bias", transistor_type="pfet"):
    """
    For nonzero bulk/substrate bias data, plot all transfer curves (Id, Ib, Isub, Ig)
    on a single figure per terminal. Both linear-scale and log-scale (absolute currents)
    plots are created.
    """
    if not idvg_files:
        return

    transfer_lin_dir = ensure_dir(os.path.join(out_dir, "transfer_lin"))
    transfer_log_dir = ensure_dir(os.path.join(out_dir, "transfer_log"))

    # Create figures for linear-scale plots (one per terminal)
    fig_drain_lin, ax_drain_lin = plt.subplots()
    fig_body_lin, ax_body_lin = plt.subplots()
    fig_sub_lin, ax_sub_lin = plt.subplots()
    fig_gate_lin, ax_gate_lin = plt.subplots()

    # Create figures for log-scale plots
    fig_drain_log, ax_drain_log = plt.subplots()
    fig_body_log, ax_body_log = plt.subplots()
    fig_sub_log, ax_sub_log = plt.subplots()
    fig_gate_log, ax_gate_log = plt.subplots()

    for fpath in idvg_files:
        df = read_data(fpath)
        # grabbing Vds bias
        vd_match = vd_pattern.search(os.path.basename(fpath))
        vd_str = vd_match.group(1).replace('p', '.') if vd_match else "?"
        # Create a label based on the bias value (Vsub for NFET, Vbulk for PFET)
        if transistor_type.lower() == "nfet":
            vsub_match = vsub_pattern.search(os.path.basename(fpath))
            bias_val_str = vsub_match.group(1).replace('p', '.') if vsub_match else "?"
            label_str = f"Vsub_source={bias_val_str} V"
        else:
            vb_match = vb_pattern.search(os.path.basename(fpath))
            bias_val_str = vb_match.group(1).replace('p', '.') if vb_match else "?"
            label_str = f"Vds={vd_str} Vbs={bias_val_str}"

        # Linear-scale transfer curves (Vg_src vs current)
        ax_drain_lin.scatter(df['Vg_src'], df['Id'], s=10, label=label_str)
        ax_body_lin.scatter(df['Vg_src'], df['Ib'], s=10, label=label_str)
        ax_sub_lin.scatter(df['Vg_src'], df['Isub'], s=10, label=label_str)
        ax_gate_lin.scatter(df['Vg_src'], df['Ig'], s=10, label=label_str)

        # Log-scale plots (using absolute values)
        ax_drain_log.scatter(df['Vg_src'], abs(df['Id']), s=10, label=label_str)
        ax_body_log.scatter(df['Vg_src'], abs(df['Ib']), s=10, label=label_str)
        ax_sub_log.scatter(df['Vg_src'], abs(df['Isub']), s=10, label=label_str)
        ax_gate_log.scatter(df['Vg_src'], abs(df['Ig']), s=10, label=label_str)

    # Configure and save linear-scale plots
    ax_drain_lin.set_xlabel("V_gate_source (V)")
    ax_drain_lin.set_ylabel("Drain_Source I (A)")
    ax_drain_lin.set_title(f"Transfer Characteristics (Drain, lin) {label_for_title}")
    ax_drain_lin.legend()
    ax_drain_lin.grid(True)
    fig_drain_lin.tight_layout()
    fig_drain_lin.savefig(os.path.join(transfer_lin_dir, "transfer_drain_lin_grouped.png"))
    plt.close(fig_drain_lin)

    ax_body_lin.set_xlabel("V_gate_source (V)")
    ax_body_lin.set_ylabel("Body_Source I (A)")
    ax_body_lin.set_title(f"Transfer Characteristics (Body, lin) {label_for_title}")
    ax_body_lin.legend()
    ax_body_lin.grid(True)
    fig_body_lin.tight_layout()
    fig_body_lin.savefig(os.path.join(transfer_lin_dir, "transfer_body_lin_grouped.png"))
    plt.close(fig_body_lin)

    ax_sub_lin.set_xlabel("V_gate_source (V)")
    ax_sub_lin.set_ylabel("Substrate_Source I (A)")
    ax_sub_lin.set_title(f"Transfer Characteristics (Substrate, lin) {label_for_title}")
    ax_sub_lin.legend()
    ax_sub_lin.grid(True)
    fig_sub_lin.tight_layout()
    fig_sub_lin.savefig(os.path.join(transfer_lin_dir, "transfer_sub_lin_grouped.png"))
    plt.close(fig_sub_lin)

    ax_gate_lin.set_xlabel("V_gate_source (V)")
    ax_gate_lin.set_ylabel("Gate_Source I (A)")
    ax_gate_lin.set_title(f"Transfer Characteristics (Gate, lin) {label_for_title}")
    ax_gate_lin.legend()
    ax_gate_lin.grid(True)
    fig_gate_lin.tight_layout()
    fig_gate_lin.savefig(os.path.join(transfer_lin_dir, "transfer_gate_lin_grouped.png"))
    plt.close(fig_gate_lin)

    # Configure and save log-scale plots
    ax_drain_log.set_xlabel("V_gate_source (V)")
    ax_drain_log.set_ylabel("Drain_Source I (A) [log]")
    ax_drain_log.set_title(f"Transfer Characteristics (Drain, log) {label_for_title}")
    ax_drain_log.set_yscale("log")
    ax_drain_log.legend()
    ax_drain_log.grid(True)
    fig_drain_log.tight_layout()
    fig_drain_log.savefig(os.path.join(transfer_log_dir, "transfer_drain_log_grouped.png"))
    plt.close(fig_drain_log)

    ax_body_log.set_xlabel("V_gate_source (V)")
    ax_body_log.set_ylabel("Body_Source I (A) [log]")
    ax_body_log.set_title(f"Transfer Characteristics (Body, log) {label_for_title}")
    ax_body_log.set_yscale("log")
    ax_body_log.legend()
    ax_body_log.grid(True)
    fig_body_log.tight_layout()
    fig_body_log.savefig(os.path.join(transfer_log_dir, "transfer_body_log_grouped.png"))
    plt.close(fig_body_log)

    ax_sub_log.set_xlabel("V_gate_source (V)")
    ax_sub_log.set_ylabel("Substrate_Source I (A) [log]")
    ax_sub_log.set_title(f"Transfer Characteristics (Substrate, log) {label_for_title}")
    ax_sub_log.set_yscale("log")
    ax_sub_log.legend()
    ax_sub_log.grid(True)
    fig_sub_log.tight_layout()
    fig_sub_log.savefig(os.path.join(transfer_log_dir, "transfer_sub_log_grouped.png"))
    plt.close(fig_sub_log)

    ax_gate_log.set_xlabel("V_gate_source (V)")
    ax_gate_log.set_ylabel("Gate_Source I (A) [log]")
    ax_gate_log.set_title(f"Transfer Characteristics (Gate, log) {label_for_title}")
    ax_gate_log.set_yscale("log")
    ax_gate_log.legend()
    ax_gate_log.grid(True)
    fig_gate_log.tight_layout()
    fig_gate_log.savefig(os.path.join(transfer_log_dir, "transfer_gate_log_grouped.png"))
    plt.close(fig_gate_log)


###############################################################################
# NEW: Output characteristics grouped by terminal
###############################################################################
def plot_output_grouped_by_terminal(idvd_files, out_dir, label_for_title="Nonzero Bias"):
    """
    Create one output plot per terminal by overlaying all curves.
    Each plot is generated from the measured data:
       - X-axis: Vd_src
       - Y-axis: the corresponding terminal current (Id, Ib, Isub, or Ig)
    """
    if not idvd_files:
        return

    output_dir = ensure_dir(os.path.join(out_dir, "output"))

    # Create figures for each terminal.
    fig_drain, ax_drain = plt.subplots()
    fig_body, ax_body = plt.subplots()
    fig_sub, ax_sub = plt.subplots()
    fig_gate, ax_gate = plt.subplots()

    for fpath in idvd_files:
        if "paused" in fpath:
            s=40
        else:
            s=10 #default
        df = read_data(fpath)
        basename = os.path.basename(fpath)
        # Use Vg for the label (you might change this as desired)
        vg_match = vg_pattern.search(basename)
        vg_str = vg_match.group(1).replace('p', '.') if vg_match else "?"
        label_str = f"Vgs={vg_str} V"

        # if "Test2" in fpath:
        #     label_str = f"keeping Vgs={vg_str}V, Vs-sub=25V"
        # else:
        #     label_str = f"Vgs={vg_str} V lower all biases"

        ax_drain.scatter(df['Vd_src'], df['Id'], s=s, label=label_str)
        ax_body.scatter(df['Vd_src'], df['Ib'], s=s, label=label_str)
        ax_sub.scatter(df['Vd_src'], df['Isub'], s=s, label=label_str)
        ax_gate.scatter(df['Vd_src'], df['Ig'], s=s, label=label_str)

    ax_drain.set_xlabel("V_d_source (V)")
    ax_drain.set_ylabel("Drain Current I (A)")
    ax_drain.set_title(f"Output Characteristics (Drain) {label_for_title}")
    ax_drain.legend()
    ax_drain.grid(True)
    fig_drain.tight_layout()
    fig_drain.savefig(os.path.join(output_dir, "output_drain_grouped.png"))
    plt.close(fig_drain)

    ax_body.set_xlabel("V_d_source (V)")
    ax_body.set_ylabel("Body Current I (A)")
    ax_body.set_title(f"Output Characteristics (Body) {label_for_title}")
    ax_body.legend()
    ax_body.grid(True)
    fig_body.tight_layout()
    fig_body.savefig(os.path.join(output_dir, "output_body_grouped.png"))
    plt.close(fig_body)

    ax_sub.set_xlabel("V_d_source (V)")
    ax_sub.set_ylabel("Substrate Current I (A)")
    ax_sub.set_title(f"Output Characteristics (Substrate) {label_for_title}")
    ax_sub.legend()
    ax_sub.grid(True)
    fig_sub.tight_layout()
    fig_sub.savefig(os.path.join(output_dir, "output_sub_grouped.png"))
    plt.close(fig_sub)

    ax_gate.set_xlabel("V_d_source (V)")
    ax_gate.set_ylabel("Gate Current I (A)")
    ax_gate.set_title(f"Output Characteristics (Gate) {label_for_title}")
    ax_gate.legend()
    ax_gate.grid(True)
    fig_gate.tight_layout()
    fig_gate.savefig(os.path.join(output_dir, "output_gate_grouped.png"))
    plt.close(fig_gate)


###############################################################################
# Existing function for Vbulk_source=0 (already overlays curves)
###############################################################################
def plot_transfer_vb0(idvg_files, out_dir, label_for_title="Vbulk_source=0"):
    if not idvg_files:
        return

    fig_drain_lin, ax_drain_lin = plt.subplots()
    fig_body_lin, ax_body_lin = plt.subplots()
    fig_sub_lin, ax_sub_lin = plt.subplots()
    fig_gate_lin, ax_gate_lin = plt.subplots()

    fig_drain_log, ax_drain_log = plt.subplots()
    fig_body_log, ax_body_log = plt.subplots()
    fig_sub_log, ax_sub_log = plt.subplots()
    fig_gate_log, ax_gate_log = plt.subplots()

    for fpath in idvg_files:
        df = read_data(fpath)
        basename = os.path.basename(fpath)
        vd_match = vd_pattern.search(basename)
        vd_str = vd_match.group(1).replace('p', '.') if vd_match else "0"
        vsub_match = vsub_pattern.search(basename)
        vsub_str = vsub_match.group(1).replace('p', '.') if vsub_match else "?"
        label_str = f"Vd={vd_str} V, Vsub={vsub_str} V"

        ax_drain_lin.scatter(df['Vg_src'], df['Id'], s=10, label=label_str)
        ax_body_lin.scatter(df['Vg_src'], df['Ib'], s=10, label=label_str)
        ax_sub_lin.scatter(df['Vg_src'], df['Isub'], s=10, label=label_str)
        ax_gate_lin.scatter(df['Vg_src'], df['Ig'], s=10, label=label_str)

        ax_drain_log.scatter(df['Vg_src'], abs(df['Id']), s=10, label=label_str)
        ax_body_log.scatter(df['Vg_src'], abs(df['Ib']), s=10, label=label_str)
        ax_sub_log.scatter(df['Vg_src'], abs(df['Isub']), s=10, label=label_str)
        ax_gate_log.scatter(df['Vg_src'], abs(df['Ig']), s=10, label=label_str)

    ax_drain_lin.set_xlabel("V_gate_source (V)")
    ax_drain_lin.set_ylabel("Drain_Source I (A)")
    ax_drain_lin.set_title(f"Transfer (Drain, lin) {label_for_title}")
    ax_drain_lin.legend()
    ax_drain_lin.grid(True)
    fig_drain_lin.tight_layout()
    fig_drain_lin.savefig(os.path.join(out_dir, "transfer_drain_lin_grouped.png"))
    plt.close(fig_drain_lin)

    ax_body_lin.set_xlabel("V_gate_source (V)")
    ax_body_lin.set_ylabel("Body_Source I (A)")
    ax_body_lin.set_title(f"Transfer (Body, lin) {label_for_title}")
    ax_body_lin.legend()
    ax_body_lin.grid(True)
    fig_body_lin.tight_layout()
    fig_body_lin.savefig(os.path.join(out_dir, "transfer_body_lin_grouped.png"))
    plt.close(fig_body_lin)

    ax_sub_lin.set_xlabel("V_gate_source (V)")
    ax_sub_lin.set_ylabel("Substrate_Source I (A)")
    ax_sub_lin.set_title(f"Transfer (Substrate, lin) {label_for_title}")
    ax_sub_lin.legend()
    ax_sub_lin.grid(True)
    fig_sub_lin.tight_layout()
    fig_sub_lin.savefig(os.path.join(out_dir, "transfer_sub_lin_grouped.png"))
    plt.close(fig_sub_lin)

    ax_gate_lin.set_xlabel("V_gate_source (V)")
    ax_gate_lin.set_ylabel("Gate_Source I (A)")
    ax_gate_lin.set_title(f"Transfer (Gate, lin) {label_for_title}")
    ax_gate_lin.legend()
    ax_gate_lin.grid(True)
    fig_gate_lin.tight_layout()
    fig_gate_lin.savefig(os.path.join(out_dir, "transfer_gate_lin_grouped.png"))
    plt.close(fig_gate_lin)

    ax_drain_log.set_xlabel("V_gate_source (V)")
    ax_drain_log.set_ylabel("Drain_Source I (A) [log]")
    ax_drain_log.set_title(f"Transfer (Drain, log) {label_for_title}")
    ax_drain_log.set_yscale("log")
    ax_drain_log.legend()
    ax_drain_log.grid(True)
    fig_drain_log.tight_layout()
    fig_drain_log.savefig(os.path.join(out_dir, "transfer_drain_log_grouped.png"))
    plt.close(fig_drain_log)

    ax_body_log.set_xlabel("V_gate_source (V)")
    ax_body_log.set_ylabel("Body_Source I (A) [log]")
    ax_body_log.set_title(f"Transfer (Body, log) {label_for_title}")
    ax_body_log.set_yscale("log")
    ax_body_log.legend()
    ax_body_log.grid(True)
    fig_body_log.tight_layout()
    fig_body_log.savefig(os.path.join(out_dir, "transfer_body_log_grouped.png"))
    plt.close(fig_body_log)

    ax_sub_log.set_xlabel("V_gate_source (V)")
    ax_sub_log.set_ylabel("Substrate_Source I (A) [log]")
    ax_sub_log.set_title(f"Transfer (Substrate, log) {label_for_title}")
    ax_sub_log.set_yscale("log")
    ax_sub_log.legend()
    ax_sub_log.grid(True)
    fig_sub_log.tight_layout()
    fig_sub_log.savefig(os.path.join(out_dir, "transfer_sub_log_grouped.png"))
    plt.close(fig_sub_log)

    ax_gate_log.set_xlabel("V_gate_source (V)")
    ax_gate_log.set_ylabel("Gate_Source I (A) [log]")
    ax_gate_log.set_title(f"Transfer (Gate, log) {label_for_title}")
    ax_gate_log.set_yscale("log")
    ax_gate_log.legend()
    ax_gate_log.grid(True)
    fig_gate_log.tight_layout()
    fig_gate_log.savefig(os.path.join(out_dir, "transfer_gate_log_grouped.png"))
    plt.close(fig_gate_log)


###############################################################################
# Main loop over transistors
###############################################################################
for transistor_key, mux_dict in mux_data.items():
    # Uncomment to restrict to a specific transistor.
    if 'pmos25_FET1' not in transistor_key:
        continue

    base_out_dir = f'plot_all_biases/{flavor}/250K0_high_Vds_tests/{transistor_key}'
    os.makedirs(base_out_dir, exist_ok=True)

    transistor_key_lower = transistor_key.lower()
    if "nfet" in transistor_key_lower:
        transistor_type = "nfet"
    elif "pfet" in transistor_key_lower or "pmos" in transistor_key_lower:
        transistor_type = "pfet"
    else:
        transistor_type = "pfet"

    all_csv_files = glob.glob(f"{data_folder}/250K0_high_Vds_tests/{flavor}/{transistor_key}/*.csv")

    idvg_files = [f for f in all_csv_files if 'idvg' in os.path.basename(f).lower()]
    idvd_files = [f for f in all_csv_files if 'idvd' in os.path.basename(f).lower()]
    paused_files = [f for f in all_csv_files if 'paused' in os.path.basename(f).lower()]

    idvg_vb0 = [f for f in idvg_files if is_vb_zero(f, transistor_type)]
    idvg_vbnon0 = [f for f in idvg_files if not is_vb_zero(f, transistor_type)]
    idvd_vb0 = [f for f in idvd_files if is_vb_zero(f, transistor_type)]
    idvd_vbnon0 = [f for f in idvd_files if not is_vb_zero(f, transistor_type)]

    # --- Plot for Vbulk_source = 0 (Vb0_forward_vs_backward) files ---
    vb0_out_dir = ensure_dir(os.path.join(base_out_dir, "Vb0"))
    #paused_out_dir = ensure_dir(os.path.join(base_out_dir, "self_heating_tests"))
    #plot_transfer_vb0(idvg_vb0, vb0_out_dir, label_for_title=" @ 20K")
    plot_transfer_grouped_by_terminal(idvg_vbnon0, vb0_out_dir, label_for_title="@ 250K")
    plot_output_grouped_by_terminal(idvd_vbnon0, vb0_out_dir, label_for_title="Paused measurements @ 250K")
    #plot_output_grouped_by_terminal(paused_files, paused_out_dir, label_for_title="Self-heating test (4K, 10min interval)")

    # --- Plot for nonzero bias files (grouped by terminal) ---
    #vbNon0_out_dir = ensure_dir(os.path.join(base_out_dir, "VbNon0"))
    #plot_transfer_grouped_by_terminal(idvg_vbnon0, vbNon0_out_dir, transistor_type=transistor_type)
    #plot_output_grouped_by_terminal(idvd_vbnon0, vbNon0_out_dir, label_for_title="Nonzero Bias")

print("Done generating plots.")
