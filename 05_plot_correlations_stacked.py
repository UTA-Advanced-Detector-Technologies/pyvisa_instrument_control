import glob
import os
import re
import json
import pandas as pd
import matplotlib.pyplot as plt
from functools import lru_cache
import matplotlib.gridspec as gridspec


# =============================================================================
# Helper Functions and Constants
# =============================================================================

def load_mux_instructions(json_file="mux_instructions.json"):
    """Load the MUX instructions from a JSON file."""
    with open(json_file, "r") as f:
        mux_data = json.load(f)
    return mux_data


# Precompiled regular expressions for parsing file names.
vd_pattern = re.compile(r'Vd([0-9e\-\+p]+)')
vg_pattern = re.compile(r'Vg([0-9e\-\+p]+)')
vb_pattern = re.compile(r'Vb([0-9e\-\+p]+)')
vsub_pattern = re.compile(r'Vsub([0-9e\-\+p]+)')


# --- New bias-zero functions for PFETs and NFETs ---
def is_vb_zero_pfet(filename):
    """
    For PFETs: Check if the filename indicates that the bulk-source voltage (Vb) is zero.
    """
    m = vb_pattern.search(filename)
    if not m:
        return False
    try:
        vb_val = float(m.group(1).replace('p', '.'))
    except ValueError:
        return False
    return abs(vb_val) < 1e-14


def is_vsub_zero_nfet(filename):
    """
    For NFETs: Check if the filename indicates that the substrate voltage (Vsub) is zero.
    """
    m = vsub_pattern.search(filename)
    if not m:
        return False
    try:
        vsub_val = float(m.group(1).replace('p', '.'))
    except ValueError:
        return False
    return abs(vsub_val) < 1e-14


def extract_vsub(filename):
    """
    Extract the substrate voltage (Vsub) from the filename if present.
    Return the float value or None.
    """
    match = vsub_pattern.search(filename)
    if match:
        try:
            return float(match.group(1).replace('p', '.'))
        except ValueError:
            return None
    return None


def get_vsub_info(files):
    """
    Return a summary string of unique Vsub values found in the list of files.
    Examples: "Vsource_sub=2.0" or "Vsub in [1.0, 2.0]". Returns None if no Vsub value is found.
    """
    vsub_values = {v for f in files if (v := extract_vsub(f)) is not None}
    if vsub_values:
        sorted_vals = sorted(vsub_values)
        if len(sorted_vals) == 1:
            return f"Vsource_sub={sorted_vals[0]}"
        else:
            return f"Vsub in {sorted_vals}"
    return None


def get_vb_info(files):
    """
    Return a summary string of unique Vb values found in the list of files.
    Examples: "Vbulk_source=1.5" or "Vbulk_source in [1.0, 1.5]". Returns None if no Vb value is found.
    """
    vb_values = set()
    for f in files:
        m = vb_pattern.search(f)
        if m:
            try:
                vb_val = float(m.group(1).replace('p', '.'))
                vb_values.add(vb_val)
            except ValueError:
                continue
    if vb_values:
        sorted_vals = sorted(vb_values)
        if len(sorted_vals) == 1:
            return f"Vbulk_source={sorted_vals[0]}"
        else:
            return f"Vbulk_source in {sorted_vals}"
    return None


@lru_cache(maxsize=None)
def read_data(csv_path):
    """
    Read the CSV file into a pandas DataFrame and assign column names.
    The CSV files now contain 15 columns:
      Vd_src, Vg_src, Vb_src, Vsub_src,
      Id, Ib, Isub, Ig,
      Vd_meas, Vb_meas, Vsub_meas, Vg_meas,
      TempA, TempB, Elapsed_time
    Caching is used to avoid re‐reading the same file multiple times.
    """
    df = pd.read_csv(csv_path, header=None)
    df.columns = [
        'Vd_src', 'Vg_src', 'Vb_src', 'Vsub_src',
        'Id', 'Ib', 'Isub', 'Ig',
        'Vd_meas', 'Vb_meas', 'Vsub_meas', 'Vg_meas',
        'TempA', 'TempB', 'Elapsed_time'
    ]
    numeric_columns = [
        'Vd_src', 'Vg_src', 'Vb_src', 'Vsub_src',
        'Id', 'Ib', 'Isub', 'Ig',
        'Vd_meas', 'Vb_meas', 'Vsub_meas', 'Vg_meas',
        'TempA', 'TempB', 'Elapsed_time'
    ]
    df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors='coerce')
    return df


# =============================================================================
# Modified Plot Function
# =============================================================================

def plot_scatter(files, x_key, y_keys, x_label, y_labels, title, save_path,
                 label_extractor, transforms=None, y_scales=None, temp_plot=False,
                 temp_keys=['TempA', 'TempB'], temp_labels=['TempA (K)', 'TempB (K)']):
    """
    Create a multi-panel scatter plot with two groups of subplots:
      - Upper panels (voltage/current): use x_key (e.g. Vg_src or Vd_src) as the x-axis.
      - Lower panels (temperature): use 'Elapsed_time' as the x-axis.

    When temp_plot is False, all subplots share the same x-axis.
    """
    if not temp_plot:
        # Old behavior: all subplots share the same x-axis.
        n_plots = len(y_keys)
        total_plots = n_plots
        fig, axs = plt.subplots(total_plots, 1, sharex=True, figsize=(8, 12))
        if total_plots == 1:
            axs = [axs]
        if transforms is None:
            transforms = [lambda x: x] * n_plots
        if y_scales is None:
            y_scales = [None] * n_plots

        for f in files:
            df = read_data(f)
            label = label_extractor(f)
            for i, y_key in enumerate(y_keys):
                axs[i].scatter(df[x_key], transforms[i](df[y_key]), s=10, label=label)

        for ax, ylabel, scale in zip(axs, y_labels, y_scales):
            ax.set_ylabel(ylabel)
            ax.grid(True)
            if scale:
                ax.set_yscale(scale)
        axs[-1].set_xlabel(x_label)
        axs[0].legend()
        fig.suptitle(title)
        plt.tight_layout()
        plt.savefig(save_path)
        plt.close(fig)

    else:
        # New behavior: split the figure into two groups.
        # Plot all y_keys in the main (voltage/current) panels.
        n_main = len(y_keys)  # <-- Changed from fixed 3 to len(y_keys)
        n_temp = len(temp_keys)  # number of temperature panels
        main_y_keys = y_keys[:n_main]
        main_y_labels = y_labels[:n_main]
        if transforms is not None:
            main_transforms = transforms[:n_main]
        else:
            main_transforms = [lambda x: x] * n_main
        if y_scales is not None:
            main_y_scales = y_scales[:n_main]
        else:
            main_y_scales = [None] * n_main

        # Create the figure with two groups of subplots using GridSpec.
        fig = plt.figure(figsize=(8, 12))
        gs = gridspec.GridSpec(n_main + n_temp, 1,
                               height_ratios=[3] * n_main + [1] * n_temp,
                               hspace=0.4)
        # Upper group: voltage/current panels.
        axs_main = [fig.add_subplot(gs[i, 0]) for i in range(n_main)]
        # Lower group: temperature panels.
        axs_temp = [fig.add_subplot(gs[n_main + i, 0]) for i in range(n_temp)]
        # Let the main axes share the same x-axis.
        for i in range(1, n_main):
            axs_main[i].sharex(axs_main[0])
        # Let the temperature axes share among themselves.
        for i in range(1, n_temp):
            axs_temp[i].sharex(axs_temp[0])

        # Plot the upper (voltage/current) panels using x_key.
        for f in files:
            #for individual point measurements (such as in self heating tests), make the points bigger
            if "paused" in f:
                s = 40
            else:
                s = 10  # default
            # if "Test2" in f:
            #     extra_label = f" keeping Vgs=-25V, Vs-sub=25V"
            # elif "Test1" in f:
            #     extra_label = f" Lower all biases"
            # else:
            #     extra_label = ""
            df = read_data(f)
            label = label_extractor(f, extra_label)
            for i, key in enumerate(main_y_keys):
                axs_main[i].scatter(df[x_key], main_transforms[i](df[key]), s=s, label=label)
        for ax, ylabel, scale in zip(axs_main, main_y_labels, main_y_scales):
            ax.set_ylabel(ylabel)
            ax.grid(True)
            if scale:
                ax.set_yscale(scale)
        axs_main[-1].set_xlabel(x_label)
        axs_main[0].legend()

        # Plot the lower (temperature) panels using 'Elapsed_time' as x-axis.
        for j, (temp_key, temp_label) in enumerate(zip(temp_keys, temp_labels)):
            for f in files:
                df = read_data(f)
                label = label_extractor(f)
                axs_temp[j].scatter(df['Elapsed_time'], df[temp_key], s=10, label=label)
            axs_temp[j].set_ylabel(temp_label)
            axs_temp[j].grid(True)
        axs_temp[-1].set_xlabel("Elapsed Time (s)")

        fig.suptitle(title)
        plt.tight_layout()
        plt.savefig(save_path)
        plt.close(fig)



# =============================================================================
# Plotting Functions
# =============================================================================

def plot_transfer_vb0(files, out_dir, vb_label="Vbulk_source=0", extra_title_info_func=None):
    """
    Plot the transfer (ID vs. Vg) and measured-voltage characteristics for files
    with bias equal to zero (Vb for PFETs or Vsub for NFETs). Temperature data is also plotted.
    """
    if not files:
        return

    # if extra_title_info_func is not None:
    #     extra_info = extra_title_info_func(files)
    # else:
    #     extra_info = get_vsub_info(files)
    # extra_info_str = f", {extra_info}" if extra_info else ""

    if extra_title_info_func is not None:
        extra_info = f", {extra_title_info_func}" if extra_title_info_func else ""

    vsub_info = get_vsub_info(files)
    title_suffix = f", {vsub_info}" if vsub_info else ""

    # Define a label extractor based on Vd from the filename.
    def label_extractor(f, extra_label=""):
        m = vd_pattern.search(f)
        return f"Vds={m.group(1).replace('p', '.')}{extra_label}" if m else "unknown"

    # Transfer characteristic (Linear)
    save_path = os.path.join(out_dir, 'transfer_characteristic_stacked_lin.png')
    plot_scatter(
        files, x_key='Vg_src', y_keys=['Id', 'Ib', 'Isub', 'Ig'],
        x_label="V_gate_source (V)",
        y_labels=["Drain_Source I (A)", "Bulk_Source I (A)",
                  "Source_Substrate I (A)", "Gate_Source I (A)"],
        title=f"Transfer (Linear) - {vb_label}{title_suffix}{extra_info}",
        save_path=save_path,
        label_extractor=label_extractor,
        temp_plot=True
    )

    # Transfer characteristic (Log scale for Drain current)
    save_path = os.path.join(out_dir, 'transfer_characteristic_stacked_log.png')
    plot_scatter(
        files, x_key='Vg_src', y_keys=['Id', 'Ib', 'Isub', 'Ig'],
        x_label="V_gate_source (V)",
        y_labels=["Drain_Source I (log A)", "Bulk_Source I (A)",
                  "Source_Substrate I (A)", "Gate_Source I (A)"],
        title=f"Transfer (Drain Log) - {vb_label}{title_suffix}{extra_info}",
        save_path=save_path,
        label_extractor=label_extractor,
        transforms=[abs, lambda x: x, lambda x: x, lambda x: x],
        y_scales=['log', None, None, None],
        temp_plot=True
    )

    # Measured Voltages (Transfer)
    save_path = os.path.join(out_dir, 'transfer_characteristic_voltages.png')
    plot_scatter(
        files, x_key='Vg_src', y_keys=['Vd_meas', 'Vb_meas', 'Vsub_meas', 'Vg_meas'],
        x_label="V_gate_source (V)",
        y_labels=["Drain_Source Voltage (V)", "Bulk_Source Voltage (V)",
                  "Source_Substrate Voltage (V)", "Gate_Source Voltage (V)"],
        title=f"Measured Voltages (Transfer) - {vb_label}{title_suffix}{extra_info}",
        save_path=save_path,
        label_extractor=label_extractor,
        temp_plot=True
    )


def plot_transfer_vds_grouped_by_bias(files, out_dir, group_by='Vsub', extra_title_info_func=None):
    """
    For transfer curves with nonzero bias (Vb for PFETs or Vsub for NFETs),
    group files by the drain bias (Vd) and then by the bias parameter.
    Temperature panels are added below the main subplots.
    """
    if not files:
        return

    # Group files by Vd.
    vds_groups = {}
    for f in files:
        m = vd_pattern.search(f)
        if not m:
            continue
        try:
            vd_val = float(m.group(1).replace('p', '.'))
        except ValueError:
            vd_val = m.group(1)
        vds_groups.setdefault(vd_val, []).append(f)

    # For each Vd group, group by the bias parameter and create plots.
    for vd_val, vds_files in sorted(vds_groups.items()):
        # Build a dictionary mapping each file to its bias label.
        file_labels = {}
        for f in vds_files:
            m = (vsub_pattern.search(f) if group_by == 'Vsub' else vb_pattern.search(f))
            if m:
                try:
                    bias_val = float(m.group(1).replace('p', '.'))
                except ValueError:
                    bias_val = m.group(1)
            else:
                bias_val = "unknown"
            file_labels[f] = f"{group_by}={bias_val}"

        label_extractor = lambda f: file_labels[f]
        extra_info = extra_title_info_func(vds_files) if extra_title_info_func else ""
        extra_title = f", {extra_info}" if extra_info else ""

        # Transfer characteristic (Linear)
        save_path = os.path.join(out_dir, f'transfer_lin_Vds{vd_val}_250K.png')
        plot_scatter(
            vds_files, x_key='Vg_src', y_keys=['Id', 'Ib', 'Isub', 'Ig'],
            x_label="V_gate_source (V)",
            y_labels=["Drain_Source I (A)", "Bulk_Source I (A)",
                      "Source_Substrate I (A)", "Gate_Source I (A)"],
            title=f"Transfer (Linear) @20K for Vds={vd_val} {extra_title}",
            save_path=save_path,
            label_extractor=label_extractor,
            temp_plot=True
        )

        # Transfer characteristic (Log scale)
        save_path = os.path.join(out_dir, f'transfer_log_Vds{vd_val}_250K.png')
        plot_scatter(
            vds_files, x_key='Vg_src', y_keys=['Id', 'Ib', 'Isub', 'Ig'],
            x_label="V_gate_source (V)",
            y_labels=["Drain_Source I (log A)", "Bulk_Source I (A)",
                      "Source_Substrate I (A)", "Gate_Source I (A)"],
            title=f"Transfer (Log) @20K for Vds={vd_val} {extra_title}",
            save_path=save_path,
            label_extractor=label_extractor,
            transforms=[abs, lambda x: x, lambda x: x, lambda x: x],
            y_scales=['log', None, None, None],
            temp_plot=True
        )

        # Measured Voltages (Transfer)
        save_path = os.path.join(out_dir, f'transfer_voltages_Vds{vd_val}_250K.png')
        plot_scatter(
            vds_files, x_key='Vg_src', y_keys=['Vd_meas', 'Vb_meas', 'Vsub_meas', 'Vg_meas'],
            x_label="V_gate_source (V)",
            y_labels=["Drain_Source Voltage (V)", "Bulk_Source Voltage (V)",
                      "Source_Substrate Voltage (V)", "Gate_Source Voltage (V)"],
            title=f"Measured Voltages @20K for Vds={vd_val} {extra_title}",
            save_path=save_path,
            label_extractor=label_extractor,
            temp_plot=True
        )


def plot_output(files, out_dir, vb_label="Vbulk_source=?", extra_title_info_func=None):
    """
    Plot output curves (e.g. ID vs. Vd_src) and corresponding measured voltages.
    Temperature panels are added below the main plots.
    """
    if not files:
        return

    vsub_info = get_vsub_info(files)
    title_suffix = f", {vsub_info}" if vsub_info else ""

    if extra_title_info_func is not None:
        extra_info = f", {extra_title_info_func}" if extra_title_info_func else ""

    # Define a label extractor based on Vg from the filename
    def label_extractor(f, extra_label=""):
        m = vd_pattern.search(f)
        #return f"Vgs={m.group(1).replace('p', '.')}{extra_label}" if m else "unknown"
        return f"Vgs=-25V{extra_label}"

    # Output characteristic (Linear)
    save_path = os.path.join(out_dir, 'output_characteristic_stacked_lin.png')
    plot_scatter(
        files, x_key='Vd_src', y_keys=['Id', 'Ib', 'Isub', 'Ig'],
        x_label="V_drain_source (V)",
        y_labels=["Drain_Source I (A)", "Bulk_Source I (A)",
                  "Source_Substrate I (A)", "Gate_Source I (A)"],
        title=f"Output (Linear) - {vb_label}{title_suffix}{extra_info}",
        save_path=save_path,
        label_extractor=label_extractor,
        temp_plot=True
    )

    # Output characteristic (Log scale)
    save_path = os.path.join(out_dir, 'output_characteristic_stacked_log.png')
    plot_scatter(
        files, x_key='Vd_src', y_keys=['Id', 'Ib', 'Isub', 'Ig'],
        x_label="V_drain_source (V)",
        y_labels=["Drain_Source I (log A)", "Bulk_Source I (A)",
                  "Source_Substrate I (A)", "Gate_Source I (A)"],
        title=f"Output (Drain Log) - {vb_label}{title_suffix}{extra_info}",
        save_path=save_path,
        label_extractor=label_extractor,
        transforms=[abs, lambda x: x, lambda x: x, lambda x: x],
        y_scales=['log', None, None, None],
        temp_plot=True
    )

    # Measured Voltages (Output)
    save_path = os.path.join(out_dir, 'output_characteristic_voltages.png')
    plot_scatter(
        files, x_key='Vd_src', y_keys=['Vd_meas', 'Vb_meas', 'Vsub_meas', 'Vg_meas'],
        x_label="V_drain_source (V)",
        y_labels=["Drain_Source Voltage (V)", "Bulk_Source Voltage (V)",
                  "Source_Substrate Voltage (V)", "Gate_Source Voltage (V)"],
        title=f"Output Measured Voltages - {vb_label}{title_suffix}{extra_info}",
        save_path=save_path,
        label_extractor=label_extractor,
        temp_plot=True
    )




# =============================================================================
# Main Routine
# =============================================================================
flavor = "250K0_high_Vds_tests/HV"
data_folder = 'Data'

# Create main output directories.
base_plot_dir = os.path.join('plot_correlations')
os.makedirs(base_plot_dir, exist_ok=True)
flavor_dir = os.path.join(base_plot_dir, flavor)
os.makedirs(flavor_dir, exist_ok=True)

mux_json_file = "mux_instructions_by_transistor_4wire_drain.json"
mux_data = load_mux_instructions(mux_json_file)

for transistor_key, mux_dict in mux_data.items():
    # Uncomment the following lines to restrict processing to certain transistors.
    if 'pmos25_FET1' not in transistor_key:
         continue

    base_out_dir = os.path.join(flavor_dir, transistor_key)
    os.makedirs(base_out_dir, exist_ok=True)

    # Collect CSV files for this transistor.
    csv_pattern = os.path.join(data_folder, flavor, transistor_key, "*.csv")
    all_csv_files = glob.glob(csv_pattern)
    # Split files based on measurement type.
    idvg_files = [f for f in all_csv_files if 'idvg' in os.path.basename(f).lower()]
    idvd_files = [f for f in all_csv_files if 'idvd' in os.path.basename(f).lower()]

    # --- Choose bias-zero test based on transistor type ---
    lower_key = transistor_key.lower()
    if any(x in lower_key for x in ['nmos', 'nfet']):
        # For NFETs use Vsub as the metric.
        bias_zero_func = is_vsub_zero_nfet
        bias_label_zero = "Vsource_sub=0"
        bias_label_nonzero = "Vsub≠0"
        group_by = 'Vsub'
    elif any(x in lower_key for x in ['pmos', 'pfet']):
        # For PFETs use Vb as the metric.
        bias_zero_func = is_vb_zero_pfet
        bias_label_zero = "Vbulk_source=0"
        bias_label_nonzero = "Vb≠0"
        group_by = 'Vb'
    else:
        # Default fallback (you may adjust this if needed)
        bias_zero_func = is_vsub_zero_nfet
        bias_label_zero = "Vsource_sub=0"
        bias_label_nonzero = "Vsub≠0"
        group_by = 'Vsub'

    # Split files based on whether the chosen bias parameter is zero.
    idvg_bias0 = [f for f in idvg_files if bias_zero_func(f)]
    idvg_biasNon0 = [f for f in idvg_files if not bias_zero_func(f)]
    idvd_bias0 = [f for f in idvd_files if bias_zero_func(f)]
    idvd_biasNon0 = [f for f in idvd_files if not bias_zero_func(f)]

    # Create output subdirectories.
    bias0_out_dir = os.path.join(base_out_dir, "Vb0")
    biasNon0_out_dir = os.path.join(base_out_dir, "VbNon0")
    os.makedirs(bias0_out_dir, exist_ok=True)
    os.makedirs(biasNon0_out_dir, exist_ok=True)

    # -- For zero bias (Vb==0 for PFETs or Vsource_sub==0 for NFETs) --
    #plot_transfer_vb0(idvg_bias0, bias0_out_dir, vb_label=bias_label_zero, extra_title_info_func="@ 250K")
    plot_output(idvd_bias0, bias0_out_dir, vb_label=bias_label_zero, extra_title_info_func="@ 250K")


    # -- For nonzero bias --
    # For nonzero bias plots we want to include the complementary voltage info:
    # For NFETs (bias based on Vsub) include Vbulk_source,
    # For PFETs (bias based on Vb) include Vsource_sub.
    # if any(x in lower_key for x in ['nmos', 'nfet']):
    #     extra_info_func = get_vb_info
    # else:
    #     extra_info_func = get_vsub_info

    #plot_transfer_vds_grouped_by_bias(idvg_biasNon0, biasNon0_out_dir, group_by=group_by,
    #                                  extra_title_info_func=extra_info_func)
    #plot_output(idvd_biasNon0, biasNon0_out_dir, vb_label=bias_label_nonzero, extra_title_info_func=extra_info_func)

print("Done generating plots")
