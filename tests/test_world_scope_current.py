from pathlib import Path


def test_world_relations_are_actor_scoped_and_legacy_relations_are_primary_only():
    text=Path('src/notsip/world.py').read_text(encoding='utf-8')
    assert "source.startswith('actor:')" in text
    assert "Legacy relations were created before relation ownership existed" in text
    assert "if self._relation_owner(relation)!=actor:continue" in text
    assert "provenance=f'actor:{actor}|{source}'" in text
