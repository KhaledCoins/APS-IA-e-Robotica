"""
Interface gráfica (tkinter — faz parte da biblioteca padrão do Python).

Permite:

* definir a dimensão N do grid e (opcionalmente) as densidades de
  obstáculos/pedágios e uma seed;
* gerar um mundo aleatório, carregar o mapa da prova ou abrir/salvar um
  mapa em arquivo;
* escolher o algoritmo (A*, custo uniforme ou largura — esta só para
  comparação) e resolver;
* ver o plano passo a passo, com custo por ação e custo acumulado, as
  estatísticas da busca e a animação do agente executando o plano;
* ser avisado, em destaque, quando o mundo **não tem solução** (e por quê).

A busca roda em uma *thread* separada para a janela não travar em grids
grandes (o custo uniforme e a largura exploram centenas de milhares de nós
em grids 60x60; o A* resolve os mesmos grids em milissegundos).
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from entregador.busca import ALGORITMOS, NOMES_ALGORITMOS, Resultado, resolver
from entregador.estado import EstadoEntrega
from entregador.mundo import Mundo, Posicao

CORES = {
    "livre": "#ffffff",
    "obstaculo": "#1f1f1f",
    "pedagio": "#b9b9b9",
    "grade": "#8a8a8a",
    "caminho": "#dbeafe",
    "linha_caminho": "#2563eb",
    "linha_volta": "#ea580c",
    "agente": "#1d4ed8",
    "pacote": "#b45309",
    "pacote_topo": "#f59e0b",
    "destino": "#dc2626",
    "atual": "#facc15",
    "ok": "#15803d",
    "erro": "#b91c1c",
    "aviso": "#b45309",
}

N_MIN, N_MAX = 1, 80
SEED_INVALIDA = object()
# Acima desta dimensão, custo uniforme e largura podem levar minutos (exploram
# centenas de milhares de estados); o A* resolve em milissegundos.
N_AVISO_LENTO = 40


class Aplicacao:
    """Janela principal."""

    def __init__(self, raiz: tk.Tk) -> None:
        self.raiz = raiz
        raiz.title("Entregador em Grid — APS de IA e Robótica")
        raiz.minsize(960, 620)
        raiz.geometry("1180x720")

        self.mundo: Optional[Mundo] = None
        self.resultado: Optional[Resultado] = None
        self.estado_exibido: Optional[EstadoEntrega] = None
        self.indice_animacao = 0
        self._animando = False
        self._job_animacao: Optional[str] = None
        self._fila: "queue.Queue[tuple[int, object]]" = queue.Queue()
        self._pedido_atual = 0  # identifica cada pedido de busca; resultados de pedidos antigos são descartados
        self._buscando = False
        self._consultando_fila = False

        self._montar_painel()
        self._montar_canvas()
        self.gerar_aleatorio()

    # ================================================================== #
    # Construção da interface
    # ================================================================== #
    def _montar_painel(self) -> None:
        painel = ttk.Frame(self.raiz, padding=10)
        painel.pack(side="left", fill="y")
        self.painel = painel

        # --- Mundo ------------------------------------------------------ #
        grupo = ttk.LabelFrame(painel, text="Mundo", padding=8)
        grupo.pack(fill="x")

        ttk.Label(grupo, text="Dimensão (N):").grid(row=0, column=0, sticky="w")
        self.var_n = tk.StringVar(value="8")
        ttk.Spinbox(grupo, from_=N_MIN, to=N_MAX, textvariable=self.var_n, width=5).grid(row=0, column=1, sticky="w")
        ttk.Label(grupo, text="Seed:").grid(row=0, column=2, sticky="e", padx=(8, 2))
        self.var_seed = tk.StringVar(value="")
        ttk.Entry(grupo, textvariable=self.var_seed, width=8).grid(row=0, column=3, sticky="w")

        self.var_densidade_auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            grupo,
            text="Quantidade de obstáculos/pedágios aleatória",
            variable=self.var_densidade_auto,
            command=self._atualizar_escalas,
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))

        ttk.Label(grupo, text="Obstáculos (%):").grid(row=2, column=0, sticky="w")
        self.var_obst = tk.IntVar(value=20)
        self.escala_obst = ttk.Scale(grupo, from_=0, to=60, variable=self.var_obst, command=lambda _v: self._atualizar_rotulos())
        self.escala_obst.grid(row=2, column=1, columnspan=2, sticky="we")
        self.rotulo_obst = ttk.Label(grupo, text="20", width=3)
        self.rotulo_obst.grid(row=2, column=3, sticky="w")

        ttk.Label(grupo, text="Pedágios (%):").grid(row=3, column=0, sticky="w")
        self.var_ped = tk.IntVar(value=10)
        self.escala_ped = ttk.Scale(grupo, from_=0, to=60, variable=self.var_ped, command=lambda _v: self._atualizar_rotulos())
        self.escala_ped.grid(row=3, column=1, columnspan=2, sticky="we")
        self.rotulo_ped = ttk.Label(grupo, text="10", width=3)
        self.rotulo_ped.grid(row=3, column=3, sticky="w")
        grupo.columnconfigure(1, weight=1)

        botoes = ttk.Frame(grupo)
        botoes.grid(row=4, column=0, columnspan=4, sticky="we", pady=(8, 0))
        linha = ttk.Frame(botoes)
        linha.pack(fill="x")
        self.btn_gerar = ttk.Button(linha, text="Gerar mundo aleatório", command=self.gerar_aleatorio)
        self.btn_gerar.pack(side="left", expand=True, fill="x")
        self.btn_prova = ttk.Button(linha, text="Mapa da prova (4×4)", command=self.carregar_prova)
        self.btn_prova.pack(side="left", expand=True, fill="x", padx=(4, 0))
        linha = ttk.Frame(botoes)
        linha.pack(fill="x", pady=(4, 0))
        self.btn_abrir = ttk.Button(linha, text="Abrir mapa…", command=self.abrir_mapa)
        self.btn_abrir.pack(side="left", expand=True, fill="x")
        self.btn_salvar = ttk.Button(linha, text="Salvar mapa…", command=self.salvar_mapa)
        self.btn_salvar.pack(side="left", expand=True, fill="x", padx=(4, 0))

        # --- Busca ------------------------------------------------------ #
        grupo2 = ttk.LabelFrame(painel, text="Busca", padding=8)
        grupo2.pack(fill="x", pady=(10, 0))
        self.var_alg = tk.StringVar(value="a_estrela")
        for chave in ALGORITMOS:
            ttk.Radiobutton(grupo2, text=NOMES_ALGORITMOS[chave], value=chave, variable=self.var_alg).pack(anchor="w")
        self.btn_resolver = ttk.Button(grupo2, text="Resolver", command=self.resolver)
        self.btn_resolver.pack(fill="x", pady=(6, 0))

        # --- Animação --------------------------------------------------- #
        grupo3 = ttk.LabelFrame(painel, text="Animação do plano", padding=8)
        grupo3.pack(fill="x", pady=(10, 0))
        linha = ttk.Frame(grupo3)
        linha.pack(fill="x")
        self.btn_animar = ttk.Button(linha, text="▶ Animar", command=self.animar, state="disabled")
        self.btn_animar.pack(side="left", expand=True, fill="x")
        self.btn_passo = ttk.Button(linha, text="Passo ▶", command=self.passo, state="disabled")
        self.btn_passo.pack(side="left", expand=True, fill="x", padx=(4, 0))
        self.btn_reiniciar = ttk.Button(linha, text="⟲", width=3, command=self.reiniciar_animacao, state="disabled")
        self.btn_reiniciar.pack(side="left", padx=(4, 0))
        linha = ttk.Frame(grupo3)
        linha.pack(fill="x", pady=(4, 0))
        ttk.Label(linha, text="Velocidade:").pack(side="left")
        self.var_vel = tk.IntVar(value=5)
        ttk.Scale(linha, from_=1, to=10, variable=self.var_vel).pack(side="left", fill="x", expand=True, padx=(6, 0))

        # --- Resultado -------------------------------------------------- #
        grupo4 = ttk.LabelFrame(painel, text="Resultado", padding=8)
        grupo4.pack(fill="both", expand=True, pady=(10, 0))
        self.var_status = tk.StringVar(value="")
        self.rotulo_status = ttk.Label(grupo4, textvariable=self.var_status, wraplength=300, font=("TkDefaultFont", 10, "bold"))
        self.rotulo_status.pack(anchor="w")
        self.var_stats = tk.StringVar(value="")
        ttk.Label(grupo4, textvariable=self.var_stats, wraplength=300).pack(anchor="w", pady=(2, 4))

        quadro = ttk.Frame(grupo4)
        quadro.pack(fill="both", expand=True)
        self.texto_plano = tk.Text(quadro, width=40, height=9, wrap="none", state="disabled", font=("TkFixedFont", 9))
        barra = ttk.Scrollbar(quadro, orient="vertical", command=self.texto_plano.yview)
        self.texto_plano.configure(yscrollcommand=barra.set)
        self.texto_plano.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.texto_plano.tag_configure("pedagio", foreground=CORES["aviso"])
        self.texto_plano.tag_configure("atual", background=CORES["atual"])
        self.texto_plano.tag_configure("total", font=("TkFixedFont", 9, "bold"))

        self._atualizar_escalas()

    def _montar_canvas(self) -> None:
        direita = ttk.Frame(self.raiz, padding=(0, 10, 10, 10))
        direita.pack(side="right", fill="both", expand=True)
        self.canvas = tk.Canvas(direita, bg="#f3f4f6", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.desenhar())
        legenda = (
            "Legenda:  agente (boneco azul)  ·  pacote (caixa laranja)  ·  destino (X vermelho)  ·  "
            "obstáculo (preto)  ·  pedágio (cinza: ação executada nele custa +2)  ·  "
            "trajeto azul = até o pacote  ·  trajeto laranja = carregando o pacote até o destino"
        )
        ttk.Label(direita, text=legenda, wraplength=680).pack(anchor="w", pady=(6, 0))

    # ================================================================== #
    # Utilidades de interface
    # ================================================================== #
    def _atualizar_escalas(self) -> None:
        estado = "disabled" if self.var_densidade_auto.get() else "normal"
        self.escala_obst.configure(state=estado)
        self.escala_ped.configure(state=estado)
        self._atualizar_rotulos()

    def _atualizar_rotulos(self) -> None:
        self.rotulo_obst.configure(text=str(int(self.var_obst.get())))
        self.rotulo_ped.configure(text=str(int(self.var_ped.get())))

    def _ler_n(self) -> Optional[int]:
        try:
            n = int(self.var_n.get())
        except ValueError:
            n = -1
        if not (N_MIN <= n <= N_MAX):
            messagebox.showerror("Dimensão inválida", f"Digite um inteiro entre {N_MIN} e {N_MAX}.")
            return None
        return n

    def _ler_seed(self) -> Optional[int] | object:
        """Devolve a seed (``None`` se vazia) ou ``SEED_INVALIDA`` após avisar o usuário."""
        texto = self.var_seed.get().strip()
        if not texto:
            return None
        try:
            return int(texto)
        except ValueError:
            messagebox.showerror("Seed inválida", "A seed deve ser um número inteiro (ou vazio).")
            return SEED_INVALIDA

    def _definir_status(self, texto: str, cor: str) -> None:
        self.var_status.set(texto)
        self.rotulo_status.configure(foreground=cor)

    def _escrever_plano(self, r: Optional[Resultado]) -> None:
        caixa = self.texto_plano
        caixa.configure(state="normal")
        caixa.delete("1.0", "end")
        if r is not None and r.encontrou:
            if not r.plano:
                caixa.insert("end", "Plano vazio: o pacote já está no destino.\n")
            for p in r.plano:
                extra = "  (+2 pedágio)" if p.em_pedagio else ""
                linha = f"{p.indice:>3}. {p.acao:<9} → {p.estado.agente}  custo {p.custo_acao}  acum. {p.custo_acumulado}{extra}\n"
                caixa.insert("end", linha, ("pedagio",) if p.em_pedagio else ())
            if r.plano:
                caixa.insert("end", f"\nTotal: {r.num_acoes} ações, custo {r.custo_total}\n", ("total",))
        caixa.configure(state="disabled")

    def _destacar_passo(self, indice: int) -> None:
        caixa = self.texto_plano
        caixa.tag_remove("atual", "1.0", "end")
        if indice >= 1:
            caixa.tag_add("atual", f"{indice}.0", f"{indice}.end")
            caixa.see(f"{indice}.0")

    def _habilitar(self, ativo: bool) -> None:
        estado = "normal" if ativo else "disabled"
        for b in (self.btn_gerar, self.btn_prova, self.btn_abrir, self.btn_salvar, self.btn_resolver):
            b.configure(state=estado)
        tem_plano = ativo and self.resultado is not None and self.resultado.encontrou and bool(self.resultado.plano)
        for b in (self.btn_animar, self.btn_passo, self.btn_reiniciar):
            b.configure(state="normal" if tem_plano else "disabled")

    # ================================================================== #
    # Ações: mundo
    # ================================================================== #
    def _instalar_mundo(self, mundo: Mundo, origem: str) -> None:
        self.parar_animacao()
        self._pedido_atual += 1  # invalida qualquer busca ainda em andamento
        self._buscando = False
        self.mundo = mundo
        self.resultado = None
        self.estado_exibido = EstadoEntrega.inicial(mundo)
        self.indice_animacao = 0
        self.var_n.set(str(mundo.n))
        self._escrever_plano(None)
        self.var_stats.set(
            f"{origem} — {mundo.n}×{mundo.n}, {len(mundo.obstaculos)} obstáculos, {len(mundo.pedagios)} pedágios.\n"
            f"Agente {mundo.agente}, pacote {mundo.pacote}, destino {mundo.destino}."
        )
        self._definir_status("Mundo pronto. Clique em Resolver.", "#111827")
        self._habilitar(True)
        self.desenhar()

    def gerar_aleatorio(self) -> None:
        n = self._ler_n()
        if n is None:
            return
        seed = self._ler_seed()
        if seed is SEED_INVALIDA:
            return
        if self.var_densidade_auto.get():
            dens_obst = dens_ped = None
        else:
            dens_obst = int(self.var_obst.get()) / 100
            dens_ped = int(self.var_ped.get()) / 100
        mundo = Mundo.gerar_aleatorio(n, seed, dens_obst, dens_ped)
        origem = "Mundo aleatório" + (f" (seed {seed})" if seed is not None else "")
        self._instalar_mundo(mundo, origem)

    def carregar_prova(self) -> None:
        self._instalar_mundo(Mundo.mapa_prova(), "Mapa da prova (Figura 2)")

    def abrir_mapa(self) -> None:
        caminho = filedialog.askopenfilename(title="Abrir mapa", filetypes=[("Mapas de texto", "*.txt"), ("Todos", "*.*")])
        if not caminho:
            return
        try:
            mundo = Mundo.carregar(caminho)
        except (OSError, ValueError) as erro:
            messagebox.showerror("Mapa inválido", str(erro))
            return
        self._instalar_mundo(mundo, f"Arquivo {caminho.rsplit('/', 1)[-1]}")

    def salvar_mapa(self) -> None:
        if self.mundo is None:
            return
        caminho = filedialog.asksaveasfilename(title="Salvar mapa", defaultextension=".txt", filetypes=[("Mapas de texto", "*.txt")])
        if not caminho:
            return
        try:
            self.mundo.salvar(caminho)
        except OSError as erro:
            messagebox.showerror("Não foi possível salvar", str(erro))

    # ================================================================== #
    # Ações: busca (em thread)
    # ================================================================== #
    def resolver(self) -> None:
        if self.mundo is None:
            return
        mundo, algoritmo = self.mundo, self.var_alg.get()
        if algoritmo != "a_estrela" and mundo.n > N_AVISO_LENTO:
            continuar = messagebox.askyesno(
                "Busca demorada",
                f"{NOMES_ALGORITMOS[algoritmo]} em um grid {mundo.n}×{mundo.n} pode explorar milhões de "
                "estados e levar vários minutos (o A* resolve o mesmo grid em milissegundos).\n\nContinuar mesmo assim?",
            )
            if not continuar:
                return
        self.parar_animacao()
        self.resultado = None
        self.estado_exibido = EstadoEntrega.inicial(mundo)
        self.indice_animacao = 0
        self._escrever_plano(None)
        self._habilitar(False)
        self._definir_status("Buscando o plano de menor custo…", "#111827")
        self.desenhar()
        self._pedido_atual += 1
        pedido = self._pedido_atual

        def trabalho() -> None:
            try:
                self._fila.put((pedido, resolver(mundo, algoritmo)))
            except Exception as erro:  # pragma: no cover - defensivo
                self._fila.put((pedido, erro))

        self._buscando = True
        threading.Thread(target=trabalho, daemon=True).start()
        if not self._consultando_fila:
            self._consultando_fila = True
            self.raiz.after(30, self._receber_resultado)

    def _receber_resultado(self) -> None:
        """Consulta a fila periodicamente (na thread da interface) até chegar o resultado do pedido atual."""
        try:
            pedido, item = self._fila.get_nowait()
        except queue.Empty:
            if self._buscando:
                self.raiz.after(30, self._receber_resultado)
            else:
                self._consultando_fila = False
            return
        if pedido != self._pedido_atual:
            # Resultado de um pedido antigo (o mundo mudou enquanto a busca rodava): descarta.
            self.raiz.after(30, self._receber_resultado)
            return
        self._buscando = False
        self._consultando_fila = False
        if isinstance(item, Exception):
            self._definir_status(f"Erro na busca: {item}", CORES["erro"])
            self._habilitar(True)
            return
        r: Resultado = item
        self.resultado = r
        self._escrever_plano(r)
        self.var_stats.set(
            f"{r.algoritmo}: {r.nos_expandidos} nós expandidos, {r.nos_gerados} gerados, "
            f"fronteira máx. {r.tamanho_max_fronteira}, {r.tempo_s * 1000:.1f} ms."
        )
        if not r.encontrou:
            self._definir_status(f"SEM SOLUÇÃO — {r.diagnostico}", CORES["erro"])
        elif not r.plano:
            self._definir_status("O pacote já está no destino: plano vazio, custo 0.", CORES["ok"])
        else:
            rotulo = "Plano ótimo" if r.otimo_garantido else "Plano encontrado (largura NÃO garante o menor custo)"
            cor = CORES["ok"] if r.otimo_garantido else CORES["aviso"]
            self._definir_status(f"{rotulo}: custo {r.custo_total}, {r.num_acoes} ações.", cor)
        self._habilitar(True)
        self.desenhar()

    # ================================================================== #
    # Ações: animação
    # ================================================================== #
    def _ir_para_passo(self, indice: int) -> None:
        assert self.resultado is not None
        self.indice_animacao = indice
        self.estado_exibido = self.resultado.estados[indice]
        self._destacar_passo(indice)
        self.desenhar()

    def passo(self) -> None:
        if self.resultado is None or not self.resultado.encontrou:
            return
        self._animando = False
        proximo = self.indice_animacao + 1
        if proximo >= len(self.resultado.estados):
            proximo = 0
        self._ir_para_passo(proximo)

    def animar(self) -> None:
        if self.resultado is None or not self.resultado.encontrou:
            return
        if self._animando:
            self.parar_animacao()
            return
        if self.indice_animacao >= len(self.resultado.estados) - 1:
            self._ir_para_passo(0)
        self._animando = True
        self.btn_animar.configure(text="❚❚ Pausar")
        self._tique()

    def _tique(self) -> None:
        if not self._animando or self.resultado is None:
            return
        proximo = self.indice_animacao + 1
        if proximo >= len(self.resultado.estados):
            self.parar_animacao()
            return
        self._ir_para_passo(proximo)
        atraso = int(900 / max(1, int(self.var_vel.get())))
        self._job_animacao = self.raiz.after(atraso, self._tique)

    def parar_animacao(self) -> None:
        self._animando = False
        if self._job_animacao is not None:
            self.raiz.after_cancel(self._job_animacao)
            self._job_animacao = None
        self.btn_animar.configure(text="▶ Animar")

    def reiniciar_animacao(self) -> None:
        self.parar_animacao()
        if self.resultado is not None and self.resultado.encontrou:
            self._ir_para_passo(0)

    # ================================================================== #
    # Desenho
    # ================================================================== #
    def desenhar(self) -> None:
        c = self.canvas
        c.delete("all")
        if self.mundo is None:
            return
        m = self.mundo
        largura = max(c.winfo_width(), 50)
        altura = max(c.winfo_height(), 50)
        mostrar_indices = m.n <= 30
        margem = 22 if mostrar_indices else 6
        lado = (min(largura, altura) - 2 * margem) / m.n
        x0 = (largura - lado * m.n) / 2
        y0 = (altura - lado * m.n) / 2

        def canto(pos: Posicao) -> tuple[float, float]:
            return x0 + pos[1] * lado, y0 + pos[0] * lado

        def centro(pos: Posicao) -> tuple[float, float]:
            x, y = canto(pos)
            return x + lado / 2, y + lado / 2

        caminho = set()
        if self.resultado is not None and self.resultado.encontrou:
            caminho = set(self.resultado.celulas_percorridas())

        # Células.
        for pos in m.celulas():
            x, y = canto(pos)
            if pos in m.obstaculos:
                cor = CORES["obstaculo"]
            elif pos in m.pedagios:
                cor = CORES["pedagio"]
            elif pos in caminho:
                cor = CORES["caminho"]
            else:
                cor = CORES["livre"]
            c.create_rectangle(x, y, x + lado, y + lado, fill=cor, outline=CORES["grade"], width=1 if lado > 6 else 0)

        # Índices de linha/coluna (0-indexados).
        if mostrar_indices:
            fonte = ("TkDefaultFont", max(6, min(10, int(lado / 3))))
            for i in range(m.n):
                cx, _ = centro((0, i))
                _, cy = centro((i, 0))
                c.create_text(cx, y0 - 10, text=str(i), font=fonte, fill="#4b5563")
                c.create_text(x0 - 11, cy, text=str(i), font=fonte, fill="#4b5563")

        # Linhas do caminho: ida até o pacote (azul) e transporte até o destino
        # (laranja, levemente deslocada para não ficar escondida se o trajeto
        # de volta repete o de ida).
        if self.resultado is not None and self.resultado.encontrou and len(self.resultado.estados) > 1:
            estados = self.resultado.estados
            k = next((i for i, e in enumerate(estados) if e.carregando), len(estados))
            ida = [centro(e.agente) for e in estados[:k]]  # até (e incluindo) a célula do "pegar"
            volta = [centro(e.agente) for e in estados[k:]]  # carregando, até o "entregar"
            esp = max(1.0, lado / 14)
            desloc = min(4.0, lado / 10)
            for pontos, cor, dx in ((ida, CORES["linha_caminho"], 0.0), (volta, CORES["linha_volta"], desloc)):
                pts = []
                for px, py in pontos:
                    if not pts or (px + dx, py + dx) != pts[-1]:
                        pts.append((px + dx, py + dx))
                if len(pts) > 1:
                    c.create_line(*[v for p in pts for v in p], fill=cor, width=esp, arrow="last", joinstyle="round")

        # Destino.
        cx, cy = centro(m.destino)
        r = lado * 0.3
        esp = max(2, lado / 10)
        c.create_line(cx - r, cy - r, cx + r, cy + r, fill=CORES["destino"], width=esp)
        c.create_line(cx - r, cy + r, cx + r, cy - r, fill=CORES["destino"], width=esp)

        estado = self.estado_exibido or EstadoEntrega.inicial(m)

        # Célula atual em destaque durante a animação.
        if self.resultado is not None and self.resultado.encontrou and self.indice_animacao > 0:
            x, y = canto(estado.agente)
            c.create_rectangle(x + 1, y + 1, x + lado - 1, y + lado - 1, outline=CORES["atual"], width=max(2, lado / 10))

        # Pacote no chão.
        if not estado.carregando:
            self._desenhar_pacote(centro(estado.posicao_pacote), lado * 0.26)

        # Agente (e pacote junto, se estiver carregando).
        self._desenhar_agente(centro(estado.agente), lado, estado.carregando)

    def _desenhar_pacote(self, centro: tuple[float, float], r: float) -> None:
        cx, cy = centro
        self.canvas.create_rectangle(cx - r, cy - r, cx + r, cy + r, fill=CORES["pacote"], outline="#78350f", width=1)
        self.canvas.create_rectangle(cx - r, cy - r, cx + r, cy - r * 0.45, fill=CORES["pacote_topo"], outline="#78350f", width=1)

    def _desenhar_agente(self, centro: tuple[float, float], lado: float, carregando: bool) -> None:
        cx, cy = centro
        c = self.canvas
        if lado < 14:  # grids grandes: só um círculo
            r = lado * 0.3
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=CORES["agente"], outline="")
            if carregando:
                self._desenhar_pacote((cx, cy), lado * 0.16)
            return
        cor, esp = CORES["agente"], max(2, lado / 12)
        rc = lado * 0.11  # cabeça
        c.create_oval(cx - rc, cy - lado * 0.38, cx + rc, cy - lado * 0.38 + 2 * rc, outline=cor, width=esp)
        topo, base = cy - lado * 0.38 + 2 * rc, cy + lado * 0.08
        c.create_line(cx, topo, cx, base, fill=cor, width=esp)  # tronco
        c.create_line(cx - lado * 0.2, topo + lado * 0.08, cx + lado * 0.2, topo + lado * 0.08, fill=cor, width=esp)  # braços
        c.create_line(cx, base, cx - lado * 0.17, cy + lado * 0.36, fill=cor, width=esp)  # pernas
        c.create_line(cx, base, cx + lado * 0.17, cy + lado * 0.36, fill=cor, width=esp)
        if carregando:
            self._desenhar_pacote((cx + lado * 0.26, topo + lado * 0.08), lado * 0.13)


def main() -> None:
    raiz = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:  # pragma: no cover
        pass
    Aplicacao(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
