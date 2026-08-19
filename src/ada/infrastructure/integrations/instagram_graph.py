"""Official Instagram Graph API publisher for Business/Creator accounts."""
import json
import os
import urllib.parse
import urllib.error
import urllib.request


def publish(config, image_url, caption, confirm=False):
    preview = {'image_url': image_url, 'caption': caption}
    if not confirm:
        return {'error': 'confirmation_required', 'preview': preview}
    user_id = config.get('instagram_user_id')
    token = config.get('instagram_access_token') or os.environ.get('INSTAGRAM_ACCESS_TOKEN')
    if not user_id or not token:
        return {'error': 'instagram_graph_not_configured', 'preview': preview}
    if not str(image_url).lower().startswith(('https://', 'http://')):
        return {'error': 'instagram_graph_requires_public_image_url', 'preview': preview}
    api_version = config.get('instagram_graph_version', 'v20.0')
    base = f'https://graph.facebook.com/{api_version}/{user_id}'
    container = _post(base + '/media', {'image_url': image_url, 'caption': caption, 'access_token': token})
    creation_id = container.get('id')
    if not creation_id:
        return {'error': 'instagram_container_failed', 'response': container}
    published = _post(base + '/media_publish', {'creation_id': creation_id, 'access_token': token})
    return {'ok': 'id' in published, 'creation_id': creation_id, 'response': published, 'preview': preview}


def _post(url, values):
    payload = urllib.parse.urlencode(values).encode('utf-8')
    request = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode('utf-8'))
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {'error': str(exc)}
