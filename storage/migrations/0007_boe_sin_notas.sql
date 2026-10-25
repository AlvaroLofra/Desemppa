-- 0007: el texto del BOE en caché incluía notas editoriales (redacción anterior, «Téngase en cuenta», «Se modifica»).
-- connectors/boe_models.py ya las excluye; se vacía la caché para que cada artículo se vuelva a descargar limpio.
DELETE FROM boe_bloques;
