"""
Compatibilidade com a biblioteca do curso (``aigyminsper``).

Estes testes só rodam se a biblioteca estiver instalada.  Eles verificam que
o nosso ``EstadoEntrega`` funciona com os algoritmos da biblioteca e
documentam a limitação da poda ``"general"`` com custos não uniformes.
"""

import contextlib
import io

import pytest

from conftest import MAPAS
from entregador.estado import AIGYMINSPER_DISPONIVEL, EstadoEntrega
from entregador.mundo import Mundo

pytestmark = pytest.mark.skipif(not AIGYMINSPER_DISPONIVEL, reason="aigyminsper não instalada")

if AIGYMINSPER_DISPONIVEL:
    with contextlib.redirect_stdout(io.StringIO()):  # a biblioteca imprime ao importar
        from aigyminsper.search.graph import HeuristicState
        from aigyminsper.search.search_algorithms import AEstrela, BuscaCustoUniforme, BuscaLargura


def test_estado_eh_um_heuristic_state_da_biblioteca():
    assert issubclass(EstadoEntrega, HeuristicState)


def test_a_estrela_da_biblioteca_resolve_a_prova_com_custo_10():
    no = AEstrela().search(EstadoEntrega.inicial(Mundo.mapa_prova()), pruning="father-son")
    assert no is not None and no.g == 10
    assert no.show_path() == " ; baixo ; direita ; direita ; pegar ; direita ; baixo ; baixo ; entregar"


def test_custo_uniforme_da_biblioteca_resolve_a_prova():
    no = BuscaCustoUniforme().search(EstadoEntrega.inicial(Mundo.mapa_prova()), pruning="general")
    assert no is not None and no.g == 10


def test_biblioteca_detecta_sem_solucao():
    m = Mundo.carregar(MAPAS / "sem_solucao_pacote_cercado_5x5.txt")
    assert AEstrela().search(EstadoEntrega.inicial(m), pruning="general") is None
    assert BuscaLargura().search(EstadoEntrega.inicial(m), pruning="general") is None


def test_algoritmos_proprios_no_formato_da_biblioteca():
    """AEstrelaGrafo/CustoUniformeGrafo são SearchAlgorithm da biblioteca e devolvem Node."""
    from aigyminsper.search.graph import Node
    from aigyminsper.search.search_algorithms import SearchAlgorithm

    from entregador.compat_aigyminsper import AEstrelaGrafo, CustoUniformeGrafo

    assert issubclass(AEstrelaGrafo, SearchAlgorithm) and issubclass(CustoUniformeGrafo, SearchAlgorithm)
    for algoritmo in (AEstrelaGrafo, CustoUniformeGrafo):
        no = algoritmo().search(EstadoEntrega.inicial(Mundo.mapa_prova()))
        assert isinstance(no, Node) and no.g == 10
        assert no.show_path() == " ; baixo ; direita ; direita ; pegar ; direita ; baixo ; baixo ; entregar"
        # No contraexemplo da poda "general" eles acham o ótimo (7), pois fecham estados na expansão.
        m = Mundo.carregar(MAPAS / "poda_biblioteca_3x3.txt")
        assert algoritmo().search(EstadoEntrega.inicial(m)).g == 7
        assert algoritmo().search(EstadoEntrega.inicial(Mundo.carregar(MAPAS / "sem_solucao_agente_cercado_4x4.txt"))) is None
    # Concordam com a implementação própria em mundos aleatórios.
    from entregador.busca import resolver

    for seed in range(60):
        m = Mundo.gerar_aleatorio(3 + seed % 6, seed=seed)
        r = resolver(m)
        for algoritmo in (AEstrelaGrafo, CustoUniformeGrafo):
            no = algoritmo().search(EstadoEntrega.inicial(m))
            assert (no is None) == (not r.encontrou)
            if no is not None:
                assert no.g == r.custo_total


def test_poda_general_da_biblioteca_pode_ser_subotima_com_pedagio():
    """Documenta a limitação: estado marcado como visitado na geração, não na expansão."""
    m = Mundo.carregar(MAPAS / "poda_biblioteca_3x3.txt")
    otimo = AEstrela().search(EstadoEntrega.inicial(m), pruning="father-son").g
    assert otimo == 7
    com_poda_general = AEstrela().search(EstadoEntrega.inicial(m), pruning="general").g
    assert com_poda_general == 9  # sub-ótimo
