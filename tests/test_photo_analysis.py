import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw

from mcps.photography.analyzer import _noise_score, run, technical_analysis
from ada.agents.coordinator import MultiAgentCoordinator
from ada.agents.photo_agents import PhotoReviewAgent
from mcps.photography.batch import run as select_photo_batch


class PhotoAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "concert.jpg"
        image = Image.new("RGB", (320, 200), (20, 20, 24))
        draw = ImageDraw.Draw(image)
        draw.rectangle((30, 30, 120, 170), fill=(220, 40, 40))
        draw.line((0, 180, 320, 20), fill=(255, 255, 255), width=4)
        image.save(self.path, quality=95)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_technical_analysis_returns_scores(self):
        result = technical_analysis(self.path)
        self.assertEqual(result["orientation"], "landscape")
        self.assertIn("focus", result)
        self.assertIn("exposure", result)
        self.assertGreaterEqual(result["overall_score"], 0)
        self.assertLessEqual(result["overall_score"], 10)

    def test_skill_works_without_vision_model(self):
        result = run({"path": str(self.path), "vision": False})
        self.assertTrue(result["ok"])
        self.assertNotIn("error", result)

    def test_missing_image_is_reported(self):
        result = run({"path": str(Path(self.tempdir.name) / "missing.jpg"), "vision": False})
        self.assertEqual(result["error"], "image not found")

    def test_all_skills_are_loaded_recursively(self):
        from ada.mcps.manager import MCPManager
        tools = [t["name"] for t in MCPManager().list_tools()]
        self.assertIn("photography.analyze_photo", tools)

    def test_multi_agent_photo_workflow(self):
        coordinator = MultiAgentCoordinator({"agent_max_workers": 2})
        result = coordinator.analyze_photo({"path": str(self.path), "vision": False})
        self.assertTrue(result["ok"])
        self.assertEqual(result["workflow"], "photo_review")
        self.assertEqual(set(result["agents"]), {"technical_photo", "context_photo", "photo_reviewer"})
        self.assertIn("review", result)

    def test_selection_rating_can_accept_artistic_photo_with_technical_issues(self):
        review = (
            PhotoReviewAgent()
            .run(
                {
                    "technical": {"overall_score": 4.99, "focus": {"score": 4.48}, "exposure": {"score": 3.19}},
                    "semantic": {"artistic_score": 7, "photographer_feedback": "Buen momento."},
                }
            )
            .data
        )
        self.assertEqual(review["selection_rating"], 3)
        self.assertEqual(review["selection_label"], "aceptada")
        self.assertIn("aceptar", review["recommendation"])

    def test_recoverable_underexposure_is_not_scored_as_rejection(self):
        image = Image.new("RGB", (320, 200), (45, 45, 50))
        image.save(self.path, quality=95)
        result = technical_analysis(self.path)
        self.assertGreaterEqual(result["exposure"]["score"], 4)

    def test_noise_prior_is_more_tolerant_for_sony_than_nikon_at_same_iso(self):
        sony, _, _ = _noise_score({"ISO": "6400", "Make": "SONY", "Model": "ILCE-7M3"})
        nikon, _, _ = _noise_score({"ISO": "6400", "Make": "Nikon", "Model": "D750"})
        self.assertGreater(sony, nikon)
        self.assertLess(sony, 8)

    def test_extreme_iso_and_borderline_focus_cannot_be_accepted_by_artistic_score_alone(self):
        review = (
            PhotoReviewAgent()
            .run(
                {
                    "technical": {
                        "overall_score": 5.45,
                        "focus": {"score": 5.52},
                        "exposure": {"score": 6.13},
                        "noise": {"score": 3.7, "iso": 25600},
                    },
                    "semantic": {"artistic_score": 8.0, "photographer_feedback": "Momento válido."},
                }
            )
            .data
        )
        self.assertEqual(review["selection_rating"], 2)
        self.assertIn("ruido", " ".join(review["issues"]))

    def test_batch_selection_scans_and_returns_shortlist_without_deleting(self):
        folder = Path(self.tempdir.name) / "batch"
        folder.mkdir()
        for index in range(3):
            (folder / f"frame_{index}.jpg").write_bytes(self.path.read_bytes())
        result = select_photo_batch({"path": str(folder), "workers": 1, "vision": False})
        self.assertTrue(result["ok"])
        self.assertEqual(result["scanned"], 3)
        self.assertEqual(result["completed"], 3)
        self.assertTrue(all((folder / f"frame_{index}.jpg").exists() for index in range(3)))

    def test_batch_selection_can_write_lightroom_xmp_status_and_rating(self):
        folder = Path(self.tempdir.name) / "xmp_batch"
        folder.mkdir()
        for index in range(2):
            (folder / f"frame_{index}.jpg").write_bytes(self.path.read_bytes())
        result = select_photo_batch({"path": str(folder), "workers": 1, "vision": False, "write_xmp": True})
        self.assertEqual(len(result["xmp_written"]), 2)
        xmp = (folder / "frame_0.xmp").read_text(encoding="utf-8")
        self.assertIn("ada:Status=", xmp)
        self.assertIn("xmp:Rating=", xmp)
        self.assertIn("xmpDM:good=", xmp)
        ET.parse(folder / "frame_0.xmp")

    def test_batch_can_repair_existing_xmp_without_photo_analysis(self):
        folder = Path(self.tempdir.name) / "repair_batch"
        folder.mkdir()
        (folder / "frame_0.xmp").write_text(
            '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmlns:ada="https://ada.local/ns/1.0/" ada:Status="Rechazada" ada:Score="2.5" xmp:Rating="0"/></rdf:RDF></x:xmpmeta>',
            encoding="utf-8",
        )
        result = select_photo_batch({"path": str(folder), "repair_xmp": True})
        self.assertEqual(result["repaired_count"], 1)
        self.assertIn('xmpDM:good="False"', (folder / "frame_0.xmp").read_text(encoding="utf-8"))

    def test_burst_label_is_yellow(self):
        folder = Path(self.tempdir.name) / "burst_batch"
        folder.mkdir()
        for name in ("_DSC4740.ARW", "_DSC4741.ARW"):
            (folder / name).write_bytes(self.path.read_bytes())
        result = select_photo_batch({"path": str(folder), "workers": 1, "vision": False, "write_xmp": True})
        self.assertEqual(result["burst_count"], 2)
        self.assertIn('xmp:Label="Amarillo"', (folder / "_DSC4740.xmp").read_text(encoding="utf-8"))

    def test_repair_keeps_user_labeled_winner_in_burst(self):
        from mcps.photography.xmp import write_photo_xmp

        folder = Path(self.tempdir.name) / "burst_repair"
        folder.mkdir()
        rejected = folder / "RECH__DSC5258.ARW"
        selected = folder / "OK__DSC5259.ARW"
        rejected.write_bytes(self.path.read_bytes())
        selected.write_bytes(self.path.read_bytes())
        write_photo_xmp(rejected, "Seleccionada", 3, 6.9, "previous")
        write_photo_xmp(selected, "Seleccionada", 3, 6.8, "previous")
        result = select_photo_batch({"path": str(folder), "repair_xmp": True, "mark_bursts": True})
        self.assertEqual(len(result["burst_duplicates_rejected"]), 1)
        rejected_xmp = (folder / "RECH__DSC5258.xmp").read_text(encoding="utf-8")
        selected_xmp = (folder / "OK__DSC5259.xmp").read_text(encoding="utf-8")
        self.assertIn('ada:Status="Rechazada"', rejected_xmp)
        self.assertIn('xmp:Label="Amarillo"', rejected_xmp)
        self.assertIn('ada:Status="Seleccionada"', selected_xmp)
        self.assertIn('xmp:Label="Amarillo"', selected_xmp)


if __name__ == "__main__":
    unittest.main()
