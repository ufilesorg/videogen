import re
import string
from urllib.parse import urlparse

regex = re.compile(
    r"^(https?|ftp):\/\/"  # http:// or https:// or ftp://
    r"(?"
    r":(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
    # r"localhost|"  # or localhost...
    # r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|"  # or IPv4...
    # r"\[?[A-F0-9]*:[A-F0-9:]+\]?"  # or IPv6...
    r")"
    r"(?::\d+)?"  # optional port
    r"(?:\/[-A-Z0-9+&@#\/%=~_|$]*)*$",
    re.IGNORECASE,
)


def is_valid_url(url):
    # Check if the URL matches the regex
    if re.match(regex, url) is None:
        return False

    # Additional check using urllib.parse to ensure proper scheme and netloc
    parsed_url = urlparse(url)
    return all([parsed_url.scheme, parsed_url.netloc])


def backtick_formatter(text: str):
    text = text.strip().strip("```json").strip("```").strip()
    # if text.startswith("```"):
    #     text = "\n".join(text.split("\n")[1:-1])
    return text


def format_keys(text: str) -> set[str]:
    return {t[1] for t in string.Formatter().parse(text) if t[1]}


def format_fixer(**kwargs):
    list_length = len(next(iter(kwargs.values())))

    # Initialize the target list
    target = []

    # Iterate over each index of the lists
    for i in range(list_length):
        # Create a new dictionary for each index
        entry = {key: kwargs[key][i] for key in kwargs}
        # Append the new dictionary to the target list
        target.append(entry)

    return target
