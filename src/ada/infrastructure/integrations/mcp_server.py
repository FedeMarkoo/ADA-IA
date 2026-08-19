"""Minimal MCP-compatible stdio server exposing ADA capabilities."""
import json
import sys
from typing import Any, Dict, List


def serve(capabilities, descriptions=None):
    descriptions = descriptions or {}
    tools: List[Dict[str, Any]] = [{'name': name, 'description': descriptions.get(name, f'ADA capability {name}'),
                                    'inputSchema': {'type': 'object'}} for name in sorted(capabilities)]
    for line in sys.stdin:
        try:
            request = json.loads(line)
            method = request.get('method')
            result: Dict[str, Any] = {}
            if method == 'initialize':
                result = {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}},
                          'serverInfo': {'name': 'ADA', 'version': '0.1.0'}}
            elif method == 'tools/list':
                result = {'tools': tools}
            elif method == 'tools/call':
                params = request.get('params') or {}
                name = params.get('name')
                if name not in capabilities:
                    raise ValueError(f'Unknown tool: {name}')
                output = capabilities[name](params.get('arguments') or {})
                result = {'content': [{'type': 'text', 'text': json.dumps(output, ensure_ascii=False, default=str)}]}
            elif method.startswith('notifications/'):
                continue
            else:
                raise ValueError(f'Unknown method: {method}')
            response = {'jsonrpc': '2.0', 'id': request.get('id'), 'result': result}
        except Exception as exc:
            response = {'jsonrpc': '2.0', 'id': request.get('id') if isinstance(request, dict) else None,
                        'error': {'code': -32000, 'message': str(exc)}}
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + '\n')
        sys.stdout.flush()
