"""Hard negative document generators for synthetic training data (PII-3-d)."""

from __future__ import annotations

import random

from faker import Faker

from piitier.datagen.render import Document, SyntheticSpan
from piitier.labels import Label


def make_hard_negative_docs(seed: int, n: int) -> list[Document]:
    """Return *n* hard negative documents with seed-derived content and spans."""
    from piitier.datagen.build import DOC_TYPES

    doc_types = sorted(DOC_TYPES)
    docs: list[Document] = []
    for i in range(n):
        doc_seed = seed + i
        rng = random.Random(doc_seed)
        faker = Faker("pl_PL")
        faker.seed_instance(doc_seed)

        doc_type = doc_types[i % len(doc_types)]
        doc_id = f"hn_{i:07d}"

        family = i % 4
        spans: list[SyntheticSpan] = []
        text = ""

        if family == 0:
            # (a) 'numer referencyjny' with 11-digit PESEL-shaped number with invalid checksum
            base_pesel = (
                f"{rng.randint(10, 99)}{rng.randint(1, 12):02d}"
                f"{rng.randint(1, 28):02d}{rng.randint(0, 9999):04d}"
            )
            weights = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
            total = sum(w * int(d) for w, d in zip(weights, base_pesel))
            correct_check = (10 - total % 10) % 10
            bad_check = (correct_check + 1) % 10
            invalid_pesel = base_pesel + str(bad_check)
            text = (
                f"W nawiązaniu do pisma nr {rng.randint(100, 999)}/{rng.randint(2020, 2026)} "
                f"przesyłamy numer referencyjny {invalid_pesel} dotyczący sprawy."
            )
            spans = []
        elif family == 1:
            # (b) Kowal / Wróbel / Zima as common noun
            noun = rng.choice(["kowal", "wróbel", "zima"])
            if noun == "kowal":
                text = "W warsztacie metalowym doświadczony kowal kuty element wykonał starannie."
            elif noun == "wróbel":
                text = "Na gałęzi starego drzewa głośno ćwierkał mały wróbel szukający pokarmu."
            else:
                text = "Nadchodząca mroźna zima zmusiła zarządcę do sprawdzenia ogrzewania."
            spans = []
        elif family == 2:
            # (c) address line ul. {Faker last_name} {number}, {postcode} {town} -> ADRES span
            last_name = faker.last_name()
            number = rng.randint(1, 150)
            postcode = f"{rng.randint(10, 99):02d}-{rng.randint(0, 999):03d}"
            town = faker.city()
            addr_str = f"ul. {last_name} {number}, {postcode} {town}"
            text = addr_str
            spans = [
                SyntheticSpan(
                    start=0,
                    end=len(text),
                    label=Label.ADRES,
                    entity="1",
                    source="synthetic",
                    score=1.0,
                    status="valid",
                    text=text,
                )
            ]
        else:
            # (d) 'numer protokołu' carrying 17-char VIN-shaped string with invalid check digit
            wmi = "ZZ" + rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ0123456789")
            vds_prefix = "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ0123456789") for _ in range(5))
            vis = "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ0123456789") for _ in range(8))
            partial = wmi + vds_prefix + "0" + vis
            translit = {
                "A": 1,
                "B": 2,
                "C": 3,
                "D": 4,
                "E": 5,
                "F": 6,
                "G": 7,
                "H": 8,
                "J": 1,
                "K": 2,
                "L": 3,
                "M": 4,
                "N": 5,
                "P": 7,
                "R": 9,
                "S": 2,
                "T": 3,
                "U": 4,
                "V": 5,
                "W": 6,
                "X": 7,
                "Y": 8,
                "Z": 9,
            }
            for d in range(10):
                translit[str(d)] = d
            weights_vin = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)
            total_vin = sum(translit[c] * w for c, w in zip(partial, weights_vin))
            rem = total_vin % 11
            vin_check = "X" if rem == 10 else str(rem)
            bad_vin_check = "Y" if vin_check != "Y" else "Z"
            invalid_vin = wmi + vds_prefix + bad_vin_check + vis
            text = (
                f"W załączniku sporządzono numer protokołu {invalid_vin} "
                f"potwierdzający stan techniczny urządzenia."
            )
            spans = []

        docs.append(
            Document(
                text=text,
                template_id=doc_id,
                doc_type=doc_type,
                seed=doc_seed,
                spans=spans,
                inflection_fallbacks=0,
            )
        )
    return docs
