import scipy.stats as stats

def get_truncated_normal(mean: float, sd: float, lower: float = 0) -> float:
    if sd == 0:
        return mean
    a = (lower - mean) / sd
    return stats.truncnorm(a, float('inf'), loc=mean, scale=sd).rvs()
