def should_refresh(refresh_due: bool, retry_due: bool) -> bool:
    return refresh_due and retry_due
