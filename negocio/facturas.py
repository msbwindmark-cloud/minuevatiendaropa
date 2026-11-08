"""Lectura de facturas: PDF con texto, OCR de fotos y relleno manual.

- PDF digital: se extrae el texto con pypdf y se buscan los datos con patrones.
- Foto (JPG/PNG): se intenta OCR con Tesseract si está instalado.
- Siempre se puede revisar y corregir a mano antes de guardar.
"""
from __future__ import annotations

import os
import re
from datetime import datetime

from django.conf import settings


CIF_RE = re.compile(r"\b([A-HJNP-SUVW]\d{7}[0-9A-J]|\d{8}[A-Z])\b")
FECHA_RE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
IMPORTE_RE = re.compile(r"(-?\d{1,3}(?:\.\d{3})*(?:,\d{2})|-?\d+(?:[.,]\d{2})?)")


def _num(txt):
    if txt is None:
        return None
    txt = str(txt).strip().replace("€", "").replace(" ", "")
    if not txt:
        return None
    if "," in txt and "." in txt:
        txt = txt.replace(".", "").replace(",", ".")
    elif "," in txt:
        txt = txt.replace(",", ".")
    try:
        return round(float(txt), 2)
    except ValueError:
        return None


def _buscar_importe(texto, etiquetas):
    for etiqueta in etiquetas:
        patron = re.compile(etiqueta + r"[^\d\-]{0,40}(-?\d{1,3}(?:\.\d{3})*(?:,\d{2})|-?\d+(?:[.,]\d{2})?)", re.I)
        m = patron.search(texto)
        if m:
            valor = _num(m.group(1))
            if valor is not None:
                return valor
    return None


def _fecha_iso(texto):
    for m in FECHA_RE.finditer(texto):
        d, mes, a = m.groups()
        if len(a) == 2:
            a = "20" + a
        try:
            return datetime(int(a), int(mes), int(d)).date().isoformat()
        except ValueError:
            continue
    return ""


def _texto_pdf(path):
    from pypdf import PdfReader

    reader = PdfReader(path)
    partes = []
    for page in reader.pages:
        try:
            partes.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(partes).strip()


def _texto_imagen(path):
    if not getattr(settings, "OCR_ACTIVO", True):
        return "", "El OCR está desactivado en la configuración."
    try:
        import pytesseract
        from PIL import Image
    except Exception:
        return "", "Falta la librería de OCR (pytesseract/Pillow)."
    try:
        with Image.open(path) as img:
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            return pytesseract.image_to_string(img, lang="spa"), ""
    except Exception as exc:  # Tesseract no instalado, imagen ilegible...
        return "", f"No se ha podido leer la imagen con OCR: {exc}"


def parsear_texto(texto: str) -> dict:
    limpio = re.sub(r"[ \t]+", " ", texto)
    lineas = [l.strip() for l in limpio.splitlines() if l.strip()]
    datos = {}

    m = re.search(r"(?:factura|fra\.?|n[ºo]\s*factura|invoice)\s*[:\-]?\s*([A-Z0-9][A-Z0-9/\-\.]{2,})", limpio, re.I)
    if m:
        datos["numero"] = m.group(1).strip()

    m = CIF_RE.search(limpio)
    if m:
        datos["cif"] = m.group(1)

    datos["fecha"] = _fecha_iso(limpio)

    base = _buscar_importe(limpio, [r"base\s+imponible", r"base", r"subtotal"])
    total = _buscar_importe(
        limpio, [r"total\s+factura", r"total\s+a\s+pagar", r"importe\s+total", r"\btotal\b"]
    )
    iva = _buscar_importe(limpio, [r"cuota\s+iva", r"i\.?v\.?a\.?"])

    if total is None and base is not None:
        total = round(base * 1.21, 2)
    if base is None and total is not None:
        base = round(total / 1.21, 2)
    if base is not None:
        datos["base"] = base
    if total is not None:
        datos["total"] = total
    if iva is not None and base:
        datos["iva_pct"] = round(iva / base * 100, 2)
    elif total and base:
        datos["iva_pct"] = round((total - base) / base * 100, 2)
    else:
        datos["iva_pct"] = 21.0

    proveedor = ""
    for linea in lineas[:12]:
        if re.search(r"(s\.?l\.?|s\.?a\.?|c\.?b\.?|s\.?l\.?u\.?|moda|textil|confecci|distribu)", linea, re.I):
            proveedor = linea
            break
    if not proveedor and lineas:
        proveedor = lineas[0]
    datos["proveedor"] = proveedor[:150]

    datos["tipo"] = "gasto"
    if re.search(r"(albar[aá]n|mercanc[ií]a|g[eé]nero|pedido)", limpio, re.I):
        datos["tipo"] = "compra"

    datos["resumen"] = " | ".join(lineas[:6])[:500]
    return datos


def extraer_datos(path: str):
    """Devuelve (datos, texto, error)."""
    if not path or not os.path.exists(path):
        return {}, "", "El archivo no existe."
    ext = os.path.splitext(path)[1].lower()
    texto = ""
    error = ""
    try:
        if ext == ".pdf":
            texto = _texto_pdf(path)
            if len(texto) < 20:
                error = (
                    "El PDF no contiene texto seleccionable (parece escaneado). "
                    "Rellena los datos a mano o sube una foto para OCR."
                )
        elif ext in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"):
            texto, error = _texto_imagen(path)
        else:
            error = "Formato no soportado. Sube un PDF o una imagen."
    except Exception as exc:
        return {}, "", f"No se ha podido leer el archivo: {exc}"

    datos = parsear_texto(texto) if texto else {}
    return datos, texto, error
