#!/usr/bin/env python3
"""Build regional and combined XMLTV guides from public EPG sources."""

from __future__ import annotations

import argparse
import gzip
import json
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "tivimate-epg-builder/1.0 (+https://github.com/quique48/tivimate-epg)"
MAX_ALL_XML_BYTES = 90 * 1024 * 1024


@dataclass(frozen=True)
class Source:
    name: str
    urls: tuple[str, ...]


GROUPS = {
    "us": (
        Source(
            "United States epg.pw",
            (
                "https://epg.pw/xmltv/epg_US.xml",
                "https://iptv-epg.org/files/epg-us.xml",
            ),
        ),
        Source(
            "EPGTalk US Full",
            (
                "https://epgtalk.com/US_guide.xml.gz",
                "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/US_guide.xml.gz",
            ),
        ),
        Source(
            "EPGTalk US Lite",
            (
                "https://epgtalk.com/US_lite.xml.gz",
                "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/US_lite.xml.gz",
            ),
        ),
        Source(
            "EPGTalk US Local",
            (
                "https://epgtalk.com/US_local_guide.xml.gz",
                "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/US_local_guide.xml.gz",
            ),
        ),
    ),
    "ca": (
        Source(
            "Canada",
            (
                "https://epg.pw/xmltv/epg_CA.xml",
                "https://iptv-epg.org/files/epg-ca.xml",
            ),
        ),
    ),
    "gb": (
        Source(
            "United Kingdom epg.pw",
            (
                "https://epg.pw/xmltv/epg_GB.xml",
                "https://iptv-epg.org/files/epg-gb.xml",
            ),
        ),
        Source(
            "EPGTalk UK Full",
            (
                "https://epgtalk.com/UK_guide.xml.gz",
                "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/UK_guide.xml.gz",
            ),
        ),
        Source(
            "EPGTalk UK Lite",
            (
                "https://epgtalk.com/UK_lite.xml.gz",
                "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/UK_lite.xml.gz",
            ),
        ),
    ),
    "sports": (
        Source(
            "EPGTalk Sports",
            (
                "https://epgtalk.com/Sports_guide.xml.gz",
                "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/Sports_guide.xml.gz",
            ),
        ),
    ),
}


def download(url: str, attempts: int = 3) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
            if attempt + 1 >= attempts:
                break
            delay = 2 ** (attempt + 1)
            if isinstance(error, urllib.error.HTTPError):
                retry_after = error.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = min(max(delay, int(retry_after)), 120)
            print(f"    Download failed; retrying in {delay}s: {error}")
            time.sleep(delay)
    raise RuntimeError(f"Could not download {url}: {last_error}")


def load_source(source: Source) -> tuple[ET.Element, str]:
    errors = []
    for url in source.urls:
        try:
            print(f"  Downloading {source.name}: {url}")
            data = download(url)
            if data.startswith(b"\x1f\x8b"):
                data = gzip.decompress(data)
            root = ET.fromstring(data)
            if root.tag != "tv":
                raise ValueError("root element is not <tv>")
            return root, url
        except Exception as error:
            errors.append(f"{url}: {error}")
            print(f"    Source failed: {error}")
    raise RuntimeError(f"{source.name} failed: {' | '.join(errors)}")


def merge_roots(roots: list[ET.Element]) -> ET.Element:
    merged = ET.Element(
        "tv",
        {
            "generator-info-name": "tivimate-epg",
            "generator-info-url": "https://github.com/quique48/tivimate-epg",
        },
    )
    channel_ids: set[str] = set()
    programme_keys: set[tuple[str, str, str]] = set()

    for root in roots:
        for element in root:
            if element.tag == "channel":
                channel_id = element.attrib.get("id", "")
                if not channel_id or channel_id in channel_ids:
                    continue
                channel_ids.add(channel_id)
                merged.append(element)
            elif element.tag == "programme":
                key = (
                    element.attrib.get("channel", ""),
                    element.attrib.get("start", ""),
                    element.attrib.get("stop", ""),
                )
                if not key[0] or not key[1] or key in programme_keys:
                    continue
                programme_keys.add(key)
                merged.append(element)
    return merged


def filter_channels_by_name(root: ET.Element, search_term: str) -> ET.Element:
    """Create a smaller guide containing channels whose display names match."""
    filtered = ET.Element("tv", root.attrib)
    search_term = search_term.casefold()
    channel_ids: set[str] = set()

    for channel in root.findall("channel"):
        names = [node.text or "" for node in channel.findall("display-name")]
        if any(search_term in name.casefold() for name in names):
            channel_id = channel.attrib.get("id", "")
            if channel_id:
                channel_ids.add(channel_id)
                filtered.append(channel)

    for programme in root.findall("programme"):
        if programme.attrib.get("channel", "") in channel_ids:
            filtered.append(programme)
    return filtered


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def write_outputs(directory: Path, name: str, root: ET.Element, plain_xml: bool = True) -> dict:
    data = xml_bytes(root)
    xml_path = directory / f"{name}.xml"
    gzip_path = directory / f"{name}.xml.gz"
    publish_plain_xml = plain_xml and len(data) <= MAX_ALL_XML_BYTES
    if publish_plain_xml:
        atomic_write(xml_path, data)
    elif xml_path.exists():
        xml_path.unlink()
    atomic_write(gzip_path, gzip.compress(data, compresslevel=9, mtime=0))
    return {
        "channels": len(root.findall("channel")),
        "programmes": len(root.findall("programme")),
        "xml_bytes": len(data) if publish_plain_xml else 0,
        "gzip_bytes": gzip_path.stat().st_size,
        "xml_url": f"guides/{name}.xml" if publish_plain_xml else None,
        "gzip_url": f"guides/{name}.xml.gz",
    }


def existing_guide(path: Path) -> ET.Element:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        root = ET.parse(stream).getroot()
    if root.tag != "tv":
        raise ValueError(f"Existing guide {path} is not XMLTV")
    return root


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="guides", help="Directory for generated guides")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    status = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "groups": {},
        "errors": {},
    }
    built: dict[str, ET.Element] = {}

    for name, sources in GROUPS.items():
        print(f"\nBuilding {name}")
        try:
            roots = [load_source(source)[0] for source in sources]
            built[name] = merge_roots(roots)
            status["groups"][name] = {"updated_from_sources": True}
        except Exception as error:
            previous = output_dir / f"{name}.xml"
            if not previous.exists():
                previous = output_dir / f"{name}.xml.gz"
            if not previous.exists():
                status["errors"][name] = str(error)
                print(f"  No previous {name} guide is available: {error}")
                continue
            print(f"  Using previous {name} guide: {error}")
            built[name] = existing_guide(previous)
            status["groups"][name] = {"updated_from_sources": False}
            status["errors"][name] = str(error)
        status["groups"][name].update(write_outputs(output_dir, name, built[name]))

    if "us" in built:
        print("\nBuilding Chicago-only guide")
        built["chicago"] = filter_channels_by_name(built["us"], "chicago")
        status["groups"]["chicago"] = {
            "updated_from_sources": status["groups"]["us"]["updated_from_sources"]
        }
        status["groups"]["chicago"].update(write_outputs(output_dir, "chicago", built["chicago"]))

    if built:
        print("\nBuilding combined guide")
        combined = merge_roots([built[name] for name in GROUPS if name in built])
        combined_data = xml_bytes(combined)
        publish_plain_xml = len(combined_data) <= MAX_ALL_XML_BYTES
        status["groups"]["all"] = write_outputs(
            output_dir,
            "all",
            combined,
            plain_xml=publish_plain_xml,
        )
        status["groups"]["all"]["updated_from_sources"] = not status["errors"]
        status["groups"]["layerseven"] = write_outputs(
            output_dir,
            "layerseven",
            combined,
            plain_xml=publish_plain_xml,
        )
        status["groups"]["layerseven"]["updated_from_sources"] = not status["errors"]

    atomic_write(
        output_dir / "status.json",
        (json.dumps(status, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )

    print("\nGuide summary")
    for name, info in status["groups"].items():
        print(
            f"  {name}: {info['channels']:,} channels, "
            f"{info['programmes']:,} programmes, {info['gzip_bytes']:,} gzip bytes"
        )
    if status["errors"]:
        print("\nSome sources used previous guide data; see guides/status.json")


if __name__ == "__main__":
    main()
