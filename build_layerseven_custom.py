#!/usr/bin/env python3
"""Build a LayerSeven-specific XMLTV alias guide from the public channel lineup."""

from __future__ import annotations

import argparse
import copy
import difflib
import gzip
import hashlib
import json
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_PLAIN_XML_BYTES = 90 * 1024 * 1024
REGION_GUIDES = {
    "US": ("us", "sports", "chicago"),
    "CA": ("ca", "sports"),
    "UK": ("gb",),
    "HR": ("sports",),
    "TS": ("sports",),
}
QUALITY_TOKENS = {
    "4K", "8K", "UHD", "FHD", "HD", "SD", "HEVC", "RAW", "VIP",
    "3840P", "2160P", "1080P", "720P", "H265", "H264",
}
STATE_TOKENS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI",
    "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
    "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
    "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

# Numbered CW feeds often retain legacy station branding. City-only feeds use
# the current local CW affiliate; subchannels without public listings fall back
# to the national CW schedule.
CW_FEED_STATIONS = {
    "US: CW ATLANTA HD": "WPCH-DT",
    "US: CW CHICAGO HD": "WCIU-DT",
    "US: CW PHILADELPHIA HD": "WPHL-DT",
    "US: CW PITTSBURGH": "WPNT-DT",
    "US: CW SACRAMENTO HD": "KQCA-DT",
    "US: CW SAN FRANCISCO HD": "KRON-DT",
    "US: CW SEATTLE HD": "KUNS-DT",
    "US: CW TAMPA BAY HD": "WTTA-DT",
    "US: CW 21 SHREVEPORT LA (KPXJ) HD": "KPXJ-DT",
    "US: CW 21 BIRMINGHAM AL (WTTO) HD": "WTTO-DT",
    "US: CW 39 (WSFL-TV) Miami (A) HD": "WSFL-DT",
    "US: CW HD": "CW",
    "US: CW (KOCB)": "KOCB-DT",
    "US: CW (KSTW)": "KSTW-DT",
    "US: CW (KVCW)": "KVCW-DT",
    "US: CW (WKBD)": "WKBD-DT",
    "US: CW (WNUV)": "WNUV-DT",
    "US: CW (WPCW)": "WPKD-DT",
    "US: CW (WPSG)": "WPSG-DT",
    "US: CW NETWORK 4K": "CW",
    "US: CW (WUCW)": "WUCW-DT",
    "US: CW 5 HD [PALM SPRINGS]": "KESQ-DT3",
    "US: CW 8  HD [MISSOULA]": "KPAX-DT2",
    "US: CW PIX 11 HD": "WPIX-DT",
    "US: CW 11 HD [SEATTLE]": "KSTW-DT",
    "US: CW 13 HD [LAREDO]": "CW",
    "US: CW 17 HD [JACKSONVILLE]": "WCWJ-DT",
    "US: CW 18 HD [DAYTONA BEACH]": "WKCF-DT",
    "US: CW 18 HD [CHARLOTTE]": "WCCB-DT",
    "US: CW 18 HD [MILWAUKEE]": "WVTV-DT",
    "US: CW 18 HD [ORLANDO]": "WKCF-DT",
    "US: CW 19 HD [TULSA]": "KQCW-DT",
    "US: CW 20 HD GREENSBORO/HIGH POINT/WINSTON-SALEM AREA": "WCWG-DT",
    "US: CW 22 HD [MONTGOMERY]": "WBMM-DT",
    "US: CW 23 HD [LANCASTER PA]": "CW",
    "US: CW 23 BUFFALO NY (WNLO)": "WNLO-DT",
    "US: CW 26 HD [CHICAGO]": "WCIU-DT",
    "US: CW 29 HD [KANSAS CITY]": "KCWE-DT",
    "US: CW 33 HD [LAS VEGAS]": "KVCW-DT",
    "US: CW 35 HD [SAN ANTONIO]": "KMYS-DT",
    "US: CW 36 (KICU) SAN JOSE HD": "KICU-DT",
    "US: CW 44 HD [ST. PETERSBURG]": "WTOG-DT",
    "US: CW 39 HD [MIAMI]": "WSFL-DT",
    "US: CW 39 (KIAH) Houston HD": "KIAH-DT",
    "US: CW 44 HD [SAN FRANCISCO]": "KPYX-DT",
    "US: CW 44 HD [TAMPA]": "WTOG-DT",
    "US: CW 46 HD [FORT MYERS]": "WXCW-DT",
    "US: CW 50 HD [DETROIT]": "WKBD-DT",
    "US: CW 53 HD [COLUMBUS]": "WWHO-DT",
    "US: CW 54 HD [BALTIMORE]": "WNUV-DT",
    "US: CW 56 HD [BOSTON]": "WLVI-DT",
    "US: CW 57 [PHILADELPHIA]": "WPSG-DT",
    "US: CW 58 HD [LOUISVILLE]": "WBKI-DT",
    "US: CW 58 [NASHVILLE]": "WNAB-DT",
    "US: CW 69 HD [ATLANTA]": "WUPA-DT",
    "CA: CW 11": "KSTW-DT",
}

TUDN_ALIASES = {
    "TUDN",
    "US: TUDN",
    "US: TUDN HD",
    "US: TUDN FHD",
    "US: TUDN 4K",
    "US: TUDN NETWORK",
    "US: TUDN NETWORK HD",
    "US: UNIVISION TDN",
    "US: UNIVISION DEPORTES",
    "US: UNIVISION DEPORTES NETWORK",
    "CA: TUDN",
    "CA: TUDN HD",
    "MXC: TUDN",
    "LAT: TUDN",
    "LAT: TUDN HD",
}

# Legacy FOX Sports names with confirmed current listings. Other regional or
# discontinued feeds stay unmatched rather than inheriting the empty 4K guide.
FOX_SPORTS_OVERRIDES = {
    "FOX SPORTS 1": "FOX SPORTS 1 US HD",
    "FOX SPORTS 2": "FOX SPORTS 2 US HD",
    "FOX SPORTS DEPORTES": "FOX DEPORTES HD",
    "FOX SPORTS DETROIT": "FANDUEL SPORTS NETWORK DETROIT HD",
    "FOX SPORTS FLORIDA": "FANDUEL SPORTS NETWORK FLORIDA HD",
    "FOX SPORTS SUN": "FANDUEL SPORTS NETWORK SUN HD",
    "FOX SPORTS OHIO": "FANDUEL SPORTS NETWORK OHIO HD",
    "FOX SPORTS NORTH": "FANDUEL SPORTS NETWORK NORTH HD",
    "FOX SPORTS WISCONSIN": "FANDUEL SPORTS NETWORK WISCONSIN HD",
    "FOX SPORTS MIDWEST": "FANDUEL SPORTS NETWORK MIDWEST HD",
    "FOX SPORTS MID WEST": "FANDUEL SPORTS NETWORK MIDWEST HD",
    "FOX SPORTS SOUTHWEST": "FANDUEL SPORTS NETWORK SOUTHWEST HD",
    "FOX SPORTS SOUTH WEST": "FANDUEL SPORTS NETWORK SOUTHWEST HD",
    "FOX SPORTS SOUTH": "FANDUEL SPORTS NETWORK SOUTH HD",
    "FOX SPORTS SOUTHEAST": "FANDUEL SPORTS NETWORK SOUTHEAST HD",
    "FOX SPORTS SOUTH EAST": "FANDUEL SPORTS NETWORK SOUTHEAST HD",
    "FOX SPORTS WEST": "FANDUEL SPORTS NETWORK WEST HD",
    "FOX SPORTS OKLAHOMA": "FANDUEL SPORTS NETWORK OKLAHOMA",
}

TSN_SPORTS_OVERRIDES = {
    "TSN": "TSN 1",
    "TSN 1": "TSN 1",
    "TSN 2": "TSN 2",
    "TSN 3": "TSN 3",
    "TSN 4": "TSN 4",
    "TSN 5": "TSN 5",
    "TSN SPORT 1": "TSN 1",
    "TSN SPORT 2": "TSN 2",
    "TSN SPORT 3": "TSN 3",
    "TSN SPORT 4": "TSN 4",
    "TSN SPORT 5": "TSN 5",
}


def fox_sports_key(value: str) -> str:
    return " ".join(token for token in tokens(value) if token not in QUALITY_TOKENS)


def read_xml(path: Path) -> ET.Element:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        return ET.parse(stream).getroot()


def tokens(value: str) -> list[str]:
    value = unicodedata.normalize("NFKD", value).upper().replace("&", " AND ")
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"(?<=[A-Z])(FHD|UHD|HD|SD|4K|8K)$", r" \1", value)
    value = re.sub(r"^(?:(?:US|UK|CA)(?:\s+(?:FR|EN))?|NOW)\s*[:|\-]\s*", "", value)
    return re.findall(r"[A-Z0-9]+", value)


NUMBER_WORDS = {
    "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5",
    "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9", "TEN": "10",
}
TOKEN_ALIASES = {
    "DOCUMENTRY": "DOCUMENTARY",
    "TELEVISION": "TV",
    "PLU": "PLUS",
    "PHILADELFIA": "PHILADELPHIA",
    "NICKELDEON": "NICKELODEON",
    "INVERSTIGATION": "INVESTIGATION",
    "ATLENTIC": "ATLANTIC",
    "CALAGRY": "CALGARY",
    "JUNIOR": "JR",
    "SPORT": "SPORTS",
}
LOCAL_STATION_OVERRIDES_PATH = Path(__file__).with_name("local-station-overrides.json")
LOCAL_STATION_OVERRIDES = (
    json.loads(LOCAL_STATION_OVERRIDES_PATH.read_text())
    if LOCAL_STATION_OVERRIDES_PATH.exists()
    else {}
)


def canonical_call_sign(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def panel_call_sign_keys(value: str) -> list[str]:
    """Extract explicit US/CA call signs, including digital subchannels."""
    cleaned = unicodedata.normalize("NFKC", value).upper()
    pattern = r"[KWC][A-Z]{2,3}(?:-?(?:DT|LD|CD|TV))?\d*"
    found = []
    for content in re.findall(r"\(([^)]+)\)", cleaned):
        found.extend(re.findall(rf"\b{pattern}\b", content))
    network_call_signs = re.finditer(
        r"\b(?:NBC|FOX|CBS|ABC|TELEMUNDO)\s*\(?\s*([KW][A-Z]{2,3}(?:-?(?:DT|LD|CD|TV))?\d*)\b",
        cleaned,
    )
    found.extend(match.group(1) for match in network_call_signs)
    keys = []
    for call_sign in found:
        if call_sign in {"WEST", "EAST"}:
            continue
        base = re.match(r"[KWC][A-Z]{2,3}", call_sign).group()
        suffix = call_sign[len(base):]
        candidates = [call_sign]
        if suffix.isdigit():
            candidates.append(f"{base}DT{suffix}")
        elif not suffix:
            candidates.extend([f"{base}DT", f"{base}TV"])
        for candidate in candidates:
            key = canonical_call_sign(candidate)
            if key not in keys:
                keys.append(key)
    return keys


def name_variants(value: str) -> list[str]:
    """Return conservative exact-match keys, most specific first."""
    raw = unicodedata.normalize("NFKC", value)
    cleaned = raw.upper()
    call_sign = re.search(r"\(([KWC][A-Z0-9]{2,3})\)", raw)
    without_call = re.sub(r"\(([KW][A-Z0-9]{2,3})\)", " ", cleaned)
    without_call = re.sub(r"\b[KW][A-Z]{2,3}\b", " ", without_call)
    variants: list[str] = []
    sources = [cleaned, without_call, cleaned.split("/")[0], without_call.split("/")[0]]
    for source in sources:
        base = [token for token in tokens(source) if token not in QUALITY_TOKENS]
        base = [NUMBER_WORDS.get(token, TOKEN_ALIASES.get(token, token)) for token in base]
        preserve_digits = base[:2] == ["SUPER", "ECRAN"]
        candidates = [
            base,
            base[2:] if base[:2] == ["U", "AND"] else base,
            [token for token in base if token not in {"UK", "USA", "CANADA", "UKTV"}],
            [token for token in base if token not in STATE_TOKENS],
            [] if preserve_digits else [token for token in base if not token.isdigit()],
            [] if preserve_digits else [token for token in base if not token.isdigit() and token not in STATE_TOKENS],
        ]
        if len(base) > 1 and base[-1] == "TV":
            candidates.append(base[:-1])
        if len(base) > 2 and base[:2] == ["GLOBAL", "NEWS"]:
            candidates.append([base[0], *base[2:]])
        if base == ["CTV", "NEWS", "NETWORK"]:
            candidates.append(["CTV", "NEWS", "CHANNEL"])
        if base == ["CBC", "NEWS"]:
            candidates.append(["CBC", "NEWS", "NETWORK"])
        if base == ["BNN"]:
            candidates.append(["BUSINESS", "NEWS", "NETWORK"])
        if base == ["RDI"]:
            candidates.append(["ICI", "RDI"])
        if base == ["NICK"]:
            candidates.append(["NICKELODEON"])
        if base[:2] == ["TELE", "TOON"]:
            candidates.append(["TELETOON", *base[2:]])
        if base == ["YTV", "E"]:
            candidates.append(["YTV", "EAST"])
        if base and base[0] == "FAMILY" and "CHANNEL" not in base:
            candidates.append(["FAMILY", "CHANNEL", *base[1:]])
        if base == ["DIY"]:
            candidates.append(["DIY", "NETWORK"])
        if base == ["VISION"]:
            candidates.append(["VISION", "TV"])
        if base[:2] == ["SERIES", "PLUS"]:
            candidates.append(["SERIES", *base[2:]])
        if base == ["FOX", "NEWS"]:
            candidates.append(["FOX", "NEWS", "CHANNEL"])
        if base == ["CBS", "SPORTS", "USA"]:
            candidates.append(["CBS", "SPORTS", "NETWORK"])
        if base[:2] == ["NBC", "GOLF"]:
            candidates.append(base[1:])
        if base == ["HISTORY", "2"]:
            candidates.append(["H2"])
        if base == ["E", "ENTERTAINMENT"]:
            candidates.append(["E"])
        if base and base[0] == "ITV1":
            candidates.append(["ITV", *base[1:]])
        if base and base[0] == "VIAPLAY" and "SPORTS" in base:
            candidates.append([token for token in base if token != "SPORTS"])
        if base[:2] == ["SKY", "SPORTS"] and "PL" in base:
            candidates.append([token for token in base if token != "PL"] + ["PREMIER", "LEAGUE"])
        if (
            len(base) > 1
            and re.fullmatch(r"[KWC][A-Z]{2,3}", base[0])
            and base[1] in {"NBC", "CBS", "ABC", "FOX", "CBC", "CTV", "GLOBAL", "CW"}
        ):
            candidates.append(base[1:])
        if (
            base
            and re.fullmatch(r"[KWC][A-Z0-9]{2,3}", base[0])
            and (len(base) == 1 or base[1] in {"DT", "LD", "CD", "TV"})
        ):
            candidates.append([base[0]])
        for candidate in candidates:
            key = " ".join(candidate).strip()
            for variant in (key, key.replace(" ", "")):
                if variant and variant not in variants:
                    variants.append(variant)
    if call_sign:
        variants.insert(1, call_sign.group(1))
    return variants


def load_public_channels(guides_dir: Path):
    root = read_xml(guides_dir / "all.xml.gz")
    channels = {channel.get("id"): channel for channel in root.findall("channel")}
    programme_counts = Counter(programme.get("channel") for programme in root.findall("programme"))
    regions: dict[str, set[str]] = defaultdict(set)
    for region in ("us", "ca", "gb", "sports", "chicago"):
        path = guides_dir / f"{region}.xml"
        if not path.exists():
            path = guides_dir / f"{region}.xml.gz"
        regional_root = read_xml(path)
        for channel in regional_root.findall("channel"):
            regions[channel.get("id")].add(region)
    return root, channels, programme_counts, regions


def add_fubo_xumo_guide(root, channels, programme_counts, regions, days=4):
    """Add the public Fubo Sports Network schedule from Xumo."""
    channel_id = "xumo.fuboSportsNetwork"
    xumo_channel_id = 99951548
    programmes = {}
    today = datetime.now(timezone.utc).date()
    for day in range(days):
        date = (today + timedelta(days=day)).strftime("%Y%m%d")
        for segment in range(4):
            url = (
                f"https://valencia-app-mds.xumo.com/v2/epg/10006/{date}/{segment}.json"
                "?limit=50&offset=50&f=asset.title&f=asset.descriptions"
            )
            request = urllib.request.Request(url, headers={"User-Agent": "LayerSeven-EPG/1.0"})
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.load(response)
            channel_data = next(
                (item for item in payload.get("channels", []) if item.get("channelId") == xumo_channel_id),
                None,
            )
            if not channel_data:
                continue
            assets = payload.get("assets", {})
            for item in channel_data.get("schedule", []):
                asset = assets.get(item.get("assetId"), {})
                key = (item["start"], item["end"], item["assetId"])
                programmes[key] = (item, asset)
    if not programmes:
        return 0

    channel = ET.Element("channel", {"id": channel_id})
    ET.SubElement(channel, "display-name").text = "Fubo Sports Network"
    channels[channel_id] = channel
    root.append(channel)
    for start, end, asset_id in sorted(programmes):
        item, asset = programmes[(start, end, asset_id)]
        start_time = datetime.fromisoformat(start).strftime("%Y%m%d%H%M%S %z")
        end_time = datetime.fromisoformat(end).strftime("%Y%m%d%H%M%S %z")
        programme = ET.Element("programme", {
            "channel": channel_id,
            "start": start_time,
            "stop": end_time,
        })
        ET.SubElement(programme, "title", {"lang": "en"}).text = asset.get("title") or "Fubo Sports"
        descriptions = asset.get("descriptions") or {}
        description = descriptions.get("medium") or descriptions.get("small") or descriptions.get("tiny")
        if description:
            ET.SubElement(programme, "desc", {"lang": "en"}).text = description
        root.append(programme)
        programme_counts[channel_id] += 1
    regions[channel_id].update({"us", "sports"})
    return len(programmes)


def build_index(channels, regions):
    index: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for channel_id, channel in channels.items():
        channel_regions = regions.get(channel_id, set())
        for display in channel.findall("display-name"):
            if not display.text:
                continue
            for key in name_variants(display.text):
                for region in channel_regions:
                    index[region][key].add(channel_id)
    return index


def choose_candidate(candidates, programme_counts, regions, allowed_regions):
    def score(channel_id):
        chicago_bonus = 1 if "chicago" in regions.get(channel_id, set()) else 0
        return (programme_counts[channel_id], chicago_bonus, channel_id)

    return max(candidates, key=score)


def match_channels(inventory, channels, programme_counts, regions):
    index = build_index(channels, regions)
    station_index: dict[str, set[str]] = defaultdict(set)
    call_sign_index: dict[str, set[str]] = defaultdict(set)
    for channel_id, channel in channels.items():
        for display in channel.findall("display-name"):
            name = (display.text or "").strip().upper()
            if name:
                station_index[name].add(channel_id)
            if re.fullmatch(r"[KWC][A-Z]{2,3}(?:-?(?:DT|LD|CD|TV))?\d*", name):
                call_sign_index[canonical_call_sign(name)].add(channel_id)
                if not re.search(r"(?:DT|LD|CD|TV)\d", name):
                    base = re.match(r"[KWC][A-Z]{2,3}", name).group()
                    call_sign_index[base].add(channel_id)
    matches = []
    unmatched = []
    subset_blocked = {
        "24", "7", "48HRS", "BUTTON", "CEINMA", "CINEMA", "CINMA", "E", "EAST",
        "EVENT", "EVENTS", "EXTRA", "LIVE", "MAIN", "MIDLANDS", "MOVIES", "NEWS", "NORTH",
        "ONLY", "PEACOCK", "PL", "PLU", "PLUS", "PPV", "RED", "SOUTH", "SPORT", "SPORTS", "STORE",
        "ULTIMATE", "W", "WEST", "WORLD", "XTRA",
    }
    for category in inventory:
        country = category["country"]
        allowed_regions = REGION_GUIDES.get(country, ())
        for layerseven_name in category["channels"]:
            if layerseven_name.lstrip().startswith("#"):
                continue
            found = None
            matched_key = None
            match_method = None
            station_override = LOCAL_STATION_OVERRIDES.get(layerseven_name)
            if station_override:
                has_subchannel = re.search(r"(?:DT|LD|CD|TV)\d", station_override)
                station_key = (
                    canonical_call_sign(station_override)
                    if has_subchannel
                    else re.match(r"[KWC][A-Z]{2,3}", station_override).group()
                )
                candidates = {
                    channel_id
                    for channel_id in call_sign_index.get(station_key, set())
                    if programme_counts[channel_id]
                    and regions.get(channel_id, set()) & set(allowed_regions)
                }
                if candidates:
                    found = choose_candidate(candidates, programme_counts, regions, allowed_regions)
                    matched_key = station_override
                    match_method = "local-station"

            sports_key = fox_sports_key(layerseven_name)
            sports_override = FOX_SPORTS_OVERRIDES.get(sports_key)
            sports_method = "fox-sports"
            if sports_key == "FUBO SPORTS NETWORK":
                sports_override = "FUBO SPORTS NETWORK"
                sports_method = "fubo-sports"
            elif sports_key in TSN_SPORTS_OVERRIDES:
                sports_override = TSN_SPORTS_OVERRIDES[sports_key]
                sports_method = "tsn-sports"
            if sports_override and not found:
                candidates = {
                    channel_id
                    for channel_id in station_index.get(sports_override, set())
                    if programme_counts[channel_id]
                    and (
                        sports_method == "tsn-sports"
                        or regions.get(channel_id, set()) & set(allowed_regions)
                    )
                }
                if candidates:
                    found = choose_candidate(candidates, programme_counts, regions, allowed_regions)
                    matched_key = sports_override
                    match_method = sports_method
            block_generic_sports = sports_key.startswith("FOX SPORTS") or sports_key.startswith("TSN RDS EXTRA")
            variants = [] if block_generic_sports and not found else name_variants(layerseven_name)
            for key in ([] if found else variants):
                candidates = set()
                for region in allowed_regions:
                    candidates.update(index.get(region, {}).get(key, set()))
                if candidates:
                    found = choose_candidate(candidates, programme_counts, regions, allowed_regions)
                    matched_key = key
                    match_method = "exact"
                    break

            # Explicit call signs supplement exact matches and override only generic network names.
            generic_network_keys = {"NBC", "FOX", "CBS", "ABC", "TELEMUNDO"}
            if not found or matched_key in generic_network_keys:
                station_keys = panel_call_sign_keys(layerseven_name)
                candidates = set()
                for key in station_keys:
                    candidates = {
                        channel_id
                        for channel_id in call_sign_index.get(key, set())
                        if programme_counts[channel_id]
                        and regions.get(channel_id, set()) & set(allowed_regions)
                    }
                    if candidates:
                        matched_key = key
                        break
                if candidates:
                    found = choose_candidate(candidates, programme_counts, regions, allowed_regions)
                    match_method = "call-sign"

            # Regional variants may add a city, but not a different brand or service.
            if not found and variants and "+" not in layerseven_name:
                layerseven_tokens = set(variants[0].split())
                first_token = variants[0].split()[0]
                candidates = set()
                candidate_keys = {}
                for region in allowed_regions:
                    for key, channel_ids in index.get(region, {}).items():
                        key_tokens = set(key.split())
                        extra_tokens = layerseven_tokens - key_tokens
                        if (
                            len(key_tokens) >= 2
                            and key_tokens < layerseven_tokens
                            and key.split()[0] == first_token
                            and first_token not in {"ITV", "CTV", "ICI"}
                            and variants[0].split()[:2] != ["NBC", "SPORTS"]
                            and not (extra_tokens & subset_blocked)
                            and not any(char.isdigit() for token in extra_tokens for char in token)
                        ):
                            candidates.update(channel_ids)
                            for channel_id in channel_ids:
                                candidate_keys.setdefault(channel_id, key)
                if candidates:
                    found = min(
                        candidates,
                        key=lambda channel_id: (
                            len(tokens(channels[channel_id].findtext("display-name") or "")),
                            -programme_counts[channel_id],
                            channel_id,
                        ),
                    )
                    matched_key = candidate_keys[found]
                    match_method = "regional-subset"

            # Correct only very close spelling differences; avoid speculative matches.
            if not found and variants and len(variants[0]) >= 6 and country in {"UK", "CA"}:
                keys = {
                    key: region
                    for region in allowed_regions
                    for key in index.get(region, {})
                    if " " in key
                }
                close = difflib.get_close_matches(variants[0], list(keys), n=1, cutoff=0.94)
                if close:
                    matched_key = close[0]
                    candidates = set()
                    for region in allowed_regions:
                        candidates.update(index.get(region, {}).get(matched_key, set()))
                    found = min(
                        candidates,
                        key=lambda channel_id: (
                            len(tokens(channels[channel_id].findtext("display-name") or "")),
                            -programme_counts[channel_id],
                            channel_id,
                        ),
                    )
                    match_method = "close-spelling"

            station_name = CW_FEED_STATIONS.get(layerseven_name)
            if station_name:
                candidates = station_index.get(station_name, set())
                if candidates:
                    found = choose_candidate(candidates, programme_counts, regions, allowed_regions)
                    matched_key = station_name
                    match_method = "cw-station"

            record = {
                "layerseven_name": layerseven_name,
                "category": category["name"],
                "country": country,
            }
            if found:
                epg_channel = channels[found]
                record.update({
                    "epg_id": found,
                    "epg_name": (epg_channel.findtext("display-name") or "").strip(),
                    "matched_key": matched_key,
                    "match_method": match_method,
                })
                matches.append(record)
            else:
                unmatched.append(record)
    return matches, unmatched


def is_hbo_epix_channel(channel):
    names = " ".join(node.text or "" for node in channel.findall("display-name")).upper()
    return any(term in names for term in ("HBO", "EPIX", "MGM+", "SCREENPIX"))


def is_paramount_plus_channel(channel):
    names = " ".join(node.text or "" for node in channel.findall("display-name")).upper()
    return "PARAMOUNT+" in names or "PARAMOUNT PLUS" in names


def is_disney_plus_channel(channel):
    names = " ".join(node.text or "" for node in channel.findall("display-name")).upper()
    return "DISNEY+" in names or "DISNEY PLUS" in names


def is_max_channel(channel):
    return any(
        (node.text or "").strip().upper() == "MAX"
        for node in channel.findall("display-name")
    )


def is_tudn_channel(channel):
    return any(
        (node.text or "").strip().upper() == "TUDN"
        for node in channel.findall("display-name")
    )


def write_custom_guide(guides_dir: Path, root, channels, matches, unmatched):
    aliases: dict[str, list[str]] = defaultdict(list)
    for match in matches:
        aliases[match["epg_id"]].append(match["layerseven_name"])

    lineup_names = {
        record["layerseven_name"] for record in [*matches, *unmatched]
    }
    # Verified directly in the panel's Mexico category, outside the saved regions.
    lineup_names.add("MXC: TUDN")

    premium_channel_ids = {
        channel_id for channel_id, channel in channels.items() if is_hbo_epix_channel(channel)
    }
    paramount_channel_ids = {
        channel_id for channel_id, channel in channels.items() if is_paramount_plus_channel(channel)
    }
    disney_channel_ids = {
        channel_id for channel_id, channel in channels.items() if is_disney_plus_channel(channel)
    }
    max_channel_ids = {
        channel_id for channel_id, channel in channels.items() if is_max_channel(channel)
    }
    tudn_channel_ids = {
        channel_id for channel_id, channel in channels.items() if is_tudn_channel(channel)
    }
    programme_counts = Counter(programme.get("channel") for programme in root.findall("programme"))
    main_mgm = [
        channel_id
        for channel_id in premium_channel_ids
        if any((node.text or "").strip().upper() == "MGM+" for node in channels[channel_id].findall("display-name"))
    ]
    if main_mgm:
        main_mgm_id = max(main_mgm, key=lambda channel_id: (programme_counts[channel_id], channel_id))
        aliases[main_mgm_id].extend(
            alias for alias in ("US: EPIX 4K", "UK: EPIX 4K") if alias in lineup_names
        )
    if tudn_channel_ids:
        main_tudn_id = max(tudn_channel_ids, key=lambda channel_id: (programme_counts[channel_id], channel_id))
        aliases[main_tudn_id].extend(
            alias for alias in sorted(TUDN_ALIASES) if alias in lineup_names
        )

    output = ET.Element("tv", {"generator-info-name": "LayerSeven public-lineup alias guide"})
    # Do not emit public channels or speculative aliases absent from the panel.
    selected = {channel_id for channel_id, names in aliases.items() if names}
    for channel_id in sorted(selected):
        channel = copy.deepcopy(channels[channel_id])
        existing = {(node.text or "").strip() for node in channel.findall("display-name")}
        for alias in sorted(set(aliases[channel_id])):
            if alias not in existing:
                node = ET.SubElement(channel, "display-name")
                node.text = alias
        output.append(channel)

    # TiViMate does not reliably use secondary display-name aliases for local
    # stations. Give each LayerSeven station name its own channel and programmes.
    direct_station_aliases = []
    direct_ids_by_source: dict[str, list[str]] = defaultdict(list)
    seen_direct_aliases = set()
    for match in matches:
        source_id = match["epg_id"]
        public_name = (channels[source_id].findtext("display-name") or "").strip().upper()
        if match["match_method"] not in {"fox-sports", "fubo-sports", "tsn-sports"} and not re.fullmatch(
            r"[KWC][A-Z]{2,3}(?:-?(?:DT|LD|CD|TV))?\d*", public_name
        ):
            continue
        alias = match["layerseven_name"]
        if (source_id, alias) in seen_direct_aliases:
            continue
        seen_direct_aliases.add((source_id, alias))
        digest = hashlib.sha256(f"{source_id}\0{alias}".encode("utf-8")).hexdigest()[:16]
        direct_id = f"layerseven.{digest}"
        direct_station_aliases.append((direct_id, source_id, alias))
        direct_ids_by_source[source_id].append(direct_id)
    for direct_id, source_id, alias in direct_station_aliases:
        direct = ET.Element("channel", {"id": direct_id})
        ET.SubElement(direct, "display-name").text = alias
        for child in channels[source_id]:
            if child.tag != "display-name":
                direct.append(copy.deepcopy(child))
        output.append(direct)

    programme_count = 0
    for programme in root.findall("programme"):
        source_id = programme.get("channel")
        if source_id in selected:
            output.append(copy.deepcopy(programme))
            programme_count += 1
            for direct_id in direct_ids_by_source[source_id]:
                direct_programme = copy.deepcopy(programme)
                direct_programme.set("channel", direct_id)
                output.append(direct_programme)
                programme_count += 1

    nbc_ids = {
        direct_id
        for direct_id, source_id, alias in direct_station_aliases
        if "NBC" in alias.upper()
    }
    nbc_output = ET.Element("tv", {"generator-info-name": "LayerSeven NBC alias guide"})
    for channel in output.findall("channel"):
        if channel.get("id") in nbc_ids:
            nbc_output.append(copy.deepcopy(channel))
    nbc_programme_count = 0
    for programme in output.findall("programme"):
        if programme.get("channel") in nbc_ids:
            nbc_output.append(copy.deepcopy(programme))
            nbc_programme_count += 1
    ET.indent(nbc_output, space="  ")
    nbc_payload = ET.tostring(nbc_output, encoding="utf-8", xml_declaration=True)
    nbc_gzip_path = guides_dir / "layerseven-nbc.xml.gz"
    with gzip.open(nbc_gzip_path, "wb", compresslevel=9) as stream:
        stream.write(nbc_payload)

    ET.indent(output, space="  ")
    payload = ET.tostring(output, encoding="utf-8", xml_declaration=True)
    plain_path = guides_dir / "layerseven-custom.xml"
    gzip_path = guides_dir / "layerseven-custom.xml.gz"
    if len(payload) <= MAX_PLAIN_XML_BYTES:
        plain_path.write_bytes(payload)
        xml_url = "guides/layerseven-custom.xml"
        xml_bytes = len(payload)
    else:
        plain_path.unlink(missing_ok=True)
        xml_url = None
        xml_bytes = 0
    with gzip.open(gzip_path, "wb", compresslevel=9) as stream:
        stream.write(payload)

    mapping_path = guides_dir / "layerseven-custom-mapping.json"
    mapping_path.write_text(json.dumps({
        "matched": matches,
        "unmatched": unmatched,
    }, indent=2, ensure_ascii=False) + "\n")

    return {
        "channels": len(selected) + len(direct_station_aliases),
        "programmes": programme_count,
        "direct_station_aliases": len(direct_station_aliases),
        "hbo_epix_channels": len(premium_channel_ids & selected),
        "paramount_plus_channels": len(paramount_channel_ids & selected),
        "disney_plus_channels": len(disney_channel_ids & selected),
        "max_channels": len(max_channel_ids & selected),
        "tudn_channels": len(tudn_channel_ids & selected),
        "tudn_aliases": len({
            alias
            for channel_id in selected
            for alias in aliases[channel_id]
            if alias in TUDN_ALIASES
        }),
        "cw_layerseven_entries": sum(
            match["match_method"] == "cw-station" for match in matches
        ),
        "matched_layerseven_entries": len(matches),
        "unmatched_layerseven_entries": len(unmatched),
        "xml_url": xml_url,
        "xml_bytes": xml_bytes,
        "gzip_url": "guides/layerseven-custom.xml.gz",
        "gzip_bytes": gzip_path.stat().st_size,
        "nbc_gzip_url": "guides/layerseven-nbc.xml.gz",
        "nbc_gzip_bytes": nbc_gzip_path.stat().st_size,
        "nbc_channels": len(nbc_ids),
        "nbc_programmes": nbc_programme_count,
        "updated_from_sources": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=Path("layerseven-channels.json"))
    parser.add_argument("--guides-dir", type=Path, default=Path("guides"))
    args = parser.parse_args()

    inventory = json.loads(args.inventory.read_text())
    root, channels, programme_counts, regions = load_public_channels(args.guides_dir)
    try:
        fubo_programmes = add_fubo_xumo_guide(root, channels, programme_counts, regions)
    except (OSError, ValueError, KeyError) as error:
        print(f"Warning: Fubo Xumo schedule unavailable: {error}")
        fubo_programmes = 0
    matches, unmatched = match_channels(inventory, channels, programme_counts, regions)
    summary = write_custom_guide(args.guides_dir, root, channels, matches, unmatched)
    summary["fubo_programmes"] = fubo_programmes

    status_path = args.guides_dir / "status.json"
    status = json.loads(status_path.read_text())
    status["groups"]["layerseven-custom"] = summary
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")

    print(json.dumps(summary, indent=2))
    print("\nSample unmatched channels:")
    for record in unmatched[:40]:
        print(f"  {record['layerseven_name']}")


if __name__ == "__main__":
    main()
