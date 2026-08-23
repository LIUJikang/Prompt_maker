import json
import tempfile
import unittest
from pathlib import Path

from prompt_maker.comfy_client import ComfyUIClient
from prompt_maker.config import Settings
from prompt_maker.schemas import DirectorResult


class ComfyWorkflowTests(unittest.TestCase):
    def test_prepare_image_workflow_injects_prompt_size_and_new_seed(self):
        source = Path("image_z_image_turbo.json")
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow_path = Path(temp_dir) / "image_workflow.json"
            workflow_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            client = ComfyUIClient(
                Settings(comfy_image_workflow=str(workflow_path))
            )

            workflow = client.prepare_image_workflow(
                "A cinematic first frame", width=1344, height=768
            )

        self.assertEqual(
            workflow["57:27"]["inputs"]["text"], "A cinematic first frame"
        )
        self.assertEqual(workflow["57:13"]["inputs"]["width"], 1344)
        self.assertEqual(workflow["57:13"]["inputs"]["height"], 768)
        self.assertIsInstance(workflow["57:3"]["inputs"]["seed"], int)
        json.dumps(workflow)

    def test_prepare_workflow_injects_director_outputs(self):
        source = Path("video_ltx2_5_i2v.json")
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow_path = Path(temp_dir) / "workflow.json"
            workflow_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            client = ComfyUIClient(Settings(comfy_workflow=str(workflow_path)))
            result = DirectorResult.model_validate(
                {
                    "title": "Test",
                    "director_notes_zh": "测试",
                    "creative_intent": "test",
                    "shots": [
                        {
                            "number": 1,
                            "duration_seconds": 6.375,
                            "purpose": "test movement",
                            "timeline": [],
                            "prompt_en": "The camera slowly pushes toward the subject.",
                        }
                    ],
                    "final_prompt_en": "positive prompt",
                    "negative_prompt_en": "negative prompt",
                    "continuity_constraints": [
                        "Preserve the subject's facial geometry and eye color."
                    ],
                    "parameters": {
                        "duration_seconds": 6.375,
                        "fps": 24,
                        "num_frames": 153,
                        "aspect_ratio": "16:9",
                        "shot_mode": "single_take",
                        "motion_intensity": "cinematic",
                    },
                }
            )

            workflow = client.prepare_workflow(image_name="uploaded.png", result=result)

        self.assertEqual(workflow["395"]["inputs"]["image"], "uploaded.png")
        positive = workflow["398:376"]["inputs"]["value"]
        self.assertEqual(positive, "positive prompt")
        self.assertNotIn("Shot 1", positive)
        self.assertEqual(workflow["398:373"]["inputs"]["text"], "negative prompt")
        self.assertEqual(workflow["398:361"]["inputs"]["value"], 24)
        self.assertEqual(workflow["398:378"]["inputs"]["expression"], "153")
        json.dumps(workflow)


if __name__ == "__main__":
    unittest.main()
