"""Lightroom-compatible XMP sidecar metadata shared by photo workflows."""
import re
from pathlib import Path


def write_photo_xmp(path, status, rating, score, reason):
    """Create/update ADA fields while preserving all unrelated XMP metadata."""
    sidecar = Path(path).with_suffix('.xmp')
    content = sidecar.read_text(encoding='utf-8', errors='ignore') if sidecar.is_file() else (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '  <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" rdf:about=""/>\n'
        ' </rdf:RDF>\n</x:xmpmeta>\n'
    )
    if '<rdf:Description' not in content:
        raise ValueError('XMP has no rdf:Description element')
    if 'xmlns:ada=' not in content:
        content = content.replace('<rdf:Description', '<rdf:Description xmlns:ada="https://ada.local/ns/1.0/"', 1)
    if 'xmlns:xmp=' not in content:
        content = content.replace('<rdf:Description', '<rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/"', 1)
    values = {
        'xmp:Rating': str(int(rating if status == 'Seleccionada' else 0)),
        'xmp:Label': status,
        'ada:Status': status,
        'ada:Score': f'{float(score):.2f}',
        'ada:Reason': reason,
    }
    for key, value in values.items():
        escaped = str(value).replace('&', '&amp;').replace('"', '&quot;')
        pattern = rf'{re.escape(key)}="[^"]*"'
        replacement = f'{key}="{escaped}"'
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content, count=1)
        else:
            content = content.replace('<rdf:Description ', f'<rdf:Description {replacement} ', 1)
    sidecar.write_text(content, encoding='utf-8')
    return str(sidecar)
