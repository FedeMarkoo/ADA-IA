import os
import json
import argparse
from pathlib import Path
from src.ada.infrastructure.imaging.embeddings import get_image_embedding
from src.ada.infrastructure.integrations.web_search import search_web
from src.ada.infrastructure.persistence.sqlite import Memory

def index_folder(folder, mem: Memory):
    p = Path(folder)
    for img in p.rglob('*'):
        if img.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
            emb = get_image_embedding(str(img))
            if emb is not None:
                mem.add(str(img), emb, meta={'name': img.name})
                print('Indexed', img)

def suggest_organization(folder, mem: Memory):
    from collections import Counter
    p = Path(folder)
    suggestions = Counter()
    for img in p.rglob('*'):
        if img.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
            tokens = img.stem.replace('_', ' ').replace('-', ' ').split()
            query = ' '.join(tokens[:5]) if tokens else img.name
            results = search_web(query, max_results=3)
            if results:
                title = results[0].get('title') or ''
                folder_guess = title.split(' - ')[0].split('|')[0].strip()
                suggestions[folder_guess] += 1
    for name, count in suggestions.most_common(20):
        print(f"Suggest folder: {name}  ({count} matches)")
