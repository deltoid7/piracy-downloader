import base64
import json

def _b64(s):
    s = s.strip().replace("-", "+").replace("_", "/")
    return base64.b64decode(s + "=" * ((-len(s)) % 4), validate=False)

def decrypt_key(data):
    o = json.loads(_b64(data).decode())
    r = o["rule"]
    blob = _b64(o["encrypted_key"])
    perm, sizes, n, nl = r["permutation"], r["segment_sizes"], r["segments_count"], r["noise_length"]
    chunks, i = [], 0
    for p in range(n):
        t = sizes[perm[p]] + nl
        chunks.append(blob[i : i + t])
        i += t
    out = bytearray()
    for L in range(n):
        out += chunks[perm.index(L)][: sizes[L]]
    return bytes(out)

# etc
def print_credit():
    print("""_______    _____                                         \n|__   __|  |  __ \                                        \n    | |_   _| |__) |___   ___  _ __ ___                    \n    | \ \ / /  _  // _ \ / _ \| '_ ` _ \                   \n    | |\ V /| | \ \ (_) | (_) | | | | | |                  \n__|_| \_/ |_|  \_\___/ \___/|_| |_| |_|      _           \n|  __ \                    | |               | |          \n| |  | | _____      ___ __ | | ___   __ _  __| | ___ _ __ \n| |  | |/ _ \ \ /\ / / '_ \| |/ _ \ / _` |/ _` |/ _ \ '__|\n| |__| | (_) \ V  V /| | | | | (_) | (_| | (_| |  __/ |   \n|_____/ \___/ \_/\_/ |_| |_|_|\___/ \__,_|\__,_|\___|_|   \n\nhttps://github.com/deltoid7/tvroom-downloader\n""")