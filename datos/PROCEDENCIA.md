# Procedencia y atribución

Este proyecto no inventó ninguno de los formatos que manipula. Lo que sabe,
lo sabe porque otros lo publicaron.

## nfs2iso2nfs

El formato NFS —el encabezado "EGGS", los tres tramos, el cifrado por sector
con vector contador— está documentado en el código de
[nfs2iso2nfs](https://github.com/FIX94/nfs2iso2nfs) de FIX94, a su vez
derivado del de piratesephiroth. `wii2wiiu/nfs.py` es la mitad de ida de esa
herramienta reescrita en Python: la original es C# para Windows, usa
`DllImport` de `msvcrt` y rutas con barra invertida, y en Linux no corre ni
con Mono.

Los parches al `fw.img` de `wii2wiiu/firmware.py` —fakefirma, AHBPROT,
MEMPROT— también salen de ahí. Quedaron afuera a propósito los tres parches de
Nintendont que esa herramienta aplica junto con los de homebrew: son para
arrancar juegos de GameCube y un emulador que no los usa no gana nada.

## wit (Wiimms ISO Tool)

[wit](https://wit.wiimm.de), de Dirk Clemens, arma el disco de Wii, calcula
los hashes de la partición y la fake-firma. No viene incluido.

## NUSPacker

Cifra y empaqueta el título final. No viene incluido: es de terceros y no
declara licencia, así que distribuirlo acá sería atribuirse una decisión que
no es nuestra.

## Lo que no está acá y no va a estar

- Claves de Nintendo, de ninguna clase.
- Bases, `fw.img`, `frisbiiU.rpx` ni ningún otro código de Nintendo. Todo eso
  sale de la consola de quien usa la herramienta, que es suya.
- Homebrew de terceros. El `.dol`, el `icon.png` y el nombre los pone quien
  inyecta, y la licencia del programa inyectado es la que ese programa tenga.
