"""Testes da representação do estado, dos sucessores e da heurística."""

import pytest

from entregador.busca import custo_uniforme
from entregador.estado import ACAO_ENTREGAR, ACAO_PEGAR, EstadoEntrega
from entregador.mundo import Mundo


def _por_acao(estados):
    return {e.operator: e for e in estados}


def test_estado_inicial_e_final_da_prova():
    m = Mundo.mapa_prova()
    inicial = EstadoEntrega.inicial(m)
    assert inicial.agente == (0, 0)
    assert inicial.pacote == (1, 2)
    assert not inicial.carregando
    assert not inicial.is_goal()
    assert inicial.env() == "((0, 0), (1, 2))"

    final = EstadoEntrega("entregar", m, (3, 3), (3, 3), 1)
    assert final.is_goal()
    assert final.env() == "((3, 3), (3, 3))"


def test_sucessores_do_estado_inicial_da_prova_so_permitem_descer():
    # Em (0,0): cima e esquerda saem do grid, direita é obstáculo -> só "baixo".
    inicial = EstadoEntrega.inicial(Mundo.mapa_prova())
    suc = _por_acao(inicial.successors())
    assert set(suc) == {"baixo"}
    assert suc["baixo"].agente == (1, 0)
    assert suc["baixo"].pacote == (1, 2)  # pacote continua no chão
    assert suc["baixo"].cost() == 1  # ação executada fora do pedágio


def test_acao_executada_em_pedagio_custa_3():
    m = Mundo.mapa_prova()
    no_pedagio = EstadoEntrega("baixo", m, (1, 0), m.pacote, 1)
    suc = _por_acao(no_pedagio.successors())
    assert set(suc) == {"cima", "baixo", "direita"}  # esquerda sai do grid
    assert all(e.cost() == 3 for e in suc.values())


def test_pegar_so_quando_sobre_o_pacote_e_entregar_so_quando_carregando():
    m = Mundo.mapa_prova()
    longe = EstadoEntrega("", m, (1, 1), m.pacote)
    assert ACAO_PEGAR not in _por_acao(longe.successors())
    assert ACAO_ENTREGAR not in _por_acao(longe.successors())

    sobre = EstadoEntrega("", m, m.pacote, m.pacote)
    suc = _por_acao(sobre.successors())
    assert ACAO_PEGAR in suc and ACAO_ENTREGAR not in suc
    carregando = suc[ACAO_PEGAR]
    assert carregando.carregando and carregando.pacote is None
    assert carregando.posicao_pacote == carregando.agente

    suc2 = _por_acao(carregando.successors())
    assert ACAO_ENTREGAR in suc2 and ACAO_PEGAR not in suc2
    # O pacote vai junto com o agente ao se mover.
    assert suc2["direita"].carregando and suc2["direita"].agente == (1, 3)
    # Entregar deixa o pacote na célula atual (fora do destino não é meta).
    largado = suc2[ACAO_ENTREGAR]
    assert largado.pacote == (1, 2) and not largado.is_goal()


def test_entregar_no_destino_gera_estado_final():
    m = Mundo.mapa_prova()
    no_destino = EstadoEntrega("baixo", m, (3, 3), None, 1)
    suc = _por_acao(no_destino.successors())
    assert suc[ACAO_ENTREGAR].is_goal()


def test_movimentos_nulos_nao_geram_sucessores():
    m = Mundo(3, (0, 0), (2, 2), (1, 1), frozenset({(0, 1), (1, 0)}), frozenset())
    inicial = EstadoEntrega.inicial(m)
    assert inicial.successors() == []  # cercado: nenhum sucessor, nada de "ficar parado"


def test_valores_da_heuristica():
    m = Mundo.mapa_prova()
    inicial = EstadoEntrega.inicial(m)
    # d((0,0),(1,2)) = 3 ; d((1,2),(3,3)) = 3 ; +2 (pegar e entregar) = 8 <= custo real 10
    assert inicial.h() == 8
    carregando = EstadoEntrega("pegar", m, (1, 2), None, 1)
    assert carregando.h() == 3 + 1
    no_destino_carregando = EstadoEntrega("baixo", m, (3, 3), None, 1)
    assert no_destino_carregando.h() == 1
    final = EstadoEntrega("entregar", m, (3, 3), (3, 3), 1)
    assert final.h() == 0


def _todos_os_estados(inicial):
    """Explora o grafo de estados inteiro (pequeno) a partir do inicial."""
    vistos = {inicial.chave(): inicial}
    pilha = [inicial]
    while pilha:
        s = pilha.pop()
        for t in s.successors():
            if t.chave() not in vistos:
                vistos[t.chave()] = t
                pilha.append(t)
    return list(vistos.values())


@pytest.mark.parametrize("seed", range(25))
def test_heuristica_eh_admissivel_e_consistente(seed):
    m = Mundo.gerar_aleatorio(4, seed=seed)
    for estado in _todos_os_estados(EstadoEntrega.inicial(m)):
        # Consistência: h(s) <= c(s, s') + h(s')
        for s2 in estado.successors():
            assert estado.h() <= s2.cost() + s2.h(), (seed, estado, s2)
        # Admissibilidade: h(s) <= custo ótimo real a partir de s (via custo uniforme).
        real = custo_uniforme(estado)
        if real.encontrou:
            assert estado.h() <= real.custo_total, (seed, estado)


def test_igualdade_e_hash_dependem_apenas_de_agente_e_pacote():
    m = Mundo.mapa_prova()
    a = EstadoEntrega("cima", m, (1, 1), (1, 2), 1)
    b = EstadoEntrega("baixo", m, (1, 1), (1, 2), 3)
    assert a == b and hash(a) == hash(b)
    assert a != EstadoEntrega("cima", m, (1, 1), None, 1)
