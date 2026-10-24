"""Verificación de documentos del BOE antes de indexar convenios (sin red)."""

from datetime import date

from connectors.convenios_boe import parse_documento, verificar_documento


def _xml(titulo: str, cuerpo: str, fecha: str = "20230923") -> bytes:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<documento fecha_actualizacion="20260101">
  <metadatos><titulo>{titulo}</titulo><fecha_publicacion>{fecha}</fecha_publicacion></metadatos>
  <analisis><referencias>
    <anteriores><anterior referencia="BOE-A-2015-11430"><palabra>DE CONFORMIDAD con</palabra>
      <texto>el art. 90 del Estatuto</texto></anterior></anteriores>
    <posteriores><posterior referencia="BOE-A-2024-426"><palabra>SE MODIFICA</palabra>
      <texto>los arts. 1 y 2</texto></posterior></posteriores>
  </referencias></analisis>
  <texto>{cuerpo}</texto>
</documento>""".encode()


CONVENIO = _xml(
    "Resolución de 6 de septiembre de 2023, de la Dirección General de Trabajo, por la que se registra y publica "
    "el VII Convenio colectivo general del sector de la construcción.",
    "<p>Visto el texto del Convenio (código de convenio n.º 99005585011900), que fue suscrito...</p>"
    "<p>Artículo 1. Partes signatarias.</p><p>Lo firman las partes.</p>",
)


def test_documento_correcto_se_verifica():
    doc = parse_documento("BOE-A-2023-19903", CONVENIO)
    assert doc.fecha_publicacion == date(2023, 9, 23)
    assert doc.codigos_convenio == ["99005585011900"]
    assert doc.modificaciones_posteriores == ["BOE-A-2024-426"]
    assert "el art. 90 del Estatuto" not in doc.texto  # el <texto> del análisis no se mezcla con el cuerpo
    assert verificar_documento(doc, "99005585011900") == []


def test_codigo_distinto_se_rechaza():
    doc = parse_documento("BOE-A-2023-19903", CONVENIO)
    errores = verificar_documento(doc, "99003435011981")
    assert any("99003435011981" in e for e in errores)


def test_documento_que_no_es_un_convenio_se_rechaza():
    # Caso real: el seed inventado apuntaba a una convocatoria municipal
    doc = parse_documento(
        "BOE-A-2023-20461",
        _xml(
            "Resolución de 25 de septiembre de 2023, del Ayuntamiento de Pego (Alicante), referente a la "
            "convocatoria para proveer varias plazas.",
            "<p>Bases de la convocatoria.</p>",
        ),
    )
    errores = verificar_documento(doc, "99005585011900")
    assert len(errores) == 2


def test_revision_salarial_no_es_el_texto_del_convenio():
    doc = parse_documento(
        "BOE-A-2023-6347",
        _xml(
            "Resolución de 27 de febrero de 2023, de la Dirección General de Trabajo, por la que se registra y "
            "publica la revisión salarial y tablas salariales para 2023 del Convenio colectivo X.",
            "<p>(código de convenio n.º 99004625011981)</p>",
        ),
    )
    assert any("revisión" in e for e in verificar_documento(doc, "99004625011981"))
