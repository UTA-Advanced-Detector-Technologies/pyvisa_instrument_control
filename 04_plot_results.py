import glob
import os
import pandas as pd
import matplotlib.pyplot as plt
import re
import json


flavor = "LV"
data_folder = 'Data'

# Regex patterns to extract numeric substrings from filenames.
vd_pattern = re.compile(r'Vd([0-9e\-\+p]+)')
vg_pattern = re.compile(r'Vg([0-9e\-\+p]+)')
vb_pattern = re.compile(r'Vb([0-9e\-\+p]+)')
vsub_pattern = re.compile(r'Vsub([0-9e\-\+p]+)')


def read_data(csv_path):
    """Read the CSV file into a DataFrame with consistent column names."""
    df = pd.read_csv(csv_path, header=None)
    df.columns = [
        'Vd_src', 'Vg_src',
        'Id', 'Ig'
    ]
    numeric_cols = [
        'Vd_src', 'Vg_src',
        'Id', 'Ig'
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

def plot_transfer_grouped_by_terminal(idvg_files, out_dir, label_for_title="Nonzero bias", transistor_type="pfet"):

    if not idvg_files:
        return

    transfer_lin_dir = ensure_dir(os.path.join(out_dir, "transfer_lin"))
    transfer_log_dir = ensure_dir(os.path.join(out_dir, "transfer_log"))

    # Create figures for linear-scale plots (one per terminal)
    fig_drain_lin, ax_drain_lin = plt.subplots()
    fig_gate_lin, ax_gate_lin = plt.subplots()

    # Create figures for log-scale plots
    fig_drain_log, ax_drain_log = plt.subplots()
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
        ax_gate_lin.scatter(df['Vg_src'], df['Ig'], s=10, label=label_str)

        # Log-scale plots (using absolute values)
        ax_drain_log.scatter(df['Vg_src'], abs(df['Id']), s=10, label=label_str)
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

    ax_gate_log.set_xlabel("V_gate_source (V)")
    ax_gate_log.set_ylabel("Gate_Source I (A) [log]")
    ax_gate_log.set_title(f"Transfer Characteristics (Gate, log) {label_for_title}")
    ax_gate_log.set_yscale("log")
    ax_gate_log.legend()
    ax_gate_log.grid(True)
    fig_gate_log.tight_layout()
    fig_gate_log.savefig(os.path.join(transfer_log_dir, "transfer_gate_log_grouped.png"))
    plt.close(fig_gate_log)


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

        ax_drain.scatter(df['Vd_src'], df['Id'], s=s, label=label_str)
        ax_gate.scatter(df['Vd_src'], df['Ig'], s=s, label=label_str)

    ax_drain.set_xlabel("V_d_source (V)")
    ax_drain.set_ylabel("Drain Current I (A)")
    ax_drain.set_title(f"Output Characteristics (Drain) {label_for_title}")
    ax_drain.legend()
    ax_drain.grid(True)
    fig_drain.tight_layout()
    fig_drain.savefig(os.path.join(output_dir, "output_drain_grouped.png"))
    plt.close(fig_drain)

    ax_gate.set_xlabel("V_d_source (V)")
    ax_gate.set_ylabel("Gate Current I (A)")
    ax_gate.set_title(f"Output Characteristics (Gate) {label_for_title}")
    ax_gate.legend()
    ax_gate.grid(True)
    fig_gate.tight_layout()
    fig_gate.savefig(os.path.join(output_dir, "output_gate_grouped.png"))
    plt.close(fig_gate)


def plot_transfer_vb0(idvg_files, out_dir, label_for_title="Vsource=0"):
    if not idvg_files:
        return

    fig_drain_lin, ax_drain_lin = plt.subplots()
    fig_gate_lin, ax_gate_lin = plt.subplots()

    fig_drain_log, ax_drain_log = plt.subplots()
    fig_gate_log, ax_gate_log = plt.subplots()

    for fpath in idvg_files:
        if "range5" in fpath:
            extra_label= ", Range 5 (10uA)"
        elif "range6." in fpath:
            extra_label= ", Range 6 (100uA)"
        elif "range7" in fpath:
            extra_label=", Range 7 (1mA)"
        elif "range4" in fpath:
            extra_label=", Range 4 (1uA)"
        elif "range6(2)" in fpath:
            extra_label=", Range 6 (100uA) (not changing range)"
        else:
            extra_label=""
        df = read_data(fpath)
        basename = os.path.basename(fpath)
        vd_match = vd_pattern.search(basename)
        vd_str = vd_match.group(1).replace('p', '.') if vd_match else "0"
        vsub_match = vsub_pattern.search(basename)
        vsub_str = vsub_match.group(1).replace('p', '.') if vsub_match else "?"
        label_str = f"Vd={vd_str} V"

        ax_drain_lin.scatter(df['Vg_src'], df['Id'], s=10, label=f"{label_str}{extra_label}")
        ax_gate_lin.scatter(df['Vg_src'], df['Ig'], s=10, label=f"{label_str}{extra_label}")

        ax_drain_log.scatter(abs(df['Vg_src']), abs(df['Id']), s=10, label=f"{label_str}{extra_label}")
        ax_gate_log.scatter(abs(df['Vg_src']), abs(df['Ig']), s=10, label=f"{label_str}{extra_label}")

    ax_drain_lin.set_xlabel("V_gate_source (V)")
    ax_drain_lin.set_ylabel("Drain_Source I (A)")
    ax_drain_lin.set_title(f"Transfer (Drain, lin) {label_for_title}")
    ax_drain_lin.legend()
    ax_drain_lin.grid(True)
    fig_drain_lin.tight_layout()
    fig_drain_lin.savefig(os.path.join(out_dir, "transfer_drain_lin_grouped.png"))
    plt.close(fig_drain_lin)

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
    #ax_drain_log.set_ylim(0, 1e-6)
    ax_drain_log.set_yscale("log")
    ax_drain_log.legend()
    ax_drain_log.grid(True)
    fig_drain_log.tight_layout()
    fig_drain_log.savefig(os.path.join(out_dir, "transfer_drain_log_grouped.png"))
    plt.close(fig_drain_log)

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
# Main plot function
###############################################################################
transistor_key = 'pmos_FET_len_8_wid_1.6'

base_out_dir = f'plot_all_biases/{flavor}/160K_bonding_diagram_1_05-20-2025/{transistor_key}'
os.makedirs(base_out_dir, exist_ok=True)

transistor_key_lower = transistor_key.lower()
if "nfet" in transistor_key_lower:
    transistor_type = "nfet"
elif "pfet" in transistor_key_lower or "pmos" in transistor_key_lower:
    transistor_type = "pfet"
else:
    transistor_type = "pfet"

all_csv_files = glob.glob(f"{data_folder}/160K_bonding_diagram_1_05-20-2025/{flavor}/{transistor_key}/*.csv")

idvg_files = [f for f in all_csv_files if 'idvg' in os.path.basename(f).lower()]
idvd_files = [f for f in all_csv_files if 'idvd' in os.path.basename(f).lower()]

vb0_out_dir = ensure_dir(os.path.join(base_out_dir, "Vs0"))
plot_transfer_vb0(idvg_files, vb0_out_dir, label_for_title=f"{transistor_key} @ 160K")
plot_output_grouped_by_terminal(idvd_files, vb0_out_dir, label_for_title=f"{transistor_key} @ 160K")

print("Done generating plots.")
