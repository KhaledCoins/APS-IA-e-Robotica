"""
A* e custo uniforme **como algoritmos da biblioteca do curso** (``aigyminsper``).

Na disciplina, um algoritmo de busca é uma subclasse de
``aigyminsper.search.search_algorithms.SearchAlgorithm`` com um método
``search(initial_state, ...)`` que devolve um ``Node`` (ou ``None``) — foi
exatamente assim que a ``BuscaProfundidadeIterativa`` apareceu na Questão 7
da prova.  Este módulo segue o mesmo padrão: :class:`AEstrelaGrafo` e
:class:`CustoUniformeGrafo` podem ser usados no lugar de ``AEstrela`` e
``BuscaCustoUniforme`` da biblioteca, com o mesmo ``main()`` do guia do
curso::

    estado = EstadoEntrega.inicial(mundo)
    algoritmo = AEstrelaGrafo()
    resultado = algoritmo.search(estado)
    if resultado is not None:
        print(resultado.show_path(), resultado.g)
    else:
        print("Sem solução")

Diferença em relação aos algoritmos da biblioteca: aqui a busca é **em
grafo com lista fechada preenchida na expansão** (e reinserção de estados
abertos quando se acha um caminho mais barato).  A poda ``"general"`` da
biblioteca marca o estado como visitado já na **geração**, o que com custos
de ação diferentes (1 ou 3) pode produzir um plano sub-ótimo — ver
``exemplos/comparar_biblioteca.py``.  O parâmetro ``pruning`` é aceito só
por compatibilidade de assinatura e não altera o comportamento.

Este módulo só pode ser importado com a ``aigyminsper`` instalada; o
restante do projeto não depende dele.
"""

from __future__ import annotations

import contextlib
import heapq
import io
from itertools import count
from typing import Literal

with contextlib.redirect_stdout(io.StringIO()):  # a biblioteca imprime ao importar
    from aigyminsper.search.graph import Node, State
    from aigyminsper.search.search_algorithms import SearchAlgorithm


class _MelhorPrimeiroGrafo(SearchAlgorithm):
    """Busca de melhor-primeiro em grafo: f(n) = g(n) + PESO_H * h(n)."""

    PESO_H: float = 1.0
    NOME = "Busca de melhor-primeiro em grafo"

    def search(  # noqa: D102 - assinatura da biblioteca
        self,
        initial_state: State,
        /,
        _m: None = None,
        pruning: Literal["without", "father-son", "general"] = "general",
        *,
        trace: bool = False,
        **kwargs,
    ) -> Node | None:
        super().validate_pruning_option(pruning)
        contador = count()
        raiz = Node(initial_state, None)
        fronteira: list[tuple[float, int, Node]] = [(self.PESO_H * raiz.h(), next(contador), raiz)]
        melhor_g = {initial_state.env(): 0}
        fechados: set[str] = set()

        while fronteira:
            _, _, no = heapq.heappop(fronteira)
            chave = no.state.env()
            if chave in fechados:
                continue
            fechados.add(chave)
            if no.state.is_goal():
                return no
            for sucessor in no.state.successors():
                chave_s = sucessor.env()
                if chave_s in fechados:
                    continue
                filho = Node(sucessor, no)  # a biblioteca calcula filho.g = no.g + sucessor.cost()
                if filho.g < melhor_g.get(chave_s, float("inf")):
                    melhor_g[chave_s] = filho.g
                    heapq.heappush(fronteira, (filho.g + self.PESO_H * filho.h(), next(contador), filho))
        return None

    def __str__(self) -> str:
        return self.NOME


class AEstrelaGrafo(_MelhorPrimeiroGrafo):
    """A* em grafo (f = g + h). Ótimo com heurística consistente."""

    PESO_H = 1.0
    NOME = "A* (busca em grafo)"


class CustoUniformeGrafo(_MelhorPrimeiroGrafo):
    """Custo uniforme em grafo (f = g). Ótimo para custos de passo positivos."""

    PESO_H = 0.0
    NOME = "Custo uniforme (busca em grafo)"
