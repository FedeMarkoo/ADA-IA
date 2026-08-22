import unittest
from ada.infrastructure.persistence.sqlite import Memory
from ada.application.services.memory_refiner import MemoryRefiner


class TestMemoryRefiner(unittest.TestCase):
    def setUp(self):
        self.mem = Memory(":memory:")
        self.config = {
            "memory_refiner_enabled": True,
            "memory_refiner_interval_seconds": 600,
            "memory_max_age_days": 30,
        }
        self.refiner = MemoryRefiner(self.mem, config=self.config)

    def test_extract_knowledge_from_preference(self):
        self.mem.append_conversation([
            {"role": "user", "text": "Mi correo es usuario@ejemplo.com y recordá que guardo siempre las fotos en /home/fotos"},
            {"role": "assistant", "text": "Entendido, recordaré que guardas tus fotos allí."},
        ], session="test_pref")

        res = self.refiner.refine_cycle()
        self.assertGreaterEqual(res["extracted_facts"], 1)

        knowledge = self.mem.knowledge("fotos", limit=5)
        self.assertTrue(any("guardo siempre las fotos en /home/fotos" in k for k in knowledge))

    def test_extract_knowledge_from_user_correction(self):
        self.mem.append_conversation([
            {"role": "user", "text": "No, en realidad la reunión de planeamiento es siempre los martes a las 10"},
            {"role": "assistant", "text": "Perfecto, lo tengo presente."},
        ], session="test_corr")

        res = self.refiner.refine_cycle()
        self.assertGreaterEqual(res["extracted_facts"], 1)

        knowledge = self.mem.knowledge("martes", limit=5)
        self.assertTrue(any("martes a las 10" in k for k in knowledge))

    def test_prune_old_tasks(self):
        for i in range(20):
            self.mem.record_task({"prompt": f"test {i}"}, f"result {i}")
        
        pruned = self.refiner._prune_old_tasks()
        # purge_tasks keeps up to 500
        self.assertIsInstance(pruned, int)


if __name__ == "__main__":
    unittest.main()
