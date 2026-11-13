# wii2wiiu

Pone **homebrew de Wii como íconos del menú de Wii U**. Desde Linux.

## Para qué sirve

Una Wii U con CFW ejecuta homebrew de Wii, pero para llegar a él hay que
entrar a vWii y abrir el Canal Homebrew: tres pantallas y un cambio de modo
antes de ver nada. Esta herramienta salta todo eso. El resultado es un ícono
más en el menú de Wii U, con su nombre, su imagen y su pantalla de arranque,
que abre el programa directo.

Sirve para cualquier `.dol` que corra en Wii: emuladores (Not64, Snes9x GX,
WiiFlow), cargadores (USB Loader GX), utilidades. Probado con Not64.

## Cómo funciona

Una Wii U guarda cada juego de Wii que vende en el menú como un título normal
cuyo programa, `frisbiiU.rpx`, no hace más que arrancar el disco de Wii que
lleva adentro, en un formato propio llamado NFS.

O sea que ya existe, en tu consola, la maquinaria para arrancar un disco de
Wii desde un ícono del menú. Lo único que hay que hacer es cambiarle el disco.

Y un disco de Wii es más simple de lo que parece: el aparato lee el
encabezado, carga el *apploader* —un cargador chico, igual en todos los
discos— y ese cargador salta a `sys/main.dol`. Nada de eso depende del juego.
Así que un disco con el `.dol` del homebrew como `main.dol` y el sistema de
archivos vacío arranca igual de bien que uno de 4,7 GB.

En resumen, los cinco pasos:

1. Se saca el esqueleto de arranque de un disco de Wii cualquiera que tengas
   (unos 6 MB; el juego no interviene).
2. Se arma con él un disco mínimo cuyo `main.dol` es el homebrew.
3. Se convierte a NFS, cifrado con la clave `htk.bin` de la base.
4. Se copia el `code/` de un acceso a vWii de tu consola, se le parchan al
   `fw.img` las protecciones que el homebrew necesita soltar, y se le cambia
   la identidad para que no pise al original.
5. Se empaqueta, se cifra y se instala.

## Lo que necesitás

| | |
|---|---|
| **Una Wii U con CFW** | Aroma con el complemento `ftpiiu`, para bajar la base y subir el resultado |
| **Un acceso a vWii instalado** | Cualquier juego de Wii que ya tengas como ícono del menú. De ahí salen el `fw.img` y la clave `htk.bin` |
| **Un disco de Wii** | `.iso`, `.wbfs` o `.ciso`. Solo se le leen 6 MB de arranque |
| **El homebrew** | El `.dol` que querés inyectar |
| [`wit`](https://wit.wiimm.de) | Arma el disco y calcula los hashes |
| `NUSPacker.jar` | Cifra el paquete final. No viene incluido: es de terceros y no declara licencia |
| `otp.bin` de tu consola | De ahí sale la clave común con la que se cifra el paquete. Nunca se imprime ni se guarda |
| Java, Python 3, `Pillow`, `cryptography` | |

## Uso

Primero mirá qué accesos a vWii tenés instalados:

```
./wii2wiiu.py --ip 192.168.1.50 accesos
```

Bajate uno para usarlo de base:

```
./wii2wiiu.py --ip 192.168.1.50 extraer \
    --titulo /storage_usb/usr/title/00050002/a46f7d36 \
    --destino ~/bases/acceso-vwii
```

Y después, todo de una vez:

```
./wii2wiiu.py --ip 192.168.1.50 inyectar \
    --base ~/bases/acceso-vwii \
    --disco-wii ~/juegos/cualquiera.wbfs \
    --dol ~/apps/not64/boot.dol \
    --logo ~/apps/not64/icon.png \
    --nombre "Not64" --codigo NT64 --id-disco NOTP01 \
    --editor "Extrems / Wii64 Team" \
    --salida ~/paquetes/not64
```

El paquete queda en `sd:/install/Not64` de la consola y se instala con
**WUP Installer GX2**.

Lo que cuesta elegir son dos valores:

- `--codigo`: cuatro letras o números. De ahí sale el identificador del
  título, así que tiene que ser distinto del de cualquier otro que tengas.
- `--id-disco`: seis caracteres para el disco de Wii de adentro. El cuarto es
  la región y conviene que coincida con la de la base (`P` europea, `E`
  americana, `J` japonesa). No uses el de un juego real: el identificador
  decide dónde guarda la partida, y chocaría con la del juego.

Las rutas que no cambian —`--ip`, `--base`, `--disco-wii`, `--nuspacker`,
`--otp`— se pueden dejar en `~/.config/wii2wiiu/config.ini` y no escribirlas
más.

## Lo que no hace

- **No descarga nada de Nintendo.** La base sale de tu propia consola, por
  FTP, ya descifrada.
- **No incluye claves.** La clave común se lee de tu `otp.bin` en el momento y
  no se escribe en ningún lado; la salida del empaquetador se tacha antes de
  mostrarla, porque NUSPacker la imprime.
- **No toca el sistema.** Los parches al `fw.img` viven dentro del título que
  se arma y no afectan a vWii ni a ningún otro.

## Cosas medidas que conviene saber

- El FTP de la consola **solo responde mientras está en el menú principal**.
  Al abrir cualquier título el complemento se descarga y el puerto se cierra.
- La tarjeta SD **no está en la raíz del FTP**: está en `/fs/vol/external01`.
- Los `hif_*.nfs` de un acceso instalado **no se pueden leer por FTP**:
  contestan siempre `450 Device or resource busy`, aunque el `code/` y el
  `meta/` del mismo título bajen sin problema. Por suerte son justo lo único
  que no hace falta.
- Si el homebrew pide `<ahb_access/>` en su `meta.xml`, necesita los parches
  de AHBPROT y MEMPROT, que esta herramienta aplica por omisión. Sin ellos
  llega al menú pero no ve la tarjeta.

## Licencia

GPL-3.0. Ver [LICENSE](LICENSE) y [datos/PROCEDENCIA.md](datos/PROCEDENCIA.md).
