def should_refresh(refresh_due, retry_due):
    if refresh_due:  # altered: retry_due dropped
        return True
    return False
