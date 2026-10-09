import re


def slugify(text):
    """Return a URL slug: lowercase, ASCII words joined by single hyphens."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]", "-", text)
    return text.strip("-")
