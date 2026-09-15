from pyswmm import Simulation, Nodes
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib as mpl
import pandas as pd
import numpy as np
import os

# Pasta com os arquivos
base_dir = r"C:\Users\wpcal\Dropbox\Arquivos Pacheco 02_05_2022\Programacao\Ambiente_VirtualCS\Marcella\cenarios"

# Lista dos cenários
cenarios = [f"cenario_{i:02d}.inp" for i in range(1, 12)]

# Armazena estatísticas e curvas máximas
estatisticas_gerais = []
curvas_maximas = []

# Define tamanho fixo da fonte
mpl.rcParams.update({'font.size': 20})

# Loop pelos cenários
for inp_file in cenarios:
    inp_path = os.path.join(base_dir, inp_file)
    rpt_path = inp_path.replace(".inp", ".rpt")
    out_path = inp_path.replace(".inp", ".out")

    tempo = []
    profundidades = {}

    with Simulation(inp_path, rpt_path, out_path) as sim:
        todos_nos = list(Nodes(sim))
        for n in todos_nos:
            profundidades[n.nodeid] = []

        for step in sim:
            tempo.append(sim.current_time)
            for n in todos_nos:
                profundidades[n.nodeid].append(n.depth)

    picos = {n: max(vals) for n, vals in profundidades.items() if any(vals)}
    ordenados = sorted(picos.items(), key=lambda x: x[1], reverse=True)

    if len(ordenados) >= 5:
        selecionados = [ordenados[0][0]] + [n for n, _ in ordenados[1:-1]][:3] + [ordenados[-1][0]]
    else:
        selecionados = [n for n, _ in ordenados]

    # Estatísticas
    valores_pico = list(picos.values())
    nome_cenario = inp_file.replace(".inp", "")
    estat = {
        'Cenário': nome_cenario,
        'Pico_Máximo_m': np.max(valores_pico),
        'Pico_Mínimo_m': np.min(valores_pico),
        'Pico_Médio_m': np.mean(valores_pico),
        'Desvio_Padrão_m': np.std(valores_pico)
    }
    estatisticas_gerais.append(estat)

    # Salva estatísticas individuais
    df_estat = pd.DataFrame([estat])
    csv_path = os.path.join(base_dir, f"{nome_cenario}_estatisticas_picos.csv")
    df_estat.to_csv(csv_path, index=False, float_format="%.4f")

    # Plot gráfico individual
    # mpl.rcParams.update({'font.size': mpl.rcParams['font.size'] * 1.5})
    cores = ['red', 'blue', 'green', 'orange', 'purple']
    plt.figure(figsize=(12, 6))
    plt.plot([], [], color='none', label=f"Scenario {nome_cenario[-2:]}")
    for i, n in enumerate(selecionados):
        plt.plot(tempo, profundidades[n], label=f"Node {n} (Peak: {picos[n]:.2f} m)", color=cores[i])
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xlabel("Time [hh:mm]")
    plt.ylabel("Depth [m]")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    pdf_path = os.path.join(base_dir, f"{nome_cenario}.pdf")
    plt.savefig(pdf_path)
    plt.close()

    # Guarda curva máxima
    curva_maxima = np.max(np.array([profundidades[n] for n in profundidades]), axis=0)
    curvas_maximas.append((nome_cenario, tempo, curva_maxima))

# Salva todas as estatísticas em um único CSV
df_todos = pd.DataFrame(estatisticas_gerais)
df_todos.to_csv(os.path.join(base_dir, "estatisticas_picos_todos_cenarios.csv"), index=False, float_format="%.4f")

# Gráfico combinado das curvas máximas
plt.figure(figsize=(12, 6))
for nome_cenario, tempo, curva in curvas_maximas:
    plt.plot(tempo, curva, label=f"Scenario {nome_cenario[-2:]}")
plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
plt.xlabel("Time [hh:mm]")
plt.ylabel("Maximum Depth [m]")
plt.title("Maximum Depth Curves – All Scenarios")
plt.legend(title="All Scenarios")
plt.grid(True)
plt.tight_layout()
plt.savefig(os.path.join(base_dir, "curvas_maximas_todos_cenarios.pdf"))
plt.close()
