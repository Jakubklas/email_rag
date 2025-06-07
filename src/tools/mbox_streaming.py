import mmap


def fast_stream_first_n(path, n):
    """
    Memory-map or chunk-read the mbox, find first n messages by searching
    for b'\nFrom ' separators, and yield raw message strings.
    """
    # If local, use mmap for max speed, else fallback to chunked reads
    try:
        with open(path, 'rb') as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            count, prev = 0, 0
            # Skip the very first “From “ which may not have preceding '\n'
            first_idx = mm.find(b'From ')
            if first_idx != 0:
                prev = first_idx
                count = 1
                yield mm[:first_idx].decode('utf-8', errors='replace')
            while count < n:
                idx = mm.find(b'\nFrom ', prev + 1)
                if idx == -1:
                    # yield last bit if any
                    if prev < mm.size():
                        yield mm[prev:].decode('utf-8', errors='replace')
                    return
                yield mm[prev:idx + 1].decode('utf-8', errors='replace')
                prev = idx + 1
                count += 1
            mm.close()
    except (ValueError, OSError):
        # Fallback: chunked binary read + manual buffer
        with open(path, 'rb') as f:
            buffer = b''
            count = 0
            chunk_size = 4 * 1024 * 1024  # 4 MB
            while True:
                data = f.read(chunk_size)
                if not data:
                    if buffer and count < n:
                        yield buffer.decode('utf-8', errors='replace')
                    return
                data = buffer + data
                parts = data.split(b'\nFrom ')
                # Reattach the last (possibly incomplete) part to next read
                buffer = parts.pop()
                for part in parts:
                    if count == 0 and part.startswith(b'From '):
                        # The very first message including leading “From “
                        yield part.decode('utf-8', errors='replace')
                    else:
                        yield b'From ' + part.decode('utf-8', errors='replace')
                    count += 1
                    if count >= n:
                        return
