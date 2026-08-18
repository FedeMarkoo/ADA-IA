"""Photo-specialist agents.

They deliberately reuse the existing photo analysis primitives instead of
duplicating RAW decoding, model access, or scoring logic.
"""
from pathlib import Path

from skills.photos.analyze_photo import (
    _folder_context,
    technical_analysis,
    vision_analysis,
)

from .base import AgentResult, SpecialistAgent


class TechnicalPhotoAgent(SpecialistAgent):
    name = 'technical_photo'

    def run(self, task):
        path = Path(task['path'])
        return AgentResult(self.name, True, technical_analysis(path))


class ContextPhotoAgent(SpecialistAgent):
    name = 'context_photo'

    def run(self, task):
        path = Path(task['path'])
        context = _folder_context(path, task.get('folder'))
        if not task.get('vision', True):
            return AgentResult(self.name, True, {'available': False, 'reason': 'vision_disabled', 'context': context})
        result = vision_analysis(str(path), context, task.get('config'))
        return AgentResult(self.name, bool(result.get('available')), result)


class PhotoReviewAgent(SpecialistAgent):
    name = 'photo_reviewer'

    def run(self, task):
        technical = task.get('technical') or {}
        semantic = task.get('semantic') or {}
        issues = []
        strengths = []
        exposure = technical.get('exposure', {})
        focus = technical.get('focus', {})
        if focus.get('score', 0) >= 6:
            strengths.append('nitidez aceptable o buena')
        else:
            issues.append('nitidez limitada; conviene revisar foco y trepidación')
        if exposure.get('score', 0) >= 6:
            strengths.append('exposición equilibrada')
        else:
            issues.append('exposición baja o irregular; revisar sombras')
        if semantic.get('photographer_feedback'):
            strengths.append('el análisis visual encontró contexto fotográfico')
        return AgentResult(self.name, True, {
            'strengths': strengths,
            'issues': issues,
            'recommendation': 'conservar y revelar' if len(issues) <= 1 else 'revisar antes de seleccionar',
        })
