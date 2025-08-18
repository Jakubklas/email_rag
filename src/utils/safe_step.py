import functools

def safe_step(func):
    """
    Func. decorator to catch errors without breaking the ingestion
    pipeline and prints errors.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            name = func.__name__
            print(f"[ERROR] {name} failed: {e!r}")
            return None
    return wrapper