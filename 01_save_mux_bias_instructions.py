import os
import re
import json
import pprint
import numpy as np
import pandas as pd


def extract_bias_data_from_excel(file_path, sheet_name="Sheet1"):
    """
    Extract bias data from an Excel file.

    The function looks for two sections: "NMOS" and "PMOS". Within each section,
    it identifies primary sweeps (e.g., 'Primary sweep: Vgs Set 1' or 'Primary sweep: Vds')
    and captures parameter values in a structured dictionary.

    Parameters:
    -----------
    file_path : str
        Path to the Excel file.
    sheet_name : str, optional
        Name of the sheet to read from. Defaults to "Sheet1".

    Returns:
    --------
    dict
        A nested dictionary containing the extracted bias data, organized as:
        {
            "NMOS": {
                "Primary sweep: Vgs Set 1": {
                    "Vs": [...],
                    "Vg": [...],
                    ...
                },
                ...
            },
            "PMOS": {
                ...
            }
        }
    """
    # Read the Excel file
    df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')

    # Remove empty rows and columns
    df = df.dropna(how='all').reset_index(drop=True)

    # Define sections to look for
    sections = ["NMOS", "PMOS"]
    data = {section: {} for section in sections}

    current_section = None
    current_sweep = None

    for idx, row in df.iterrows():
        # Check for section headers in the first column
        for section in sections:
            if section in str(row[0]):
                current_section = section
                current_sweep = None
                break

        # Look for rows that define a primary sweep
        if "Primary sweep" in str(row[0]):
            current_sweep = row[0].strip()
            data[current_section][current_sweep] = {}

        # If we are in a known sweep, extract parameter values
        if current_sweep and pd.notna(row[1]):
            parameter = str(row[0]).strip()
            values = [val for val in row[1:] if pd.notna(val)]
            data[current_section][current_sweep][parameter] = values

    return data


def process_bias_data(data):
    """
    Process the 'data' dictionary to convert string values into lists of floats.

    This function handles:
      - Zero values (turns "0" into [0.0])
      - Ranges (e.g., "0 to 1 in steps of 0.1")
      - Discrete values separated by '/' (e.g., "0.5 / 1.0")

    Parameters:
    -----------
    data : dict
        A nested dictionary of extracted bias data.

    Returns:
    --------
    dict
        The processed dictionary with the same structure but all parameter
        values converted to numeric lists.
    """
    processed_data = {}

    for section, sweeps in data.items():
        processed_data[section] = {}
        for sweep_type, parameters in sweeps.items():
            processed_data[section][sweep_type] = {}
            for param, values in parameters.items():
                processed_values = []

                for value in values:

                    # 1) Check for direct 0 or "0"
                    if value == 0 or value == "0":
                        processed_values.append([0.0])

                    # 2) If it's a string, attempt to parse range or discrete sets
                    elif isinstance(value, str):
                        # Remove any parentheses and "V"
                        cleaned_value = re.sub(r"\(.*?\)", "", value)
                        cleaned_value = cleaned_value.replace("V", "").strip()

                        # 2a) Check if it matches the "to ... steps of ..." pattern
                        if "to" in cleaned_value and "steps" in cleaned_value:

                            try:
                                start_str = cleaned_value.split("to")[0].strip()
                                end_and_step = cleaned_value.split("to")[1]
                                end_str = end_and_step.split("in")[0].strip()
                                step_str = end_and_step.split("steps of")[1].strip()

                                start = float(start_str)
                                end = float(end_str)
                                step = float(step_str)

                                # Use np.arange to generate the numeric sequence
                                if start<end:
                                    range_vals = np.arange(start, end + step, step)
                                if end < start:
                                    range_vals = np.arange(end, start + step, step)
                                    range_vals = np.flip(range_vals)
                                processed_values.append([round(val, 4) for val in range_vals])

                            except Exception as e:
                                print(f"Error processing range: {value}. Error: {e}")

                        # 2b) Handle discrete values separated by '/'
                        elif "/" in cleaned_value:

                            try:
                                split_values = cleaned_value.split("/")
                                numeric_values = []
                                for v in split_values:
                                    v = v.strip()
                                    if v:
                                        numeric_values.append(float(v))
                                processed_values.append(numeric_values)
                            except Exception as e:
                                print(f"Error processing discrete values: {value}. Error: {e}")

                        else:

                            try:
                                float_val = float(value)
                                processed_values.append(float_val)
                            except Exception as e:
                                # If the string doesn't match known patterns, print a warning.
                                print(f"Unhandled value format: {value}")

                processed_data[section][sweep_type][param] = processed_values

    return processed_data


def save_processed_bias_data_to_json(processed_data, output_file):
    """
    Save the processed bias data to a JSON file.

    Parameters:
    -----------
    processed_data : dict
        The dictionary containing processed data.
    output_file : str
        Path to the output JSON file.
    """
    try:
        with open(output_file, 'w') as f:
            json.dump(processed_data, f, indent=4)
        print(f"Processed data successfully saved to '{output_file}'")
    except Exception as e:
        print(f"Failed to save processed data to '{output_file}'. Error: {e}")


def parse_mux_channel_string(channel_str):
    """
    Parse a MUX channel string (e.g., 'P1016_pmos25_FET3_CH7_BiasDS_Force')
    into its components (type, FET #, channel, bias type, operation).

    Parameters:
    -----------
    channel_str : str
        A single MUX channel instruction string.

    Returns:
    --------
    dict
        A dictionary with parsed elements. Example:
        {
            "raw_string": "P1016_pmos25_FET3_CH7_BiasDS_Force",
            "transistor_type": "pmos25",
            "fet": 3,
            "channel": 7,
            "bias_type": "DS",
            "operation": "Force"
        }
    """
    parts = channel_str.split('_')
    # Example parts: ["P1016", "pmos25", "FET3", "CH7", "BiasDS", "Force"]

    transistor_type = parts[1]  # e.g., "pmos25" or "nmos25"
    fet_number = int(parts[2].replace("FET", ""))  # e.g., 3 from "FET3"
    channel_number = int(parts[3].replace("CH", ""))  # e.g., 7 from "CH7"

    # Determine the bias type and operation
    bias_part = parts[4]  # e.g., "BiasDS"
    if bias_part == "BiasGS":
        bias_type = "GS"
        operation = None
    else:
        # If it's "BiasDS", the next part may be "Force" or "Sense"
        bias_type = "DS"
        operation = parts[5] if len(parts) > 5 else None

    return {
        "raw_string": channel_str,
        "transistor_type": transistor_type,
        "fet": fet_number,
        "channel": channel_number,
        "bias_type": bias_type,
        "operation": operation
    }


def load_and_parse_mux_instructions(excel_file, json_file):
    """
    Read an Excel file containing MUX channel instructions and parse each entry.

    The results are reorganized by transistor. Each transistor will have sub-keys
    for each column in the Excel (e.g., 'Mux1', 'Mux2'), which contain lists of
    parsed channel strings.

    Parameters:
    -----------
    excel_file : str
        Path to the Excel file containing MUX channel instructions.
    json_file : str
        Path to the JSON file where the parsed data will be saved.

    Returns:
    --------
    None
        The data is saved directly to 'json_file' as JSON.
    """
    df = pd.read_excel(excel_file)

    # Dictionary to accumulate results by transistor
    # transistor_dict = { "pmos25_FET3": { "Mux1": [parsed_entries], ... }, ... }
    transistor_dict = {}

    for col in df.columns:  # e.g., "Mux1", "Mux2"
        for cell_value in df[col].dropna():
            parsed = parse_mux_channel_string(cell_value)

            # Create a unique key for each transistor: "pmos25_FET3"
            transistor_key = f"{parsed['transistor_type']}_FET{parsed['fet']}"

            if transistor_key not in transistor_dict:
                transistor_dict[transistor_key] = {}

            if col not in transistor_dict[transistor_key]:
                transistor_dict[transistor_key][col] = []

            transistor_dict[transistor_key][col].append(parsed)

    # Write out transistor_dict to JSON
    with open(json_file, "w") as f:
        json.dump(transistor_dict, f, indent=2)

    print(f"Saved reorganized MUX instructions to '{json_file}'")


# ------------------------------------------------------------------------------
# Use
# ------------------------------------------------------------------------------
# 1. Extract raw bias data from an Excel file.
excel_bias_file = "28nm_test_biases_v3.xlsx"
raw_data = extract_bias_data_from_excel(excel_bias_file)

# 2. Process the extracted bias data to convert strings to numeric lists.
processed_data = process_bias_data(raw_data)

# 3. Save processed bias data to a JSON file.
output_json_path = "sweep_bias_instructions_v3.json"
save_processed_bias_data_to_json(processed_data, output_json_path)

# 4. (Optional) Print processed data for verification
pprint.pprint(processed_data)
for section_name, sweeps in processed_data.items():
    print(f"\n================= {section_name} =================")
    for sweep_type, parameters in sweeps.items():
        print(f"--- {sweep_type} ---")
        for param, values_list in parameters.items():
            print(f"Param: {param}, Values: {values_list}")
        print()

# 5. Parse MUX instructions from another Excel file.
mux_excel_file = "muxChannelInstructions_4wire_drain.xlsx"
mux_json_output = "mux_instructions_by_transistor_4wire_drain.json"
load_and_parse_mux_instructions(mux_excel_file, mux_json_output)
