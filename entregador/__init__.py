"""
Pacote ``entregador`` — APS de Inteligência Artificial e Robótica (Insper).

Problema: um agente em um mundo em grid quadrado (com obstáculos e células
de pedágio) precisa pegar um pacote e entregá-lo na célula de destino com o
menor custo possível.

Módulos:

- :mod:`entregador.mundo`  — o ambiente (grid, obstáculos, pedágios, posições)
  e a geração aleatória de mundos.
- :mod:`entregador.estado` — a representação do estado e a geração de
  sucessores (interface compatível com a biblioteca ``aigyminsper``).
- :mod:`entregador.busca`  — os algoritmos de busca (A*, custo uniforme e,
  para comparação, busca em largura) e o diagnóstico de "sem solução".
- :mod:`entregador.gui`    — interface gráfica (tkinter).
- :mod:`entregador.cli`    — execução pelo terminal.
"""

from entregador.mundo import Mundo, Posicao
from entregador.estado import EstadoEntrega
from entregador.busca import (
    Resultado,
    Passo,
    a_estrela,
    custo_uniforme,
    busca_largura,
    resolver,
    diagnostico,
    ALGORITMOS,
)

__all__ = [
    "Mundo",
    "Posicao",
    "EstadoEntrega",
    "Resultado",
    "Passo",
    "a_estrela",
    "custo_uniforme",
    "busca_largura",
    "resolver",
    "diagnostico",
    "ALGORITMOS",
]

__version__ = "1.0.0"
