# Genera el arte del titulo: el icono del menu y las pantallas de arranque del
# televisor y del GamePad.
#
# Los formatos salieron de medir los archivos de una base real: TGA sin
# comprimir, con las filas de abajo hacia arriba. Hay un detalle que cambia
# entre bases y que por eso no va fijo en el codigo: algunas llevan cuatro
# bytes nulos de mas despues del pie estandar y otras no. Las de Consola
# Virtual de DS los llevan; los accesos a vWii no. Asi que el relleno se mide
# del archivo que la base ya trae, en vez de suponerlo.
import os
import struct

TIPO_SIN_COMPRIMIR = 2
PIE = b'\x00' * 8 + b'TRUEVISION-XFILE.\x00'

FUENTES = ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
           '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf']

# (ancho, alto, bits)
FORMATOS = {
    'iconTex.tga':    (128, 128, 32),
    'bootTvTex.tga':  (1280, 720, 24),
    'bootDrcTex.tga': (854, 480, 24),
}

FONDO_CLARO = (34, 40, 54)
FONDO_OSCURO = (12, 14, 20)


def _fuente(alto):
    from PIL import ImageFont
    for ruta in FUENTES:
        if os.path.isfile(ruta):
            return ImageFont.truetype(ruta, alto)
    return ImageFont.load_default()


def escribir_tga(ruta, imagen, bits, relleno):
    """Guarda la imagen como TGA sin comprimir, de abajo hacia arriba."""
    if bits == 32:
        imagen = imagen.convert('RGBA')
        canales, descriptor = 4, 0x08
    else:
        imagen = imagen.convert('RGB')
        canales, descriptor = 3, 0x00
    ancho, alto = imagen.size
    px = imagen.load()
    cuerpo = bytearray()
    for y in range(alto - 1, -1, -1):
        for x in range(ancho):
            if canales == 4:
                r, g, b, a = px[x, y]
                cuerpo += bytes((b, g, r, a))
            else:
                r, g, b = px[x, y]
                cuerpo += bytes((b, g, r))
    cabecera = struct.pack('<BBBHHBHHHHBB', 0, 0, TIPO_SIN_COMPRIMIR, 0, 0, 0,
                           0, 0, ancho, alto, bits, descriptor)
    with open(ruta, 'wb') as f:
        f.write(cabecera + bytes(cuerpo) + PIE + b'\x00' * relleno)
    return os.path.getsize(ruta)


def _relleno_de(meta_base, nombre, ancho, alto, bits):
    """Cuantos bytes de mas lleva ese archivo en la base, 0 si no esta."""
    ruta = os.path.join(meta_base, nombre) if meta_base else None
    if not ruta or not os.path.isfile(ruta):
        return 0
    esperado = 18 + ancho * alto * (bits // 8) + len(PIE)
    sobra = os.path.getsize(ruta) - esperado
    return sobra if 0 <= sobra <= 16 else 0


def _degradado(ancho, alto, claro, oscuro):
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (ancho, alto))
    d = ImageDraw.Draw(im)
    for y in range(alto):
        t = y / max(alto - 1, 1)
        d.line([(0, y), (ancho, y)],
               fill=tuple(int(claro[i] + (oscuro[i] - claro[i]) * t) for i in range(3)))
    return im


def _texto_centrado(im, texto, y, alto_fuente, color=(255, 255, 255)):
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    fuente = _fuente(alto_fuente)
    caja = d.textbbox((0, 0), texto, font=fuente)
    d.text(((im.width - (caja[2] - caja[0])) // 2 - caja[0], y), texto,
           font=fuente, fill=color)


def _pegar_centrado(fondo, dibujo, ancho_destino, y):
    from PIL import Image
    f = ancho_destino / dibujo.width
    d = dibujo.resize((ancho_destino, max(1, round(dibujo.height * f))),
                      Image.LANCZOS)
    fondo.paste(d, ((fondo.width - d.width) // 2, y), d)


def generar(destino, logo, nombre, pie='', meta_base=None):
    """Escribe los tres .tga en 'destino' a partir de una imagen y un nombre.

    'logo' es la imagen del programa —la misma que muestra el Canal Homebrew
    sirve— y 'meta_base' la carpeta meta/ de la base, que solo se usa para
    medir el relleno.
    """
    from PIL import Image
    os.makedirs(destino, exist_ok=True)
    dibujo = Image.open(logo).convert('RGBA')
    hechos = {}

    ancho, alto, bits = FORMATOS['iconTex.tga']
    icono = _degradado(ancho, alto, FONDO_CLARO, FONDO_OSCURO).convert('RGBA')
    _pegar_centrado(icono, dibujo, round(ancho * 0.90), round(alto * 0.20))
    _texto_centrado(icono, nombre, round(alto * 0.67), round(alto * 0.17))
    hechos['iconTex.tga'] = escribir_tga(
        os.path.join(destino, 'iconTex.tga'), icono, bits,
        _relleno_de(meta_base, 'iconTex.tga', ancho, alto, bits))

    for n in ('bootTvTex.tga', 'bootDrcTex.tga'):
        ancho, alto, bits = FORMATOS[n]
        im = _degradado(ancho, alto, FONDO_CLARO, FONDO_OSCURO).convert('RGBA')
        _pegar_centrado(im, dibujo, round(ancho * 0.42), round(alto * 0.30))
        _texto_centrado(im, nombre, round(alto * 0.56), round(alto * 0.09))
        if pie:
            _texto_centrado(im, pie, round(alto * 0.72), round(alto * 0.030),
                            (150, 158, 175))
        hechos[n] = escribir_tga(os.path.join(destino, n), im, bits,
                                 _relleno_de(meta_base, n, ancho, alto, bits))
    return hechos
