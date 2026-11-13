# Arma el titulo de Wii U a partir de un acceso a vWii de la consola.
#
# Un acceso a vWii es un titulo comun del menu cuyo programa, frisbiiU.rpx,
# no hace mas que arrancar el disco de Wii que lleva en content/ en formato
# NFS. Si ese disco se reemplaza por uno cuyo main.dol es un homebrew, el
# icono del menu abre el homebrew.
#
# Aparte del disco hay que cambiar cuatro cosas:
#
#   code/rvlt.tik y code/rvlt.tmd   el ticket y el TMD del disco, que el
#                                   titulo guarda sueltos fuera del NFS. Si
#                                   quedan los de la base, no coinciden.
#   code/fw.img                     el IOS, que necesita los parches de
#                                   homebrew (ver firmware.py).
#   code/app.xml y meta/meta.xml    la identidad, para no pisar a la base.
#   meta/*.tga                      el arte del icono y del arranque.
#
# El identificador del titulo sale del codigo de producto de cuatro letras, en
# hexadecimal, igual que en los titulos de Consola Virtual: NT64 -> 4E543634.
# Los accesos a vWii que circulan usan un numero al azar en su lugar, pero
# derivarlo del codigo deja los dos datos coherentes y evita elegir a ciegas.
import os
import re
import shutil

CATEGORIA = '00050002'
IDIOMAS = ['ja', 'en', 'fr', 'de', 'it', 'es', 'zhs', 'ko', 'nl', 'pt', 'ru', 'zht']

# La forma instalada que entrega la consola trae estos dos, que el
# empaquetador genera por su cuenta. Si se los dejamos puestos se planta.
SOBRANTES = [('code', 'title.fst'), ('code', 'title.tmd')]

# Lo que tiene que traer una base para que sirva.
NECESARIOS = ['code/frisbiiU.rpx', 'code/fw.img', 'code/htk.bin',
              'code/app.xml', 'meta/meta.xml']


def identidad_desde_codigo(codigo):
    codigo = codigo.upper()
    if not re.fullmatch(r'[A-Z0-9]{4}', codigo):
        raise ValueError('el codigo de producto deben ser 4 letras o numeros: %r'
                         % codigo)
    ident = ''.join('%02X' % ord(c) for c in codigo)
    return CATEGORIA + ident, '0000' + ident[2:6]


def comprobar_base(base):
    """Devuelve lo que le falta a la carpeta para ser un acceso a vWii."""
    return [n for n in NECESARIOS if not os.path.isfile(os.path.join(base, *n.split('/')))]


def clave_htk(base):
    with open(os.path.join(base, 'code', 'htk.bin'), 'rb') as f:
        clave = f.read()
    if len(clave) != 16:
        raise ValueError('code/htk.bin deberia tener 16 bytes, tiene %d' % len(clave))
    return clave


def _reemplazar_en_xml(ruta, cambios):
    with open(ruta, encoding='utf-8') as f:
        texto = f.read()
    for etiqueta, valor in cambios.items():
        patron = r'(<%s\b[^>]*>)(.*?)(</%s>)' % (etiqueta, etiqueta)
        nuevo, n = re.subn(patron, lambda m: m.group(1) + valor + m.group(3),
                           texto, flags=re.S)
        if n == 0:
            raise ValueError('no se encontro la etiqueta <%s> en %s' % (etiqueta, ruta))
        texto = nuevo
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(texto)


def inyectar(base, nfs_dir, tik, tmd, salida, nombre, codigo, id_disco,
             editor='homebrew', arte=None, parchar_fw=True):
    """Deja en 'salida' el titulo listo para empaquetar.

    'nfs_dir' son los hif_*.nfs ya armados; 'tik' y 'tmd', el ticket y el TMD
    del mismo disco. 'arte' es una carpeta con los .tga que reemplazan a los
    de la base, o None para dejar los que vengan.
    """
    falta = comprobar_base(base)
    if falta:
        raise ValueError('%s no parece un acceso a vWii, le falta: %s'
                         % (base, ', '.join(falta)))
    if os.path.exists(salida):
        raise FileExistsError('ya existe %s' % salida)
    tid, grupo = identidad_desde_codigo(codigo)
    shutil.copytree(base, salida)

    quitados = []
    for partes in SOBRANTES:
        r = os.path.join(salida, *partes)
        if os.path.isfile(r):
            os.remove(r)
            quitados.append('/'.join(partes))

    # El disco nuevo reemplaza al de la base, y los sobrantes de la base se
    # van: si el de ella ocupaba cuatro hif y el nuestro uno, quedarian tres
    # pedazos de un disco que ya no esta.
    destino = os.path.join(salida, 'content')
    os.makedirs(destino, exist_ok=True)
    for n in sorted(os.listdir(destino)):
        if n.startswith('hif_') and n.endswith('.nfs'):
            os.remove(os.path.join(destino, n))
    discos = []
    for n in sorted(os.listdir(nfs_dir)):
        shutil.copyfile(os.path.join(nfs_dir, n), os.path.join(destino, n))
        discos.append((n, os.path.getsize(os.path.join(destino, n))))

    shutil.copyfile(tik, os.path.join(salida, 'code', 'rvlt.tik'))
    shutil.copyfile(tmd, os.path.join(salida, 'code', 'rvlt.tmd'))

    fw = {}
    if parchar_fw:
        from wii2wiiu import firmware
        fw = firmware.parchar(os.path.join(salida, 'code', 'fw.img'))

    if arte:
        for n in sorted(os.listdir(arte)):
            if n.lower().endswith('.tga'):
                shutil.copyfile(os.path.join(arte, n),
                                os.path.join(salida, 'meta', n))

    _reemplazar_en_xml(os.path.join(salida, 'code', 'app.xml'),
                       {'title_id': tid, 'group_id': grupo})
    cambios = {'title_id': tid, 'group_id': grupo,
               'product_code': 'WUP-N-' + codigo.upper(),
               # Guarda el identificador del disco de Wii que lleva adentro.
               'reserved_flag2': id_disco[:4].encode('ascii').hex().upper()}
    for i in IDIOMAS:
        cambios['longname_' + i] = nombre
        cambios['shortname_' + i] = nombre
        cambios['publisher_' + i] = editor
    _reemplazar_en_xml(os.path.join(salida, 'meta', 'meta.xml'), cambios)

    return {'title_id': tid, 'grupo': grupo,
            'codigo': 'WUP-N-' + codigo.upper(), 'quitados': quitados,
            'firmware': fw, 'disco': discos}
