"""
O ambiente do problema: um grid quadrado N x N.

Convenções adotadas em todo o projeto
-------------------------------------
* Uma posição é um par ``(linha, coluna)``, ambos **0-indexados**:
  ``(0, 0)`` é o canto superior esquerdo e ``(N-1, N-1)`` o canto inferior
  direito.  (No enunciado da prova as células aparecem 1-indexadas; a
  interface gráfica e a saída textual mostram as duas formas quando útil.)
* Células **pretas** são obstáculos: o agente nunca entra nelas.
* Células **cinzas** são pedágios: o agente pode entrar, mas toda ação
  executada *enquanto está nelas* custa 2 a mais.
* O que NÃO muda durante a busca (tamanho, obstáculos, pedágios e célula de
  destino) fica aqui, no :class:`Mundo`.  O que muda (posição do agente e do
  pacote) fica no :class:`~entregador.estado.EstadoEntrega`.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

Posicao = tuple[int, int]
"""Uma célula do grid: ``(linha, coluna)``, 0-indexada."""

# Caracteres do formato textual de mapa (ver ``Mundo.de_texto``).
CHAR_LIVRE = "."
CHAR_OBSTACULO = "#"
CHAR_PEDAGIO = "$"

# Faixas padrão (fração das células) usadas na geração aleatória.
DENSIDADE_OBSTACULOS_PADRAO = (0.10, 0.35)
DENSIDADE_PEDAGIOS_PADRAO = (0.05, 0.20)


@dataclass(frozen=True)
class Mundo:
    """
    Descrição imutável do ambiente.

    Atributos
    ---------
    n : int
        Dimensão do grid (N linhas x N colunas).
    agente : Posicao
        Posição inicial do agente.
    pacote : Posicao
        Posição inicial do pacote (no chão).
    destino : Posicao
        Célula marcada com X, onde o pacote deve ser entregue.
    obstaculos : frozenset[Posicao]
        Células pretas (intransponíveis).
    pedagios : frozenset[Posicao]
        Células cinzas (ação executada nelas custa +2).
    """

    n: int
    agente: Posicao
    pacote: Posicao
    destino: Posicao
    obstaculos: frozenset[Posicao]
    pedagios: frozenset[Posicao]

    # ------------------------------------------------------------------ #
    # Validação
    # ------------------------------------------------------------------ #
    def __post_init__(self) -> None:
        if self.n < 1:
            raise ValueError("A dimensão do grid deve ser um inteiro >= 1.")
        # Garante conjuntos imutáveis mesmo se o chamador passou set/list.
        object.__setattr__(self, "obstaculos", frozenset(self.obstaculos))
        object.__setattr__(self, "pedagios", frozenset(self.pedagios))
        object.__setattr__(self, "agente", tuple(self.agente))
        object.__setattr__(self, "pacote", tuple(self.pacote))
        object.__setattr__(self, "destino", tuple(self.destino))

        for nome in ("agente", "pacote", "destino"):
            pos = getattr(self, nome)
            if not self.dentro(pos):
                raise ValueError(f"Posição de '{nome}' {pos} fora do grid {self.n}x{self.n}.")
            if pos in self.obstaculos:
                raise ValueError(f"Posição de '{nome}' {pos} coincide com um obstáculo.")
        for pos in self.obstaculos | self.pedagios:
            if not self.dentro(pos):
                raise ValueError(f"Célula {pos} fora do grid {self.n}x{self.n}.")
        if self.obstaculos & self.pedagios:
            raise ValueError("Uma célula não pode ser obstáculo e pedágio ao mesmo tempo.")

    # ------------------------------------------------------------------ #
    # Consultas simples
    # ------------------------------------------------------------------ #
    def dentro(self, pos: Posicao) -> bool:
        """``True`` se a posição está dentro dos limites do grid."""
        linha, coluna = pos
        return 0 <= linha < self.n and 0 <= coluna < self.n

    def transitavel(self, pos: Posicao) -> bool:
        """``True`` se o agente pode ocupar a célula (dentro do grid e não obstáculo)."""
        return self.dentro(pos) and pos not in self.obstaculos

    def eh_pedagio(self, pos: Posicao) -> bool:
        """``True`` se a célula é um pedágio."""
        return pos in self.pedagios

    def custo_acao_em(self, pos: Posicao) -> int:
        """
        Custo de executar *qualquer* ação estando na célula ``pos``.

        Regra do enunciado: toda ação custa 1; se o agente a executa em uma
        célula de pedágio, ``custo = custo + 2`` (ou seja, 3).
        """
        return 3 if pos in self.pedagios else 1

    def vizinhos_transitaveis(self, pos: Posicao) -> Iterator[Posicao]:
        """Células adjacentes (4-vizinhança) em que o agente pode entrar."""
        linha, coluna = pos
        for dl, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            viz = (linha + dl, coluna + dc)
            if self.transitavel(viz):
                yield viz

    def celulas(self) -> Iterator[Posicao]:
        """Todas as células do grid, em ordem de leitura."""
        for linha in range(self.n):
            for coluna in range(self.n):
                yield (linha, coluna)

    # ------------------------------------------------------------------ #
    # Alcançabilidade (usada no diagnóstico de "sem solução")
    # ------------------------------------------------------------------ #
    def alcancaveis(self, origem: Posicao) -> set[Posicao]:
        """Conjunto de células alcançáveis a partir de ``origem`` (BFS em 4-vizinhança)."""
        vistos = {origem}
        fila = deque([origem])
        while fila:
            atual = fila.popleft()
            for viz in self.vizinhos_transitaveis(atual):
                if viz not in vistos:
                    vistos.add(viz)
                    fila.append(viz)
        return vistos

    def tem_solucao(self) -> bool:
        """
        Verificação rápida de existência de solução, independente da busca.

        Existe solução se e somente se o agente alcança o pacote **e** o
        pacote alcança o destino (o agente carrega o pacote pelo mesmo grid).
        """
        if self.pacote == self.destino:
            return True
        return self.pacote in self.alcancaveis(self.agente) and self.destino in self.alcancaveis(self.pacote)

    # ------------------------------------------------------------------ #
    # Geração aleatória
    # ------------------------------------------------------------------ #
    @classmethod
    def gerar_aleatorio(
        cls,
        n: int,
        seed: int | None = None,
        densidade_obstaculos: float | tuple[float, float] | None = None,
        densidade_pedagios: float | tuple[float, float] | None = None,
    ) -> "Mundo":
        """
        Sorteia um mundo N x N.

        * As posições do agente, do pacote e do destino são sorteadas em
          células distintas (para ``n >= 2``).
        * A **quantidade** e a **posição** dos obstáculos são aleatórias.
          Por padrão a quantidade é sorteada entre 10% e 35% das células
          restantes; ``densidade_obstaculos`` pode fixar um valor ou uma
          faixa ``(min, max)``.
        * Pedágios idem, por padrão entre 5% e 20% das células não-obstáculo
          (podem cair sob o agente, o pacote ou o destino — a regra de custo
          trata isso normalmente).
        * ``seed`` torna o sorteio reprodutível.

        O mundo gerado **pode não ter solução** (por exemplo, pacote cercado
        de obstáculos).  Isso é intencional: detectar esse caso é parte do
        problema e cabe ao algoritmo de busca.
        """
        if n < 1:
            raise ValueError("A dimensão do grid deve ser um inteiro >= 1.")
        rng = random.Random(seed)

        celulas = [(l, c) for l in range(n) for c in range(n)]
        rng.shuffle(celulas)
        if n == 1:
            agente = pacote = destino = celulas[0]
            restantes: list[Posicao] = []
        else:
            agente, pacote, destino = celulas[:3]
            restantes = celulas[3:]

        qtd_obst = cls._sortear_quantidade(rng, len(restantes), densidade_obstaculos, DENSIDADE_OBSTACULOS_PADRAO)
        obstaculos = frozenset(restantes[:qtd_obst])

        candidatas_pedagio = [p for p in celulas if p not in obstaculos]
        qtd_ped = cls._sortear_quantidade(rng, len(candidatas_pedagio), densidade_pedagios, DENSIDADE_PEDAGIOS_PADRAO)
        pedagios = frozenset(rng.sample(candidatas_pedagio, qtd_ped))

        return cls(n, agente, pacote, destino, obstaculos, pedagios)

    @staticmethod
    def _sortear_quantidade(
        rng: random.Random,
        total: int,
        densidade: float | tuple[float, float] | None,
        padrao: tuple[float, float],
    ) -> int:
        """Converte uma densidade (fixa ou faixa) em uma quantidade inteira de células."""
        if total <= 0:
            return 0
        if densidade is None:
            minimo, maximo = padrao
        elif isinstance(densidade, (int, float)):
            minimo = maximo = float(densidade)
        else:
            minimo, maximo = densidade
        if not (0.0 <= minimo <= maximo <= 1.0):
            raise ValueError(f"Densidade inválida: {densidade!r} (esperado valores em [0, 1]).")
        q_min = int(round(minimo * total))
        q_max = int(round(maximo * total))
        return rng.randint(q_min, q_max)

    # ------------------------------------------------------------------ #
    # Mapa fixo da prova (Figura 2, grid 4x4)
    # ------------------------------------------------------------------ #
    @classmethod
    def mapa_prova(cls) -> "Mundo":
        """
        O mundo 4x4 da Figura 2 da avaliação intermediária::

            A # . .        A = agente      (0,0)
            $ . P .        P = pacote      (1,2)
            . . # .        X = destino     (3,3)
            . . . X        # = obstáculo   $ = pedágio

        A solução ótima custa 10 (ver README).
        """
        return cls(
            n=4,
            agente=(0, 0),
            pacote=(1, 2),
            destino=(3, 3),
            obstaculos=frozenset({(0, 1), (2, 2)}),
            pedagios=frozenset({(1, 0)}),
        )

    # ------------------------------------------------------------------ #
    # Formato textual (salvar / carregar / exibir)
    # ------------------------------------------------------------------ #
    def para_texto(self) -> str:
        """
        Serializa o mundo em texto::

            n=4
            agente=0,0
            pacote=1,2
            destino=3,3
            .#..
            $...
            ..#.
            ....

        Comentários (linhas iniciadas com ``#``) só são aceitos **antes** do
        cabeçalho, pois dentro do grid ``#`` significa obstáculo.
        """
        linhas = [
            f"n={self.n}",
            f"agente={self.agente[0]},{self.agente[1]}",
            f"pacote={self.pacote[0]},{self.pacote[1]}",
            f"destino={self.destino[0]},{self.destino[1]}",
        ]
        for linha in range(self.n):
            chars = []
            for coluna in range(self.n):
                pos = (linha, coluna)
                if pos in self.obstaculos:
                    chars.append(CHAR_OBSTACULO)
                elif pos in self.pedagios:
                    chars.append(CHAR_PEDAGIO)
                else:
                    chars.append(CHAR_LIVRE)
            linhas.append("".join(chars))
        return "\n".join(linhas) + "\n"

    @classmethod
    def de_texto(cls, texto: str) -> "Mundo":
        """Reconstrói um mundo a partir do formato de :meth:`para_texto`."""
        cabecalho: dict[str, str] = {}
        grid: list[str] = []
        for bruta in texto.splitlines():
            linha = bruta.strip()
            if not linha:
                continue
            if not cabecalho and linha.startswith("#"):
                continue  # comentário antes do cabeçalho
            if "=" in linha and not grid:
                chave, valor = linha.split("=", 1)
                cabecalho[chave.strip().lower()] = valor.strip()
            else:
                grid.append(linha)

        try:
            n = int(cabecalho["n"])
            agente = cls._ler_posicao(cabecalho["agente"])
            pacote = cls._ler_posicao(cabecalho["pacote"])
            destino = cls._ler_posicao(cabecalho["destino"])
        except KeyError as erro:
            raise ValueError(f"Cabeçalho incompleto: falta '{erro.args[0]}'.") from None

        if len(grid) != n or any(len(l) != n for l in grid):
            raise ValueError(f"O grid deve ter exatamente {n} linhas de {n} caracteres.")

        obstaculos: set[Posicao] = set()
        pedagios: set[Posicao] = set()
        for l, linha in enumerate(grid):
            for c, ch in enumerate(linha):
                if ch == CHAR_OBSTACULO:
                    obstaculos.add((l, c))
                elif ch == CHAR_PEDAGIO:
                    pedagios.add((l, c))
                elif ch != CHAR_LIVRE:
                    raise ValueError(f"Caractere inválido {ch!r} na linha {l}, coluna {c}.")
        return cls(n, agente, pacote, destino, frozenset(obstaculos), frozenset(pedagios))

    @staticmethod
    def _ler_posicao(texto: str) -> Posicao:
        partes = [p.strip() for p in texto.replace("(", "").replace(")", "").split(",")]
        if len(partes) != 2:
            raise ValueError(f"Posição inválida: {texto!r} (esperado 'linha,coluna').")
        return (int(partes[0]), int(partes[1]))

    def salvar(self, caminho: str | Path) -> None:
        """Grava o mundo em um arquivo de texto."""
        Path(caminho).write_text(self.para_texto(), encoding="utf-8")

    @classmethod
    def carregar(cls, caminho: str | Path) -> "Mundo":
        """Lê um mundo de um arquivo de texto."""
        return cls.de_texto(Path(caminho).read_text(encoding="utf-8"))

    def render_ascii(
        self,
        agente: Posicao | None = None,
        pacote: Posicao | None = None,
        carregando: bool = False,
        caminho: Iterable[Posicao] = (),
    ) -> str:
        """
        Desenho em texto do grid, opcionalmente com agente/pacote em outras
        posições (para mostrar um estado intermediário) e com o caminho
        percorrido marcado com ``*``.

        Legenda: ``A`` agente, ``A+`` agente carregando o pacote, ``P`` pacote
        no chão, ``X`` destino, ``#`` obstáculo, ``$`` pedágio, ``*`` célula
        do caminho.  Marcas se combinam (``AP`` = agente sobre o pacote,
        ``A$`` = agente em pedágio).
        """
        agente = self.agente if agente is None else agente
        pacote = self.pacote if pacote is None else pacote
        marcados = set(caminho)
        linhas = []
        for linha in range(self.n):
            celulas = []
            for coluna in range(self.n):
                pos = (linha, coluna)
                if pos in self.obstaculos:
                    tok = "###"
                else:
                    marca = ""
                    if pos == agente:
                        marca += "A+" if carregando else "A"
                    if pos == pacote and not carregando:
                        marca += "P"
                    if pos == self.destino:
                        marca += "X"
                    if not marca and pos in marcados:
                        marca = "*"
                    if pos in self.pedagios:
                        marca += "$"
                    tok = marca or "."
                    tok = f"{tok:^3}"
                celulas.append(tok)
            linhas.append("".join(celulas))
        return "\n".join(linhas)

    def __str__(self) -> str:  # pragma: no cover - conveniência
        return self.render_ascii()
