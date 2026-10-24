from datetime import date

from connectors.convenios_db import (
    ConveniosRepository,
    FilaSalarial,
    importe_en_texto,
    load_seed,
    split_articulos,
)

TEXTO = """CONVENIO COLECTIVO DE PRUEBA (SINTÉTICO)
Artículo 1. Ámbito funcional.
Este convenio se aplica a las empresas de hostelería.
Artículo 22. Jornada.
La jornada máxima anual será de 1.780 horas de trabajo efectivo.
Artículo 30. Faltas muy graves.
Se considerarán faltas muy graves las faltas repetidas e injustificadas de asistencia.
ANEXO I. TABLA SALARIAL 2026
Grupo I - Camarero/a: salario base mensual 1.425,30 euros.
Grupo II - Ayudante: salario base mensual 1.310,00 euros.
"""


def test_split_articulos():
    arts = split_articulos(TEXTO)
    assert [a[0] for a in arts] == ["1", "22", "30"]
    assert arts[1][1].startswith("Jornada") and "1.780 horas" in arts[1][2]


def test_importe_en_texto():
    assert importe_en_texto(1425.30, "salario base 1.425,30 euros")
    assert importe_en_texto(1310.0, "salario 1.310,00 euros")
    assert not importe_en_texto(1425.30, "salario base 11.425,30 euros")
    assert not importe_en_texto(1425.31, "salario base 1.425,30 euros")


def test_version_search_and_salary_verification(db):
    repo = ConveniosRepository(db)
    repo.upsert_convenio("99999999999999", "Convenio de prueba", "Hostelería", "Madrid", prioridad=1)
    vid = repo.add_version("99999999999999", TEXTO, boletin_ref="TEST", vigencia_desde=date(2026, 1, 1))
    assert repo.version_vigente("99999999999999", date(2026, 6, 1)) == vid
    assert repo.version_vigente("99999999999999", date(2025, 6, 1)) is None
    hits = repo.buscar_clausulas(vid, "faltas muy graves de asistencia")
    assert hits[0]["articulo"] == "30"
    ok = FilaSalarial(
        2026,
        "Grupo I",
        "salario base",
        1425.30,
        "mensual",
        "Grupo I - Camarero/a: salario base mensual 1.425,30 euros.",
    )
    inventada = FilaSalarial(
        2026,
        "Grupo I",
        "salario base",
        1500.00,
        "mensual",
        "Grupo I - Camarero/a: salario base mensual 1.500,00 euros.",
    )
    rechazos = repo.add_tabla_salarial(vid, [ok, inventada])
    assert len(rechazos) == 1 and "Grupo I" in rechazos[0]
    assert [r[0] for r in db.execute("SELECT importe_eur FROM convenios_tablas_salariales")] == [1425.30]
    assert repo.listar(sector="hostel")[0]["codigo"] == "99999999999999"


def test_seed_has_30_candidates():
    seed = load_seed()
    assert len(seed) == 30 and sorted(c["prioridad"] for c in seed) == list(range(1, 31))


def _dos_convenios(db):
    repo = ConveniosRepository(db)
    repo.upsert_convenio("11111111111111", "Convenio de hostelería", "Hostelería", "estatal", prioridad=1)
    repo.upsert_convenio("22222222222222", "Convenio del metal", "Metal", "estatal", prioridad=2)
    repo.add_version(
        "11111111111111",
        TEXTO,
        boletin_ref="BOE-A-2020-1",
        vigencia_desde=date(2020, 1, 1),
        vigencia_hasta=date(2022, 12, 31),
    )
    repo.add_version(
        "11111111111111", TEXTO.replace("1.780", "1.750"), boletin_ref="BOE-A-2023-1", vigencia_desde=date(2023, 1, 1)
    )
    repo.add_version(
        "22222222222222",
        TEXTO.replace("hostelería", "metal"),
        boletin_ref="BOE-A-2023-2",
        vigencia_desde=date(2023, 1, 1),
    )
    return repo


def test_buscar_en_vigentes_solo_en_el_convenio_y_la_version_vigentes(db):
    repo = _dos_convenios(db)
    hits = repo.buscar_en_vigentes("jornada máxima anual", date(2024, 5, 1), "11111111111111")
    assert hits and {h["codigo_convenio"] for h in hits} == {"11111111111111"}  # nunca del metal
    assert {h["version_id"] for h in hits} == {"11111111111111:2023"}  # la de 2020 caducó en 2022
    assert "1.750 horas" in hits[0]["texto"]
    antiguos = repo.buscar_en_vigentes("jornada máxima anual", date(2021, 5, 1), "11111111111111")
    assert {h["version_id"] for h in antiguos} == {"11111111111111:2020"}
    assert repo.buscar_en_vigentes("jornada", date(2019, 1, 1), "11111111111111") == []  # sin versión vigente
    assert repo.buscar_en_vigentes("jornada", date(2024, 1, 1), "99999999999999") == []  # convenio inexistente


def test_indexados_solo_lista_convenios_con_texto(db):
    repo = _dos_convenios(db)
    repo.upsert_convenio("33333333333333", "Sin texto todavía", "Limpieza", "Madrid", prioridad=3)
    assert [c["codigo"] for c in repo.indexados()] == ["11111111111111", "22222222222222"]


def test_seed_estatales_tienen_referencia_y_codigo_regcon():
    estatales = [c for c in load_seed() if c["territorio"] == "estatal"]
    assert len(estatales) == 10
    for c in estatales:
        assert str(c["boletin_ref"]).startswith("BOE-A-") and len(str(c["codigo_regcon"])) == 14
