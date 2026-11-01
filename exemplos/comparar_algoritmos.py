"""
Compara A*, custo uniforme e largura em muitos mundos aleatórios.

Uso::

    python exemplos/comparar_algoritmos.py            # padrão: 300 mundos, N em {4,...,12}
    python exemplos/comparar_algoritmos.py 500 6 20   # 500 mundos, N entre 6 e 20

O que é verificado/medido:

* A* e custo uniforme devolvem **sempre** o mesmo custo (ambos ótimos);
* em quantos mundos a largura devolve um plano **mais caro** (ela minimiza o
  número de ações, não o custo);
* nós expandidos e tempo médio de cada algoritmo;
* quantos mundos aleatórios não têm solução.
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from entregador.busca import ALGORITMOS, resolver  # noqa: E402
from entregador.mundo import Mundo  # noqa: E402


def main(qtd: int = 300, n_min: int = 4, n_max: int = 12) -> None:
    expandidos = {a: [] for a in ALGORITMOS}
    tempos = {a: [] for a in ALGORITMOS}
    sem_solucao = 0
    largura_pior = 0
    diferencas = []
    for seed in range(qtd):
        n = n_min + seed % (n_max - n_min + 1)
        mundo = Mundo.gerar_aleatorio(n, seed=seed)
        resultados = {a: resolver(mundo, a) for a in ALGORITMOS}
        ra, ru, rl = resultados["a_estrela"], resultados["custo_uniforme"], resultados["largura"]
        assert ra.encontrou == ru.encontrou == rl.encontrou == mundo.tem_solucao()
        if not ra.encontrou:
            sem_solucao += 1
            continue
        assert ra.custo_total == ru.custo_total, f"A* e custo uniforme divergiram na seed {seed}!"
        assert rl.custo_total >= ra.custo_total
        if rl.custo_total > ra.custo_total:
            largura_pior += 1
            diferencas.append(rl.custo_total - ra.custo_total)
        for a, r in resultados.items():
            expandidos[a].append(r.nos_expandidos)
            tempos[a].append(r.tempo_s * 1000)

    com_solucao = qtd - sem_solucao
    print(f"Mundos avaliados: {qtd} (N de {n_min} a {n_max})")
    print(f"  sem solução: {sem_solucao} ({100 * sem_solucao / qtd:.1f}%)  |  com solução: {com_solucao}")
    print("  A* == custo uniforme em 100% dos mundos com solução (verificado por assert)")
    print(
        f"  largura devolveu plano mais caro em {largura_pior} de {com_solucao} "
        f"({100 * largura_pior / max(1, com_solucao):.1f}%), diferença média de custo "
        f"{statistics.mean(diferencas) if diferencas else 0:.2f} (máx. {max(diferencas) if diferencas else 0})"
    )
    print()
    print(f"{'algoritmo':<16}{'expandidos (média)':>20}{'expandidos (máx)':>18}{'tempo médio (ms)':>18}")
    for a in ALGORITMOS:
        print(
            f"{a:<16}{statistics.mean(expandidos[a]):>20.1f}{max(expandidos[a]):>18}{statistics.mean(tempos[a]):>18.2f}"
        )


if __name__ == "__main__":
    args = [int(x) for x in sys.argv[1:4]]
    main(*args)
