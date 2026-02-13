"""
Utilities for string sanitization and filename normalization.
"""

import os
import re
import unicodedata
import uuid


def make_filename_portable(filename: str, max_length: int = 64) -> str:
    """
    Converts a filename to a safe, portable, ASCII-only version.
    1. NFKD normalization (splits characters from accents).
    2. Encodes to ASCII, ignoring non-convertible chars (like emojis/kanji).
    3. Replaces non-alphanumeric chars with underscores.
    4. Collapses multiple underscores.
    5. Truncates to max_length.

    Logic: Normalizes unicode, strips non-ascii/special chars, truncates,
    and handles empty result.
    """
    name, ext = os.path.splitext(filename)
    nfkd_form = unicodedata.normalize("NFKD", name)
    only_ascii = nfkd_form.encode("ASCII", "ignore").decode("ASCII")
    clean_name = re.sub(r"[^a-zA-Z0-9\-\.]", "_", only_ascii)
    clean_name = re.sub(r"[_\-]+", "_", clean_name)
    clean_name = clean_name.lower()
    if len(clean_name) > max_length:
        clean_name = clean_name[:max_length]
    clean_name = clean_name.strip("._-")
    if not clean_name:
        clean_name = f"renamed_{uuid.uuid4().hex[:8]}"
    return f"{clean_name}{ext.lower()}"


def get_unique_filename(directory: str, filename: str) -> str:
    """
    Ensures the filename does not exist in the
    directory by appending _1, _2.

    Logic: Appends counter to filename if it already exists in directory.
    """
    destination = os.path.join(directory, filename)
    if not os.path.exists(destination):
        return filename
    name, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_name = f"{name}_{counter}{ext}"
        if not os.path.exists(os.path.join(directory, new_name)):
            return new_name
        counter += 1
