"""Business rules for deciding whether a photo is worth selecting."""


def evaluate_selection(technical, semantic):
    """Blend technical and artistic evidence into a Lightroom rating."""
    technical = technical or {}
    semantic = semantic or {}
    technical_score = float(technical.get('overall_score', 0) or 0)
    artistic_score = semantic.get('artistic_score')
    if isinstance(artistic_score, (int, float)):
        blended_score = technical_score * 0.45 + float(artistic_score) * 0.55
    else:
        blended_score = technical_score
    noise_score = float((technical.get('noise') or {}).get('score', 10) or 10)
    focus_score = float((technical.get('focus') or {}).get('score', 10) or 10)
    if noise_score < 4.5 and focus_score < 6:
        blended_score = min(blended_score, 4.9)
    if blended_score >= 8.5:
        rating, label = 5, 'excelente'
    elif blended_score >= 7.2:
        rating, label = 4, 'muy buena'
    elif blended_score >= 5.0:
        rating, label = 3, 'aceptada'
    elif blended_score >= 3.5:
        rating, label = 2, 'dudosa'
    else:
        rating, label = 1, 'rechazo técnico'
    return round(blended_score, 2), rating, label
