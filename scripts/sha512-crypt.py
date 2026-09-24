#!/usr/bin/env python3
"""SHA-512 crypt ($6$) hashing, per Ulrich Drepper's specification.

macOS cannot do this with its own tools: LibreSSL's `openssl passwd` has no -6,
and the system libcrypt silently falls back to 13-character DES when asked for
METHOD_SHA512, so Python's crypt module returns a hash the Pi will not accept.

Reads the password on stdin (so it never appears in the process list) and prints
the hash. Verify with --self-test, which checks the published test vectors.

    echo -n 'secret' | ./sha512-crypt.py
    ./sha512-crypt.py --self-test
"""

import hashlib
import os
import sys

ALPHABET = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
SALT_CHARS = ALPHABET[2:]
DEFAULT_ROUNDS = 5000

# The spec shuffles the 64 digest bytes into this order before base64 encoding.
_GROUPS = [
    (0, 21, 42), (22, 43, 1), (44, 2, 23), (3, 24, 45), (25, 46, 4), (47, 5, 26),
    (6, 27, 48), (28, 49, 7), (50, 8, 29), (9, 30, 51), (31, 52, 10), (53, 11, 32),
    (12, 33, 54), (34, 55, 13), (56, 14, 35), (15, 36, 57), (37, 58, 16), (59, 17, 38),
    (18, 39, 60), (40, 61, 19), (62, 20, 41),
]


def _encode(digest):
    out = []
    for b2, b1, b0 in _GROUPS:
        word = (digest[b2] << 16) | (digest[b1] << 8) | digest[b0]
        for _ in range(4):
            out.append(ALPHABET[word & 0x3F])
            word >>= 6
    word = digest[63]
    for _ in range(2):
        out.append(ALPHABET[word & 0x3F])
        word >>= 6
    return "".join(out)


def _repeat(block, length):
    """The spec's 'add block, repeating, for exactly `length` bytes'."""
    return block * (length // len(block)) + block[: length % len(block)]


def sha512_crypt(password, salt, rounds=DEFAULT_ROUNDS):
    pw = password.encode("utf-8") if isinstance(password, str) else password
    sa = salt.encode("ascii") if isinstance(salt, str) else salt
    sa = sa[:16]

    # Digest B: password, salt, password.
    b = hashlib.sha512(pw + sa + pw).digest()

    # Digest A: password, salt, then B repeated for len(password) bytes, then
    # one bit of len(password) at a time selecting B or the password itself.
    ctx = pw + sa + _repeat(b, len(pw))
    bits = len(pw)
    while bits:
        ctx += b if bits & 1 else pw
        bits >>= 1
    a = hashlib.sha512(ctx).digest()

    # Sequences P and S, derived from the password and salt respectively.
    dp = hashlib.sha512(pw * len(pw)).digest()
    p = _repeat(dp, len(pw))
    ds = hashlib.sha512(sa * (16 + a[0])).digest()
    s = _repeat(ds, len(sa))

    c = a
    for i in range(rounds):
        ctx = p if i & 1 else c
        if i % 3:
            ctx += s
        if i % 7:
            ctx += p
        ctx += c if i & 1 else p
        c = hashlib.sha512(ctx).digest()

    prefix = "$6$" if rounds == DEFAULT_ROUNDS else f"$6$rounds={rounds}$"
    return f"{prefix}{sa.decode('ascii')}${_encode(c)}"


def make_salt(length=16):
    return "".join(SALT_CHARS[b % len(SALT_CHARS)] for b in os.urandom(length))


# Test vectors from the specification at akkadia.org/drepper/SHA-crypt.txt,
# each cross-checked against glibc: OpenSSL 3.4.1 for the default-rounds case and
# libcrypt (via perl) for the rounds= cases.
VECTORS = [
    ("Hello world!", "saltstring", DEFAULT_ROUNDS,
     "$6$saltstring$svn8UoSVapNtMuq1ukKS4tPQd8iKwSMHWjl/O817G3uBnIFNjnQJuesI68u4OTLiBFdcbYEdFCoEOfaS35inz1"),
    ("Hello world!", "saltstringsaltstring", 10000,
     "$6$rounds=10000$saltstringsaltst$OW1/O6BYHV6BcXZu8QVeXbDWra3Oeqh0sbHbbMCVNSnCM/UrjmM0Dp8vOuZeHBy/YTBmSK6H9qs/y3RnOaw5v."),
    ("a short string", "toolongsaltstring", 1400,
     "$6$rounds=1400$toolongsaltstrin$JZj2ZhmKy0ewUWKOX79nDxgSHqOf.66NOKp/YVNTFSCJ7pbZeDOTF9Korsxj.E./lK0eYE5mVrIebv3rTGYbK1"),
    ("a short string", "toolongsaltstring", DEFAULT_ROUNDS,
     "$6$toolongsaltstrin$BlmL1qgiT7LmskajFpTr8VKepTs4Gv.u/7NmhnnB3D6aivtwtkK.OELpa.W/umS4osfOA.PI4lFhAB3dMhPuv1"),
]


def self_test():
    failures = 0
    for password, salt, rounds, expected in VECTORS:
        actual = sha512_crypt(password, salt, rounds)
        ok = actual == expected
        failures += not ok
        print(f"{'ok     ' if ok else 'FAILED '} rounds={rounds:<6d} {salt}")
        if not ok:
            print(f"    expected {expected}\n    actual   {actual}")

    # A round trip through the system's own crypt, where it is trustworthy.
    try:
        import crypt
        reference = crypt.crypt("Hello world!", "$6$saltstring")
        if reference and reference.startswith("$6$") and len(reference) > 20:
            match = reference == VECTORS[0][3]
            failures += not match
            print("%s system crypt agrees" % ("ok     " if match else "FAILED "))
        else:
            print("skipped system crypt (no $6$ support on this platform)")
    except ImportError:
        print("skipped system crypt (module unavailable)")

    return failures


def main():
    if "--self-test" in sys.argv:
        failures = self_test()
        print(f"\n{'all vectors passed' if not failures else f'{failures} FAILURES'}")
        return 1 if failures else 0

    password = sys.stdin.buffer.read()
    password = password.rstrip(b"\n")
    if not password:
        sys.stderr.write("no password on stdin\n")
        return 2

    salt = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else make_salt()
    print(sha512_crypt(password, salt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
