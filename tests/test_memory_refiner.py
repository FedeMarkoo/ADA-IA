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

    def test_deduplicate_known_facts(self):
        self.mem.append_conversation([
            {"role": "user", "text": "Mi correo es usuario@ejemplo.com y recordá que guardo siempre las fotos en /home/fotos"},
            {"role": "assistant", "text": "Entendido."},
        ], session="test_pref_1")
        self.refiner.refine_cycle()

        self.mem.append_conversation([
            {"role": "user", "text": "Mi correo es usuario@ejemplo.com y recordá que guardo siempre las fotos en /home/fotos"},
            {"role": "assistant", "text": "Entendido de nuevo."},
        ], session="test_pref_2")
        res2 = self.refiner.refine_cycle()
        self.assertEqual(res2["extracted_facts"], 0)

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
        for i in range(520):
            self.mem.record_task({"prompt": f"test {i}"}, f"result {i}")

        pruned = self.refiner._prune_old_tasks()
        # purge_tasks keeps up to 500, so 20 must be pruned
        self.assertEqual(pruned, 20)
        remaining = len(self.mem.recent_tasks(limit=1000))
        self.assertEqual(remaining, 500)


if __name__ == "__main__":
    unittest.main()
