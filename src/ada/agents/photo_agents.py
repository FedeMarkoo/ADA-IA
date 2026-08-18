"""Photo-specialist agents.

They deliberately reuse the existing photo analysis primitives instead of
duplicating RAW decoding, model access, or scoring logic.
"""
from pathlib import Path

from src.ada.capabilities.photography.analyze_photo import (
    _folder_context,
    technical_analysis,
    vision_analysis,
)
from src.ada.domain.photography.selection import evaluate_selection

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
        selection_score, selection_rating, selection_label = evaluate_selection(technical, semantic)
        if focus.get('score', 0) >= 6:
            strengths.append('nitidez aceptable o buena')
        else:
            issues.append('nitidez limitada; conviene revisar foco y trepidación')
        if exposure.get('score', 0) >= 6:
            strengths.append('exposición equilibrada')
        elif exposure.get('score', 0) >= 4:
            issues.append('exposición algo baja; probablemente recuperable al revelar')
        else:
            issues.append('exposición baja o irregular; revisar sombras y altas luces')
        noise_score = float((technical.get('noise') or {}).get('score', 10) or 10)
        if noise_score < 4.5:
            issues.append('ISO extremo; revisar ruido, detalle fino y tamaño de entrega')
        if semantic.get('photographer_feedback'):
            strengths.append('el análisis visual encontró contexto fotográfico')
        return AgentResult(self.name, True, {
            'strengths': strengths,
            'issues': issues,
            'technical_score': technical.get('overall_score', 0),
            'artistic_score': semantic.get('artistic_score'),
            'selection_score': selection_score,
            'selection_rating': selection_rating,
            'selection_label': selection_label,
            'recommendation': (
                'aceptar como seleccionada y revelar' if selection_rating >= 3
                else 'revisar antes de seleccionar' if selection_rating == 2
                else 'rechazar'
            ),
        })
