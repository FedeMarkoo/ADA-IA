"""Local-first voice contracts with safe subprocess boundaries."""
import subprocess
from typing import Protocol


class SpeechToText(Protocol):
    def transcribe(self, audio_path: str) -> str: ...


class TextToSpeech(Protocol):
    def synthesize(self, text: str, output_path: str) -> str: ...


class LocalCommandVoice:
    def __init__(self, stt_command=None, tts_command=None, timeout=120):
        self.stt_command = list(stt_command or [])
        self.tts_command = list(tts_command or [])
        self.timeout = timeout

    def transcribe(self, audio_path):
        if not self.stt_command:
            raise RuntimeError('STT local no configurado')
        result = subprocess.run(self.stt_command + [str(audio_path)], capture_output=True, text=True, timeout=self.timeout)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or 'STT falló')
        return result.stdout.strip()

    def synthesize(self, text, output_path):
        if not self.tts_command:
            raise RuntimeError('TTS local no configurado')
        result = subprocess.run(self.tts_command + [str(output_path), str(text)], capture_output=True, text=True, timeout=self.timeout)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or 'TTS falló')
        return str(output_path)
