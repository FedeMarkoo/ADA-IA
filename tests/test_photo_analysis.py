import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from skills import load_skills
from skills.photos.analyze_photo import _noise_score, run, technical_analysis
from agents import MultiAgentCoordinator
from agents.photo_agents import PhotoReviewAgent


class PhotoAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / 'concert.jpg'
        image = Image.new('RGB', (320, 200), (20, 20, 24))
        draw = ImageDraw.Draw(image)
        draw.rectangle((30, 30, 120, 170), fill=(220, 40, 40))
        draw.line((0, 180, 320, 20), fill=(255, 255, 255), width=4)
        image.save(self.path, quality=95)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_technical_analysis_returns_scores(self):
        result = technical_analysis(self.path)
        self.assertEqual(result['orientation'], 'landscape')
        self.assertIn('focus', result)
        self.assertIn('exposure', result)
        self.assertGreaterEqual(result['overall_score'], 0)
        self.assertLessEqual(result['overall_score'], 10)

    def test_skill_works_without_vision_model(self):
        result = run({'path': str(self.path), 'vision': False})
        self.assertTrue(result['ok'])
        self.assertNotIn('error', result)

    def test_missing_image_is_reported(self):
        result = run({'path': str(Path(self.tempdir.name) / 'missing.jpg'), 'vision': False})
        self.assertEqual(result['error'], 'image not found')

    def test_all_skills_are_loaded_recursively(self):
        skills = load_skills()
        self.assertIn('analyze_photo', skills)

    def test_multi_agent_photo_workflow(self):
        coordinator = MultiAgentCoordinator({'agent_max_workers': 2})
        result = coordinator.analyze_photo({'path': str(self.path), 'vision': False})
        self.assertTrue(result['ok'])
        self.assertEqual(result['workflow'], 'photo_review')
        self.assertEqual(set(result['agents']), {'technical_photo', 'context_photo', 'photo_reviewer'})
        self.assertIn('review', result)

    def test_selection_rating_can_accept_artistic_photo_with_technical_issues(self):
        review = PhotoReviewAgent().run({
            'technical': {'overall_score': 4.99, 'focus': {'score': 4.48}, 'exposure': {'score': 3.19}},
            'semantic': {'artistic_score': 7, 'photographer_feedback': 'Buen momento.'},
        }).data
        self.assertEqual(review['selection_rating'], 3)
        self.assertEqual(review['selection_label'], 'aceptada')
        self.assertIn('aceptar', review['recommendation'])

    def test_recoverable_underexposure_is_not_scored_as_rejection(self):
        image = Image.new('RGB', (320, 200), (45, 45, 50))
        image.save(self.path, quality=95)
        result = technical_analysis(self.path)
        self.assertGreaterEqual(result['exposure']['score'], 4)

    def test_noise_prior_is_more_tolerant_for_sony_than_nikon_at_same_iso(self):
        sony, _, _ = _noise_score({'ISO': '6400', 'Make': 'SONY', 'Model': 'ILCE-7M3'})
        nikon, _, _ = _noise_score({'ISO': '6400', 'Make': 'Nikon', 'Model': 'D750'})
        self.assertGreater(sony, nikon)
        self.assertLess(sony, 8)


if __name__ == '__main__':
    unittest.main()
