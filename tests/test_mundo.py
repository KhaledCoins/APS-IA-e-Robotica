"""Testes do ambiente (geração aleatória, validação, serialização)."""

import pytest

from entregador.mundo import Mundo


def test_mapa_prova_tem_a_configuracao_da_figura_2():
    m = Mundo.mapa_prova()
    assert m.n == 4
    assert m.agente == (0, 0)
    assert m.pacote == (1, 2)
    assert m.destino == (3, 3)
    assert m.obstaculos == {(0, 1), (2, 2)}
    assert m.pedagios == {(1, 0)}


def test_custo_da_acao_depende_da_celula_onde_o_agente_esta():
    m = Mundo.mapa_prova()
    assert m.custo_acao_em((0, 0)) == 1
    assert m.custo_acao_em((1, 0)) == 3  # pedágio: custo = custo + 2


def test_transitavel_respeita_borda_e_obstaculos():
    m = Mundo.mapa_prova()
    assert m.transitavel((0, 0))
    assert not m.transitavel((0, 1))  # obstáculo
    assert not m.transitavel((-1, 0))  # fora do grid
    assert not m.transitavel((0, 4))  # fora do grid
    assert sorted(m.vizinhos_transitaveis((0, 0))) == [(1, 0)]


@pytest.mark.parametrize("n", [1, 2, 3, 5, 10, 25])
def test_geracao_aleatoria_produz_mundo_valido(n):
    for seed in range(20):
        m = Mundo.gerar_aleatorio(n, seed=seed)
        assert m.n == n
        for pos in (m.agente, m.pacote, m.destino):
            assert m.dentro(pos)
            assert pos not in m.obstaculos
        if n >= 2:
            assert len({m.agente, m.pacote, m.destino}) == 3
        assert not (m.obstaculos & m.pedagios)
        assert all(m.dentro(p) for p in m.obstaculos | m.pedagios)


def test_geracao_aleatoria_eh_reprodutivel_com_seed():
    assert Mundo.gerar_aleatorio(8, seed=123) == Mundo.gerar_aleatorio(8, seed=123)
    assert Mundo.gerar_aleatorio(8, seed=123) != Mundo.gerar_aleatorio(8, seed=124)


def test_quantidade_de_obstaculos_e_pedagios_varia_entre_mundos():
    quantidades = {len(Mundo.gerar_aleatorio(10, seed=s).obstaculos) for s in range(30)}
    assert len(quantidades) > 1  # a quantidade também é sorteada, não só a posição
    pedagios = {len(Mundo.gerar_aleatorio(10, seed=s).pedagios) for s in range(30)}
    assert len(pedagios) > 1


def test_densidades_fixas_sao_respeitadas():
    m = Mundo.gerar_aleatorio(10, seed=1, densidade_obstaculos=0.0, densidade_pedagios=0.0)
    assert not m.obstaculos and not m.pedagios
    m = Mundo.gerar_aleatorio(10, seed=1, densidade_obstaculos=0.5, densidade_pedagios=0.0)
    assert len(m.obstaculos) == round(0.5 * (100 - 3))
    with pytest.raises(ValueError):
        Mundo.gerar_aleatorio(5, seed=1, densidade_obstaculos=1.5)


def test_mundo_sem_solucao_eventualmente_eh_gerado():
    # Entre muitos mundos aleatórios alguns não têm solução (pacote cercado etc.).
    resultados = [Mundo.gerar_aleatorio(5, seed=s).tem_solucao() for s in range(300)]
    assert any(resultados) and not all(resultados)


def test_validacao_rejeita_mundos_invalidos():
    with pytest.raises(ValueError):
        Mundo(0, (0, 0), (0, 0), (0, 0), frozenset(), frozenset())
    with pytest.raises(ValueError):  # agente fora do grid
        Mundo(3, (3, 0), (0, 0), (1, 1), frozenset(), frozenset())
    with pytest.raises(ValueError):  # pacote sobre obstáculo
        Mundo(3, (0, 0), (1, 1), (2, 2), frozenset({(1, 1)}), frozenset())
    with pytest.raises(ValueError):  # obstáculo e pedágio na mesma célula
        Mundo(3, (0, 0), (0, 1), (2, 2), frozenset({(1, 1)}), frozenset({(1, 1)}))


def test_serializacao_ida_e_volta():
    original = Mundo.mapa_prova()
    texto = original.para_texto()
    assert Mundo.de_texto(texto) == original
    assert texto.splitlines()[4:] == [".#..", "$...", "..#.", "...."]
    for seed in range(10):
        m = Mundo.gerar_aleatorio(7, seed=seed)
        assert Mundo.de_texto(m.para_texto()) == m


def test_de_texto_aceita_comentarios_e_rejeita_grid_errado():
    texto = "# mapa da prova\n" + Mundo.mapa_prova().para_texto()
    assert Mundo.de_texto(texto) == Mundo.mapa_prova()
    with pytest.raises(ValueError):
        Mundo.de_texto("n=2\nagente=0,0\npacote=0,1\ndestino=1,1\n..\n")  # falta uma linha
    with pytest.raises(ValueError):
        Mundo.de_texto("n=2\nagente=0,0\npacote=0,1\ndestino=1,1\n..\n.?\n")  # caractere inválido


def test_render_ascii_mostra_marcas_corretas():
    desenho = Mundo.mapa_prova().render_ascii()
    linhas = desenho.splitlines()
    assert len(linhas) == 4
    assert "A" in linhas[0] and "###" in linhas[0]
    assert "$" in linhas[1] and "P" in linhas[1]
    assert "X" in linhas[3]
