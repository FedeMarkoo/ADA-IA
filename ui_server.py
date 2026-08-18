from flask import Flask, request, jsonify, send_from_directory
import json
import os
from pathlib import Path

from agent_loop import Agent
from skills.operations.files.filesystem import IMAGE_EXTENSIONS
import re

app = Flask(__name__, static_folder='ui')


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    app.logger.exception('Unhandled ADA request error')
    return jsonify({'error': 'internal_error', 'message': str(error)}), 500

cfg_path = os.path.join(os.path.dirname(__file__), 'config.json')
if os.path.exists(cfg_path):
    cfg = json.loads(open(cfg_path).read())
else:
    cfg = {}
for key in ('db_path', 'local_model_path', 'gpt4all_model_path'):
    value = cfg.get(key)
    if isinstance(value, str) and not os.path.isabs(value):
        cfg[key] = os.path.join(os.path.dirname(__file__), value.replace('ADA/', '', 1))

agent = Agent(cfg)
class PersistentConversation(list):
    """List-compatible history that survives UI and server restarts."""
    def __init__(self, memory):
        self.memory = memory
        super().__init__(memory.conversation(limit=1000))

    def extend(self, items):
        items = list(items)
        super().extend(items)
        self.memory.append_conversation(items)

    def clear(self):
        super().clear()
        self.memory.clear_conversation()


conversation = PersistentConversation(agent.mem)
pending_action = None


def _context_prompt(text):
    recent = conversation[-30:]
    if not recent:
        return text
    history = '\n'.join(f"{item['role']}: {item['text']}" for item in recent)
    return "Conversación reciente:\n" + history + "\n\nMensaje actual del usuario:\n" + text


def _desktop_path():
    return os.path.expanduser('~/Desktop')


def _resolve_folder(text, previous):
    value = text.lower() + ' ' + previous.lower()
    if 'escritorio' in text.lower() or 'desktop' in text.lower():
        return _desktop_path()
    if 'organized' in value and ('archivo' in value or 'carpeta' in value or 'agrupar' in value):
        return os.path.expanduser('~/Desktop/ADA/test_photos/organized')
    if 'test' in value:
        return os.path.expanduser('~/Desktop/ADA/test_photos')
    if 'escritorio' in value or 'desktop' in value:
        return _desktop_path()
    return None


def _last_known_folder(previous):
    """Resolve the most specific folder ADA mentioned in the conversation."""
    if 'organized' in previous.lower():
        return os.path.expanduser('~/Desktop/ADA/test_photos/organized')
    return _resolve_folder('', previous)


def _resolve_photo_reference(text, previous, parsed):
    """Resolve a camera filename without ever falling back to another photo."""
    path = parsed.get('path')
    if path and Path(path).is_file():
        return {'path': path}
    name = parsed.get('photo_name')
    if not name:
        match = re.search(r"(?<!\w)_?dsc\d+(?:\.(?:nef|arw|cr2|dng|raf|orf|jpg|jpeg|png))?", text, re.I)
        name = match.group(0) if match else None
    if not name:
        return {'path': path}
    stem = Path(name).stem.lower()
    extensions = {'.nef', '.arw', '.cr2', '.dng', '.raf', '.orf', '.jpg', '.jpeg', '.png'}
    roots = []
    # Reuse the folder of a previously explicit image path in this conversation.
    for match in re.finditer(r"(/[^\n\"]+?\.(?:nef|arw|cr2|dng|raf|orf|jpg|jpeg|png))", previous, re.I):
        candidate = Path(match.group(1).rstrip('.,;:!?'))
        if candidate.is_file():
            roots.append(candidate.parent)
    roots.extend([Path(cfg.get('photo_root', ''))] if cfg.get('photo_root') else [])
    candidates = []
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for candidate in root.rglob('*'):
                if candidate.is_file() and candidate.suffix.lower() in extensions and candidate.stem.lower() == stem and str(candidate) not in seen:
                    seen.add(str(candidate))
                    candidates.append(candidate)
        except OSError:
            continue
    # RAW wins over a rendered JPG, and files in Originales win over exports.
    unique = []
    for candidate in candidates:
        if any(candidate.samefile(existing) for existing in unique):
            continue
        unique.append(candidate)
    raw_candidates = [item for item in unique if item.suffix.lower() in {'.nef', '.arw', '.cr2', '.dng', '.raf', '.orf'}]
    raw_candidates.sort(key=lambda item: ('originales' not in str(item).lower(), str(item)))
    if len(raw_candidates) == 1:
        return {'path': str(raw_candidates[0])}
    if len(unique) == 1:
        return {'path': str(unique[0])}
    if unique:
        unique.sort(key=lambda item: (item.suffix.lower() not in {'.nef', '.arw', '.cr2', '.dng', '.raf', '.orf'}, 'originales' not in str(item).lower(), str(item)))
        return {'ambiguous': [str(item) for item in unique], 'photo_name': name}
    return {'not_found': name}


def _reply(text, model='ADA · agente'):
    conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': text}])
    return jsonify({'reply': text, 'model': model})


def _photo_reply(result):
    """Turn the internal multi-agent contract into a readable photographer report."""
    technical = result.get('technical') or {}
    semantic = result.get('semantic') or {}
    review = result.get('review') or {}
    focus = technical.get('focus', {})
    exposure = technical.get('exposure', {})
    composition = technical.get('composition', {})
    match = semantic.get('session_match') or {}
    lines = [
        '# Análisis fotográfico',
        '',
        f"**Archivo:** `{result.get('path', 'sin identificar')}`",
        '',
        f"## Veredicto: {review.get('recommendation', 'revisar')} · {technical.get('overall_score', '—')}/10",
        '',
        '| Área | Puntuación | Lectura |',
        '|---|---:|---|',
        f"| Enfoque | {focus.get('score', '—')}/10 | {'Nitidez limitada; revisar foco o trepidación' if focus.get('score', 0) < 5 else 'Nitidez aceptable'} |",
        f"| Exposición | {exposure.get('score', '—')}/10 | {'Subexpuesta o con sombras densas' if exposure.get('score', 0) < 5 else 'Equilibrada'} |",
        f"| Composición técnica | {composition.get('score', '—')}/10 | {composition.get('note', 'Evaluación técnica')} |",
        '',
    ]
    if semantic.get('subject'):
        lines += ['## Lectura de la escena', '', f"**Sujeto y contexto:** {semantic['subject']}", '']
    if semantic.get('style'):
        lines += [f"**Estilo:** {semantic['style']}", '']
    if semantic.get('photographer_feedback'):
        lines += ['## Devolución como fotógrafo', '', semantic['photographer_feedback'], '']
    if match:
        confidence = match.get('confidence')
        if isinstance(confidence, (int, float)):
            confidence_text = f"{round(float(confidence) * 100 if confidence <= 1 else float(confidence))}%"
        else:
            confidence_text = str(confidence or '—')
        lines += [f"**Coincidencia con la sesión:** {confidence_text}", str(match.get('reason', '')), '']
    if review.get('strengths'):
        lines += ['**Puntos fuertes**', ''] + [f"- {item}" for item in review['strengths']] + ['']
    if review.get('issues'):
        lines += ['**A revisar**', ''] + [f"- {item}" for item in review['issues']] + ['']
    lines += [f"_Analizado por ADA con el workflow multiagente y {semantic.get('model', 'modelo visual local')}._"]
    return '\n'.join(lines)


@app.route('/')
def index():
    return send_from_directory('ui', 'index.html')


@app.route('/api/status')
def status():
    """Return active engines, local runtime health, and agent registry."""
    return jsonify({
        'engines': agent.model_manager.available(),
        'runtime': agent.model_manager.runtime_status(),
        'agents': list(agent.coordinator.available_agents()),
    })


@app.route('/api/conversation', methods=['GET', 'DELETE'])
def conversation_api():
    if request.method == 'DELETE':
        conversation.clear()
        return jsonify({'ok': True, 'messages': []})
    return jsonify({'messages': list(conversation), 'count': len(conversation)})


@app.route('/api/chat', methods=['POST'])
def chat():
    global pending_action
    data = request.get_json() or {}
    text = data.get('message', '')
    lang = data.get('lang')
    if lang:
        agent.lang = lang
    if not text:
        return jsonify({'error': 'empty message'}), 400
    # simple heuristic: short greetings get a canned reply (avoid calling LLM)
    if isinstance(text, str) and len(text.strip().split()) <= 3 and re.match(r'^(hola|hi|hello|buenas|buenos d[ií]as|hey)$', text.strip(), flags=re.I):
        canned = 'Hola, ¿en qué puedo ayudarte?' if lang and lang.startswith('es') else ('Hello, how can I help you?' if lang and lang.startswith('en') else 'Hola, ¿en qué puedo ayudarte?')
        conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': canned}])
        return jsonify({'reply': canned, 'model': 'ADA · respuesta rápida'})

    lowered = text.strip().lower()
    if lowered in {'que podes hacer?', 'qué podés hacer?', 'que puedes hacer?', 'qué puedes hacer?'}:
        reply = ('Soy ADA, un agente local. Puedo consultar la base de fotos, mostrar cómo están organizadas, '
                 'analizar RAW/XMP, preparar planes y ordenar fotos; también puedo listar, buscar y mover archivos, '
                 'ejecutar scripts con confirmación y aprender procedimientos que me enseñes. '
                 'Cuando una operación modifica archivos, primero te muestro el plan y pido confirmación.')
        conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
        return jsonify({'reply': reply, 'model': 'ADA · agente'})
    if any(phrase in lowered for phrase in ('sos agente', 'quiero que lo hagas vos', 'la idea es que lo hagas vos')):
        reply = ('Sí. Estoy configurada para trabajar como agente: consulto la información disponible, uso las skills '
                 'y ejecuto las tareas dentro de ADA. Para acciones que mueven, borran o modifican archivos, te muestro '
                 'primero un plan y solicito confirmación antes de ejecutarlas.')
        conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
        return jsonify({'reply': reply, 'model': 'ADA · agente'})

    parsed = agent.parse_prompt(text)
    previous_text = ' '.join(item['text'] for item in conversation[-4:])
    previous = previous_text.lower()
    affirmative = text.strip().lower() in {'si', 'sí', 's', 'dale', 'hacelo', 'hazlo', 'confirmo', 'confirmar'}
    if pending_action and affirmative:
        action = pending_action
        pending_action = None
        result = agent.decide_and_run({**action, 'confirm': True})
        out = result.get('result', {})
        reply = json.dumps(out, ensure_ascii=False, indent=2) if isinstance(out, dict) else str(out)
        conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
        return jsonify({'reply': reply, 'model': result.get('model', 'tool')})
    if parsed.get('action') == 'lightroom':
        lr_action = parsed.get('lightroom_action', 'plan')
        root = parsed.get('path') or cfg.get('photo_root') or os.path.expanduser('~/Desktop/Fotos')
        if lr_action in {'status', 'structure', 'report'}:
            result = agent.decide_and_run({
                'type': 'sqlite',
                'payload': {'action': lr_action, 'db': cfg.get('lightroom_db')},
                'complexity': 2,
            })
            out = result.get('result', {})
            if isinstance(out, dict) and out.get('action') == 'status' and out.get('ok'):
                s = out['summary']
                reply = (f"Estado de la biblioteca (SQLite):\n\n"
                         f"- Carpetas: {s['carpetas']}\n- Fotos RAW registradas: {s['total']}\n"
                         f"- Buenas: {s['buenas']}\n- Rechazadas: {s['rechazadas']}\n"
                         f"- Eliminadas: {s['eliminadas']}\n- Movidas: {s['movidas']}\n\n"
                         "Estados:\n" + '\n'.join(f"- {item['estado']}: {item['cantidad']}" for item in out['estados']) +
                         "\n\nFormatos:\n" + '\n'.join(f"- {item['formato']}: {item['colecciones']} colecciones" for item in out['formatos']))
            elif isinstance(out, dict) and out.get('action') == 'structure' and out.get('ok'):
                groups = {}
                for item in out['collections']:
                    groups.setdefault(item['formato'] or 'Sin formato', []).append(item)
                lines = [f"Estructura registrada en SQLite ({out['count']} colecciones):"]
                for formato, items in groups.items():
                    lines.append(f"\n{formato} ({len(items)}):")
                    for item in items:
                        date = f"{item['fecha']} - " if item['fecha'] else ''
                        context = f"{item['contexto']}/" if item['contexto'] else ''
                        lines.append(f"- {context}{date}{item['contenido']}\n  {item['ruta']}")
                reply = '\n'.join(lines)
            elif isinstance(out, dict) and out.get('action') == 'report' and out.get('ok'):
                s = out['summary']
                lines = [
                    'Reporte real de la biblioteca (SQLite):',
                    f"- Carpetas: {s['carpetas']}", f"- RAW registrados: {s['total']}",
                    f"- Buenas: {s['buenas']}", f"- Rechazadas: {s['rechazadas']}",
                    f"- Eliminadas: {s['eliminadas']}", f"- Movidas: {s['movidas']}", '',
                    f"- JPG registrados: {s.get('jpg', 0)} ({s.get('jpg_asociados', 0)} asociados)",
                    f"- Videos: {s.get('videos', 0)} · Editables: {s.get('editables', 0)} · Otros: {s.get('otros', 0)}", '',
                    'Resumen por formato:'
                ]
                for item in out['formatos']:
                    label = (f"{item['colecciones']} colecciones" if item['colecciones'] else
                             f"{item['carpetas']} carpeta sin colección")
                    lines.append(f"- {item['formato']}: {label}, "
                                 f"{item['total']} RAW, {item.get('jpg', 0)} JPG "
                                 f"({item['buenas']} buenas, {item['rechazadas']} rechazadas)")
                lines.append('\nDetalle completo por carpeta:')
                for item in out['collections']:
                    date = f"{item['fecha']} - " if item['fecha'] else ''
                    context = f"{item['contexto']}/" if item['contexto'] else ''
                    lines.append(f"- [{item['formato']}] {context}{date}{item['contenido']}: "
                                 f"{item['total']} RAW ({item['buenas']} buenas, {item['rechazadas']} rechazadas)\n  {item['ruta']}")
                reply = '\n'.join(lines)
            else:
                reply = json.dumps(out, ensure_ascii=False, indent=2)
            conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
            return jsonify({'reply': reply, 'model': result.get('model', 'tool: sqlite')})
        payload = {
            'action': lr_action,
            'root': root,
            'script': cfg.get('lightroom_script'),
            'db': cfg.get('lightroom_db'),
        }
        if lr_action in {'organize', 'organizar', 'mover', 'limpiar', 'recuperar'}:
            pending_action = {'type': 'lightroom', 'payload': payload, 'complexity': 7}
            reply = f"Preparé una operación Lightroom sobre {root}. Primero conviene revisar el plan simulado. ¿Querés que lo ejecute después de confirmar?"
            conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
            return jsonify({'reply': reply, 'model': 'ADA · agente'})
        result = agent.decide_and_run({'type': 'lightroom', 'payload': payload, 'complexity': 6})
        out = result.get('result', {})
        if isinstance(out, dict) and out.get('action') == 'status' and out.get('ok'):
            s = out['summary']
            reply = (f"Estado de la biblioteca:\n\n"
                     f"- Carpetas: {s['carpetas']}\n- Fotos RAW registradas: {s['total']}\n"
                     f"- Buenas: {s['buenas']}\n- Rechazadas: {s['rechazadas']}\n"
                     f"- Eliminadas: {s['eliminadas']}\n- Movidas: {s['movidas']}\n\n"
                     "Estados:\n" + '\n'.join(f"- {item['estado']}: {item['cantidad']}" for item in out['estados']) +
                     "\n\nFormatos:\n" + '\n'.join(f"- {item['formato']}: {item['colecciones']} colecciones" for item in out['formatos']))
        elif isinstance(out, dict) and out.get('action') == 'structure' and out.get('ok'):
            groups = {}
            for item in out['collections']:
                groups.setdefault(item['formato'] or 'Sin formato', []).append(item)
            lines = [f"Estructura registrada en la base ({out['count']} colecciones):"]
            for formato, items in groups.items():
                lines.append(f"\n{formato} ({len(items)}):")
                for item in items:
                    date = f"{item['fecha']} - " if item['fecha'] else ''
                    context = f"{item['contexto']}/" if item['contexto'] else ''
                    lines.append(f"- {context}{date}{item['contenido']}\n  {item['ruta']}")
            reply = '\n'.join(lines)
        else:
            reply = out.get('stdout', '') if isinstance(out, dict) else str(out)
        if isinstance(out, dict) and out.get('stderr'):
            reply += '\n\nErrores/avisos:\n' + out['stderr']
        conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
        return jsonify({'reply': reply or json.dumps(out, ensure_ascii=False, indent=2), 'model': result.get('model', 'tool')})
    if pending_action and pending_action.get('type') == 'filesystem' and pending_action.get('payload', {}).get('action') in {'list_dirs', 'list_files'} and ('escritorio' in text.lower() or 'desktop' in text.lower() or 'test' in text.lower()):
        parsed = {'action': pending_action['payload']['action'], 'complexity': 2}
        pending_action = None
    if 'escritorio' in text.lower() and 'fotos' in previous:
        parsed = {'action': 'list_photos', 'complexity': 2}
    elif ('escritorio' in text.lower() or 'desktop' in text.lower()) and ('carpet' in previous or 'directori' in previous) and any(w in previous for w in ('list', 'mostrar', 'ver')):
        parsed = {'action': 'list_dirs', 'complexity': 2}
    if parsed.get('action') == 'analyze_photo':
        resolved = _resolve_photo_reference(text, previous_text, parsed)
        if resolved.get('ambiguous'):
            reply = 'Encontré varias versiones de ' + resolved['photo_name'] + ':\n\n' + '\n'.join(f'- {item}' for item in resolved['ambiguous']) + '\n\nIndicame cuál querés analizar.'
            conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
            return jsonify({'reply': reply, 'model': 'ADA · agente'})
        if resolved.get('not_found'):
            reply = f"No encontré una foto llamada {resolved['not_found']} en la carpeta de la sesión. No analicé ninguna otra foto."
            conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
            return jsonify({'reply': reply, 'model': 'ADA · agente'})
        path = resolved.get('path')
        if not path:
            reply = 'Necesito la ruta de la imagen. Por ejemplo: “analizá la foto /ruta/imagen.jpg”.'
            conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
            return jsonify({'reply': reply, 'model': 'ADA · agente'})
        result = agent.decide_and_run({'type': 'analyze_photo', 'payload': {'path': path}, 'complexity': 5})
        out = result.get('result', {})
        reply = _photo_reply(out)
        conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
        return jsonify({'reply': reply, 'model': result.get('model', 'tool: analyze_photo')})
    if parsed.get('action') in {'list_dirs', 'list_files'}:
        folder = parsed.get('path') or _resolve_folder(text, previous)
        if not folder:
            reply = '¿En qué carpeta querés buscar? Podés decirme “las de test” o “el escritorio”.'
            pending_action = {'type': 'filesystem', 'payload': {'action': parsed['action']}, 'complexity': 2}
            conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
            return jsonify({'reply': reply, 'model': 'ADA · agente'})
        result = agent.decide_and_run({'type': 'filesystem', 'payload': {'action': parsed['action'], 'dir': folder, 'recursive': True}, 'complexity': 2})
        out = result.get('result', {})
        key = 'dirs' if parsed['action'] == 'list_dirs' else 'files'
        reply = (f"Encontré {out.get('count', 0)} elementos en {out.get('dir', folder)}.\n\n" + '\n'.join(out.get(key, []))) if isinstance(out, dict) and out.get('ok') else json.dumps(out, ensure_ascii=False, indent=2)
        conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
        return jsonify({'reply': reply, 'model': result.get('model', 'tool')})
    group_words = ('nombre', 'llamala', 'llamalo', 'agrup', 'carpeta nueva', 'movelas', 'moverlas', 'mover todos', 'todas las fotos', 'la segunda')
    if parsed.get('action') == 'group_files' or (pending_action and any(w in text.lower() for w in group_words)):
        source = (pending_action or {}).get('payload', {}).get('source') if pending_action else None
        source = source or _last_known_folder(previous) or _resolve_folder(text, previous)
        if not source:
            reply = '¿De qué carpeta querés agrupar los archivos?'
        else:
            match = re.search(r'(?:nombre|llam(?:ar|ala|alo)?)\s+(?:a\s+)?[\"“]?([\w.-]+)', text, re.I)
            name = match.group(1) if match else None
            if not name and any(w in text.lower() for w in ('agrupad', 'grouped')):
                name = 'grouped' if 'grouped' in text.lower() else 'Agrupadas'
            if not name and 'la segunda' in text.lower():
                name = 'Agrupadas'
            if pending_action and name:
                pending_action['payload']['name'] = name
            if not name and pending_action:
                name = pending_action['payload'].get('name')
            if not name:
                pending_action = {'type': 'filesystem', 'payload': {'action': 'move_files', 'source': source}, 'complexity': 4}
                reply = f"Voy a agrupar los archivos de {source}. ¿Qué nombre querés ponerle a la carpeta nueva?"
            else:
                pending_action = {'type': 'filesystem', 'payload': {'action': 'move_files', 'source': source, 'name': name}, 'complexity': 4}
                reply = f"Voy a mover los archivos de {source} a {source.rsplit('/', 1)[0]}/{name}. ¿Confirmás?"
        conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
        return jsonify({'reply': reply, 'model': 'ADA · agente'})
    if parsed.get('action') == 'list_photos':
        folder = parsed.get('path')
        if not folder and ('escritorio' in text.lower() or ('fotos' in previous and 'carpeta' in previous)):
            folder = _desktop_path()
        if not folder:
            reply = '¿En qué carpeta querés que liste las fotos? Podés decirme, por ejemplo, “escritorio”.'
            conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
            return jsonify({'reply': reply, 'model': 'ADA · agente'})
        result = agent.decide_and_run({'type': 'filesystem', 'payload': {'action': 'list_files', 'dir': folder, 'extensions': list(IMAGE_EXTENSIONS)}, 'complexity': 2})
        out = result.get('result', {})
        if isinstance(out, dict) and out.get('ok'):
            photos = out.get('files', out.get('photos', []))
            reply = f"Encontré {out['count']} fotos en {out['dir']}.\n\n" + ('\n'.join(photos) if photos else 'No encontré imágenes.')
        else:
            reply = json.dumps(out, ensure_ascii=False, indent=2)
        conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': reply}])
        return jsonify({'reply': reply, 'model': result.get('model', 'tool')})

    # by default avoid injecting RAG context for UI chat messages unless caller requests it
    task = {
        'type': None,
        'prompt': _context_prompt(text),
        'complexity': agent.estimate_complexity(text),
        'use_memory': True,
        'mode': 'agent',
    }
    res = agent.decide_and_run(task)
    model = res.get('model') if isinstance(res, dict) else None
    # Normalize output
    out = res.get('result') if isinstance(res, dict) else res
    if isinstance(out, dict):
        # try to get text in common fields
        out_text = out.get('text') or out.get('result') or str(out)
    else:
        out_text = str(out)

    # sanitize output: remove persona statements (age/gender) and trim auto-inserted language blocks
    # remove explicit age/gender roleplay lines
    out_text = re.sub(r"I(?:'m| am) a \d{1,3}[- ]?year[- ]?old [a-zA-Z]+[\.,]?", '', out_text, flags=re.I)
    out_text = re.sub(r"My name is [A-Za-z ]{1,30}\.?", '', out_text)
    # remove common auto-questions and assistant self-introductions
    out_text = re.sub(r"What is your name\??", '', out_text, flags=re.I)
    out_text = re.sub(r"What is your purpose\??", '', out_text, flags=re.I)
    out_text = re.sub(r"ADA:.*?", '', out_text, flags=re.I)
    out_text = re.sub(r"user prompt:.*", '', out_text, flags=re.I|re.S)
    # remove leading 'English:' / 'Spanish:' blocks if lang specified
    if lang == 'es':
        # keep Spanish block after 'Spanish:' or 'Spanish' marker
        m = re.search(r"Spanish:\s*(.*?)$", out_text, flags=re.I|re.S)
        if m:
            out_text = m.group(1).strip()
        else:
            # remove any English: ... Spanish: markers and keep whole text
            out_text = re.sub(r"English:.*?Spanish:\s*", '', out_text, flags=re.I|re.S)
    elif lang == 'en':
        m = re.search(r"English:\s*(.*?)($|Spanish:)", out_text, flags=re.I|re.S)
        if m:
            out_text = m.group(1).strip()
        else:
            out_text = re.sub(r"Spanish:.*?English:\s*", '', out_text, flags=re.I|re.S)
    # strip repeated whitespace and odd characters
    out_text = out_text.strip()

    # detect roleplay/storytelling outputs and retry with stricter instruction
    roleplay_patterns = [r"Your Character", r"The Environment", r"What do you want to do", r"I'll describe", r"you are a skilled", r"adventurer", r"text-based adventure"]
    try:
        if any(re.search(pat, out_text, flags=re.I) for pat in roleplay_patterns):
            # retry once with a stronger non-roleplay instruction
            retry_task = {'type': None, 'prompt': f"Respuesta breve en {lang if lang!='auto' else 'español'} al mensaje: {text}. No roleplay. Contesta sólo un saludo y pregunta cómo puedo ayudar.", 'complexity': 1, 'use_memory': False}
            retry_res = agent.decide_and_run(retry_task)
            model = retry_res.get('model') if isinstance(retry_res, dict) else model
            out = retry_res.get('result') if isinstance(retry_res, dict) else retry_res
            out_text = out if isinstance(out, str) else str(out)
            out_text = re.sub(r"I(?:'m| am) a \d{1,3}[- ]?year[- ]?old [a-zA-Z]+[\.,]?", '', out_text, flags=re.I)
            out_text = re.sub(r"My name is [A-Za-z ]{1,30}\.?", '', out_text)
            out_text = out_text.strip()
    except Exception:
        pass
    conversation.extend([{'role': 'user', 'text': text}, {'role': 'assistant', 'text': out_text}])
    return jsonify({'reply': out_text, 'model': model or 'sin modelo'})


if __name__ == '__main__':
    port = int(os.environ.get('ADA_UI_PORT', '5005'))
    app.run(host='127.0.0.1', port=port)
