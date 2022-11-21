#!/usr/bin/python
"""Using csv created from csv_inventory script, check title casing and spelling"""

from csv import DictReader, Error
import logging
import os
import re

import pkg_resources
from symspellpy import SymSpell
from symspellpy.suggest_item import SuggestItem
from titlecase import titlecase

base_dir: str = os.path.expanduser("~/Documents/Comics/Tagged")
csv_filename: str = base_dir + "/Comics.csv"
out_filename: str = base_dir + "/Comics Title Check.txt"

logger: logging.Logger = logging.getLogger(__name__)
sym_spell: SymSpell = None


def main() -> None:
    initialize_dictionary()

    with open(out_filename, "w") as out_file:
        with open(csv_filename, "r", newline="") as csv_file:
            csv_reader: DictReader = DictReader(csv_file)
            try:
                for row in csv_reader:
                    result: str = analyze_row(row)
                    if result:
                        out_file.write(f'{row["Filename"]} - {row["Series"]} #{row["Number"]}:\r\n{result}')
            except Error as e:
                logger.error(f"file {csv_file}, line {csv_reader.line_num}: {e}")


def analyze_row(row: dict[str, str]) -> str:
    result: str = analyze_field("Series Group", row["SeriesGroup"])
    result += analyze_field("Series", row["Series"])
    result += analyze_field("Title", row["Title"])
    result += analyze_field("Story Arc", row["StoryArc"])
    result += analyze_field("Alternate", row["Alternate"])
    result += analyze_field("Bookmark", row["Bookmarks"])
    return result


def analyze_field(header: str, value: str) -> str:
    result: str = ""
    if value:
        for title in split_value(value):
            # Check Title Case
            title_cased: str = titlecase(title)
            if title != title_cased:
                result += f'  {header}: "{title}" should be capitalized as\r\n{" "*(4 + len(header))}"{title_cased}"\r\n'

            # Check Spelling
            title_filtered: str = title.strip().replace("/", " ")
            title_filtered = title_filtered.replace("-", " ")
            title_filtered = title_filtered.replace("’", "'")
            title_filtered = re.sub(r"[^A-Za-z0-9\' ]", "", title_filtered)
            title_filtered = ' '.join(title_filtered.split())
            suggestions: List[SuggestItem] = sym_spell.lookup_compound(
                title_filtered, max_edit_distance=2, ignore_non_words=True, transfer_casing=True
            )
            for suggestion in suggestions:
                if title_filtered != suggestion.term and title_filtered.replace("'", "") != suggestion.term:
                    result += f'  {header}: "{title_filtered}" possibly misspelled, could be\r\n{" "*(4 + len(header))}"{suggestion.term}"\r\n'
    return result


def initialize_dictionary() -> None:
    global sym_spell
    sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    dictionary_path: pkg_resources.IResourceProvider = pkg_resources.resource_filename("symspellpy", "frequency_dictionary_en_82_765.txt")
    bigram_path: pkg_resources.IResourceProvider = pkg_resources.resource_filename("symspellpy", "frequency_bigramdictionary_en_243_342.txt")
    sym_spell.load_dictionary(dictionary_path, term_index=0, count_index=1)
    sym_spell.load_bigram_dictionary(bigram_path, term_index=0, count_index=2)

    with open(os.path.abspath((os.path.dirname(__file__)) + "/dictionary_adds.txt"), "r") as infile:
        for word in infile:
            sym_spell.create_dictionary_entry(word.strip(), 90000000000)

def split_value(value: str) -> list[str]:
    new_value: str = value.replace("’", "'")

    lines: list[str] = new_value.splitlines()
    split_values_by_sep(lines, " / ")
    split_values_by_sep(lines, "... ")
    split_values_by_sep(lines, "Martin's ")
    split_values_by_sep(lines, "Butcher's ")
    return lines


def split_values_by_sep(values: list[str], sep: str) -> list[str]:
    for line in values:
        if sep in line:
            values.remove(line)
            values.extend(line.split(sep))


if __name__ == "__main__":
    main()
