#!/usr/bin/env python3
"""wii2wiiu - pone homebrew de Wii como iconos del menu de Wii U, desde Linux.

Cada subcomando es un paso, y 'inyectar' los encadena todos. Las rutas y la
direccion de la consola salen de la linea de ordenes o del archivo de
configuracion; no hay nada fijo en el codigo.
"""
import argparse
import os
import shutil
import sys
import tempfile

from wii2wiiu import (claves, config, consola, disco, empaquetado, firmware,
                      inyeccion, nfs)

CONFIG = config.RUTA


class Parser(argparse.ArgumentParser):
    """Agrega una pista cuando el error huele a comodin sin comillas."""

    def error(self, mensaje):
        if 'unrecognized arguments' in mensaje:
            mensaje += ('\n\npista: si una ruta tiene espacios o un *, ponela '
                        'entre comillas.')
        super().error(mensaje)


def opcion(args, cfg, nombre, obligatorio=False):
    valor = getattr(args, nombre, None) or cfg.get(nombre)
    if valor:
        valor = os.path.expanduser(valor)
    if obligatorio and not valor:
        sys.exit('falta --%s (o ponelo en %s)' % (nombre.replace('_', '-'), CONFIG))
    return valor


def paso(texto):
    print('\n== %s' % texto)


def cmd_accesos(args, cfg):
    ip = opcion(args, cfg, 'ip', True)
    encontrados = consola.accesos(ip, aviso=lambda t: print('  ' + t))
    if not encontrados:
        print('\nNo hay accesos a vWii instalados. Hace falta al menos uno: es '
              'de donde salen el fw.img y la clave htk.bin.')
        return
    print('\n%d accesos a vWii:\n' % len(encontrados))
    for a in encontrados:
        print('  %-56s %s' % (a['ruta'], a['nombre']))


def cmd_extraer(args, cfg):
    ip = opcion(args, cfg, 'ip', True)
    destino = os.path.expanduser(args.destino)
    paso('bajando %s' % args.titulo)
    consola.extraer(ip, args.titulo, destino, aviso=lambda t: print('  ' + t))
    falta = inyeccion.comprobar_base(destino)
    if falta:
        sys.exit('\nlo bajado no sirve como base, le falta: %s' % ', '.join(falta))
    print('\nbase lista en %s' % destino)


def _armar(args, cfg, trabajo):
    """Disco + NFS + titulo. Devuelve la carpeta del titulo sin empaquetar."""
    base = opcion(args, cfg, 'base', True)
    disco_wii = opcion(args, cfg, 'disco_wii', True)
    dol = os.path.expanduser(args.dol)

    falta = inyeccion.comprobar_base(base)
    if falta:
        sys.exit('%s no es un acceso a vWii, le falta: %s' % (base, ', '.join(falta)))

    paso('esqueleto de arranque desde %s' % os.path.basename(disco_wii))
    esq = disco.esqueleto(disco_wii, os.path.join(trabajo, 'esqueleto'))
    print('  %d bytes' % sum(os.path.getsize(os.path.join(r, n))
                             for r, _, ns in os.walk(esq) for n in ns))

    paso('disco de Wii con %s adentro' % os.path.basename(dol))
    d = disco.armar(esq, dol, trabajo, args.id_disco, args.nombre)
    print('  particion de %d bytes en 0x%X' % (d['particion_bytes'], d['particion']))

    paso('convirtiendo el disco a NFS')
    r = nfs.empacar(d['iso'], inyeccion.clave_htk(base),
                    os.path.join(trabajo, 'nfs'), aviso=lambda t: print('  ' + t))
    print('  %d bytes en %d archivo(s)' % (r['bytes'], r['archivos']))

    paso('arte')
    arte = None
    logo = opcion(args, cfg, 'logo')
    if logo:
        from wii2wiiu import imagenes
        arte = os.path.join(trabajo, 'arte')
        hechos = imagenes.generar(arte, logo, args.nombre, args.pie or '',
                                  os.path.join(base, 'meta'))
        for n, t in sorted(hechos.items()):
            print('  %-16s %d bytes' % (n, t))
    else:
        print('  sin --logo: se dejan las imagenes de la base')

    paso('armando el titulo')
    salida = os.path.join(trabajo, 'titulo')
    res = inyeccion.inyectar(base, os.path.join(trabajo, 'nfs'), d['tik'],
                             d['tmd'], salida, args.nombre, args.codigo,
                             args.id_disco, args.editor, arte)
    print('  title id %s   grupo %s   %s'
          % (res['title_id'], res['grupo'], res['codigo']))
    print('  quitados %s' % ', '.join(res['quitados']))
    fw = res['firmware']
    print('  fw.img %s%s' % (fw.get('revision'),
                             '' if fw.get('esperada') else ' (no es r590: los '
                             'parches pueden no aplicar)'))
    for n, c in sorted(fw.get('parches', {}).items()):
        print('    %-10s %d' % (n, c))
    return salida


def cmd_armar(args, cfg):
    trabajo = os.path.expanduser(args.salida)
    os.makedirs(trabajo, exist_ok=True)
    titulo = _armar(args, cfg, trabajo)
    print('\ntitulo sin empaquetar en %s' % titulo)


def cmd_empaquetar(args, cfg):
    jar = opcion(args, cfg, 'nuspacker', True)
    clave = claves.obtener(opcion(args, cfg, 'otp'), None)
    salida = os.path.expanduser(args.salida)
    codigo, texto = empaquetado.empaquetar(os.path.expanduser(args.entrada),
                                           salida, jar, clave)
    print(texto)
    if codigo != 0:
        sys.exit('el empaquetador fallo (codigo %d)' % codigo)
    ok, detalle = empaquetado.verificar(salida)
    if not ok:
        sys.exit('el paquete quedo incompleto: falta %s' % ', '.join(detalle))
    print('paquete listo en %s (%d archivos)' % (salida, len(detalle) + 3))


def cmd_subir(args, cfg):
    ip = opcion(args, cfg, 'ip', True)
    r = consola.subir(ip, os.path.expanduser(args.carpeta), args.nombre,
                      aviso=lambda t: print('  ' + t))
    print('\nsubido a %s (%d bytes)' % (r['destino'], r['bytes']))
    print('Instalalo desde la consola con WUP Installer GX2.')


def cmd_inyectar(args, cfg):
    trabajo = os.path.expanduser(args.trabajo) if args.trabajo else \
        tempfile.mkdtemp(prefix='wii2wiiu-')
    os.makedirs(trabajo, exist_ok=True)
    try:
        titulo = _armar(args, cfg, trabajo)

        paso('empaquetando')
        jar = opcion(args, cfg, 'nuspacker', True)
        clave = claves.obtener(opcion(args, cfg, 'otp'), None)
        paquete = os.path.expanduser(args.salida)
        codigo, texto = empaquetado.empaquetar(titulo, paquete, jar, clave)
        if codigo != 0:
            sys.exit(texto + '\nel empaquetador fallo (codigo %d)' % codigo)
        ok, detalle = empaquetado.verificar(paquete)
        if not ok:
            sys.exit('el paquete quedo incompleto: falta %s' % ', '.join(detalle))
        print('  %d archivos en %s' % (len(detalle) + 3, paquete))

        if args.ip or cfg.get('ip'):
            paso('subiendo a la consola')
            r = consola.subir(opcion(args, cfg, 'ip'), paquete, args.nombre,
                              aviso=lambda t: print('  ' + t))
            print('\nsubido a %s (%d bytes)' % (r['destino'], r['bytes']))
            print('Instalalo desde la consola con WUP Installer GX2.')
        else:
            print('\nCopialo a sd:/install/%s e instalalo con WUP Installer GX2.'
                  % args.nombre)
    finally:
        if not args.trabajo:
            shutil.rmtree(trabajo, ignore_errors=True)


def comunes(p):
    p.add_argument('--base', help='carpeta de un acceso a vWii ya bajado')
    p.add_argument('--disco-wii', dest='disco_wii',
                   help='un disco de Wii cualquiera, de donde sale el arranque')
    p.add_argument('--dol', required=True, help='el homebrew a inyectar')
    p.add_argument('--nombre', required=True, help='el nombre que se vera')
    p.add_argument('--codigo', required=True,
                   help='codigo de producto de 4 letras, p.ej. NT64')
    p.add_argument('--id-disco', dest='id_disco', required=True,
                   help='identificador del disco de Wii, 6 caracteres')
    p.add_argument('--editor', default='homebrew')
    p.add_argument('--logo', help='imagen del programa para el icono')
    p.add_argument('--pie', help='linea chica bajo el nombre en el arranque')


def main():
    p = Parser(description=__doc__,
               formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--ip', help='direccion de la consola')
    sub = p.add_subparsers(dest='orden', required=True)

    s = sub.add_parser('accesos', help='lista los accesos a vWii instalados')
    s.set_defaults(func=cmd_accesos)

    s = sub.add_parser('extraer', help='baja un acceso para usarlo de base')
    s.add_argument('--titulo', required=True, help='ruta que dio "accesos"')
    s.add_argument('--destino', required=True)
    s.set_defaults(func=cmd_extraer)

    s = sub.add_parser('armar', help='arma el titulo sin empaquetar')
    comunes(s)
    s.add_argument('--salida', required=True, help='carpeta de trabajo')
    s.set_defaults(func=cmd_armar)

    s = sub.add_parser('empaquetar', help='cifra un titulo ya armado')
    s.add_argument('--entrada', required=True)
    s.add_argument('--salida', required=True)
    s.add_argument('--nuspacker')
    s.add_argument('--otp')
    s.set_defaults(func=cmd_empaquetar)

    s = sub.add_parser('subir', help='deja el paquete en sd:/install')
    s.add_argument('--carpeta', required=True)
    s.add_argument('--nombre', required=True)
    s.set_defaults(func=cmd_subir)

    s = sub.add_parser('inyectar', help='todo de una vez')
    comunes(s)
    s.add_argument('--salida', required=True, help='carpeta del paquete final')
    s.add_argument('--trabajo', help='carpeta intermedia (si no, temporal)')
    s.add_argument('--nuspacker')
    s.add_argument('--otp')
    s.set_defaults(func=cmd_inyectar)

    args = p.parse_args()
    cfg = config.leer()
    try:
        args.func(args, cfg)
    except disco.SinWit as e:
        sys.exit(str(e))
    except (ValueError, FileNotFoundError, FileExistsError,
            NotADirectoryError, RuntimeError) as e:
        sys.exit('error: %s' % e)


if __name__ == '__main__':
    main()
