"""Optional Gmail API adapter; credentials are always supplied outside Git."""
import base64
import os
from email.mime.text import MIMEText
from pathlib import Path


def _service(config, scopes):
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError('Instalá la extra Gmail para habilitar esta integración.') from exc
    token_path = Path(os.path.expanduser(config.get('gmail_token_path', '~/.config/ada/gmail-token.json')))
    if not token_path.is_file():
        raise RuntimeError(f'Falta el token OAuth local de Gmail: {token_path}')
    credentials = Credentials.from_authorized_user_file(str(token_path), scopes)
    return build('gmail', 'v1', credentials=credentials, cache_discovery=False)


def read(config, query='is:unread', limit=10):
    service = _service(config, ['https://www.googleapis.com/auth/gmail.readonly'])
    response = service.users().messages().list(userId='me', q=query, maxResults=max(1, min(int(limit), 50))).execute()
    messages = []
    for item in response.get('messages', []):
        data = service.users().messages().get(userId='me', id=item['id'], format='metadata',
                                              metadataHeaders=['Subject', 'From', 'Date']).execute()
        headers = {header['name'].lower(): header['value'] for header in data.get('payload', {}).get('headers', [])}
        messages.append({'id': item['id'], 'subject': headers.get('subject', ''),
                         'from': headers.get('from', ''), 'date': headers.get('date', '')})
    return {'ok': True, 'query': query, 'messages': messages}


def send(config, to, subject, body, confirm=False):
    if not confirm:
        return {'error': 'confirmation_required', 'preview': {'to': to, 'subject': subject, 'body': body}}
    service = _service(config, ['https://www.googleapis.com/auth/gmail.send'])
    message = MIMEText(str(body), 'plain', 'utf-8')
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')
    result = service.users().messages().send(userId='me', body={'raw': raw}).execute()
    return {'ok': True, 'id': result.get('id'), 'to': to, 'subject': subject}
