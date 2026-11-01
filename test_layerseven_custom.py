import unittest
import xml.etree.ElementTree as ET
from collections import Counter

from build_layerseven_custom import (
    is_disney_plus_channel,
    is_hbo_epix_channel,
    is_max_channel,
    is_paramount_plus_channel,
    is_tudn_channel,
    match_channels,
    name_variants,
    tokens,
)


class LayerSevenMatchingTest(unittest.TestCase):
    def test_chicago_local_normalizes_to_public_station_name(self):
        variants = name_variants("US: NBC 5 CHICAGO IL (WMAQ) HD")
        self.assertIn("NBC CHICAGO", variants)

    def test_now_prefix_is_ignored(self):
        self.assertEqual(tokens("NOW: SKY CINEMA ACTION"), ["SKY", "CINEMA", "ACTION"])

    def test_network_names_retain_gold_and_plus(self):
        self.assertIn("GOLD", name_variants("UK: GOLD 4K"))
        self.assertIn("AMC PLUS", name_variants("US: AMC PLUS HD"))

    def test_call_sign_matches_broadcast_suffix(self):
        self.assertIn("KNBC", name_variants("US: NBC 4 (KNBC) LOS ANGELES HD"))
        self.assertIn("KNBC", name_variants("KNBC-DT"))

    def test_west_direction_is_not_a_call_sign(self):
        self.assertNotIn("WEST", name_variants("US: NBC UNIVERSO (West)"))

    def test_hbo_and_epix_family_detection(self):
        for name in ("HBO East", "EPIX", "MGM+ Hits", "ScreenPix Action"):
            channel = ET.Element("channel")
            ET.SubElement(channel, "display-name").text = name
            self.assertTrue(is_hbo_epix_channel(channel))
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "PIX 11"
        self.assertFalse(is_hbo_epix_channel(channel))

    def test_paramount_plus_detection_excludes_paramount_network(self):
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "Paramount+ with Showtime"
        self.assertTrue(is_paramount_plus_channel(channel))
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "Paramount Network"
        self.assertFalse(is_paramount_plus_channel(channel))

    def test_disney_plus_detection_excludes_disney_channel(self):
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "Disney+CineHD"
        self.assertTrue(is_disney_plus_channel(channel))
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "Disney Channel"
        self.assertFalse(is_disney_plus_channel(channel))

    def test_max_detection_requires_exact_channel_name(self):
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "Max"
        self.assertTrue(is_max_channel(channel))
        for name in ("Sky Max", "Sony MAX", "Pop Max", "Cinemax"):
            channel = ET.Element("channel")
            ET.SubElement(channel, "display-name").text = name
            self.assertFalse(is_max_channel(channel))

    def test_tudn_detection_excludes_xtra_event_feeds(self):
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "TUDN"
        self.assertTrue(is_tudn_channel(channel))
        from build_layerseven_custom import TUDN_ALIASES
        self.assertIn("MXC: TUDN", TUDN_ALIASES)
        channel = ET.Element("channel")
        ET.SubElement(channel, "display-name").text = "TUDN Xtra 1"
        self.assertFalse(is_tudn_channel(channel))

    def test_unlisted_public_channels_and_aliases_are_excluded(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from build_layerseven_custom import read_xml, write_custom_guide

        root = ET.Element("tv")
        tudn = ET.SubElement(root, "channel", {"id": "tudn"})
        ET.SubElement(tudn, "display-name").text = "TUDN"
        hbo = ET.SubElement(root, "channel", {"id": "hbo"})
        ET.SubElement(hbo, "display-name").text = "HBO East"
        channels = {"tudn": tudn, "hbo": hbo}

        with TemporaryDirectory() as temp_dir:
            summary = write_custom_guide(Path(temp_dir), root, channels, [], [])
            output = read_xml(Path(temp_dir) / "layerseven-custom.xml.gz")

        self.assertEqual([channel.get("id") for channel in output.findall("channel")], ["tudn"])
        names = [node.text for node in output.findall("channel/display-name")]
        self.assertIn("MXC: TUDN", names)
        self.assertNotIn("US: TUDN HD", names)
        self.assertEqual(summary["hbo_epix_channels"], 0)
        self.assertEqual(summary["tudn_aliases"], 1)

    def test_call_sign_extraction_includes_subchannels(self):
        from build_layerseven_custom import panel_call_sign_keys

        self.assertIn("WWAYDT2", panel_call_sign_keys("US: CBS 3 (WWAY-DT2) WILMINGTON HD"))
        self.assertIn("WEVVDT2", panel_call_sign_keys("US: FOX (WEVV2) OWENSBORO HD"))
        self.assertIn("WTXFTV", panel_call_sign_keys("US: FOX WTXF TV"))
        self.assertNotIn("WEST", panel_call_sign_keys("US: NBC UNIVERSO (West)"))
        self.assertEqual(panel_call_sign_keys("US: TWINS FEED"), [])
        self.assertEqual(panel_call_sign_keys("US: DOCTOR WHO 4K"), [])
        self.assertEqual(panel_call_sign_keys("US: KING OF THE HILL 4K"), [])
        self.assertEqual(panel_call_sign_keys("US: WILL & GRACE 4K"), [])

    def test_conservative_network_name_variants(self):
        self.assertIn("NBC SPORTS BAY AREA PLUS", name_variants("US: NBC SPORTS BAY AREA PLU HD"))
        self.assertIn("GLOBAL TORONTO", name_variants("CA EN: GLOBAL NEWS TORONTO HD"))
        self.assertIn("CTV NEWS CHANNEL", name_variants("CA: CTV NEWS NETWORK"))
        self.assertIn("VIAPLAY 1", name_variants("UK: VIAPLAY SPORT 1 4K"))
        self.assertIn("NICK JR", name_variants("UK: NICK JUNIOR"))
        self.assertIn("CBC MONTREAL", name_variants("CBMT - CBC Montréal"))
        self.assertNotIn("ABC LOS ANGELES", name_variants("US: NBC LOS ANGELES"))
        self.assertNotIn("SUPER ECRAN", name_variants("CA FR: SUPER ECRAN 1 HD"))
        self.assertNotIn("NATIONAL GEOGRAPHIC", name_variants("US: NAT GEO HD"))

    def test_explicit_call_sign_overrides_generic_network_match(self):
        def public_channel(channel_id, name):
            channel = ET.Element("channel", {"id": channel_id})
            ET.SubElement(channel, "display-name").text = name
            return channel

        channels = {
            "waco": public_channel("waco", "FOX"),
            "philadelphia": public_channel("philadelphia", "WTXF-DT"),
        }
        programme_counts = Counter({"waco": 500, "philadelphia": 100})
        regions = {channel_id: {"us"} for channel_id in channels}
        inventory = [{
            "country": "US",
            "name": "US| NETWORK HD/4K",
            "channels": ["US: FOX WTXF TV"],
        }]

        matches, unmatched = match_channels(inventory, channels, programme_counts, regions)

        self.assertEqual(unmatched, [])
        self.assertEqual(matches[0]["epg_id"], "philadelphia")
        self.assertEqual(matches[0]["match_method"], "call-sign")

    def test_first_explicit_call_sign_wins(self):
        def public_channel(channel_id, name):
            channel = ET.Element("channel", {"id": channel_id})
            ET.SubElement(channel, "display-name").text = name
            return channel

        channels = {
            "nbc": public_channel("nbc", "WSVW-LD"),
            "abc": public_channel("abc", "WHSV-LD"),
        }
        programme_counts = Counter({"nbc": 89, "abc": 500})
        regions = {channel_id: {"us"} for channel_id in channels}
        inventory = [{
            "country": "US",
            "name": "US| NETWORK HD/4K",
            "channels": ["US: NBC (WSVW/WHSV) HARRISONBURG HD"],
        }]

        matches, unmatched = match_channels(inventory, channels, programme_counts, regions)

        self.assertEqual(unmatched, [])
        self.assertEqual(matches[0]["epg_id"], "nbc")
        self.assertEqual(matches[0]["matched_key"], "WSVW")

    def test_call_sign_match_preserves_exact_subchannel(self):
        def public_channel(channel_id, name):
            channel = ET.Element("channel", {"id": channel_id})
            ET.SubElement(channel, "display-name").text = name
            return channel

        channels = {
            "main": public_channel("main", "KRQE-DT"),
            "fox": public_channel("fox", "KRQE-DT2"),
        }
        programme_counts = Counter({"main": 500, "fox": 100})
        regions = {channel_id: {"us"} for channel_id in channels}
        inventory = [{
            "country": "US",
            "name": "US| FOX HD/4K",
            "channels": ["US: FOX (KRQEDT2) ALBUQUERQUE NEW MEXICO"],
        }]

        matches, unmatched = match_channels(inventory, channels, programme_counts, regions)

        self.assertEqual(unmatched, [])
        self.assertEqual(matches[0]["epg_id"], "fox")
        self.assertEqual(matches[0]["match_method"], "call-sign")

    def test_cw_station_mapping_overrides_generic_match(self):
        def public_channel(channel_id, name):
            channel = ET.Element("channel", {"id": channel_id})
            ET.SubElement(channel, "display-name").text = name
            return channel

        channels = {
            "wsfl": public_channel("wsfl", "WSFL-DT"),
            "cw-miami": public_channel("cw-miami", "US - CW Miami"),
            "national": public_channel("national", "CW"),
        }
        programme_counts = Counter({"wsfl": 100, "cw-miami": 128, "national": 60})
        regions = {channel_id: {"us"} for channel_id in channels}
        inventory = [{
            "country": "US",
            "name": "US| CW HD/4K",
            "channels": ["US: CW 39 HD [MIAMI]", "US: CW NETWORK 4K"],
        }]

        matches, unmatched = match_channels(inventory, channels, programme_counts, regions)

        self.assertEqual(unmatched, [])
        by_name = {match["layerseven_name"]: match for match in matches}
        self.assertEqual(by_name["US: CW 39 HD [MIAMI]"]["epg_id"], "wsfl")
        self.assertEqual(by_name["US: CW NETWORK 4K"]["epg_id"], "national")
        self.assertTrue(all(match["match_method"] == "cw-station" for match in matches))


if __name__ == "__main__":
    unittest.main()
