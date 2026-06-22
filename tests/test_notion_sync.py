from scripts.notion_sync import md_to_blocks


def test_md_to_blocks_types():
    md = ("# Titre\n## Sous-titre\n### H3\n"
          "- puce un\n* puce deux\n"
          "paragraphe simple\n\n"
          "```\ncode line\n```\n")
    blocks = md_to_blocks(md)
    types = [b["type"] for b in blocks]
    assert types == ["heading_1", "heading_2", "heading_3",
                     "bulleted_list_item", "bulleted_list_item", "paragraph", "code"]
    # le code conserve son contenu
    assert blocks[-1]["code"]["rich_text"][0]["text"]["content"] == "code line"
    # le titre H1 est nettoyé du marqueur
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Titre"


def test_md_to_blocks_truncates_rich_text():
    long = "x" * 5000
    b = md_to_blocks(long)[0]
    assert len(b["paragraph"]["rich_text"][0]["text"]["content"]) <= 1900


def test_md_to_blocks_block_limit():
    md = "\n".join(f"- item {i}" for i in range(500))
    assert len(md_to_blocks(md, limit=95)) <= 95
