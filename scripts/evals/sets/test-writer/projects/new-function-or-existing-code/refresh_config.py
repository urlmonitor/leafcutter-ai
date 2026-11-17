DEFAULTS = {"interval": 30, "retries": 3}


def refresh_config(overrides):
    merged = dict(DEFAULTS)
    for key, value in overrides.items():
        if value:
            merged[key] = value
    return merged
