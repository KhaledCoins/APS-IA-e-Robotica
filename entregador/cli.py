"""
Execução pelo terminal (sem interface gráfica).

Exemplos::

    python -m entregador.cli --prova                      # mapa da Figura 2 (custo 10)
    python -m entregador.cli --n 10 --seed 42             # mundo aleatório reprodutível
    python -m entregador.cli --mapa exemplos/mapas/exemplo_10x10.txt --algoritmo todos
    python -m entregador.cli --n 8 --passos               # mostra o grid após cada ação
    python -m entregador.cli --n 12 --salvar meu_mapa.txt # guarda o mundo sorteado
"""

from __future__ import annotations

import argparse
import sys

from entregador.busca import ALGORITMOS, Resultado, resolver
from entregador.mundo import Mundo


def _faixa(texto: str) -> float | tuple[float, float]:
    """Aceita '0.2' ou '0.1-0.3' para densidades."""
    if "-" in texto:
        a, b = texto.split("-", 1)
        return (float(a), float(b))
    return float(texto)


def montar_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m entregador.cli",
        description="Entregador em grid: encontra o plano ótimo para pegar e entregar o pacote.",
    )
    origem = p.add_mutually_exclusive_group()
    origem.add_argument("--prova", action="store_true", help="usa o mapa 4x4 da Figura 2 da prova")
    origem.add_argument("--mapa", metavar="ARQUIVO", help="carrega um mundo de um arquivo de texto")
    p.add_argument("--n", type=int, default=8, help="dimensão do grid aleatório (padrão: 8)")
    p.add_argument("--seed", type=int, default=None, help="semente do sorteio (reprodutibilidade)")
    p.add_argument("--obstaculos", type=_faixa, default=None, metavar="D", help="densidade de obstáculos: 0.2 ou 0.1-0.3")
    p.add_argument("--pedagios", type=_faixa, default=None, metavar="D", help="densidade de pedágios: 0.1 ou 0.0-0.2")
    p.add_argument(
        "--algoritmo",
        choices=[*ALGORITMOS, "todos"],
        default="a_estrela",
        help="algoritmo de busca (padrão: a_estrela)",
    )
    p.add_argument("--passos", action="store_true", help="imprime o grid após cada ação do plano")
    p.add_argument("--salvar", metavar="ARQUIVO", help="salva o mundo usado em um arquivo")
    return p


def imprimir_resultado(r: Resultado, passos: bool = False) -> None:
    print(f"== {r.algoritmo} ==")
    print(r.descricao_plano())
    print(r.resumo())
    if r.encontrou and r.plano:
        print("\nCaminho percorrido (*):")
        print(r.mundo.render_ascii(caminho=r.celulas_percorridas()))
    if passos and r.encontrou:
        for i, estado in enumerate(r.estados):
            titulo = "estado inicial" if i == 0 else f"após '{r.plano[i - 1].acao}' (acumulado {r.plano[i - 1].custo_acumulado})"
            print(f"\n-- passo {i}: {titulo}")
            print(r.mundo.render_ascii(estado.agente, estado.posicao_pacote, estado.carregando))
    print()


def main(argv: list[str] | None = None) -> int:
    """
    Executa a CLI.  Código de saída: 0 se encontrou solução, 1 se o mundo não
    tem solução, 2 se os argumentos/arquivos são inválidos.
    """
    parser = montar_parser()
    args = parser.parse_args(argv)

    try:
        if args.prova:
            mundo = Mundo.mapa_prova()
            origem = "mapa da prova (Figura 2)"
        elif args.mapa:
            mundo = Mundo.carregar(args.mapa)
            origem = f"arquivo {args.mapa}"
        else:
            mundo = Mundo.gerar_aleatorio(args.n, args.seed, args.obstaculos, args.pedagios)
            origem = f"aleatório n={args.n}" + (f", seed={args.seed}" if args.seed is not None else "")
        if args.salvar:
            mundo.salvar(args.salvar)
    except FileNotFoundError as erro:
        parser.exit(2, f"erro: arquivo não encontrado: {erro.filename}\n")
    except (OSError, ValueError) as erro:
        parser.exit(2, f"erro: {erro}\n")

    print(f"Mundo: {origem} | {mundo.n}x{mundo.n} | agente {mundo.agente}, pacote {mundo.pacote}, destino {mundo.destino}")
    print(f"Obstáculos: {len(mundo.obstaculos)} | Pedágios: {len(mundo.pedagios)}")
    print("Legenda: A agente (A+ = carregando o pacote), P pacote, X destino, ### obstáculo, $ pedágio, * caminho\n")
    print(mundo.render_ascii())
    print()

    algoritmos = list(ALGORITMOS) if args.algoritmo == "todos" else [args.algoritmo]
    resultados = [resolver(mundo, a) for a in algoritmos]
    for r in resultados:
        imprimir_resultado(r, args.passos)

    if len(resultados) > 1:
        print("== Comparação ==")
        for r in resultados:
            custo = r.custo_total if r.encontrou else "-"
            otimo = "ótimo" if r.otimo_garantido else "não garante ótimo"
            print(f"{r.algoritmo:<16} custo {custo!s:<4} ações {r.num_acoes:<4} expandidos {r.nos_expandidos:<6} ({otimo})")
    return 0 if resultados[0].encontrou else 1


if __name__ == "__main__":
    sys.exit(main())
