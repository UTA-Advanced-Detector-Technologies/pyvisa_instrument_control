import glob
import os
import re
import json
import pandas as pd
import matplotlib.pyplot as plt


# ---------------------------
# Helper Functions
# ---------------------------

def load_mux_instructions(json_file="mux_instructions.json"):
    with open(json_file, "r") as f:
        mux_data = json.load(f)
    return mux_data


def ensure_dir(path):
    """Create the directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)
    return path


def read_data(csv_path):
    """
    Read CSV into a DataFrame with pre-defined column names
    and convert them to numeric types.
    """
    cols = [
        'Vd_src', 'Vg_src', 'Vb_src', 'Vsub_src',
        'Id', 'Ib', 'Isub', 'Ig',
        'Vd_meas', 'Vb_meas', 'Vsub_meas', 'Vg_meas',
        'TempA', 'TempB', 'Elapsed_time'
    ]
    df = pd.read_csv(csv_path, header=None, names=cols)
    df = df.apply(pd.to_numeric, errors='coerce')
    return df


def parse_bias(match_obj):
    """
    Given a regex match object, return a tuple of:
      - float value for numeric comparisons/plotting,
      - a string label (with '.' as decimal separator) for plot titles,
      - a filename-friendly string (with '.' replaced by 'p').
    """
    if not match_obj:
        return None, "?", "?"
    raw_str = match_obj.group(1)  # e.g., "1p2" or "3.5"
    # Replace 'p' with '.' so we can parse it
    decimal_str = raw_str.replace('p', '.')
    try:
        val_float = float(decimal_str)
    except ValueError:
        return None, raw_str, raw_str
    plot_label = str(val_float)
    file_label = plot_label.replace('.', 'p')
    return val_float, plot_label, file_label


def extract_bias_values(fpath, bias_patterns):
    """
    Given a filename and a dictionary of regex patterns,
    return a dictionary mapping a bias key (e.g., 'Vd') to a tuple:
       (float_value, label_string, file_string).
    """
    bias_values = {}
    for key, pattern in bias_patterns.items():
        bias_values[key] = parse_bias(pattern.search(fpath))
    return bias_values


def plot_scatter(x, y, xlabel, ylabel, title, save_path, yscale="linear", s=10):
    """Create a scatter plot and save it."""
    fig, ax = plt.subplots()
    ax.scatter(x, y, s=s)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if yscale:
        ax.set_yscale(yscale)
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(save_path)
    plt.close(fig)


def bias_str(bias_info, keys):
    """
    Given a bias_info dictionary and a list of bias keys, return a filename part,
    e.g., "Vd1p2_Vb0_Vsub0p5"
    """
    return "_".join(f"{key}{bias_info.get(f'{key}_file', '?')}" for key in keys)


def process_plot_task(df, task, bias_info, output_dir):
    """
    Process one plot task:
      - df: the data frame with the data.
      - task: a dictionary describing the plot.
      - bias_info: dictionary of bias values for formatting titles and filenames.
      - output_dir: where to save the generated plot.
    """
    x_data = df[task['x_col']]
    # Use absolute values if specified (for log-scale plots)
    y_data = df[task['y_col']].abs() if task.get('abs', False) else df[task['y_col']]

    title = task['title'].format(**bias_info)
    fname = f"{task['prefix']}__{bias_str(bias_info, task['bias_keys'])}.png"
    save_path = os.path.join(output_dir, fname)

    plot_scatter(
        x=x_data,
        y=y_data,
        xlabel=task['xlabel'],
        ylabel=task['ylabel'],
        title=title,
        save_path=save_path,
        yscale=task.get('yscale', 'linear'),
        s=10
    )


# ---------------------------
# Plot Task Definitions
# ---------------------------
# For ID-VG (transfer) plots, the filename carries Vd, Vb, and Vsub biases.
transfer_lin_tasks = [
    {
        "prefix": "transfer_drain_lin",
        "x_col": "Vg_src", "y_col": "Id",
        "xlabel": "V_gate_source (V)", "ylabel": "Drain_Source I (A)",
        "title": "Transfer (Drain, lin)\nVd={Vd_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vd", "Vb", "Vsub"],
    },
    {
        "prefix": "transfer_body_lin",
        "x_col": "Vg_src", "y_col": "Ib",
        "xlabel": "V_gate_source (V)", "ylabel": "Bulk_Source I (A)",
        "title": "Transfer (Body, lin)\nVd={Vd_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vd", "Vb", "Vsub"],
    },
    {
        "prefix": "transfer_gate_lin",
        "x_col": "Vg_src", "y_col": "Ig",
        "xlabel": "V_gate_source (V)", "ylabel": "Gate_Source I (A)",
        "title": "Transfer (Gate, lin)\nVd={Vd_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vd", "Vb", "Vsub"],
    },
]

transfer_log_tasks = [
    {
        "prefix": "transfer_drain_log",
        "x_col": "Vg_src", "y_col": "Id",
        "xlabel": "V_gate_source (V)", "ylabel": "Drain_Source I (A) [log]",
        "title": "Transfer (Drain, log)\nVd={Vd_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vd", "Vb", "Vsub"],
        "yscale": "log", "abs": True,
    },
    {
        "prefix": "transfer_body_log",
        "x_col": "Vg_src", "y_col": "Ib",
        "xlabel": "V_gate_source (V)", "ylabel": "Bulk_Source I (A) [log]",
        "title": "Transfer (Body, log)\nVd={Vd_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vd", "Vb", "Vsub"],
        "yscale": "log", "abs": True,
    },
    {
        "prefix": "transfer_gate_log",
        "x_col": "Vg_src", "y_col": "Ig",
        "xlabel": "V_gate_source (V)", "ylabel": "Gate_Source I (A) [log]",
        "title": "Transfer (Gate, log)\nVd={Vd_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vd", "Vb", "Vsub"],
        "yscale": "log", "abs": True,
    },
]

transfer_voltage_tasks = [
    {
        "prefix": "transfer_drain_voltage",
        "x_col": "Vg_src", "y_col": "Vd_meas",
        "xlabel": "V_gate_source (V)", "ylabel": "Drain-Source Voltage (V)",
        "title": "Transfer: Vd_meas vs. Vg_src\nVd={Vd_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vd", "Vb", "Vsub"],
    },
    {
        "prefix": "transfer_gate_voltage",
        "x_col": "Vg_src", "y_col": "Vg_meas",
        "xlabel": "V_gate_source (V)", "ylabel": "Gate-Source Voltage (V)",
        "title": "Transfer: Vg_meas vs. Vg_src\nVd={Vd_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vd", "Vb", "Vsub"],
    },
]

# For ID-VD (output) plots, the filename carries Vg, Vb, and Vsub biases.
output_lin_tasks = [
    {
        "prefix": "output_drain_lin",
        "x_col": "Vd_src", "y_col": "Id",
        "xlabel": "V_drain_source (V)", "ylabel": "Drain_Source I (A)",
        "title": "Output (Drain, lin)\nVgs={Vg_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vg", "Vb", "Vsub"],
    },
    {
        "prefix": "output_body_lin",
        "x_col": "Vd_src", "y_col": "Ib",
        "xlabel": "V_drain_source (V)", "ylabel": "Bulk_Source I (A)",
        "title": "Output (Body, lin)\nVgs={Vg_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vg", "Vb", "Vsub"],
    },
    {
        "prefix": "output_gate_lin",
        "x_col": "Vd_src", "y_col": "Ig",
        "xlabel": "V_drain_source (V)", "ylabel": "Gate_Source I (A)",
        "title": "Output (Gate, lin)\nVgs={Vg_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vg", "Vb", "Vsub"],
    },
]

output_log_tasks = [
    {
        "prefix": "output_drain_log",
        "x_col": "Vd_src", "y_col": "Id",
        "xlabel": "V_drain_source (V)", "ylabel": "Drain_Source I (A) [log]",
        "title": "Output (Drain, log)\nVgs={Vg_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vg", "Vb", "Vsub"],
        "yscale": "log", "abs": True,
    },
    {
        "prefix": "output_body_log",
        "x_col": "Vd_src", "y_col": "Ib",
        "xlabel": "V_drain_source (V)", "ylabel": "Bulk_Source I (A) [log]",
        "title": "Output (Body, log)\nVgs={Vg_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vg", "Vb", "Vsub"],
        "yscale": "log", "abs": True,
    },
    {
        "prefix": "output_gate_log",
        "x_col": "Vd_src", "y_col": "Ig",
        "xlabel": "V_drain_source (V)", "ylabel": "Gate_Source I (A) [log]",
        "title": "Output (Gate, log)\nVgs={Vg_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vg", "Vb", "Vsub"],
        "yscale": "log", "abs": True,
    },
]

output_voltage_tasks = [
    {
        "prefix": "output_drain_voltage",
        "x_col": "Vd_src", "y_col": "Vd_meas",
        "xlabel": "V_drain_source (V)", "ylabel": "Drain-Source Voltage (V)",
        "title": "Output: Vd_meas vs. Vd_src\nVgs={Vg_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vg", "Vb", "Vsub"],
    },
    {
        "prefix": "output_gate_voltage",
        "x_col": "Vd_src", "y_col": "Vg_meas",
        "xlabel": "V_drain_source (V)", "ylabel": "Gate-Source Voltage (V)",
        "title": "Output: Vg_meas vs. Vd_src\nVgs={Vg_label} V, Vbulk_source={Vb_label} V, Vsource_sub={Vsub_label} V",
        "bias_keys": ["Vg", "Vb", "Vsub"],
    },
]

# ---------------------------
# Main Processing Script
# ---------------------------
# Parameters and directories
flavor = "HV"
data_folder = 'Data'
mux_json_file = "mux_instructions_by_transistor_4wire_drain.json"
mux_data = load_mux_instructions(mux_json_file)

# Define regex patterns for bias extraction
vd_pattern = re.compile(r'Vd([0-9e\-\+p]+)')
vg_pattern = re.compile(r'Vg([0-9e\-\+p]+)')
vb_pattern = re.compile(r'Vb([0-9e\-\+p]+)')
vsub_pattern = re.compile(r'Vsub([0-9e\-\+p]+)')

# Define output root directory
output_root = os.path.join('plot_by_bias')
ensure_dir(output_root)
ensure_dir(os.path.join(output_root, flavor))

for transistor_key, mux_dict in mux_data.items():
    # Uncomment the following lines to process only a specific transistor.
    # if 'pmos25_FET1' not in transistor_key:
    #     continue

    base_out_dir = ensure_dir(os.path.join(output_root, flavor, transistor_key))

    # Collect all CSV files for this transistor
    all_csv_files = glob.glob(os.path.join(data_folder, flavor, transistor_key, "*.csv"))
    # Separate files based on their name content
    idvg_files = [f for f in all_csv_files if 'idvg' in os.path.basename(f).lower()]
    idvd_files = [f for f in all_csv_files if 'idvd' in os.path.basename(f).lower()]

    # Process ID-VG (transfer) files
    if idvg_files:
        transfer_lin_dir = ensure_dir(os.path.join(base_out_dir, "transfer_lin"))
        transfer_log_dir = ensure_dir(os.path.join(base_out_dir, "transfer_log"))
        transfer_volt_dir = ensure_dir(os.path.join(base_out_dir, "transfer_voltages"))

        for fpath in idvg_files:
            # Extract biases using patterns for Vd, Vb, Vsub
            biases = extract_bias_values(fpath, {'Vd': vd_pattern, 'Vb': vb_pattern, 'Vsub': vsub_pattern})
            # Build a bias_info dictionary for string formatting
            bias_info = {f"{key}_label": label for key, (_, label, _) in biases.items()}
            for key, (_, _, file_str) in biases.items():
                bias_info[f"{key}_file"] = file_str

            df = read_data(fpath)

            for task in transfer_lin_tasks:
                process_plot_task(df, task, bias_info, transfer_lin_dir)
            for task in transfer_log_tasks:
                process_plot_task(df, task, bias_info, transfer_log_dir)
            for task in transfer_voltage_tasks:
                process_plot_task(df, task, bias_info, transfer_volt_dir)

    # Process ID-VD (output) files
    if idvd_files:
        output_lin_dir = ensure_dir(os.path.join(base_out_dir, "output_lin"))
        output_log_dir = ensure_dir(os.path.join(base_out_dir, "output_log"))
        output_volt_dir = ensure_dir(os.path.join(base_out_dir, "output_voltages"))

        for fpath in idvd_files:
            # Extract biases using patterns for Vg, Vb, Vsub
            biases = extract_bias_values(fpath, {'Vg': vg_pattern, 'Vb': vb_pattern, 'Vsub': vsub_pattern})
            bias_info = {f"{key}_label": label for key, (_, label, _) in biases.items()}
            for key, (_, _, file_str) in biases.items():
                bias_info[f"{key}_file"] = file_str

            df = read_data(fpath)

            for task in output_lin_tasks:
                process_plot_task(df, task, bias_info, output_lin_dir)
            for task in output_log_tasks:
                process_plot_task(df, task, bias_info, output_log_dir)
            for task in output_voltage_tasks:
                process_plot_task(df, task, bias_info, output_volt_dir)

print("Done generating separate plots in subfolders.")
