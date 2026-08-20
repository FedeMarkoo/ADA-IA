"""Provider result normalization without content-rewriting regexes."""


def text_from_result(result):
    if isinstance(result, dict):
        value = result.get("text") or result.get("reply") or result.get("result")
        return str(value) if value is not None else str(result)
    return str(result or "")
