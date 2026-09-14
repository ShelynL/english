"""python3 -m unittest tools/test_tools.py -v"""
import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_lesson  # noqa: E402
import parse_vtt  # noqa: E402

ROOT = os.path.dirname(HERE)
SAMPLE_VTT = os.path.join(ROOT, "lessons", "raw", "al_mercato_it.vtt")
SAMPLE_LESSON = os.path.join(ROOT, "lessons", "raw", "al_mercato_lesson.json")


class ParseVttTests(unittest.TestCase):
    def test_rolling_duplicates_and_tags(self):
        vtt = (
            "WEBVTT\nKind: captions\nLanguage: it\n\n"
            "00:00:00.000 --> 00:00:02.000 align:start position:0%\n \n"
            "ciao<00:00:00.500><c> a</c><00:00:01.000><c> tutti</c>\n\n"
            "00:00:02.000 --> 00:00:02.010 align:start position:0%\nciao a tutti\n \n\n"
            "00:00:02.010 --> 00:00:04.000 align:start position:0%\nciao a tutti\n"
            "come<00:00:02.500><c> state?</c>\n\n"
        )
        got = parse_vtt.parse_vtt_text(vtt)
        self.assertEqual(got, [{"t": "00:00", "it": "ciao a tutti"}, {"t": "00:02", "it": "come state?"}])

    def test_entities_and_hours(self):
        vtt = "WEBVTT\n\n01:02:03.000 --> 01:02:05.000\nS&igrave;,&nbsp;va bene.\n\n"
        got = parse_vtt.parse_vtt_text(vtt)
        self.assertEqual(got, [{"t": "01:02:03", "it": "Sì, va bene."}])

    def test_mm_ss_timestamps_and_cue_numbers(self):
        vtt = "WEBVTT\n\n1\n00:05.000 --> 00:07.000\nBuongiorno.\n\n2\n00:07.000 --> 00:09.000\nCome va?\n\n"
        got = parse_vtt.parse_vtt_text(vtt)
        self.assertEqual([e["t"] for e in got], ["00:05", "00:07"])
        self.assertEqual([e["it"] for e in got], ["Buongiorno.", "Come va?"])

    def test_merge_sentences(self):
        frags = [{"t": "00:00", "it": "Vorrei un chilo"}, {"t": "00:02", "it": "di pomodori."},
                 {"t": "00:04", "it": "Quanto costano?"}]
        got = parse_vtt.merge_sentences(frags)
        self.assertEqual(got, [{"t": "00:00", "it": "Vorrei un chilo di pomodori."},
                               {"t": "00:04", "it": "Quanto costano?"}])

    def test_sample_file(self):
        got = parse_vtt.merge_sentences(parse_vtt.parse_vtt(SAMPLE_VTT))
        self.assertEqual(len(got), 16)
        joined = " ".join(e["it"] for e in got)
        self.assertNotIn("<", joined)
        self.assertNotIn("&", joined)
        self.assertEqual(got[0]["it"], "Buongiorno signora, cosa desidera oggi?")


class BuildLessonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SAMPLE_LESSON, encoding="utf-8") as f:
            cls.lesson = json.load(f)
        with open(build_lesson.DEFAULT_TEMPLATE, encoding="utf-8") as f:
            cls.template = f.read()

    def bad(self, mutate, msg_part):
        lesson = copy.deepcopy(self.lesson)
        mutate(lesson)
        with self.assertRaises(build_lesson.LessonError) as cm:
            build_lesson.validate(lesson)
        self.assertIn(msg_part, str(cm.exception))

    def test_sample_valid(self):
        build_lesson.validate(self.lesson)

    def test_wrong_sentence_count(self):
        self.bad(lambda l: l["sentences"].append(l["sentences"][0]), "sentences 必须恰好 6")

    def test_wrong_blank_count(self):
        seven = copy.deepcopy(self.lesson); seven["blanks"].pop()
        build_lesson.validate(seven)  # 7 个仍合法
        self.bad(lambda l: l.__setitem__("blanks", l["blanks"][:5]), "blanks 必须 6-8")
        self.bad(lambda l: l["blanks"].extend(["oggi", "grazie"]), "blanks 必须 6-8")

    def test_blank_not_in_text(self):
        self.bad(lambda l: l["blanks"].__setitem__(0, "formaggio"), "找不到")

    def test_distractor_in_text(self):
        self.bad(lambda l: l["distractors"].__setitem__(0, "chilo"), "出现在原文里")

    def test_mcq_answer_range(self):
        self.bad(lambda l: l["mcqs"][0].__setitem__("a", 5), "mcqs[0].a")

    def test_fill_segments(self):
        fill = build_lesson.build_fill(self.lesson["sentences"], self.lesson["blanks"])
        holes = [p for seg in fill for p in seg if isinstance(p, dict)]
        self.assertEqual(len(holes), 8)
        self.assertEqual(sorted(h["i"] for h in holes), list(range(8)))
        self.assertEqual({h["a"].lower() for h in holes}, {b.lower() for b in self.lesson["blanks"]})
        # "chilo" 只挖第一次出现 (第 2 句), 第 3 句 "al chilo?" 保持原样
        third_text = "".join(p if isinstance(p, str) else "_" for p in fill[2])
        self.assertEqual(third_text, "Quanto _ al chilo?")

    def test_render_has_data_and_escapes(self):
        lesson = copy.deepcopy(self.lesson)
        lesson["meta"]["title"] = 'Titolo <b>"x"</b>'
        lesson["vocab"][0]["mean"] = "含 </script> 的释义"
        out = build_lesson.render(lesson, self.template)
        self.assertIn("const sentences = [", out)
        self.assertIn("<title>Titolo &lt;b&gt;&quot;x&quot;&lt;/b&gt;</title>", out)
        self.assertNotIn("</script> 的释义", out)
        self.assertIn("<\\/script> 的释义", out)
        for ph in ("{{TITLE}}", "{{EYEBROW}}", "{{TAGS}}", "/*__LESSON_DATA__*/"):
            self.assertNotIn(ph, out)


if __name__ == "__main__":
    unittest.main()
