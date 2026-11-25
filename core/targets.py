"""
Weibo target link management.

Targets are stored in conf/comment_data.json and conf/forward_data.json.
A link that is not present yet is appended automatically with a counter of 0.
"""
import json
import logging
import os
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

DATA_FILES = {
    "comment": "conf/comment_data.json",
    "forward": "conf/forward_data.json",
}


def _data_file(weibo_type):
    try:
        return DATA_FILES[weibo_type]
    except KeyError:
        raise ValueError(f"Unknown weibo type: {weibo_type}")


def normalize_weibo_url(url):
    """
    Normalize a Weibo URL for storage and comparison.

    - adds https:// when the scheme is missing,
    - lowercases the scheme/host,
    - removes the fragment (#comment, #repost, ...),
    - removes a trailing slash,
    - keeps the query string (some non-status pages need it).
    """
    url = (url or "").strip().strip("\"'")
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url

    parts = urlsplit(url)
    if not parts.netloc or not parts.path:
        raise ValueError(f"Invalid Weibo link: {url}")

    path = parts.path.rstrip("/")
    if not path:
        raise ValueError(f"Invalid Weibo link (missing post path): {url}")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def target_key(url):
    """
    Identity of a target, used to avoid duplicates.

    Tracking query parameters and the #comment/#repost fragment do not change
    the identity of a Weibo post, so they are ignored here.
    """
    try:
        parts = urlsplit(normalize_weibo_url(url))
    except ValueError:
        return ""
    if not parts.netloc or not parts.path:
        return ""
    return f"{parts.netloc}{parts.path}".rstrip("/")


def load_weibo_details(weibo_type):
    """
    Return the ``weibo_details`` list of the selected data file.

    A missing file is created with an empty list.
    """
    filename = _data_file(weibo_type)
    try:
        with open(filename, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
    except FileNotFoundError:
        save_weibo_details(weibo_type, [])
        return []
    except json.JSONDecodeError as exc:
        raise ValueError(f"{filename} is not valid JSON: {exc}") from exc

    details = data.get("weibo_details")
    if not isinstance(details, list):
        raise ValueError(f"{filename} must contain a 'weibo_details' list")
    return details


def save_weibo_details(weibo_type, details):
    """
    Save the ``weibo_details`` list back to the selected data file.
    """
    filename = _data_file(weibo_type)
    directory = os.path.dirname(filename)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(filename, "w", encoding="utf-8") as json_file:
        json.dump({"weibo_details": details}, json_file, ensure_ascii=False, indent=2)
        json_file.write("\n")


def find_target_index(details, link):
    """
    Return the index of an existing target, or None.
    """
    key = target_key(link)
    if not key:
        return None
    for index, entry in enumerate(details):
        if target_key(entry.get("link", "")) == key:
            return index
    return None


def ensure_weibo_target(weibo_type, link, tag=None):
    """
    Find a target by link; append it with counter 0 when it is new.

    :return: (index, entry, created)
    """
    normalized = normalize_weibo_url(link)
    if not normalized:
        raise ValueError("Weibo link cannot be empty")
    details = load_weibo_details(weibo_type)
    index = find_target_index(details, normalized)
    if index is not None:
        return index, details[index], False

    entry = {
        "link": normalized,
        "total_comment_count": 0,
        "tag": tag or f"自动添加 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "index": len(details),
    }
    details.append(entry)
    save_weibo_details(weibo_type, details)
    logging.info(f"New {weibo_type} target added: {normalized} (count starts at 0)")
    return len(details) - 1, entry, True


def get_last_target(weibo_type):
    """
    Return the link of the most recently added target, or None.
    """
    details = load_weibo_details(weibo_type)
    if not details:
        return None
    return details[-1].get("link")


def get_target_by_index(weibo_type, index, filename=None):
    """
    Return one target entry, with a clear error for an invalid index.
    """
    details = load_weibo_details(weibo_type)
    filename = filename or _data_file(weibo_type)
    if not 0 <= index < len(details):
        raise IndexError(
            f"index={index} is out of range for {filename} "
            f"({len(details)} entr{'y' if len(details) == 1 else 'ies'}; valid "
            f"index 0-{len(details) - 1}).")
    return details[index]
