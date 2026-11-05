def should_refresh(refresh_due, retry_due):
    if refresh_due and retry_due:
        return True
    return False
