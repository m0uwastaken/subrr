"""python -m subrr → arranca el trabajador y la web."""
import os

from . import config as C
from . import motores as M
from . import trabajador, web


def main():
    for d in (C.DATOS, C.ORIGEN, C.CACHE, C.TMP):
        os.makedirs(d, exist_ok=True)
    activos = [m['nombre'] for m in C.cfg()['motores'] if m.get('activo') and M.disponible(m)[0]]
    C.log(f'subrr {web.VERSION} · datos en {C.DATOS} · web en {C.BIND}:{C.PUERTO} · motores: {", ".join(activos) or "ninguno (añádelos en Ajustes → Motores)"}')
    C.token_webhook()                       # lo crea la primera vez, para que los webhooks funcionen desde el principio
    if not C.PASSWORD and C.BIND not in ('127.0.0.1', 'localhost', '::1'):
        C.log('AVISO: la web no tiene contraseña (SUBRR_PASSWORD) y escucha en', C.BIND, '· no la expongas a internet')
    trabajador.arrancar()
    web.servir()


if __name__ == '__main__':
    main()
