"""Hồi quy đổi Việt→Anh tại chỗ và tham số/quy trình, stdlib/CPU, không GPU."""
import math
import sys
import unittest
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "colab"))
from prompt_lib import TagIndex, PromptBuilder
from prompt_lib.editing import split_prompt, replace_or_append, convert_tags
from prompt_lib.workflow import (WORKFLOW_PRESETS, workflow_settings, validate_generation,
                                 generation_metadata, seed_at, generation_error)


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = TagIndex(ROOT)
        cls.builder = PromptBuilder(cls.index)

    def test_01_replace_vietnamese_not_append(self):
        for vi in ("áo dài", "ao dai", "ÁO DÀI", unicodedata.normalize("NFD", "áo dài")):
            with self.subTest(vi=vi):
                self.assertEqual(replace_or_append(f"1girl, {vi}, long_hair", "ao_dai", self.index),
                                 "1girl, ao_dai, long_hair")
        self.assertEqual(replace_or_append("1girl, ao_dai", "ao_dai", self.index), "1girl, ao_dai")
        self.assertEqual(replace_or_append("1girl, áo dài, ao_dai, long_hair", "ao_dai", self.index),
                         "1girl, ao_dai, long_hair")
        self.assertEqual(replace_or_append("1girl, very awa", "very awa", self.index), "1girl, very awa")
        self.assertEqual(replace_or_append("1girl, very_awa", "very awa", self.index), "1girl, very awa")

    def test_02_weight_spaces_and_specials_preserved(self):
        source = "<lora:test:0.8>,  (áo dài:1.2)  , custom words, __style__, :3"
        expected = "<lora:test:0.8>,  (ao_dai:1.2)  , custom words, __style__, :3"
        self.assertEqual(replace_or_append(source, "ao_dai", self.index), expected)
        self.assertEqual(replace_or_append("1girl, ", "ao_dai", self.index), "1girl, ao_dai")
        for text in ("((áo dài):1.2)", "( áo dài :1.20 )", "((áo dài:1.2))", "(áo dài:6)"):
            with self.subTest(text=text):
                expected = text.replace("áo dài", "ao_dai")
                self.assertEqual(replace_or_append(text, "ao_dai", self.index), expected)
                self.assertEqual(convert_tags(text, self.index)[0], expected)
        self.assertEqual(replace_or_append("(áo dài:1.2), (ao_dai:1.3)", "ao_dai", self.index),
                         "(ao_dai:1.2), (ao_dai:1.3)")

    def test_03_convert_exact_only(self):
        source = "1girl, áo dài, (tóc dài:1.15), custom words, <lora:test:0.8>, 16:9, ಠ_ಠ"
        result, changes, unknown = convert_tags(source, self.index)
        self.assertEqual(result, "1girl, ao_dai, (long_hair:1.15), custom words, <lora:test:0.8>, 16:9, ಠ_ಠ")
        self.assertIn(("áo dài", "ao_dai"), changes)
        self.assertIn("custom words", unknown)
        self.assertEqual(convert_tags(result, self.index)[0], result)
        self.assertEqual(convert_tags("áo dài, ao_dai, (ao_dai:1.2)", self.index)[0],
                         "ao_dai, (ao_dai:1.2)")
        self.assertEqual(self.index.exact_tag("váy"), "skirt")
        self.assertNotEqual(self.index.exact_tag("vảy"), "skirt")
        self.assertIsNone(self.index.exact_tag("áo d"))  # prefix không được đoán thành áo dài
        # Chỉ bỏ trùng target vừa chuyển, không sửa tag Anh/tên riêng hoặc mục khác.
        self.assertEqual(convert_tags("1girl, 1girl, áo dài, ao_dai, custom words, custom words", self.index)[0],
                         "1girl, 1girl, ao_dai, custom words, custom words")
        english = "hat, bat, may, pokemon, ao_dai, ao_dai"
        self.assertEqual(convert_tags(english, self.index)[0], english)
        self.assertEqual(replace_or_append("hat, hát", "singing", self.index), "hat, singing")
        self.assertEqual(replace_or_append("hát", "hat", self.index), "hát, hat")
        self.assertEqual(self.index.exact_tag(unicodedata.normalize("NFD", "áo dài")), "ao_dai")
        self.assertEqual(self.index.exact_tag("toc dai"), "long_hair")
        self.assertEqual(convert_tags(unicodedata.normalize("NFD", "(áo dài:1.2)"), self.index)[0], "(ao_dai:1.2)")
        for tag in self.index._info:
            expected = tag.replace(" ", "_") if tag.replace(" ", "_") in self.index._info else tag
            self.assertEqual(self.index.exact_tag(tag), expected, f"Không được đổi nghĩa tag Anh {tag}")

    def test_04_split_protected_syntax(self):
        text = "solo, (red, blue:1.2), [a,b:c], <lora:test:0.8>, comma\\,literal"
        parts = split_prompt(text)
        self.assertEqual(len(parts), 5)
        self.assertEqual(",".join(parts), text)
        self.assertEqual(len(split_prompt("<_<, <3, áo dài")), 3)
        self.assertEqual(convert_tags("<_<, <3, áo dài", self.index)[0], "<_<, <3, ao_dai")

    def test_05_builder_unknown_and_user_quality_kept(self):
        result = self.builder.assemble("1girl, unusual custom words, (masterpiece:1.2), newest, rating_general")
        self.assertIn("unusual custom words", result["prompt"])
        self.assertNotIn("unusual_custom_words", result["prompt"])
        self.assertIn("(masterpiece:1.2)", result["prompt"])
        self.assertEqual(result["prompt"].count("masterpiece"), 1)
        result = self.builder.assemble("((áo dài):1.2), (masterpiece), (tóc dài:6), __style__, [a,b:c]")
        self.assertIn("((ao_dai):1.2)", result["prompt"])
        self.assertIn("(long_hair:6)", result["prompt"])
        self.assertIn("__style__", result["prompt"])
        self.assertIn("[a,b:c]", result["prompt"])
        self.assertEqual(result["prompt"].count("masterpiece"), 1)
        self.assertNotIn("((ao_dai):1.2)", result["unresolved"])
        result = self.builder.assemble("(very awa:1.2)")
        self.assertEqual(result["prompt"].replace("_", " ").count("very awa"), 1)

    def test_06_model_aware_modes(self):
        fp16 = {"steps": 25, "cfg_scale": 6, "sampler_name": "Euler a", "hr_second_pass_steps": 20}
        turbo = {**fp16, "steps": 10, "cfg_scale": 1, "hr_second_pass_steps": 10}
        for label, mode in WORKFLOW_PRESETS.items():
            f, t = workflow_settings(label, fp16), workflow_settings(label, turbo)
            self.assertEqual(f[0], 18 if mode == "draft" else 25)
            self.assertEqual(t[0:2], (10, 1))
            self.assertEqual(t[5], 10)
            self.assertEqual(f[3], mode == "final")
        self.assertEqual(workflow_settings("Hoàn thiện — Hires 1.5×", fp16, "DPM++ 2M Karras")[2],
                         "DPM++ 2M Karras")

    def test_07_api_scheduler_and_clip_options(self):
        for name, expected in {"DPM++ 2M Karras": "DPM++ 2M", "DPM++ 2M SDE Karras": "DPM++ 2M SDE",
                               "DPM++ 3M SDE Karras": "DPM++ 3M SDE"}.items():
            body = self.builder.payload("landscape", "", {"sampler_name": name, "enable_hr": False})
            self.assertEqual(body["sampler_name"], expected)
            self.assertEqual(body["scheduler"], "Karras")
            self.assertNotIn("clip_skip", body)
            self.assertEqual(body["override_settings"]["clip_stop_at_last_layers"], 2)
            self.assertNotIn("hr_upscaler", body)

    def test_08_bad_values_rejected_before_request(self):
        base = self.builder.payload("landscape", "", {"enable_hr": False})
        for key, value in (("cfg_scale", math.nan), ("cfg_scale", math.inf), ("seed", -2),
                           ("seed", 1.5), ("width", 833), ("steps", 0), ("n_iter", 20)):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_generation({**base, key: value})
        hires = self.builder.payload("landscape", "", {"width": 1536, "height": 1536, "enable_hr": True})
        with self.assertRaises(ValueError):
            validate_generation(hires)
        self.assertEqual(validate_generation({**base, "batch_size": 1, "n_iter": 4})["n_iter"], 4)

    def test_09_seed_state_per_image_and_grid(self):
        payload = self.builder.payload("landscape", "")
        meta = generation_metadata({"seed": 10, "all_seeds": [10, 11], "index_of_first_image": 1}, payload, 3)
        self.assertIsNone(seed_at(meta, 0))
        self.assertEqual(seed_at(meta, 1), 10)
        self.assertEqual(seed_at(meta, 2), 11)
        self.assertIsNone(seed_at(meta, 3))
        self.assertIsNone(seed_at(meta, -1))
        meta = generation_metadata({"all_seeds": [None, 12, "13"]}, payload, 3)
        self.assertIsNone(seed_at(meta, 0))
        self.assertEqual(seed_at(meta, 1), 12)
        self.assertIsNone(seed_at(meta, 2))

    def test_10_oom_error_help_without_raw_private_details(self):
        error = ValueError("CUDA out of memory; SECRET_PROMPT")
        message = generation_error(error)
        self.assertIn("Hết VRAM", message)
        self.assertNotIn("SECRET_PROMPT", message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
