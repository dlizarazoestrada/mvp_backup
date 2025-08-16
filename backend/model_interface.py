"""
Model Interface
This file acts as a bridge between the raw data processing and the final scoring logic.
Its responsibility is to take processed data (like an alpha/beta ratio) and return a
mental wellness score.
"""
import math
import random
from backend.log_config import logger

# These values were calculated offline by running analysis/calculate_baseline.py
# on the resting EEG dataset. They represent the average "calm" state for the population.
POPULATION_BASELINE_ALPHA_BETA_RATIO = 12.4438
POPULATION_STD_DEV_ALPHA_BETA_RATIO = 10.0113

def get_score_from_ratio(current_alpha_beta_ratio: float) -> int:
    """
    Calculates a mental wellness score (0-100) based on the user's current
    Alpha/Beta ratio using a logarithmic scale.

    This approach provides greater sensitivity to changes in lower ratio values, which
    is common for biometric data, while still mapping to an intuitive 0-100 scale.

    - A ratio equal to the baseline mean results in a score of 50.
    - Ratios below the baseline decrease the score towards 0.
    - Ratios above the baseline increase the score towards 100.
    
    Args:
        current_alpha_beta_ratio: The real-time Alpha/Beta power ratio from the EEG.

    Returns:
        An integer score from 0 to 100.
    """
    # Use a safe minimum for the ratio to avoid log(0) errors.
    safe_ratio = max(0.01, current_alpha_beta_ratio)
    
    # The baseline ratio corresponds to a score of 50. We use a log scale to
    # map the deviation from this baseline.
    # The 'scale_factor' controls how quickly the score changes with the ratio.
    # A higher factor means more sensitivity. We use a smaller value to give
    # more granular scores in the lower-ratio (stressed) range.
    scale_factor = 10 # Tuned for a reasonable score distribution
    
    # Calculate the score based on the logarithmic difference from the baseline
    # math.log(safe_ratio / POPULATION_BASELINE_ALPHA_BETA_RATIO) gives us a value that is:
    # - Negative if the ratio is below baseline
    # - Positive if the ratio is above baseline
    # - Zero if the ratio is equal to the baseline
    log_diff = math.log(safe_ratio / POPULATION_BASELINE_ALPHA_BETA_RATIO)
    
    score = 50 + (log_diff * scale_factor)
    
    # Clamp the score to be within the 0-100 range
    clamped_score = max(0, min(100, score))
    
    logger.debug(f"Calculated score. Input Ratio: {current_alpha_beta_ratio:.4f}, Safe Ratio: {safe_ratio:.4f}, Unclamped Score: {score:.2f}, Final Score: {int(clamped_score)}")
    
    return int(clamped_score)

def get_mock_score() -> int:
    """
    Generates a mock score for testing purposes when no real data is available.
    It simulates a fluctuating Alpha/Beta ratio.
    """
    # Simulate a ratio that can plausibly go above and below the baseline
    mock_ratio = random.uniform(1.0, 30.0)
    logger.debug(f"Generated mock ratio for scoring: {mock_ratio:.4f}")
    return get_score_from_ratio(mock_ratio)
