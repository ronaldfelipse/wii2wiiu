# Empaquetador del formato NFS, el que usa la Wii U para guardar un disco de
# Wii dentro de un titulo del menu.
#
# Es la mitad de ida de nfs2iso2nfs (FIX94), reescrita en Python. La original
# es de C# para Windows y usa DllImport de msvcrt y rutas con barra invertida,
# asi que en Linux no corre ni con Mono. Lo que hace, en orden:
#
#   1. del disco DESCIFRADO saca tres tramos y descarta el resto, que son
#      ceros: el encabezado del disco (un sector), la tabla de particiones
#      (dos sectores desde 0x40000) y la particion de datos entera. Por eso un
#      disco de 4,7 GB cuyo contenido son dos megas termina pesando dos megas.
#   2. arma el encabezado de 0x200 bytes: "EGGS" al principio, "SGGE" al
#      final, y en el medio la tabla de esos tres tramos medida en sectores.
#   3. cifra el cuerpo con AES-128-CBC y la clave de code/htk.bin. Los tres
#      primeros sectores van con vector inicial en cero; de ahi en adelante
#      cada sector lleva un vector propio, que es un contador que arranca en
#      00..00 1F 00. El encabezado queda en claro.
#   4. parte el resultado en hif_%06d.nfs de 250 MB.
#
# La clave htk.bin es la del titulo del que se copia el code/, y por eso los
# dos tienen que venir del mismo lado.
import os
import struct

from wii2wiiu.disco import particion_de_datos

SECTOR = 0x8000
ENCABEZADO = 0x200
PARTE = 0xFA00000          # 250 MB, el tamano al que corta la Wii U

# El vector del primer sector de la particion. De ahi en adelante se le suma
# uno al ultimo byte, con acarreo hacia la izquierda.
CONTADOR_INICIAL = b'\x00' * 14 + b'\x1f\x00'


def encabezado(inicio, largo):
    """Los 0x200 bytes que van en claro al principio del primer hif."""
    h = bytearray(b'\xff' * ENCABEZADO)
    h[0x00:0x04] = b'EGGS'
    h[0x04:0x08] = bytes((0x00, 0x01, 0x10, 0x11))
    h[0x08:0x10] = b'\x00' * 8
    h[0x10:0x14] = struct.pack('>I', 3)            # tres tramos
    h[0x14:0x18] = struct.pack('>I', 0)            # encabezado del disco
    h[0x18:0x1C] = struct.pack('>I', 1)
    h[0x1C:0x20] = struct.pack('>I', 8)            # tabla de particiones
    h[0x20:0x24] = struct.pack('>I', 2)
    h[0x24:0x28] = struct.pack('>I', inicio // SECTOR)
    h[0x28:0x2C] = struct.pack('>I', largo // SECTOR)
    h[0x1FC:0x200] = b'SGGE'
    return bytes(h)


def tramos(h):
    """Los (inicio, largo) en bytes que el encabezado declara."""
    cuantos = struct.unpack_from('>I', h, 0x10)[0]
    return [(struct.unpack_from('>I', h, 0x14 + i * 8)[0] * SECTOR,
             struct.unpack_from('>I', h, 0x18 + i * 8)[0] * SECTOR)
            for i in range(cuantos)]


def _cifrador():
    try:
        from cryptography.hazmat.primitives.ciphers import (Cipher, algorithms,
                                                            modes)
    except ImportError:
        raise ImportError('falta el paquete cryptography (pip install cryptography)')
    return Cipher, algorithms, modes


def empacar(iso, clave, destino, prefijo='hif', aviso=None):
    """Escribe los hif_*.nfs en 'destino' a partir de un disco descifrado."""
    if len(clave) != 16:
        raise ValueError('la clave son 16 bytes, vinieron %d' % len(clave))
    Cipher, algorithms, modes = _cifrador()
    inicio, largo = particion_de_datos(iso)
    h = encabezado(inicio, largo)
    os.makedirs(destino, exist_ok=True)

    contador = bytearray(CONTADOR_INICIAL)
    cero = b'\x00' * 16
    n = 0
    escrito = len(h)
    posicion = len(h)
    total = 0

    def abrir(i):
        return open(os.path.join(destino, '%s_%06d.nfs' % (prefijo, i)), 'wb')

    salida = abrir(0)
    salida.write(h)
    with open(iso, 'rb') as f:
        for inicio_t, largo_t in tramos(h):
            f.seek(inicio_t)
            restante = largo_t
            while restante > 0:
                pedido = min(SECTOR, restante)
                trozo = f.read(pedido)
                if len(trozo) < pedido:            # el disco termina antes
                    trozo += b'\x00' * (pedido - len(trozo))
                restante -= pedido
                iv = cero if posicion < 0x18000 else bytes(contador)
                c = Cipher(algorithms.AES(clave), modes.CBC(iv)).encryptor()
                cifrado = c.update(trozo) + c.finalize()
                if posicion >= 0x18000:
                    for k in (15, 14, 13, 12):
                        contador[k] = (contador[k] + 1) & 0xFF
                        if contador[k]:
                            break
                if escrito + len(cifrado) > PARTE:
                    cabe = PARTE - escrito
                    salida.write(cifrado[:cabe])
                    salida.close()
                    n += 1
                    if aviso:
                        aviso('%s_%06d.nfs' % (prefijo, n))
                    salida = abrir(n)
                    salida.write(cifrado[cabe:])
                    escrito = len(cifrado) - cabe
                else:
                    salida.write(cifrado)
                    escrito += len(cifrado)
                posicion += len(cifrado)
                total += len(cifrado)
    salida.close()
    return {'inicio': inicio, 'largo': largo, 'bytes': total, 'archivos': n + 1}
