"""
Executa o nosso ``EstadoEntrega`` com os algoritmos da biblioteca do curso
(``aigyminsper``) e compara com a implementação própria.

Requer ``pip install aigyminsper==0.3.9``.

Uso::

    python exemplos/comparar_biblioteca.py              # mapa da prova + contraexemplo + 200 mundos
    python exemplos/comparar_biblioteca.py 500          # 500 mundos aleatórios

Conclusões que o script demonstra:

1. O ``EstadoEntrega`` é um ``HeuristicState`` válido: ``AEstrela``,
   ``BuscaCustoUniforme`` e ``BuscaLargura`` da biblioteca rodam com ele.
2. Com a poda ``"father-son"`` a ``AEstrela`` da biblioteca encontra o ótimo
   (custo 10 no mapa da prova), mas é uma busca em árvore — exponencial —
   e só é viável em grids pequenos.
3. Com a poda ``"general"`` a biblioteca marca um estado como visitado no
   momento em que ele é **gerado**.  Com custos de ação diferentes (1 ou 3),
   isso pode descartar o caminho barato até um estado já alcançado por um
   caminho caro: o resultado é **sub-ótimo** em uma parte dos mundos.
   A implementação própria (lista fechada na **expansão**) não tem esse
   problema e sempre coincide com o custo uniforme.
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from entregador.busca import resolver  # noqa: E402
from entregador.estado import AIGYMINSPER_DISPONIVEL, EstadoEntrega  # noqa: E402
from entregador.mundo import Mundo  # noqa: E402

if not AIGYMINSPER_DISPONIVEL:
    sys.exit("A biblioteca aigyminsper não está instalada: pip install aigyminsper==0.3.9")

with contextlib.redirect_stdout(io.StringIO()):  # a biblioteca imprime ao importar
    from aigyminsper.search.search_algorithms import AEstrela, BuscaCustoUniforme


def custo_biblioteca(algoritmo, mundo: Mundo, pruning: str):
    no = algoritmo().search(EstadoEntrega.inicial(mundo), pruning=pruning)
    return None if no is None else no.g


def main(qtd: int = 200) -> None:
    print("== Mapa da prova (Figura 2) ==")
    mundo = Mundo.mapa_prova()
    print(f"  implementação própria (A*)           : custo {resolver(mundo).custo_total}")
    print(f"  aigyminsper AEstrela, poda father-son: custo {custo_biblioteca(AEstrela, mundo, 'father-son')}")
    print(f"  aigyminsper AEstrela, poda general   : custo {custo_biblioteca(AEstrela, mundo, 'general')}")
    print(f"  aigyminsper BuscaCustoUniforme, general: custo {custo_biblioteca(BuscaCustoUniforme, mundo, 'general')}")

    print("\n== Contraexemplo exemplos/mapas/poda_biblioteca_3x3.txt ==")
    mundo = Mundo.carregar(RAIZ / "exemplos" / "mapas" / "poda_biblioteca_3x3.txt")
    print(mundo.render_ascii())
    r = resolver(mundo)
    print(f"  implementação própria (A*)           : custo {r.custo_total}  plano: {' ; '.join(r.acoes)}")
    no = AEstrela().search(EstadoEntrega.inicial(mundo), pruning="general")
    print(f"  aigyminsper AEstrela, poda general   : custo {no.g}  plano:{no.show_path()}")
    no = AEstrela().search(EstadoEntrega.inicial(mundo), pruning="father-son")
    print(f"  aigyminsper AEstrela, poda father-son: custo {no.g}  plano:{no.show_path()}")

    print(f"\n== {qtd} mundos aleatórios (N entre 3 e 7), poda 'general' da biblioteca ==")
    piores_astar = piores_ucs = com_solucao = 0
    for seed in range(qtd):
        n = 3 + seed % 5
        mundo = Mundo.gerar_aleatorio(n, seed=seed)
        otimo = resolver(mundo)
        la = custo_biblioteca(AEstrela, mundo, "general")
        lu = custo_biblioteca(BuscaCustoUniforme, mundo, "general")
        assert (la is None) == (lu is None) == (not otimo.encontrou)
        if not otimo.encontrou:
            continue
        com_solucao += 1
        assert la >= otimo.custo_total and lu >= otimo.custo_total
        piores_astar += la > otimo.custo_total
        piores_ucs += lu > otimo.custo_total
    print(f"  mundos com solução: {com_solucao}")
    print(f"  AEstrela (general) sub-ótimo em {piores_astar} ({100 * piores_astar / com_solucao:.1f}%)")
    print(f"  BuscaCustoUniforme (general) sub-ótimo em {piores_ucs} ({100 * piores_ucs / com_solucao:.1f}%)")
    print("  implementação própria: ótima em 100% (igual ao custo uniforme próprio, verificado nos testes)")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
