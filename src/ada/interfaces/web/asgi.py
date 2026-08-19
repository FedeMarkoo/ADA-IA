"""FastAPI/ASGI interface, optional and compatible with the existing Agent."""
import asyncio
import json
import os
from typing import Optional

from src.ada.application.agent import Agent
from src.ada.application.services.chat import ChatService
from src.ada.config import load_config


def create_app(agent=None):
    try:
        from fastapi import FastAPI, WebSocket
        from fastapi.responses import StreamingResponse
        from pydantic import BaseModel
    except ImportError as exc:
        raise RuntimeError("Instalá la extra web: pip install -e '.[web]'") from exc

    config = load_config()
    service = ChatService(agent or Agent(config))
    app = FastAPI(title='ADA', version='0.1.0')

    class ChatRequest(BaseModel):
        message: str
        session_id: str = 'main'
        lang: Optional[str] = None
        confirm: Optional[bool] = None

    @app.get('/api/status')
    def status():
        return {'engines': service.agent.model_manager.available(),
                'runtime': service.agent.model_manager.runtime_status()}

    @app.get('/api/conversation/{session_id}')
    def conversation(session_id: str):
        return {'messages': service.history(session_id)}

    @app.delete('/api/conversation/{session_id}')
    def clear(session_id: str):
        service.clear(session_id)
        return {'ok': True, 'messages': []}

    @app.post('/api/chat')
    async def chat(request: ChatRequest):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: service.handle(request.message, request.session_id, request.lang, request.confirm))

    @app.post('/api/chat/stream')
    async def stream(request: ChatRequest):
        async def events():
            yield 'event: status\ndata: {"text":"ADA está procesando el pedido."}\n\n'
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, lambda: service.handle(request.message, request.session_id, request.lang, request.confirm))
            text = str(result.get('reply', result))
            yield f'event: reply\ndata: {json.dumps({"text": text}, ensure_ascii=False)}\n\n'
            yield 'event: done\ndata: {"ok":true}\n\n'
        return StreamingResponse(events(), media_type='text/event-stream')

    @app.websocket('/ws/{session_id}')
    async def websocket(websocket: WebSocket, session_id: str):
        await websocket.accept()
        while True:
            message = await websocket.receive_text()
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, lambda: service.handle(message, session_id))
            await websocket.send_json(result)

    return app


app = None
if os.environ.get('ADA_ASGI_EAGER') == '1':
    app = create_app()
