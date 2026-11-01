"""Testes dos algoritmos de busca: otimalidade, detecção de 'sem solução', comparação."""

import pytest

from conftest import MAPAS
from entregador.busca import ALGORITMOS, a_estrela, busca_largura, custo_uniforme, diagnostico, resolver
from entregador.estado import EstadoEntrega
from entregador.mundo import Mundo

PLANO_DA_PROVA = ["baixo", "direita", "direita", "pegar", "direita", "baixo", "baixo", "entregar"]


@pytest.mark.parametrize("algoritmo", list(ALGORITMOS))
def test_mapa_da_prova_tem_custo_10(algoritmo):
    r = resolver(Mundo.mapa_prova(), algoritmo)
    assert r.encontrou
    assert r.custo_total == 10
    assert r.acoes == PLANO_DA_PROVA
    assert r.num_acoes == 8
    # Custos por ação: só a segunda ação (executada no pedágio (1,0)) custa 3.
    assert [p.custo_acao for p in r.plano] == [1, 3, 1, 1, 1, 1, 1, 1]
    assert [p.custo_acumulado for p in r.plano] == [1, 4, 5, 6, 7, 8, 9, 10]
    assert r.estados[0].agente == (0, 0) and r.estados[-1].is_goal()


def test_plano_eh_executavel_passo_a_passo():
    """Reaplica o plano devolvido usando apenas successors(): cada ação precisa ser válida."""
    for seed in range(40):
        m = Mundo.gerar_aleatorio(6, seed=seed)
        r = a_estrela(EstadoEntrega.inicial(m))
        if not r.encontrou:
            continue
        atual = EstadoEntrega.inicial(m)
        custo = 0
        for passo in r.plano:
            opcoes = {s.operator: s for s in atual.successors()}
            assert passo.acao in opcoes, (seed, passo)
            atual = opcoes[passo.acao]
            custo += atual.cost()
        assert atual.is_goal() and custo == r.custo_total


@pytest.mark.parametrize("n", [3, 4, 6, 9])
def test_a_estrela_e_custo_uniforme_concordam_em_mundos_aleatorios(n):
    for seed in range(60):
        m = Mundo.gerar_aleatorio(n, seed=seed)
        ra = a_estrela(EstadoEntrega.inicial(m))
        ru = custo_uniforme(EstadoEntrega.inicial(m))
        assert ra.encontrou == ru.encontrou == m.tem_solucao(), seed
        if ra.encontrou:
            assert ra.custo_total == ru.custo_total, seed


def test_largura_nunca_e_melhor_e_as_vezes_e_pior():
    piores = 0
    for seed in range(150):
        m = Mundo.gerar_aleatorio(5, seed=seed)
        ra = a_estrela(EstadoEntrega.inicial(m))
        rl = busca_largura(EstadoEntrega.inicial(m))
        assert ra.encontrou == rl.encontrou
        if ra.encontrou:
            assert rl.custo_total >= ra.custo_total
            assert rl.num_acoes <= ra.num_acoes  # largura minimiza número de ações
            piores += rl.custo_total > ra.custo_total
    assert piores > 0


def test_contraexemplo_fixo_da_largura():
    m = Mundo.carregar(MAPAS / "largura_nao_otima_3x3.txt")
    assert resolver(m, "a_estrela").custo_total == 8
    assert resolver(m, "custo_uniforme").custo_total == 8
    rl = resolver(m, "largura")
    assert rl.custo_total == 12 and rl.num_acoes == 6
    assert not rl.otimo_garantido


def test_mundos_sem_solucao_sao_detectados():
    casos = {
        "sem_solucao_pacote_cercado_5x5.txt": "pacote",
        "sem_solucao_destino_cercado_5x5.txt": "destino",
        "sem_solucao_agente_cercado_4x4.txt": "agente",
    }
    for arquivo, palavra in casos.items():
        m = Mundo.carregar(MAPAS / arquivo)
        assert not m.tem_solucao()
        for algoritmo in ALGORITMOS:
            r = resolver(m, algoritmo)
            assert not r.encontrou, (arquivo, algoritmo)
            assert r.plano == [] and r.custo_total == 0
            assert palavra in r.diagnostico.lower()
            assert r.descricao_plano().startswith("SEM SOLUÇÃO")


def test_diagnostico_quando_ha_solucao():
    assert diagnostico(Mundo.mapa_prova()) == "Existe solução."


def test_pacote_ja_no_destino_da_plano_vazio():
    m = Mundo(3, (0, 0), (2, 2), (2, 2), frozenset(), frozenset())
    for algoritmo in ALGORITMOS:
        r = resolver(m, algoritmo)
        assert r.encontrou and r.plano == [] and r.custo_total == 0
        assert "já está no destino" in r.descricao_plano()


def test_grid_1x1():
    m = Mundo.gerar_aleatorio(1, seed=0)
    r = resolver(m)
    assert r.encontrou and r.custo_total == 0


def test_pedagio_na_celula_inicial_encarece_a_primeira_acao():
    m = Mundo(2, (0, 0), (0, 1), (1, 1), frozenset(), frozenset({(0, 0)}))
    r = resolver(m)
    assert r.acoes == ["direita", "pegar", "baixo", "entregar"]
    assert [p.custo_acao for p in r.plano] == [3, 1, 1, 1]
    assert r.custo_total == 6


def test_desvia_de_pedagio_quando_compensa():
    # Caminho reto passa por pedágio (custo maior); o desvio por fora é mais barato.
    # Reto: 1 + 3 + 3 = 7 para chegar ao pacote; por cima: 5 movimentos de custo 1.
    m = Mundo.de_texto("n=4\nagente=1,0\npacote=1,3\ndestino=0,3\n....\n.$$.\n....\n....\n")
    r = resolver(m)
    assert r.encontrou and r.custo_total == 8
    assert not (set(r.celulas_percorridas()) & m.pedagios)  # não pisa em pedágio
    assert resolver(m, "largura").custo_total == 10  # largura vai reto (menos ações, mais caro)


def test_exemplos_fixos_maiores_resolvem_rapido():
    for arquivo, custo in (("exemplo_10x10.txt", 41), ("exemplo_20x20.txt", 59)):
        r = resolver(Mundo.carregar(MAPAS / arquivo))
        assert r.encontrou and r.custo_total == custo
        assert r.tempo_s < 1.0


def test_grid_grande_termina_em_tempo_razoavel():
    m = Mundo.gerar_aleatorio(60, seed=7, densidade_obstaculos=0.2, densidade_pedagios=0.1)
    r = resolver(m)
    assert r.tempo_s < 5.0
    assert r.encontrou == m.tem_solucao()


def test_algoritmo_desconhecido():
    with pytest.raises(ValueError):
        resolver(Mundo.mapa_prova(), "dfs")
