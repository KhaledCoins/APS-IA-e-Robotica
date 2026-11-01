"""
Representação do estado e geração de sucessores.

Representação do estado (resposta à Questão 2 da prova)
-------------------------------------------------------
Só entra no estado aquilo que **muda** ao longo do plano:

* ``agente``  — posição ``(linha, coluna)`` do agente;
* ``pacote``  — posição ``(linha, coluna)`` do pacote quando ele está no
  chão, ou ``None`` quando o agente o está carregando.

Tudo o que é fixo (dimensão, obstáculos, pedágios, destino) fica no
:class:`~entregador.mundo.Mundo`, compartilhado por todos os estados —
representar isso em cada estado seria redundante.

Exemplos (Figura 2 da prova, posições 0-indexadas)::

    estado inicial : agente=(0, 0), pacote=(1, 2)      -> env "((0, 0), (1, 2))"
    estado final   : agente=(3, 3), pacote=(3, 3)      -> env "((3, 3), (3, 3))"

O estado é final quando o pacote está **no chão** na célula de destino
(``pacote == destino``), exatamente como o enunciado define.

Ações / sucessores (resposta à Questão 3)
------------------------------------------
``successors()`` aplica as seis ações do agente:

* ``cima``, ``baixo``, ``esquerda``, ``direita`` — movem o agente uma célula.
  Se a célula de destino do movimento está fora do grid ou é obstáculo, o
  agente ficaria parado; esse "movimento nulo" **não gera sucessor**, pois
  custaria sem mudar o estado e nunca faz parte de um plano ótimo.
  Se o agente carrega o pacote, o pacote vai junto (``pacote`` continua
  ``None``).
* ``pegar`` — só quando o agente está na célula do pacote e não o carrega.
* ``entregar`` — só quando o agente carrega o pacote; o pacote fica na célula
  atual do agente (que pode ou não ser o destino — o modelo é fiel ao
  enunciado; largar o pacote fora do destino nunca é ótimo e a heurística
  penaliza isso naturalmente).

Custo (função ``cost()``)
-------------------------
Seguindo a convenção da biblioteca ``aigyminsper`` (``Node.g = pai.g +
estado.cost()``), ``cost()`` devolve o custo da **ação que gerou** este
estado: 1, ou 3 se a ação foi executada em uma célula de pedágio
(``custo = custo + 2``).  A célula considerada é a célula em que o agente
**estava** ao executar a ação, que é a leitura literal do enunciado
("executar qualquer ação em uma célula marcada em cinza").

Heurística (resposta à Questão 6)
---------------------------------
Ver :meth:`EstadoEntrega.h`.
"""

from __future__ import annotations

from typing import Optional

from entregador.mundo import Mundo, Posicao

try:  # A biblioteca do curso é opcional: o projeto funciona sem ela.
    from aigyminsper.search.graph import HeuristicState as _Base

    AIGYMINSPER_DISPONIVEL = True
except ImportError:  # pragma: no cover - depende do ambiente

    class _Base:  # type: ignore[no-redef]
        """Substituto mínimo de ``aigyminsper.search.graph.HeuristicState``."""

        def __init__(self, operator: str) -> None:
            self.operator = operator

        def print(self) -> str:
            return str(self.operator)

    AIGYMINSPER_DISPONIVEL = False


# Deslocamentos (linha, coluna) de cada ação de movimento.
MOVIMENTOS: dict[str, tuple[int, int]] = {
    "cima": (-1, 0),
    "baixo": (1, 0),
    "esquerda": (0, -1),
    "direita": (0, 1),
}
ACAO_PEGAR = "pegar"
ACAO_ENTREGAR = "entregar"
ACOES = (*MOVIMENTOS, ACAO_PEGAR, ACAO_ENTREGAR)


def distancia_manhattan(a: Posicao, b: Posicao) -> int:
    """|Δlinha| + |Δcoluna| — número mínimo de movimentos entre duas células sem obstáculos."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class EstadoEntrega(_Base):
    """
    Um estado do problema do entregador.

    Parâmetros
    ----------
    operador : str
        Nome da ação que gerou o estado (``""`` para o estado inicial).
    mundo : Mundo
        O ambiente (compartilhado, imutável).
    agente : Posicao
        Posição do agente.
    pacote : Posicao | None
        Posição do pacote no chão, ou ``None`` se está com o agente.
    custo_acao : int
        Custo da ação que gerou este estado (0 para o estado inicial).
    """

    def __init__(
        self,
        operador: str,
        mundo: Mundo,
        agente: Posicao,
        pacote: Optional[Posicao],
        custo_acao: int = 0,
    ) -> None:
        super().__init__(operador)
        self.mundo = mundo
        self.agente = agente
        self.pacote = pacote
        self.custo_acao = custo_acao

    # ------------------------------------------------------------------ #
    # Construção do estado inicial
    # ------------------------------------------------------------------ #
    @classmethod
    def inicial(cls, mundo: Mundo) -> "EstadoEntrega":
        """Estado inicial: agente e pacote nas posições sorteadas, pacote no chão."""
        return cls("", mundo, mundo.agente, mundo.pacote, 0)

    # ------------------------------------------------------------------ #
    # Propriedades auxiliares
    # ------------------------------------------------------------------ #
    @property
    def carregando(self) -> bool:
        """``True`` se o agente está com o pacote."""
        return self.pacote is None

    @property
    def posicao_pacote(self) -> Posicao:
        """Onde o pacote está fisicamente (no chão ou com o agente)."""
        return self.agente if self.pacote is None else self.pacote

    def chave(self) -> tuple[Posicao, Optional[Posicao]]:
        """Identidade hashável do estado (usada nas listas fechadas da busca)."""
        return (self.agente, self.pacote)

    # ------------------------------------------------------------------ #
    # Interface exigida pela aigyminsper
    # ------------------------------------------------------------------ #
    def successors(self) -> list["EstadoEntrega"]:
        """Gera os estados alcançáveis com uma única ação válida."""
        mundo = self.mundo
        custo = mundo.custo_acao_em(self.agente)
        sucessores: list[EstadoEntrega] = []

        # Movimentos.
        linha, coluna = self.agente
        for nome, (dl, dc) in MOVIMENTOS.items():
            nova = (linha + dl, coluna + dc)
            if mundo.transitavel(nova):
                sucessores.append(EstadoEntrega(nome, mundo, nova, self.pacote, custo))

        # Pegar: agente na célula do pacote, pacote no chão.
        if self.pacote is not None and self.agente == self.pacote:
            sucessores.append(EstadoEntrega(ACAO_PEGAR, mundo, self.agente, None, custo))

        # Entregar: agente com o pacote; ele fica onde o agente está.
        if self.pacote is None:
            sucessores.append(EstadoEntrega(ACAO_ENTREGAR, mundo, self.agente, self.agente, custo))

        return sucessores

    def is_goal(self) -> bool:
        """Estado final: o pacote está no chão na célula de destino."""
        return self.pacote is not None and self.pacote == self.mundo.destino

    def cost(self) -> int:
        """Custo da ação que gerou este estado (1, ou 3 se executada em pedágio)."""
        return self.custo_acao

    def h(self) -> int:
        """
        Heurística admissível e consistente.

        Seja ``d`` a distância de Manhattan e ``D`` o destino:

        * pacote no chão em ``P`` (ainda não entregue):
          ``h = d(agente, P) + d(P, D) + 2``
          — o agente precisa, no mínimo, caminhar até o pacote, executar
          ``pegar``, caminhar até o destino e executar ``entregar``;
        * agente carregando o pacote:
          ``h = d(agente, D) + 1``
          — no mínimo caminhar até o destino e executar ``entregar``;
        * pacote já no destino: ``h = 0``.

        **Admissível** porque conta apenas ações obrigatórias, cada uma com
        custo real >= 1: obstáculos só alongam o caminho e pedágios só
        aumentam o custo, logo ``h(s) <= custo real de s até a meta``.

        **Consistente** porque uma ação de custo ``c >= 1`` altera ``h`` em
        no máximo 1 para baixo (um movimento aproxima no máximo 1 célula;
        ``pegar`` troca "+2 e d(P,D)" por "+1 e d(agente,D)" com
        agente = P, isto é, reduz exatamente 1; ``entregar`` no destino leva
        h de 1 para 0; ``entregar`` fora do destino *aumenta* h).  Assim
        ``h(s) <= c + h(s')`` para todo sucessor ``s'``.

        Com heurística consistente, o A* com lista fechada é ótimo.
        """
        destino = self.mundo.destino
        if self.pacote is None:
            return distancia_manhattan(self.agente, destino) + 1
        if self.pacote == destino:
            return 0
        return distancia_manhattan(self.agente, self.pacote) + distancia_manhattan(self.pacote, destino) + 2

    def env(self) -> str:
        """Descrição textual única do estado (usada pela aigyminsper para poda)."""
        return str(self.chave())

    def description(self) -> str:
        return (
            "Entregador em grid: o agente deve pegar o pacote e entregá-lo no destino "
            "com o menor custo, desviando de obstáculos e pagando pedágios."
        )

    # ------------------------------------------------------------------ #
    # Conveniências
    # ------------------------------------------------------------------ #
    def __repr__(self) -> str:
        pac = "carregado" if self.pacote is None else str(self.pacote)
        return f"EstadoEntrega(op={self.operator!r}, agente={self.agente}, pacote={pac})"

    def __eq__(self, outro: object) -> bool:
        # Igualdade só por (agente, pacote): uma busca sempre trabalha em um
        # único mundo, então o mundo não precisa entrar na comparação.
        return isinstance(outro, EstadoEntrega) and self.chave() == outro.chave()

    def __hash__(self) -> int:
        return hash(self.chave())
