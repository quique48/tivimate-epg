#!/usr/bin/env python3
"""Build a LayerSeven-specific XMLTV alias guide from the public channel lineup."""

from __future__ import annotations

import argparse
import copy
import difflib
import gzip
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
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


def read_xml(path: Path) -> ET.Element:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        return ET.parse(stream).getroot()


def tokens(value: str) -> list[str]:
    value = unicodedata.normalize("NFKC", value).upper().replace("&", " AND ")
    value = re.sub(r"^(?:(?:US|UK|CA)(?:\s+(?:FR|EN))?|NOW)\s*[:|\-]\s*", "", value)
    return re.findall(r"[A-Z0-9]+", value)


NUMBER_WORDS = {
    "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5",
    "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9", "TEN": "10",
}
TOKEN_ALIASES = {
    "DOCUMENTRY": "DOCUMENTARY",
    "TELEVISION": "TV",
}


def name_variants(value: str) -> list[str]:
    """Return conservative exact-match keys, most specific first."""
    cleaned = unicodedata.normalize("NFKC", value).upper()
    without_call = re.sub(r"\(([KW][A-Z0-9]{2,3})\)", " ", cleaned)
    without_call = re.sub(r"\b[KW][A-Z]{2,3}\b", " ", without_call)
    variants: list[str] = []
    sources = [cleaned, without_call, cleaned.split("/")[0], without_call.split("/")[0]]
    for source in sources:
        base = [token for token in tokens(source) if token not in QUALITY_TOKENS]
        base = [NUMBER_WORDS.get(token, TOKEN_ALIASES.get(token, token)) for token in base]
        candidates = [
            base,
            base[2:] if base[:2] == ["U", "AND"] else base,
            [token for token in base if token not in {"UK", "USA", "CANADA", "UKTV"}],
            [token for token in base if token not in STATE_TOKENS],
            [token for token in base if not token.isdigit()],
            [token for token in base if not token.isdigit() and token not in STATE_TOKENS],
        ]
        for candidate in candidates:
            key = " ".join(candidate).strip()
            for variant in (key, key.replace(" ", "")):
                if variant and variant not in variants:
                    variants.append(variant)
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
    matches = []
    unmatched = []
    subset_blocked = {
        "24", "7", "48HRS", "BUTTON", "CEINMA", "CINEMA", "CINMA", "EAST",
        "EVENT", "EVENTS", "EXTRA", "LIVE", "MAIN", "MOVIES", "NEWS", "NORTH",
        "PEACOCK", "PL", "PLU", "PLUS", "RED", "SOUTH", "SPORT", "SPORTS", "STORE",
        "WEST", "WORLD", "XTRA",
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
            variants = name_variants(layerseven_name)
            for key in variants:
                candidates = set()
                for region in allowed_regions:
                    candidates.update(index.get(region, {}).get(key, set()))
                if candidates:
                    found = choose_candidate(candidates, programme_counts, regions, allowed_regions)
                    matched_key = key
                    match_method = "exact"
                    break

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
                            and first_token not in {"ITV", "CTV"}
                            and not (extra_tokens & subset_blocked)
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


def write_custom_guide(guides_dir: Path, root, channels, matches, unmatched):
    aliases: dict[str, list[str]] = defaultdict(list)
    for match in matches:
        aliases[match["epg_id"]].append(match["layerseven_name"])

    output = ET.Element("tv", {"generator-info-name": "LayerSeven public-lineup alias guide"})
    selected = set(aliases)
    for channel_id in sorted(selected):
        channel = copy.deepcopy(channels[channel_id])
        existing = {(node.text or "").strip() for node in channel.findall("display-name")}
        for alias in sorted(set(aliases[channel_id])):
            if alias not in existing:
                node = ET.SubElement(channel, "display-name")
                node.text = alias
        output.append(channel)
    programme_count = 0
    for programme in root.findall("programme"):
        if programme.get("channel") in selected:
            output.append(copy.deepcopy(programme))
            programme_count += 1

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
        "channels": len(selected),
        "programmes": programme_count,
        "matched_layerseven_entries": len(matches),
        "unmatched_layerseven_entries": len(unmatched),
        "xml_url": xml_url,
        "xml_bytes": xml_bytes,
        "gzip_url": "guides/layerseven-custom.xml.gz",
        "gzip_bytes": gzip_path.stat().st_size,
        "updated_from_sources": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=Path("layerseven-channels.json"))
    parser.add_argument("--guides-dir", type=Path, default=Path("guides"))
    args = parser.parse_args()

    inventory = json.loads(args.inventory.read_text())
    root, channels, programme_counts, regions = load_public_channels(args.guides_dir)
    matches, unmatched = match_channels(inventory, channels, programme_counts, regions)
    summary = write_custom_guide(args.guides_dir, root, channels, matches, unmatched)

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
