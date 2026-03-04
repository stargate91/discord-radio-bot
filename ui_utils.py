def format_duration(seconds: int):
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"

def fixed(text: str, length: int = 42):
    text = str(text)

    if len(text) > length:
        return text[:length - 3] + "..."

    return text.ljust(length)
