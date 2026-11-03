from backlogguard.ui.glossary import IDS, glossary_markdown


def test_glossary_covers_every_id_the_screens_show():
    shown = {sigla.split("-")[0] for sigla, _ in IDS}
    assert shown >= {"C", "RQ", "P", "EP", "HU", "US", "TA", "CP", "T", "F", "G", "R"}


def test_glossary_markdown_lists_ids_and_terms():
    text = glossary_markdown()
    assert "`C-nnn`" in text and "`RQ-nnn`" in text and "`DoR`" in text and "**Términos**" in text
