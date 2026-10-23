import pytest

from core.normalize import dehyphenate, fix_ligatures, normalize, normalize_with_map
from core.pii_redactor import contains_pii, redact, valid_dni, valid_nie


def test_ligatures_and_dehyphenation():
    assert fix_ligatures("conﬁanza ﬂuye") == "confianza fluye"
    assert dehyphenate("el contra-\nto de arren-\n  damiento") == "el contrato de arrendamiento"


def test_normalize_typography():
    assert normalize("«Artículo  36» —\tfianza…") == '"artículo 36" - fianza...'
    assert normalize("“hola”  ‘mundo’\n\n") == "\"hola\" 'mundo'"
    assert normalize("pa­labra") == "palabra"


def test_normalize_offsets_point_to_original():
    original = "El «saldo»   de la ﬁanza"
    norm, offsets = normalize_with_map(original)
    assert norm == 'el "saldo" de la fianza'
    start = norm.index("fianza")
    assert original[offsets[start]] == "ﬁ"
    assert original[offsets[norm.index("de")] :].startswith("de")


@pytest.mark.parametrize("dni", ["12345678Z", "00000000T", "12345678-Z"])
def test_valid_dni(dni):
    assert valid_dni(dni)


def test_invalid_dni_and_nie():
    assert not valid_dni("12345678A")
    assert valid_nie("X1234567L") and not valid_nie("X1234567A")


def test_redact_and_restore():
    text = (
        "Me llamo Ana García López, DNI 12345678Z, NIE X1234567L, tel. 612 345 678, "
        "email ana.garcia@example.com, IBAN ES91 2100 0418 4502 0005 1332, matrícula 1234 BCD. "
        "Mi jefe es D. Pedro Martín. El importe es 1.234,56 € y el artículo 36 LAU."
    )
    r = redact(text)
    for secret in (
        "12345678Z",
        "X1234567L",
        "612 345 678",
        "ana.garcia@example.com",
        "ES91 2100",
        "1234 BCD",
        "Ana García López",
        "Pedro Martín",
    ):
        assert secret not in r.text, secret
    assert "1.234,56 €" in r.text and "artículo 36 LAU" in r.text
    assert r.restore(r.text) == text
    assert "[[DNI_1]]" in r.text and "[[PERSONA_1]]" in r.text


def test_invalid_dni_not_redacted_and_mapping_is_consistent():
    r1 = redact("El 12345678A no es válido; el 12345678Z sí.")
    assert "12345678A" in r1.text and "12345678Z" not in r1.text
    r2 = redact("Repito: 12345678Z y 00000000T", mapping=r1.mapping)
    assert "[[DNI_1]]" in r2.text and "[[DNI_2]]" in r2.text


def test_contains_pii():
    assert contains_pii("escríbeme a x@y.es")
    assert not contains_pii("me despidieron el 3 de marzo de 2025 tras 4 años")
