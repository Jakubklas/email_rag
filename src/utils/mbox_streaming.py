import mmap
from src.utils.safe_step import *

@safe_step
def fast_stream_first_n(path, n):
    """
    Generator uses mmap if possible for local files or else 4Mb binary chunk reads
    for streaming large mbox files. Looks for b'\nFrom ' to find the first n
    messages. Yields raw messages as strings.
    """
    # Mmap for local/mappable files, if possible (fast memory reads)
    try:
        with open(path, 'rb') as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            count, prev = 0, 0
            first_idx = mm.find(b'From ')

            # Start from the first message
            if first_idx != -1:
                prev = first_idx
            
            # Iterate until n messages found 
            while count < n:
                idx = mm.find(b'\nFrom ', prev + 1)
                # If no more messages, yield the last bit
                if idx == -1:
                    if prev < mm.size():
                        yield mm[prev:].decode('utf-8', errors='replace')
                    return
                yield mm[prev:idx + 1].decode('utf-8', errors='replace')
                prev = idx + 1
                count += 1
            
            mm.close()

    # 4Mb binary chunks reading if file isn't local (e.g. pulled from S3)
    except (ValueError, OSError):
        with open(path, 'rb') as f:
            buffer = b''
            count = 0
            chunk_size = 4 * 1024 * 1024

            while True:
                data = f.read(chunk_size)
                if not data:
                    if buffer and count < n:
                        yield buffer.decode('utf-8', errors='replace')
                    return
                
                data = buffer + data
                parts = data.split(b'\nFrom ')
                buffer = parts.pop()
                for part in parts:
                    # Find first message
                    if count == 0 and part.startswith(b'From '):
                        yield part.decode('utf-8', errors='replace')
                    # Find other messages & attach to the previous
                    else:
                        yield 'From ' + part.decode('utf-8', errors='replace')
                    count += 1
                    if count >= n:
                        return
