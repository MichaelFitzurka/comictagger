#!/usr/bin/python
"""Print out a csv list of basic tag info from all comics"""

import csv
import logging
import os
import re
import xmltodict

from py7zr import Bad7zFile, SevenZipFile
from typing import Any, Tuple

archive_extension: str = ".cb7"
base_dir: str = os.path.expanduser("~/Documents/Comics/Tagged")
cix_filename: str = "ComicInfo.xml"
csv_filename: str = base_dir + "/Comics.csv"
fields: list[str] = [
    "SeriesSort",
    "SeriesGroup",
    "Series",
    "Volume",
    "Format",
    "Number",
    "Count",
    "Title",
    "Alternate",
    "Bookmarks",
    # "EmbeddedComics",
    "StoryArc",
    "StoryArcNum",
    "Publisher",
    "Imprint",
    "Year",
    "Month",
    "Day",
    "ScanInformation",
    "PageCount",
    "PageTypeCount",
    "Notes",
    "Web",
    "Directory",
    "Filename",
]

logger: logging.Logger = logging.getLogger(__name__)

fcbd_regex: re.Pattern = re.compile(r"FCBD|Free Comic Book Day", re.IGNORECASE)
number_regex: re.Pattern = re.compile(r"#(\S+)$")
number_count_regex: re.Pattern = re.compile(r"#(\S+) of (\S+)$")
volume_regex: re.Pattern = re.compile(r"\((\d{4})\)")


def main() -> None:
    write_csv_file(process_directory())


def extract_bookmarks(pages: list[dict[str, str]]) -> Tuple[dict[int, str], dict[int, str]]:
    comic_bookmarks: dict[int, str] = {}
    other_bookmarks: dict[int, str] = {}

    for page in pages:
        if "@Bookmark" in page:
            if volume_regex.search(page["@Bookmark"]):
                comic_bookmarks[int(page["@Image"]) + 1] = page["@Bookmark"]
            elif "@Type" in page and page["@Type"] == "Preview":
                other_bookmarks[int(page["@Image"]) + 1] = f'{page["@Bookmark"]} (Preview)'
            else:
                other_bookmarks[int(page["@Image"]) + 1] = page["@Bookmark"]

    return comic_bookmarks, other_bookmarks


def extract_page_type_counts(pages: list[dict[str, str]]) -> dict[str, int]:
    page_type_counts: dict[str, int] = {}

    for page in pages:
        page_type: str = "Story"
        if "@Type" in page:
            page_type = page["@Type"]
        if page_type in page_type_counts:
            page_type_counts[page_type] += 1
        else:
            page_type_counts[page_type] = 1

    return page_type_counts


def format_bookmarks(bookmarks: dict[int, str]) -> str:
    formatted: str = ""

    for k, v in sorted(bookmarks.items()):
        formatted += f"{k}: {v}\r\n"

    if formatted:
        formatted = formatted[:-2]
    else:
        formatted = None

    return formatted


def format_page_type_count(page_type_counts: dict[str, int]) -> str:
    formatted: str = ""

    for k, v in sorted(page_type_counts.items()):
        formatted += f"{k}: {v}, "

    if formatted:
        formatted = formatted[:-2]
    else:
        formatted = None

    return formatted


def generate_row(cix: dict[str, Any]) -> list[str | None]:
    row: list[str | None] = [None] * len(fields)
    i: int = -1
    for field in fields:
        i += 1
        if field in cix:
            row[i] = cix[field]
    return row


def process_archive(archive_filename: str) -> list[list[str | None]]:
    rows: list[list[str | None]] = []

    cix_data: bytes = read_cix_from_archive(archive_filename)
    cix: dict[str, Any] = xmltodict.parse(cix_data)["ComicInfo"]
    pages: list[dict[str, str]] = cix["Pages"]["Page"]

    if "AlternateSeries" in cix:
        cix["Alternate"] = cix["AlternateSeries"]
        if "AlternateNumber" in cix:
            cix["Alternate"] += " #" + cix["AlternateNumber"]
            if "AlternateCount" in cix:
                cix["Alternate"] += " of " + cix["AlternateCount"]

    comic_bookmarks, other_bookmarks = extract_bookmarks(pages)
    for k, v in comic_bookmarks.items():
        rows.append(generate_row(transform_bookmark(k, v, cix, other_bookmarks)))
    cix["Bookmarks"] = format_bookmarks(other_bookmarks)
    cix["EmbeddedComics"] = format_bookmarks(comic_bookmarks)

    cix["PageTypeCount"] = format_page_type_count(extract_page_type_counts(pages))

    if (
        ":" in cix["Series"]
        and "Format" in cix
        and cix["Format"] == "Trade Paper Back"
        and (
            cix["Series"].endswith("Edition")
            or cix["Series"].endswith("Collection")
            or cix["Series"].endswith("Compendium")
        )
    ):
        cix["SeriesSort"] = cix["Series"][0 : cix["Series"].rfind(":")]
    else:
        cix["SeriesSort"] = cix["Series"]
    if "SeriesGroup" in cix:
        cix["SeriesSort"] = cix["SeriesGroup"] + "; " + cix["SeriesSort"]

    if "Title" in cix:
        cix["Title"] = cix["Title"].replace("; ", "\r\n")

    rows.append(generate_row(cix))
    return rows


def process_directory() -> list[list[str | None]]:
    rows: list[list[str | None]] = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(archive_extension):
                print(f"Processing: {file}")
                new_rows: list[list[str | None]] = process_archive(os.path.join(root, file))
                for new_row in new_rows:
                    new_row[fields.index("Directory")] = root.replace(base_dir, "")
                    new_row[fields.index("Filename")] = file.replace(archive_extension, "")
                    rows.append(new_row)
    return rows


def read_cix_from_archive(archive_filename: str) -> bytes:
    cix_data: bytes = bytes()
    try:
        with SevenZipFile(archive_filename, "r") as zf:
            cix_data = zf.read(cix_filename)[cix_filename].read()
    except Bad7zFile as e:
        logger.error(f"bad 7zip file [{e}]: {archive_filename}")
        raise IOError from e
    except Exception as e:
        logger.error(f"bad 7zip file [{e}]: {archive_filename}")
        raise IOError
    return cix_data


def transform_bookmark(
    bookmark_page: int, bookmark_text: str, cix: dict[str, Any], other_bookmarks: dict[int, str]
) -> dict[str, str]:
    bookmark_cix: dict[str, str] = {}

    cix_id = cix["Series"]
    if "Title" in cix:
        cix_id += f' [{cix["Title"]}]'
    bookmark_cix["Bookmarks"] = f"{cix_id}: {bookmark_page}"

    bookmark_cix["Volume"] = volume_regex.search(bookmark_text).group(1)

    if " [" in bookmark_text:
        bookmark_cix["Series"] = bookmark_text[0 : bookmark_text.find(" [")]
        title = bookmark_text[bookmark_text.find("[") + 1 : bookmark_text.rfind("]")]
        if "; " in title:
            bookmark_cix["Bookmarks"] = f'{cix_id}\r\n{bookmark_page}: {title[0 : title.find("; ")]}'
            key_pops: list[int] = []
            for k, v in other_bookmarks.items():
                if title.find(v) > 0:
                    bookmark_cix["Bookmarks"] += f"\r\n{k}: {v}"
                    key_pops.append(k)
            for key in key_pops:
                other_bookmarks.pop(key, None)
        bookmark_cix["Title"] = title.replace("; ", "\r\n")
    else:
        bookmark_cix["Series"] = bookmark_text[0 : bookmark_text.find(" (")]

    if number_count_regex.search(bookmark_text):
        bookmark_cix["Format"] = "Limited Series"
        found = number_count_regex.search(bookmark_text)
        bookmark_cix["Number"] = found.group(1).lstrip("0")
        bookmark_cix["Count"] = found.group(2).lstrip("0")
    elif number_regex.search(bookmark_text):
        bookmark_cix["Format"] = "Series"
        bookmark_cix["Number"] = number_regex.search(bookmark_text).group(1).lstrip("0")
        if not bookmark_cix["Number"]:
            bookmark_cix["Number"] = "0"
        elif bookmark_cix["Number"] == "½":
            bookmark_cix["Format"] = "1/2"
    else:
        bookmark_cix["Format"] = "One Shot"
        bookmark_cix["Number"] = "1"

    if bookmark_cix["Series"].endswith("Annual"):
        bookmark_cix["Format"] = "Annual"
    elif fcbd_regex.search(bookmark_text):
        bookmark_cix["Format"] = "FCBD"
    elif bookmark_cix["Series"].endswith("Giant"):
        bookmark_cix["Format"] = "Giant"

    if "SeriesGroup" in cix:
        bookmark_cix["SeriesGroup"] = cix["SeriesGroup"]
        bookmark_cix["SeriesSort"] = cix["SeriesGroup"] + "; " + bookmark_cix["Series"]
    else:
        bookmark_cix["SeriesSort"] = bookmark_cix["Series"]

    if "Publisher" in cix:
        bookmark_cix["Publisher"] = cix["Publisher"]
    if "Imprint" in cix:
        bookmark_cix["Imprint"] = cix["Imprint"]

    return bookmark_cix


def write_csv_file(rows) -> None:
    with open(csv_filename, "w+") as csv_file:
        csv_writer: csv.DictWriter = csv.writer(csv_file)
        csv_writer.writerow(fields)
        csv_writer.writerows(rows)


if __name__ == "__main__":
    main()
