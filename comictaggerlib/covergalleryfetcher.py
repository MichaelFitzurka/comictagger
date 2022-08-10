#!/usr/bin/python
"""Adds cover images from Comic Vine web page into archive"""

import os
from typing import Tuple
from urllib.parse import unquote_plus
from urllib.request import urlopen

from bs4 import BeautifulSoup

from comicapi.comicarchive import ComicArchive
from comicapi.genericmetadata import GenericMetadata, ImageMetadata, PageType
from comictaggerlib.comicvinetalker import ComicVineTalker


class CoverGalleryFetcher:
    def __init__(self, comic_archive: ComicArchive, metadata: GenericMetadata) -> None:
        self.set_comic_archive(comic_archive)
        self.set_metadata(metadata)

        self.comic_vine: ComicVineTalker = ComicVineTalker()

        self.adds: list[str] = []
        self.fails: list[str] = []
        self.skips: list[str] = []

    def set_comic_archive(self, comic_archive: ComicArchive) -> None:
        self.comic_archive: ComicArchive = comic_archive

    def set_metadata(self, metadata: GenericMetadata) -> None:
        self.metadata: GenericMetadata = metadata

    def get_adds(self) -> list[str]:
        return self.adds

    def get_fails(self) -> list[str]:
        return self.fails

    def get_skips(self) -> list[str]:
        return self.skips

    def fetch_cover_gallery(self) -> Tuple[list[str], list[str], list[str]]:
        keys: list[str] = self.find_keys(self.metadata.pages)
        if keys != [""]:
            key_count: int = 0
            for key in keys:
                key_count += 1
                self.process_key(key, key_count)

        return self.adds, self.fails, self.skips

    def find_keys(self, pages: list[ImageMetadata]) -> list[str]:
        keys: str = ""

        for page in pages:
            if "Key" in page and page["Key"]:
                keys += page["Key"].replace(" ", "") + ","

        return keys[:-1].split(",")

    def process_key(self, key: str, key_count: int) -> None:
        cover_urls: list[str] = []

        issue_url: str = self.comic_vine.fetch_issue_page_url(int(key))
        if issue_url:
            cover_urls = self.find_cover_urls(issue_url)

        cover_url_count: int = 0
        for cover_url in cover_urls:
            cover_url_count += 1
            self.process_cover_url(cover_url, key_count, cover_url_count)

    def find_cover_urls(self, issue_url: str) -> list[str]:
        cover_urls: list[str] = []

        page_html = urlopen(issue_url)
        soup = BeautifulSoup(page_html, "html.parser")
        divs = soup.find_all("div")
        for div in divs:
            if "class" in div.attrs and "imgboxart" in div["class"] and "issue-cover" in div["class"]:
                if div.img["src"].startswith("http"):
                    cover_urls.append(div.img["src"])
                elif div.img["data-src"].startswith("http"):
                    cover_urls.append(div.img["data-src"])

        return cover_urls

    def process_cover_url(self, cover_url: str, key_count: int = 999, cover_url_count: int = 999) -> None:
        cover_filename: str = "Cover Gallery/X-Cover {0:03d}-{1:03d} {2}".format(
            key_count, cover_url_count, unquote_plus(os.path.basename(cover_url))
        )

        if self.is_cover_in_archive(cover_filename):
            self.skips.append(cover_url)
        else:
            cover_data: bytes = urlopen(cover_url).read()
            if self.comic_archive.write_file(cover_filename, cover_data):
                self.add_page(key_count, cover_url_count)
                self.adds.append(cover_filename)
            else:
                self.fails.append(cover_url)

    def is_cover_in_archive(self, cover_filename: str) -> bool:
        target: str = os.path.splitext(cover_filename)[0]
        page_filenames: list[str] = self.comic_archive.get_page_name_list()
        covers_found: list[str] = list(filter(lambda x: x.startswith(target), page_filenames))
        return len(covers_found) > 0

    def add_page(self, key_count: int, cover_url_count: int) -> None:
        image_metadata: ImageMetadata = ImageMetadata()
        image_metadata["Type"] = PageType.Other
        if key_count == 1 and cover_url_count == 1:
            image_metadata["Bookmark"] = "Cover Gallery"
        self.metadata.add_page(image_metadata)