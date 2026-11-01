"""
Exemplo no formato do guia da biblioteca do curso (``aigyminsper``):
cria o estado inicial, roda um algoritmo de busca e imprime ``show_path()``.

Requer ``pip install aigyminsper==0.3.9``.

Uso::

    python exemplos/exemplo_aigyminsper.py              # mapa da prova
    python exemplos/exemplo_aigyminsper.py 10 42        # mundo aleatório 10x10 com seed 42
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from entregador.estado import AIGYMINSPER_DISPONIVEL, EstadoEntrega  # noqa: E402
from entregador.mundo import Mundo  # noqa: E402

if not AIGYMINSPER_DISPONIVEL:
    sys.exit("A biblioteca aigyminsper não está instalada: pip install aigyminsper==0.3.9")

from entregador.compat_aigyminsper import AEstrelaGrafo  # noqa: E402


def main() -> None:
    if len(sys.argv) >= 2:
        n = int(sys.argv[1])
        seed = int(sys.argv[2]) if len(sys.argv) >= 3 else None
        mundo = Mundo.gerar_aleatorio(n, seed=seed)
    else:
        mundo = Mundo.mapa_prova()

    print(mundo.render_ascii())
    print()

    estado = EstadoEntrega.inicial(mundo)
    print(estado.description())
    print("Estado inicial:", estado.env())

    algoritmo = AEstrelaGrafo()
    print(f"Usando {algoritmo}")
    resultado = algoritmo.search(estado)
    if resultado is not None:
        print("Encontrou!")
        print("Plano :", resultado.show_path().lstrip(" ;"))
        print("Custo :", resultado.g)
        print("Estado final:", resultado.state.env())
    else:
        print("Sem solução")


if __name__ == "__main__":
    main()
