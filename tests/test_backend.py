import unittest
from backend import extract_margins, replace_video_argument, validate_margins

REPORT = """Connectors:
35 34 connected HDMI-A-1 330x200 30 34
  props:
  37 left margin:
    flags: range
    values: 0 100
    value: 76
  38 right margin:
    flags: range
    values: 0 100
    value: 76
  39 top margin:
    flags: range
    values: 0 100
    value: 44
  40 bottom margin:
    flags: range
    values: 0 100
    value: 30
44 0 disconnected HDMI-A-2 0x0 0 43
  props:
  37 left margin:
    flags: range
    values: 0 100
    value: 0
CRTCs:
"""

class BackendTests(unittest.TestCase):
    def test_parse(self):
        result = extract_margins(REPORT, "HDMI-A-1")
        self.assertEqual({k: v.value for k, v in result.items()}, {
            "left": 76, "right": 76, "top": 44, "bottom": 30
        })
        self.assertEqual(extract_margins(REPORT, "HDMI-A-2")["left"].value, 0)

    def test_insert(self):
        values = dict(left=76, right=76, top=44, bottom=30)
        self.assertEqual(
            replace_video_argument("console=tty1 rootwait\n", "HDMI-A-1", values),
            "console=tty1 rootwait video=HDMI-A-1:margin_left=76,margin_right=76,margin_top=44,margin_bottom=30\n"
        )

    def test_preserve_mode(self):
        values = dict(left=10, right=11, top=12, bottom=13)
        self.assertEqual(
            replace_video_argument(
                "quiet video=HDMI-A-1:1920x1080@60D,margin_top=44 rootwait\n",
                "HDMI-A-1", values
            ),
            "quiet video=HDMI-A-1:1920x1080@60D,margin_left=10,margin_right=11,margin_top=12,margin_bottom=13 rootwait\n"
        )

    def test_validation(self):
        with self.assertRaises(ValueError):
            validate_margins(dict(left=True, right=0, top=0, bottom=0))
        with self.assertRaises(ValueError):
            validate_margins(dict(left=-1, right=0, top=0, bottom=0))
        with self.assertRaises(ValueError):
            replace_video_argument(
                "video=HDMI-A-1:D video=HDMI-A-1:1920x1080",
                "HDMI-A-1", dict(left=0,right=0,top=0,bottom=0)
            )
