"""
Band Power Data Processor

This module is responsible for processing band power data packets from the
Cortex API's 'pow' stream.
"""
from backend.log_config import logger
from typing import Union

# --- Constants based on EPOC X specifications ---
# The channel names must match the order in which the device sends them.
CHANNELS = ["AF3", "F7", "F3", "FC5", "T7", "P7", "O1", "O2", "P8", "T8", "FC6", "F4", "F8", "AF4"]
BANDS = ["theta", "alpha", "betaL", "betaH", "gamma"]

def process_band_power_data(data: dict) -> Union[float, None]:
    """
    Processes a 'pow' data packet to calculate the Alpha/Beta power ratio.

    The 'pow' stream provides pre-calculated power values for different frequency
    bands for each channel. This function simply extracts these values and
    calculates the ratio.

    Args:
        data: A dictionary representing the JSON data packet from the 'pow' stream.
              Example: {'pow': [0.1, 0.2, ...], 'sid': '...', 'time': ...}

    Returns:
        The calculated Alpha/Beta ratio as a float, or None if the data is invalid.
    """
    if "pow" not in data or not isinstance(data["pow"], list):
        logger.warning(f"Invalid or missing 'pow' data in packet: {data}")
        return None

    power_values = data["pow"]
    
    # According to the Cortex API documentation, the 'pow' array is a flat list
    # containing the power of each band for each channel, in order.
    # Total values = 14 channels * 5 bands = 70 values.
    if len(power_values) != len(CHANNELS) * len(BANDS):
        logger.warning(f"Expected {len(CHANNELS) * len(BANDS)} power values, but got {len(power_values)}.")
        return None

    try:
        total_alpha = 0.0
        total_beta = 0.0

        # Create an iterator to go through the flat list of power values
        value_iterator = iter(power_values)

        for channel in CHANNELS:
            for band in BANDS:
                power = next(value_iterator)
                if band == 'alpha':
                    total_alpha += power
                # We consider both low and high beta for the total beta power
                elif band in ['betaL', 'betaH']:
                    total_beta += power
        
        if total_beta == 0:
            logger.warning("Total beta power is zero, cannot compute ratio.")
            return None

        ratio = total_alpha / total_beta
        logger.debug(f"Band power processed. Total Alpha: {total_alpha:.4f}, Total Beta: {total_beta:.4f}, Ratio: {ratio:.4f}")
        return ratio

    except StopIteration:
        logger.error(f"Malformed 'pow' data packet. Not enough values to process all channels and bands. Data: {power_values}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error processing band power data: {e}", exc_info=True)
        return None