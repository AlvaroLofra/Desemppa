from datetime import date

from core.fechas_es import fecha_consta, fechas_en_texto, mes_consta

HOY = date(2026, 10, 24)


def test_formatos_de_fecha_en_espanol():
    f = fechas_en_texto("El 10 de junio de 2024, el 01/09/2026, el 2026-03-27 y el 5 de enero", HOY)
    assert f.exactas == {date(2024, 6, 10), date(2026, 9, 1), date(2026, 3, 27), date(2026, 1, 5)}


def test_mes_sin_dia_es_impreciso():
    f = fechas_en_texto("En junio de 2024 sufrí una inundación", HOY)
    assert f.exactas == set() and f.meses == {(2024, 6)}
    assert not fecha_consta(date(2024, 6, 1), "En junio de 2024 sufrí una inundación", HOY)
    assert mes_consta(date(2024, 6, 1), "En junio de 2024 sufrí una inundación", HOY)


def test_relativas_sin_calculo_de_calendario():
    texto = "Ayer me despidieron; hace 40 días entregué las llaves; hoy he recibido la carta"
    assert fechas_en_texto(texto, HOY).exactas == {date(2026, 10, 23), date(2026, 9, 14), HOY}


def test_una_fecha_calculada_por_el_modelo_no_consta():
    # Caso real del benchmark: el usuario dijo «han transcurrido 2 años y 4 meses» y el modelo fijó 30/09/2026.
    texto = "El siniestro ocurrió el 10 de junio de 2024 y desde entonces han transcurrido 2 años y 4 meses."
    assert fecha_consta(date(2024, 6, 10), texto, HOY)
    assert not fecha_consta(date(2026, 9, 30), texto, HOY)
