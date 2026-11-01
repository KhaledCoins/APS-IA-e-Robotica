r"""
Algoritmos de busca e diagnóstico de "sem solução".

Por que A* e Custo Uniforme (resposta à Questão 5)
---------------------------------------------------
As ações têm custos **diferentes** (1 fora do pedágio, 3 dentro).  Por isso:

* **Busca em largura** e **profundidade iterativa** minimizam o *número de
  ações*, não o *custo* — podem devolver um plano mais curto porém mais caro
  (passando por pedágios).  Não são ótimas aqui.  A largura está
  implementada apenas para **demonstrar** isso (ver ``exemplos/``).
* **Busca de custo uniforme** (Dijkstra) é ótima para custos de passo
  >= ε > 0 (aqui, 1 ou 3).
* **A\*** com heurística admissível é ótimo; com heurística **consistente**
  (caso da nossa, ver :meth:`~entregador.estado.EstadoEntrega.h`) continua
  ótimo mesmo usando lista fechada (busca em grafo), expandindo bem menos
  nós que o custo uniforme.

Implementação
-------------
A*, custo uniforme e largura são implementados aqui, de forma independente
da biblioteca ``aigyminsper`` (que é opcional), por dois motivos:

1. para ter estatísticas (nós expandidos/gerados, tempo) e o plano em
   forma estruturada para a interface;
2. porque a poda ``"general"`` da ``aigyminsper`` marca um estado como
   visitado **no momento em que é gerado**, o que, com custos de ação
   diferentes, pode descartar o caminho barato para um estado que já foi
   alcançado por um caminho caro — e devolver um plano sub-ótimo.  O script
   ``exemplos/comparar_biblioteca.py`` mostra isso na prática.

Aqui a lista fechada é atualizada **na expansão** (quando o nó sai da
fila de prioridade), e um estado **ainda não expandido** é reinserido na
fronteira sempre que um caminho mais barato até ele é encontrado.  Estados
já expandidos não são reabertos: no custo uniforme eles já têm ``g``
ótimo, e no A* isso vale porque a heurística é **consistente** (com uma
heurística apenas admissível seria preciso reabri-los).
"""

from __future__ import annotations

import heapq
import time
from collections import deque
from dataclasses import dataclass, field
from itertools import count
from typing import Callable, Optional

from entregador.estado import EstadoEntrega
from entregador.mundo import Mundo, Posicao


# ---------------------------------------------------------------------- #
# Estruturas de resultado
# ---------------------------------------------------------------------- #
@dataclass(frozen=True)
class Passo:
    """Uma ação do plano e o estado resultante."""

    indice: int
    acao: str
    estado: EstadoEntrega
    custo_acao: int
    custo_acumulado: int

    @property
    def em_pedagio(self) -> bool:
        """``True`` se a ação foi executada em uma célula de pedágio (custo 3)."""
        return self.custo_acao > 1


@dataclass
class Resultado:
    """Saída de uma busca."""

    algoritmo: str
    mundo: Mundo
    encontrou: bool
    estados: list[EstadoEntrega] = field(default_factory=list)  # do inicial ao final
    plano: list[Passo] = field(default_factory=list)
    custo_total: int = 0
    nos_expandidos: int = 0
    nos_gerados: int = 0
    tamanho_max_fronteira: int = 0
    tempo_s: float = 0.0
    diagnostico: str = ""
    otimo_garantido: bool = True

    @property
    def acoes(self) -> list[str]:
        return [p.acao for p in self.plano]

    @property
    def num_acoes(self) -> int:
        return len(self.plano)

    def celulas_percorridas(self) -> list[Posicao]:
        """Sequência de células ocupadas pelo agente ao longo do plano."""
        return [e.agente for e in self.estados]

    def descricao_plano(self, uma_linha: bool = False) -> str:
        """Plano legível, com custo por ação e custo acumulado."""
        if not self.encontrou:
            return "SEM SOLUÇÃO: " + self.diagnostico
        if not self.plano:
            return "O pacote já está no destino: plano vazio, custo 0."
        if uma_linha:
            return " ; ".join(self.acoes) + f"  (custo {self.custo_total})"
        linhas = []
        for p in self.plano:
            onde = p.estado.agente
            extra = "  [pedágio: +2]" if p.em_pedagio else ""
            linhas.append(
                f"{p.indice:>3}. {p.acao:<9} -> agente em {onde}  custo {p.custo_acao}  acumulado {p.custo_acumulado}{extra}"
            )
        linhas.append(f"Total: {self.num_acoes} ações, custo {self.custo_total}.")
        return "\n".join(linhas)

    def resumo(self) -> str:
        """Uma linha com as estatísticas da busca."""
        status = f"custo {self.custo_total}, {self.num_acoes} ações" if self.encontrou else "sem solução"
        return (
            f"[{self.algoritmo}] {status} | nós expandidos: {self.nos_expandidos}, "
            f"gerados: {self.nos_gerados}, fronteira máx.: {self.tamanho_max_fronteira}, "
            f"tempo: {self.tempo_s * 1000:.1f} ms"
        )


class _No:
    """Nó da árvore de busca: estado + ponteiro para o pai + custo acumulado g."""

    __slots__ = ("estado", "pai", "g", "profundidade")

    def __init__(self, estado: EstadoEntrega, pai: Optional["_No"], g: int) -> None:
        self.estado = estado
        self.pai = pai
        self.g = g
        self.profundidade = 0 if pai is None else pai.profundidade + 1

    def caminho(self) -> list["_No"]:
        nos: list[_No] = []
        atual: Optional[_No] = self
        while atual is not None:
            nos.append(atual)
            atual = atual.pai
        nos.reverse()
        return nos


def _montar_resultado(algoritmo: str, mundo: Mundo, no_final: Optional[_No], **stats) -> Resultado:
    if no_final is None:
        return Resultado(algoritmo, mundo, encontrou=False, diagnostico=diagnostico(mundo), **stats)
    nos = no_final.caminho()
    estados = [n.estado for n in nos]
    plano = [
        Passo(indice=i, acao=n.estado.operator, estado=n.estado, custo_acao=n.estado.cost(), custo_acumulado=n.g)
        for i, n in enumerate(nos[1:], start=1)
    ]
    return Resultado(algoritmo, mundo, encontrou=True, estados=estados, plano=plano, custo_total=no_final.g, **stats)


# ---------------------------------------------------------------------- #
# Busca de melhor-primeiro genérica: f(n) = g(n) + peso * h(n)
# ---------------------------------------------------------------------- #
def _melhor_primeiro(inicial: EstadoEntrega, peso_h: float, nome: str) -> Resultado:
    """
    Busca em grafo com fila de prioridade.

    * ``peso_h = 1`` -> A*  (f = g + h)
    * ``peso_h = 0`` -> custo uniforme (f = g)

    Lista fechada preenchida na **expansão**; um estado ainda não expandido
    volta à fronteira se for encontrado um caminho mais barato (``g`` menor)
    até ele.  Estados fechados não são reabertos (correto para o custo
    uniforme e, no A*, porque ``h`` é consistente).
    """
    inicio = time.perf_counter()
    contador = count()  # desempate estável na fila (FIFO entre f iguais)
    raiz = _No(inicial, None, 0)
    fronteira: list[tuple[float, int, _No]] = [(peso_h * inicial.h(), next(contador), raiz)]
    melhor_g: dict = {inicial.chave(): 0}
    fechados: set = set()
    expandidos = gerados = 0
    max_fronteira = 1
    no_final: Optional[_No] = None

    while fronteira:
        _, _, no = heapq.heappop(fronteira)
        chave = no.estado.chave()
        if chave in fechados:
            continue  # entrada obsoleta (já expandimos esse estado com g menor ou igual)
        fechados.add(chave)
        expandidos += 1

        if no.estado.is_goal():  # teste de meta na expansão -> garante otimalidade
            no_final = no
            break

        for sucessor in no.estado.successors():
            gerados += 1
            chave_s = sucessor.chave()
            if chave_s in fechados:
                continue
            g = no.g + sucessor.cost()
            if g < melhor_g.get(chave_s, float("inf")):
                melhor_g[chave_s] = g
                f = g + peso_h * sucessor.h()
                heapq.heappush(fronteira, (f, next(contador), _No(sucessor, no, g)))
        max_fronteira = max(max_fronteira, len(fronteira))

    return _montar_resultado(
        nome,
        inicial.mundo,
        no_final,
        nos_expandidos=expandidos,
        nos_gerados=gerados,
        tamanho_max_fronteira=max_fronteira,
        tempo_s=time.perf_counter() - inicio,
    )


def a_estrela(inicial: EstadoEntrega) -> Resultado:
    """A*: f(n) = g(n) + h(n). Ótimo (heurística admissível e consistente)."""
    return _melhor_primeiro(inicial, peso_h=1.0, nome="A*")


def custo_uniforme(inicial: EstadoEntrega) -> Resultado:
    """Busca de custo uniforme (Dijkstra): f(n) = g(n). Ótimo."""
    return _melhor_primeiro(inicial, peso_h=0.0, nome="Custo Uniforme")


# ---------------------------------------------------------------------- #
# Busca em largura — apenas para comparação (NÃO é ótima com pedágios)
# ---------------------------------------------------------------------- #
def busca_largura(inicial: EstadoEntrega) -> Resultado:
    """
    Busca em largura em grafo.  Encontra o plano com **menos ações**, que
    não é necessariamente o de **menor custo** quando há pedágios.
    """
    inicio = time.perf_counter()
    raiz = _No(inicial, None, 0)
    expandidos = gerados = 0
    max_fronteira = 1
    no_final: Optional[_No] = None

    if inicial.is_goal():
        no_final = raiz
    else:
        fila = deque([raiz])
        visitados = {inicial.chave()}
        while fila and no_final is None:
            no = fila.popleft()
            expandidos += 1
            for sucessor in no.estado.successors():
                gerados += 1
                chave_s = sucessor.chave()
                if chave_s in visitados:
                    continue
                visitados.add(chave_s)
                filho = _No(sucessor, no, no.g + sucessor.cost())
                if sucessor.is_goal():
                    no_final = filho
                    break
                fila.append(filho)
            max_fronteira = max(max_fronteira, len(fila))

    resultado = _montar_resultado(
        "Largura",
        inicial.mundo,
        no_final,
        nos_expandidos=expandidos,
        nos_gerados=gerados,
        tamanho_max_fronteira=max_fronteira,
        tempo_s=time.perf_counter() - inicio,
    )
    resultado.otimo_garantido = False
    return resultado


# ---------------------------------------------------------------------- #
# Fachada
# ---------------------------------------------------------------------- #
ALGORITMOS: dict[str, Callable[[EstadoEntrega], Resultado]] = {
    "a_estrela": a_estrela,
    "custo_uniforme": custo_uniforme,
    "largura": busca_largura,
}
NOMES_ALGORITMOS = {
    "a_estrela": "A* (ótimo)",
    "custo_uniforme": "Custo uniforme (ótimo)",
    "largura": "Largura (não ótima — comparação)",
}


def resolver(mundo: Mundo, algoritmo: str = "a_estrela") -> Resultado:
    """Monta o estado inicial do ``mundo`` e executa o algoritmo escolhido."""
    if algoritmo not in ALGORITMOS:
        raise ValueError(f"Algoritmo desconhecido: {algoritmo!r}. Opções: {', '.join(ALGORITMOS)}.")
    return ALGORITMOS[algoritmo](EstadoEntrega.inicial(mundo))


def diagnostico(mundo: Mundo) -> str:
    """
    Explica, em uma frase, por que o mundo não tem solução (ou confirma que tem).

    A busca já detecta a ausência de solução ao esgotar a fronteira; esta
    função apenas traduz o motivo para o usuário, usando alcançabilidade
    por BFS no grid.
    """
    if mundo.pacote == mundo.destino:
        return "O pacote já está no destino."
    alc_agente = mundo.alcancaveis(mundo.agente)
    if mundo.pacote not in alc_agente:
        if len(alc_agente) == 1:
            return f"O agente em {mundo.agente} está cercado por obstáculos/bordas e não consegue se mover."
        return f"Não existe caminho entre o agente {mundo.agente} e o pacote {mundo.pacote}."
    if mundo.destino not in mundo.alcancaveis(mundo.pacote):
        if not list(mundo.vizinhos_transitaveis(mundo.destino)):
            return f"O destino {mundo.destino} está cercado por obstáculos/bordas e é inalcançável."
        return f"Não existe caminho entre o pacote {mundo.pacote} e o destino {mundo.destino}."
    return "Existe solução."
