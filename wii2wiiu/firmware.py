# Parches al fw.img, que es el IOS con el que la Wii U corre el disco de Wii.
#
# Los patrones salen del bloque de parches de nfs2iso2nfs (FIX94) y estan
# escritos para la revision r590 del firmware, que es la que traen los accesos
# a vWii. Son tres cosas distintas y conviene no confundirlas:
#
#   FAKEFIRMA  hace que el aparato acepte un disco firmado por nosotros. Sin
#              esto no arranca ningun disco armado a mano. Los accesos que ya
#              estan instalados en una consola suelen traerlo puesto, porque
#              el disco que llevan adentro tambien esta fake-firmado.
#   AHBPROT    suelta el acceso directo al hardware. El Canal Homebrew se lo
#              concede a los programas que lo piden en su meta.xml con
#              <ahb_access/>; un disco normal no, asi que hay que parchearlo.
#   MEMPROT    suelta la proteccion de memoria, que va de la mano del anterior.
#
# Quedan afuera a proposito los tres parches de Nintendont que la herramienta
# original aplica junto con estos dos: son para arrancar juegos de GameCube.
# Un emulador que no los usa no gana nada y el IOS se toca de menos.
import re

REVISION = re.compile(rb'svn-(r\d+)')
ESPERADA = 'r590'

# (nombre, patron, desplazamiento desde el patron, reemplazo)
FAKEFIRMA = [
    ('fakefirma', bytes.fromhex('200723A2'), 1, b'\x00'),
    ('fakefirma', bytes.fromhex('20074B0B'), 1, b'\x00'),
]
HOMEBREW = [
    ('AHBPROT', bytes.fromhex('D00B23084313600B'), 0, bytes.fromhex('46C0')),
    ('MEMPROT', bytes.fromhex('0194B5004B082201'), 6, bytes.fromhex('2200')),
]


def revision(datos):
    m = REVISION.search(datos)
    return m.group(1).decode('ascii') if m else None


def _aplicar(datos, parches):
    hechos = {}
    for nombre, patron, desp, reemplazo in parches:
        i = datos.find(patron)
        while i >= 0:
            datos[i + desp:i + desp + len(reemplazo)] = reemplazo
            hechos[nombre] = hechos.get(nombre, 0) + 1
            i = datos.find(patron, i + 1)
        hechos.setdefault(nombre, 0)
    return hechos


def parchar(ruta, fakefirma=True, homebrew=True):
    """Parcha el fw.img en su lugar. Devuelve que se aplico y cuantas veces.

    Que un parche no encuentre nada no siempre es un error: lo normal es que
    la fakefirma ya este puesta en el acceso del que se copio el code/.
    """
    with open(ruta, 'rb') as f:
        datos = bytearray(f.read())
    rev = revision(datos)
    hechos = {}
    if fakefirma:
        hechos.update(_aplicar(datos, FAKEFIRMA))
    if homebrew:
        hechos.update(_aplicar(datos, HOMEBREW))
    with open(ruta, 'wb') as f:
        f.write(bytes(datos))
    return {'revision': rev, 'esperada': rev == ESPERADA, 'parches': hechos}
