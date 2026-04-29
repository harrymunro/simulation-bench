import numpy as np

def truncated_normal(mean: float, sd: float, random_state: np.random.RandomState, lower_bound: float = 0.1) -> float:
    # simple rejection sampling to ensure > lower_bound
    val = -1
    while val < lower_bound:
        val = random_state.normal(mean, sd)
    return val
