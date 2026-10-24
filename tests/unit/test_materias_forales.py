from core.materias import normas_aplicables, submaterias


def test_danos_vecinales_en_cataluna_usan_el_cccat_y_no_la_lph():
    sub = submaterias()["CIV_DANOS_VECINO"]
    comun = {n.norma for n in normas_aplicables(sub, None)}
    catalan = {(n.norma, tuple(n.articulos)) for n in normas_aplicables(sub, "CT")}
    assert "LPH" in comun and "CCCAT_L1" not in comun
    assert ("CCCAT_L1", ("121-21",)) in catalan and all(n != "LPH" for n, _ in catalan)
    assert ("CC", ("1902", "1907", "1910")) in catalan  # el CC sigue siendo supletorio
