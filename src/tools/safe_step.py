import functools

def safe_step(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            name = func.__name__
            print(f"{name} failed: {e!r}")
            return False
    return wrapper