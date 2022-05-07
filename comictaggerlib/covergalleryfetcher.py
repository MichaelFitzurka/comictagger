#!/usr/bin/python
"""Adds cover images from Comic Vine web page into archive"""

import os
from urllib.parse import unquote_plus
from urllib.request import urlopen

from bs4 import BeautifulSoup
from py7zr import SevenZipFile

from comicapi.genericmetadata import ImageMetadata, PageType
from comictaggerlib.comicvinetalker import ComicVineTalker

class CoverGalleryFetcher:
    def __init__(self, comic_archive, metadata):
        self.set_comic_archive(comic_archive)
        self.set_metadata(metadata)

        self.comic_vine = ComicVineTalker()

        self.adds = []
        self.fails = []
        self.skips = []

    def set_comic_archive(self, comic_archive):
        self.comic_archive = comic_archive

    def set_metadata(self, metadata):
        self.metadata = metadata

    def get_adds(self):
        return self.adds

    def get_fails(self):
        return self.fails

    def get_skips(self):
        return self.skips

    def fetch_cover_gallery(self):
        keys = self.find_keys(self.metadata.pages)
        key_count = 0
        for key in keys:
            key_count += 1
            self.process_key(key, key_count)

        return self.adds, self.fails, self.skips

    def find_keys(self, pages):
        keys = ""

        for page in pages:
            if "Key" in page and page["Key"]:
                keys += page["Key"].replace(" ", "") + ","

        return keys[:-1].split(",")

    def process_key(self, key, key_count):
        cover_urls = []

        issue_url = self.comic_vine.fetch_issue_page_url(key)
        if issue_url is not None:
            cover_urls = self.find_cover_urls(issue_url)

        cover_url_count = 0
        for cover_url in cover_urls:
            cover_url_count += 1
            self.process_cover_url(cover_url, key_count, cover_url_count)

    def find_cover_urls(self, issue_url):
        cover_urls = []

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

    def process_cover_url(self, cover_url, key_count, cover_url_count):
        cover_filename = "CoverGallery/X-Cover-{0:03d}-{1:03d}-{2}".format(
            key_count, cover_url_count, unquote_plus(os.path.basename(cover_url)))

        if self.is_cover_in_archive(cover_filename):
            self.skips.append(cover_url)
        else:
            cover_data = urlopen(cover_url).read()
            if self.comic_archive.write_file(cover_filename, cover_data):
                self.add_page(key_count, cover_url_count)
                self.adds.append(cover_filename)
            else:
                self.fails.append(cover_url)

    def is_cover_in_archive(self, cover_filename):
        target = os.path.splitext(cover_filename)[0]
        page_filenames = self.comic_archive.get_page_name_list()
        covers_found = list(filter(lambda x: x.startswith(target), page_filenames))
        return len(covers_found) > 0

    def add_page(self, key_count, cover_url_count):
        image_metadata = ImageMetadata()
        image_metadata["Type"] = PageType.Other
        if key_count == 1 and cover_url_count == 1:
            image_metadata["Bookmark"] = "Cover Gallery"
        self.metadata.add_page(image_metadata)
