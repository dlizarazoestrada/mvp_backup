"""
Analyzes the 'db_resting_eeg' dataset to calculate a population-level
baseline for the Alpha/Beta power ratio.

The script dynamically determines the number of channels from the data,
applies the corresponding standard montage (e.g., 10-10 or 10-05) to
rename channels from a generic format (e.g., 'E1') to a standard format
(e.g., 'Fp1'), and then processes the signal to compute the desired metrics.
"""
import mne
import numpy as np
import os
from glob import glob
import sys

# Add the project root to the path to allow importing from the 'backend' module.
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.append(project_root)

from backend.log_config import logger

# --- Configuration ---
mne.set_log_level('WARNING')

CHANNELS_OF_INTEREST = ['AF3', 'F7', 'F3', 'FC5', 'T7', 'P7', 'O1', 'O2', 'P8', 'T8', 'FC6', 'F4', 'F8', 'AF4']

BANDS = {
    'Alpha': (8.0, 13.0),
    'Beta': (13.0, 30.0)
}

# --- Main Analysis Function ---
def analyze_dataset(data_path):
    subject_files = glob(os.path.join(data_path, 'sub-*/eeg/*.set'))

    if not subject_files:
        logger.error(f"No .set files found in '{data_path}'. Please check the path.")
        return

    logger.info(f"Found {len(subject_files)} subjects to analyze.")
    all_subject_ratios = []

    for f_path in subject_files:
        subject_id = f_path.split(os.sep)[-3]
        logger.info(f"Processing {subject_id}...")

        try:
            raw = mne.io.read_raw_eeglab(f_path, preload=True)

            eeg_indices = mne.pick_types(raw.info, eeg=True)
            n_channels = len(eeg_indices)
            logger.info(f"  Found {n_channels} EEG channels in the file.")

            montage_name = 'standard_1005'
            
            montage = mne.channels.make_standard_montage(montage_name)
            
            # Rename channels assuming the order in the file matches the standard montage order
            current_eeg_names = [raw.ch_names[i] for i in eeg_indices]
            rename_map = {current_eeg_names[i]: montage.ch_names[i] for i in range(n_channels)}
            raw.rename_channels(rename_map)
            raw.set_montage(montage, on_missing='ignore')

            raw.pick_channels(CHANNELS_OF_INTEREST, ordered=True)
            raw.filter(l_freq=1.0, h_freq=45.0, fir_design='firwin', skip_by_annotation='edge')

            psd, freqs = raw.compute_psd(method='welch', fmin=1.0, fmax=45.0, picks='eeg').get_data(return_freqs=True)

            # 7. Calculate the average power within our defined bands
            alpha_power = np.mean(psd[:, (freqs >= BANDS['Alpha'][0]) & (freqs < BANDS['Alpha'][1])])
            beta_power = np.mean(psd[:, (freqs >= BANDS['Beta'][0]) & (freqs < BANDS['Beta'][1])])
            
            if beta_power > 0:
                ratio = alpha_power / beta_power
                all_subject_ratios.append(ratio)
            else:
                logger.warning(f"  Skipping {subject_id} due to zero beta power.")

        except Exception as e:
            logger.error(f"Could not process {subject_id}. Error: {e}", exc_info=False) # Set exc_info to False for cleaner logs

    # --- Population Statistics ---
    if not all_subject_ratios:
        logger.error("Could not calculate any ratios. No baseline was determined.")
        return

    mean_ratio = np.mean(all_subject_ratios)
    std_ratio = np.std(all_subject_ratios)

    logger.info("--- Analysis Complete ---")
    logger.info(f"Successfully analyzed {len(all_subject_ratios)} subjects.")
    logger.info(f"Population Alpha/Beta Ratio:")
    logger.info(f"  - Mean: {mean_ratio:.4f}")
    logger.info(f"  - Standard Deviation: {std_ratio:.4f}")
    logger.info("This 'Mean' value is your population baseline. Use it in 'model_interface.py'.")

if __name__ == '__main__':
    dataset_path = os.path.join(project_root, 'db_resting_eeg')
    analyze_dataset(dataset_path)
