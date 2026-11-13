# Arma un disco de Wii minimo cuyo programa principal es el homebrew que se
# quiere inyectar.
#
# Un disco de Wii arranca asi: el aparato lee el encabezado, carga el
# "apploader" —un cargador chico que Nintendo pone en todos los discos— y ese
# cargador lee el sistema de archivos y salta a sys/main.dol. Nada de eso
# depende del juego: el apploader de cualquier disco sirve para arrancar
# cualquier main.dol.
#
# De ahi que el disco se arme en dos partes: el esqueleto de arranque, que se
# saca de un disco de Wii que ya se tenga, y el .dol del homebrew puesto como
# main.dol. El sistema de archivos queda vacio, porque el homebrew no lo usa:
# lee sus datos de la tarjeta SD.
#
# El trabajo pesado lo hace wit (Wiimms ISO Tool), que es quien sabe calcular
# los hashes de las particiones y firmarlas. Se llama dos veces porque hacen
# falta las dos formas del mismo disco:
#
#   cifrado     para quedarnos con su ticket y su TMD, que wit deja
#               fake-firmados y que el titulo guarda sueltos en code/.
#   descifrado  porque el formato NFS guarda los datos en claro.
#
# El encabezado de particion del descifrado se pisa con el del cifrado: ahi
# viven el ticket y el TMD, que no van cifrados, y asi los dos coinciden. Es
# exactamente lo que deja nfs2iso2nfs cuando convierte un disco a NFS.
import os
import shutil
import struct
import subprocess

# Lo unico que se saca del disco de Wii de origen. El resto —los gigabytes del
# juego— no se toca ni se copia.
PARTES = ['+/sys/*', '+/disc/*', '+/cert.bin']

TITULO = 0x20          # el nombre del disco, dentro de sys/boot.bin
LARGO_TITULO = 0x40


class SinWit(Exception):
    """No esta instalado wit, que es quien arma el disco."""


def hay_wit():
    return shutil.which('wit') is not None


def _wit(*args):
    if not hay_wit():
        raise SinWit('falta wit (Wiimms ISO Tool); en Debian y derivados no '
                     'esta empaquetado: se baja de https://wit.wiimm.de')
    p = subprocess.run(('wit',) + args, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError('wit fallo: %s' % (p.stderr.strip() or p.stdout.strip()))
    return p.stdout


def esqueleto(disco_wii, destino):
    """Saca de un disco de Wii lo que hace falta para que otro arranque.

    Sirve cualquier disco: .iso, .wbfs, .ciso. Son unos 6 MB; el juego que el
    disco traiga no interviene en nada.
    """
    if os.path.exists(destino):
        shutil.rmtree(destino)
    args = ['extract', disco_wii, destino]
    for p in PARTES:
        args += ['--files', p]
    _wit(*args)
    falta = [n for n in ('sys/boot.bin', 'sys/bi2.bin', 'sys/apploader.img')
             if not os.path.isfile(os.path.join(destino, n))]
    if falta:
        raise ValueError('%s no entrego %s: no parece un disco de Wii'
                         % (disco_wii, ', '.join(falta)))
    return destino


def particion_de_datos(iso):
    """(offset, tamano) de la particion de datos, leyendo la tabla del disco.

    La tabla esta en 0x40000 y son cuatro pares (cantidad, offset>>2). De cada
    entrada de 8 bytes interesan el offset y el tipo; tipo 0 es la particion de
    datos, que es la unica que la Wii U guarda.
    """
    with open(iso, 'rb') as f:
        f.seek(0x40000)
        tabla = f.read(0x20)
        encontrados = []
        for i in range(4):
            cantidad = struct.unpack_from('>I', tabla, 8 * i)[0]
            if not cantidad:
                continue
            f.seek(struct.unpack_from('>I', tabla, 8 * i + 4)[0] * 4)
            entradas = f.read(8 * cantidad)
            for j in range(cantidad):
                off, tipo = struct.unpack_from('>II', entradas, 8 * j)
                if tipo == 0:
                    encontrados.append(off * 4)
        if not encontrados:
            raise ValueError('%s no tiene particion de datos' % iso)
        off = min(encontrados)
        f.seek(off + 0x2B8)
        datos_off, datos_tam = struct.unpack('>II', f.read(8))
        if datos_off * 4 != 0x20000:
            raise ValueError('la particion empieza en 0x%X y no en 0x20000'
                             % (datos_off * 4))
        return off, 0x20000 + datos_tam * 4


def _poner_titulo(boot_bin, nombre):
    with open(boot_bin, 'r+b') as f:
        f.seek(TITULO)
        texto = nombre.encode('ascii', 'replace')[:LARGO_TITULO - 1]
        f.write(texto + b'\x00' * (LARGO_TITULO - len(texto)))


def armar(esqueleto_dir, dol, trabajo, id_disco, nombre):
    """Deja en 'trabajo' el disco descifrado, su ticket y su TMD.

    Devuelve un resumen. El identificador de disco son seis caracteres: el
    cuarto es la region y conviene que sea la misma que la de la base, porque
    el titulo de Wii U la declara aparte.
    """
    if len(id_disco) != 6:
        raise ValueError('el identificador de disco son 6 caracteres: %r' % id_disco)
    os.makedirs(trabajo, exist_ok=True)
    fst = os.path.join(trabajo, 'fst')
    if os.path.exists(fst):
        shutil.rmtree(fst)
    shutil.copytree(esqueleto_dir, fst)

    # El sistema de archivos queda vacio y wit regenera sys/fst.bin solo.
    fst_bin = os.path.join(fst, 'sys', 'fst.bin')
    if os.path.isfile(fst_bin):
        os.remove(fst_bin)
    os.makedirs(os.path.join(fst, 'files'), exist_ok=True)
    shutil.copyfile(dol, os.path.join(fst, 'sys', 'main.dol'))
    _poner_titulo(os.path.join(fst, 'sys', 'boot.bin'), nombre)

    cifrado = os.path.join(trabajo, 'disco-cifrado.iso')
    claro = os.path.join(trabajo, 'disco.iso')
    comunes = ['--iso', '--id', id_disco, '--name', nombre, '--overwrite']
    _wit('copy', fst, cifrado, *comunes)
    _wit('copy', fst, claro, '--enc', 'DECRYPT', *comunes)

    # El encabezado de particion del cifrado —ticket, TMD, cadena de
    # certificados y tabla de hashes— al descifrado, que es donde wit no se
    # molesto en fake-firmar.
    off, largo = particion_de_datos(cifrado)
    with open(cifrado, 'rb') as f:
        f.seek(off)
        cabecera = f.read(0x20000)
    with open(claro, 'r+b') as f:
        f.seek(off)
        f.write(cabecera)

    tam_tmd, off_tmd = struct.unpack('>II', cabecera[0x2A4:0x2AC])
    tik = os.path.join(trabajo, 'rvlt.tik')
    tmd = os.path.join(trabajo, 'rvlt.tmd')
    with open(tik, 'wb') as f:
        f.write(cabecera[:0x2A4])
    with open(tmd, 'wb') as f:
        f.write(cabecera[off_tmd * 4:off_tmd * 4 + tam_tmd])
    os.remove(cifrado)
    return {'iso': claro, 'tik': tik, 'tmd': tmd, 'id': id_disco,
            'particion': off, 'particion_bytes': largo,
            'dol_bytes': os.path.getsize(dol)}
