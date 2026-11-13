# Dialogo con la consola por FTP.
#
# El complemento ftpiiu de Aroma entrega el contenido YA DESCIFRADO, asi que un
# acceso bajado de aqui sirve directamente como base: no hay que descargar nada
# de Nintendo ni manejar claves de titulo.
#
# El FTP solo esta disponible mientras la consola esta en su menu principal. Al
# abrir cualquier titulo el complemento se descarga de memoria y el puerto se
# cierra; eso es normal y no significa que la consola se haya colgado.
#
# Dos cosas medidas que conviene saber de antemano:
#
#   * la tarjeta SD NO esta en la raiz: esta en /fs/vol/external01. Pedir
#     /storage_sdcard contesta "550 No such device".
#   * los hif_*.nfs de un acceso NO se pueden leer: contestan siempre "450
#     Device or resource busy", aunque el code/ y el meta/ del mismo titulo
#     bajen sin problema. Por suerte son justo lo unico que no hace falta.
import os
import re
from ftplib import FTP, all_errors, error_perm

PUERTO = 21
BLOQUE = 65536
RUTA_INSTALL = '/fs/vol/external01/install'

# Donde busca accesos a vWii. Los inyectados por terceros suelen ir a
# 00050002; los que imitan a un juego de disco, a 00050000.
RAICES = ['/storage_usb/usr/title/00050002',
          '/storage_mlc/usr/title/00050002',
          '/storage_usb/usr/title/00050000',
          '/storage_mlc/usr/title/00050000']

# Lo unico que se baja de un acceso. El content/ entero son los gigabytes del
# disco de Wii, y de eso no se necesita nada.
CARPETAS = ['code', 'meta', 'content/assets']


def conectar(ip, tiempo=60):
    f = FTP()
    f.connect(ip, PUERTO, timeout=tiempo)
    f.login()
    f.voidcmd('TYPE I')
    return f


def _nlst(f, ruta):
    try:
        return sorted(f.nlst(ruta))
    except error_perm:
        return []


def _texto(f, ruta):
    trozos = []
    try:
        f.retrbinary('RETR ' + ruta, trozos.append, 4096)
    except all_errors:
        return ''
    return b''.join(trozos).decode('utf-8', 'replace')


def _nombre(f, titulo):
    m = re.search(r'<longname_en[^>]*>(.*?)</longname_en>',
                  _texto(f, titulo + '/meta/meta.xml'), re.S)
    return ' '.join(m.group(1).split()) if m else ''


def accesos(ip, aviso=None):
    """Los titulos instalados que son accesos a vWii.

    Se reconocen por llevar code/frisbiiU.rpx: ese es el programa de Wii U que
    no hace mas que arrancar el disco de Wii que el titulo lleva adentro.
    """
    f = conectar(ip)
    try:
        salida = []
        for raiz in RAICES:
            hijos = _nlst(f, raiz)
            if not hijos:
                continue
            if aviso:
                aviso('%s: %d titulos' % (raiz, len(hijos)))
            for h in hijos:
                archivos = [os.path.basename(a) for a in _nlst(f, h + '/code')]
                if any(a.lower().startswith('frisbii') for a in archivos):
                    salida.append({'ruta': h, 'id': os.path.basename(h),
                                   'nombre': _nombre(f, h)})
        return salida
    finally:
        try:
            f.quit()
        except all_errors:
            pass


def _bajar_dir(f, remoto, local, aviso=None):
    hijos = _nlst(f, remoto)
    if hijos and hijos[0] != remoto:          # es carpeta
        os.makedirs(local, exist_ok=True)
        for h in hijos:
            _bajar_dir(f, h, os.path.join(local, os.path.basename(h)), aviso)
        return
    os.makedirs(os.path.dirname(local), exist_ok=True)
    with open(local, 'wb') as g:
        f.retrbinary('RETR ' + remoto, g.write, BLOQUE)
    if aviso:
        aviso('%s (%d bytes)' % (os.path.basename(local), os.path.getsize(local)))


def extraer(ip, titulo, destino, aviso=None):
    """Baja el code/, el meta/ y el content/assets/ de un acceso."""
    f = conectar(ip)
    try:
        for carpeta in CARPETAS:
            _bajar_dir(f, '%s/%s' % (titulo, carpeta),
                       os.path.join(destino, *carpeta.split('/')), aviso)
    finally:
        try:
            f.quit()
        except all_errors:
            pass
    return destino


def subir(ip, carpeta, nombre_remoto, aviso=None):
    """Deja el titulo empaquetado en sd:/install/<nombre> de la consola."""
    f = conectar(ip)
    try:
        destino = '%s/%s' % (RUTA_INSTALL, nombre_remoto)
        try:
            f.mkd(destino)
        except error_perm:
            pass                               # ya existia
        total = 0
        for n in sorted(os.listdir(carpeta)):
            r = os.path.join(carpeta, n)
            if not os.path.isfile(r):
                continue
            with open(r, 'rb') as g:
                f.storbinary('STOR %s/%s' % (destino, n), g, BLOQUE)
            total += os.path.getsize(r)
            if aviso:
                aviso('%s (%d bytes)' % (n, os.path.getsize(r)))
        return {'destino': destino, 'bytes': total}
    finally:
        try:
            f.quit()
        except all_errors:
            pass
