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
            raise RuntimeError("STT local no configurado")
        result = subprocess.run(
            self.stt_command + [str(audio_path)], capture_output=True, text=True, timeout=self.timeout
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "STT falló")
        return result.stdout.strip()

    def synthesize(self, text, output_path):
        if not self.tts_command:
            raise RuntimeError("TTS local no configurado")
        result = subprocess.run(
            self.tts_command + [str(output_path), str(text)], capture_output=True, text=True, timeout=self.timeout
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "TTS falló")
        return str(output_path)


class FasterWhisperSTT:
    def __init__(self, model="small", device="cpu", compute_type="int8"):
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def transcribe(self, audio_path):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("Instalá la extra voice para usar faster-whisper.") from exc
        if self._model is None:
            self._model = WhisperModel(self.model_name, device=self.device, compute_type=self.compute_type)
        segments, _ = self._model.transcribe(str(audio_path))
        return " ".join(segment.text.strip() for segment in segments).strip()


class PiperTTS:
    def __init__(self, binary="piper", model=None, timeout=120):
        self.binary = binary
        self.model = model
        self.timeout = timeout

    def synthesize(self, text, output_path):
        if not self.model:
            raise RuntimeError("Configurá un modelo Piper local.")
        command = [self.binary, "--model", self.model, "--output_file", str(output_path)]
        result = subprocess.run(command, input=str(text), capture_output=True, text=True, timeout=self.timeout)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Piper falló")
        return str(output_path)
