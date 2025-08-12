# THIS IS THE TYPE CHART MAKER. THIS IS HIDDEN FROM THE LLM.

import pandas as pd
import numpy as np
import os
import random
from itertools import combinations

# --- 1. Define the Type Chart and Classification Rules ---
# This is the ground truth for the custom Pokemon romhack.

TYPE_CHART = {
    # Attacking Type -> { Defending Type: Multiplier }
    'Fire':     {'Fire': 0.5, 'Water': 1.0, 'Grass': 1.0, 'Electric': 0.5, 'Psychic': 2.0, 'Ghost': 2.0},
    'Water':    {'Fire': 2.0, 'Water': 0.5, 'Grass': 0, 'Electric': 2.0, 'Psychic': 1.0, 'Ghost': 0.5},
    'Grass':    {'Fire': 1.0, 'Water': 1.0, 'Grass': 0.5, 'Electric': 0.5, 'Psychic': 1.0, 'Ghost': 1.0},
    'Electric': {'Fire': 2.0, 'Water': 1.0, 'Grass': 0.5, 'Electric': 0.0, 'Psychic': 1.0, 'Ghost': 0.0},
    'Psychic':  {'Fire': 1.0, 'Water': 2.0, 'Grass': 2.0, 'Electric': 0.0, 'Psychic': 0.5, 'Ghost': 2.0},
    'Ghost':    {'Fire': 1.0, 'Water': 1.0, 'Grass': 1.0, 'Electric': 1.0, 'Psychic': 0.0, 'Ghost': 2.0},
}

CLASSIFICATION_MAP = {
    0.0:  "immune",
    0.25: "barely_effective",
    0.5:  "not_very_effective",
    1.0:  "neutral",
    2.0:  "very_effective",
    4.0:  "super_effective"
}

# --- 2. Logic for Calculating Final Effectiveness ---

def get_effectiveness_classification(row):
    """
    Calculates the total multiplier from the ground truth chart and finds the 
    matching classification string. This function correctly handles the "dirty" data.
    """
    attack_type = row['attack_type']
    
    # Identify the valid defending types, ignoring placeholders like NaN, None, or '-'.
    defending_types = []
    if pd.notna(row['type1']) and row['type1'] != '-':
        defending_types.append(row['type1'])
    if pd.notna(row['type2']) and row['type2'] != '-':
        defending_types.append(row['type2'])

    # If no valid defending types are found, assume it's a neutral interaction.
    # (This case shouldn't be reached with the current generation logic).
    if not defending_types:
        total_multiplier = 1.0
    else:
        # Calculate the final multiplier by multiplying effectiveness against each type.
        total_multiplier = 1.0
        for d_type in defending_types:
            total_multiplier *= TYPE_CHART[attack_type][d_type]
            
    # Return the classification string, using .get() for safety.
    return CLASSIFICATION_MAP.get(total_multiplier)

# --- 3. Script to Generate Exhaustive and Dirty CSVs ---

def generate_exhaustive_csvs(unfilled_path, filled_path):
    """
    Generates two CSVs: one with the target classification filled, and one
    without. The data covers every possible type combination and includes
    random "dirty" data to make parsing more challenging.
    """
    all_types = list(TYPE_CHART.keys())
    all_rows_data = []

    # Get all possible defending type combinations (single and dual types)
    single_type_combos = list(combinations(all_types, 1))
    dual_type_combos = list(combinations(all_types, 2))
    all_defender_combos = single_type_combos + dual_type_combos

    # Iterate through every attacker and every defender combination
    for attack_type in all_types:
        for combo in all_defender_combos:
            row = {"attack_type": attack_type, "type1": None, "type2": None}
            
            # --- Apply Data Dirtying Logic ---
            if len(combo) == 1: # Single-type defender
                defender_type = combo[0]
                # 50% chance to swap the type into the 'type2' column
                if random.random() < 0.33:
                    row["type2"] = defender_type
                else:
                    row["type1"] = defender_type

                # 50% chance to fill the empty slot with a "-"
                if random.random() < 0.33:
                    if row["type1"] is None:
                        row["type1"] = "-"
                    else:
                        row["type2"] = "-"
            else: # Dual-type defender
                row["type1"] = combo[0]
                row["type2"] = combo[1]

            all_rows_data.append(row)

    # Create the base DataFrame
    df = pd.DataFrame(all_rows_data)

    # --- Create and Save the 'filled.csv' ---
    df_filled = df.copy()
    df_filled['target'] = df_filled.apply(get_effectiveness_classification, axis=1)
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(filled_path), exist_ok=True)
    df_filled.to_csv(filled_path, index=False)
    print(f"Successfully generated 'filled.csv' with {len(df_filled)} rows at '{filled_path}'.")

    # --- Create and Save the 'unfilled.csv' ---
    df_unfilled = df.copy()
    df_unfilled['target'] = "" # Leave the target column empty
    
    os.makedirs(os.path.dirname(unfilled_path), exist_ok=True)
    df_unfilled.to_csv(unfilled_path, index=False)
    print(f"Successfully generated 'unfilled.csv' with {len(df_unfilled)} rows at '{unfilled_path}'.")


if __name__ == "__main__":
    # Define file paths as per the standard task structure
    base_dir = './'
    unfilled_output_path = os.path.join(base_dir, 'unfilled.csv')
    filled_output_path = os.path.join(base_dir, 'filled.csv')
    
    generate_exhaustive_csvs(unfilled_path=unfilled_output_path, filled_path=filled_output_path)