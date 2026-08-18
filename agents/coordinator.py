"""Workflow coordinator for ADA's specialist agents."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .base import AgentRegistry
from .photo_agents import ContextPhotoAgent, PhotoReviewAgent, TechnicalPhotoAgent


class MultiAgentCoordinator:
    """Coordinates specialists while keeping execution and memory in ADA core."""

    def __init__(self, config=None):
        self.config = config or {}
        self.registry = AgentRegistry([
            TechnicalPhotoAgent(),
            ContextPhotoAgent(),
            PhotoReviewAgent(),
        ])
        self.max_workers = max(1, int(self.config.get('agent_max_workers', 2)))

    def available_agents(self):
        return self.registry.names()

    def analyze_photo(self, task):
        path = Path(task.get('path', '')).expanduser().resolve()
        if not path.is_file():
            return {'error': 'image not found', 'path': str(path), 'workflow': 'photo_review'}
        shared = dict(task)
        shared['path'] = str(path)
        shared.setdefault('config', self.config)
        results = {}
        failures = {}
        parallel = [self.registry.get('technical_photo'), self.registry.get('context_photo')]
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(parallel))) as pool:
            futures = {pool.submit(agent.run, shared): agent.name for agent in parallel}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    item = future.result()
                    results[name] = item.data
                except Exception as exc:
                    failures[name] = str(exc)
                    results[name] = {'available': False, 'error': str(exc)}
        review = self.registry.get('photo_reviewer').run({
            'technical': results.get('technical_photo'),
            'semantic': results.get('context_photo'),
        })
        results['photo_reviewer'] = review.data
        technical = results.get('technical_photo', {})
        semantic = results.get('context_photo', {})
        context = semantic.get('context') or {
            'folder': str(task.get('folder') or path.parent),
            'siblings': [],
        }
        return {
            'ok': not failures,
            'workflow': 'photo_review',
            'agents': results,
            'agent_failures': failures,
            # Compatibility fields for existing UI and callers.
            'path': str(path),
            'technical': technical,
            'semantic': semantic,
            'session_context': context,
            'review': results['photo_reviewer'],
        }

    def run(self, task):
        workflow = task.get('workflow') or task.get('type')
        if workflow in {'photo_review', 'analyze_photo'}:
            return self.analyze_photo(task)
        return {'error': f'workflow not available: {workflow}'}
