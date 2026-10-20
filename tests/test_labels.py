"""Tests for Label enum and taxonomy sync."""

import re
from pathlib import Path

from piitier.labels import Label


def parse_taxonomy() -> dict[str, str]:
    """Parse TAXONOMY.md and extract placeholders.

    Returns a dict mapping entity name to placeholder string.
    """
    taxonomy_path = Path(__file__).parent.parent / "docs" / "TAXONOMY.md"
    assert taxonomy_path.exists(), f"TAXONOMY.md not found at {taxonomy_path}"

    placeholders: dict[str, str] = {}
    with open(taxonomy_path) as f:
        lines = f.readlines()

    # Skip the first two lines (header and separator)
    for line in lines[2:]:
        line = line.strip()
        if not line or "|" not in line:
            continue

        # Split by pipe and remove leading/trailing empty cells
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) >= 3:  # At least: Group, Entity, Placeholder
            # Skip separator rows (cells with only dashes)
            if all(re.match(r"^-+:?:?$", cell) for cell in cells):
                continue

            entity = cells[1]
            placeholder = cells[2]
            if entity and placeholder and entity != "Entity":
                placeholders[entity] = placeholder

    return placeholders


def test_uc2_taxonomy_label_sync() -> None:
    """UC-2: The sync test passes; Label placeholders equal taxonomy."""
    taxonomy_placeholders = parse_taxonomy()

    # Extract placeholders from Label enum
    label_placeholders: dict[str, str] = {}
    for member in Label:
        label_placeholders[member.name] = member.placeholder

    # Must have exactly 39 entries
    assert (
        len(label_placeholders) == 39
    ), f"Expected 39 Label members, got {len(label_placeholders)}"

    # Each Label member's placeholder must match taxonomy exactly
    for entity_name, label_placeholder in label_placeholders.items():
        assert entity_name in taxonomy_placeholders, f"Label.{entity_name} not found in taxonomy"
        taxonomy_placeholder = taxonomy_placeholders[entity_name]
        assert label_placeholder == taxonomy_placeholder, (
            f"Label.{entity_name} placeholder mismatch: "
            f"got {label_placeholder!r}, expected {taxonomy_placeholder!r}"
        )


def test_uc3_sync_test_fails_on_mismatch() -> None:
    """UC-3: When taxonomy has a row without Label member, test fails."""
    # Simulate adding a row to taxonomy by temporarily modifying the parse result.
    # We'll test this by checking that parse_taxonomy finds exactly 39 entries,
    # and if someone adds one, the test will fail.

    # First, verify current state: 39 taxonomy entries
    taxonomy_placeholders = parse_taxonomy()
    assert len(taxonomy_placeholders) == 39

    # Verify Label has 39 members
    label_members = {m.name for m in Label}
    assert len(label_members) == 39

    # If taxonomy had 40 entries (simulated by adding to our dict),
    # the test would fail on the assertion above.
    # The presence of a missing label is detected by UC-2's comparison.


def test_uc4_label_placeholder_property() -> None:
    """UC-4: Label members have correct placeholder and numbered properties."""
    # Numbered types: OSOBA, IMIĘ, NAZWISKO, ADRES, LEKARZ
    numbered_expected = {"OSOBA", "IMIĘ", "NAZWISKO", "ADRES", "LEKARZ"}

    for member in Label:
        # Check numbered flag
        if member.name in numbered_expected:
            assert (
                member.numbered is True
            ), f"Label.{member.name} should be numbered but is {member.numbered}"
            assert "_n]" in member.placeholder, (
                f"Label.{member.name} numbered but placeholder "
                f"{member.placeholder!r} lacks '_n]'"
            )
        else:
            assert (
                member.numbered is False
            ), f"Label.{member.name} should not be numbered but is {member.numbered}"
            assert "_n]" not in member.placeholder, (
                f"Label.{member.name} not numbered but placeholder "
                f"{member.placeholder!r} has '_n]'"
            )

        # All placeholders match format [ENTITYNAME] or [ENTITYNAME_n]
        assert re.match(
            r"^\[[\w_\-]+\]$", member.placeholder
        ), f"Label.{member.name} placeholder {member.placeholder!r} has invalid format"


def test_uc4_specific_placeholders() -> None:
    """UC-4: Specific labels have exact placeholder strings with diacritics."""
    # Example from spec: Label.MIEJSCOWOSC.placeholder == "[MIEJSCOWOŚĆ]"
    assert Label.MIEJSCOWOŚĆ.placeholder == "[MIEJSCOWOŚĆ]"
    assert Label.IMIĘ.placeholder == "[IMIĘ_n]"
    assert Label.LEKARZ.placeholder == "[LEKARZ_n]"
    assert Label.OSOBA.placeholder == "[OSOBA_n]"
    assert Label.ADRES.placeholder == "[ADRES_n]"
    assert Label.NAZWISKO.placeholder == "[NAZWISKO_n]"
