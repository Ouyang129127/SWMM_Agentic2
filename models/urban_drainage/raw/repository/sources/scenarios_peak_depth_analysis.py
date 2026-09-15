from pyswmm import Simulation, Nodes
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib as mpl
import pandas as pd
import numpy as np
import os

# Caminho do arquivo
base_dir = r"C:\Users\wpcal\Dropbox\Arquivos Pacheco 02_05_2022\Programacao\Ambiente_VirtualCS\Marcella\cenarios"
inp_path = os.path.join(base_dir, "cenario_11.inp")
rpt_path = inp_path.replace(".inp", ".rpt")
out_path = inp_path.replace(".inp", ".out")

# Inicialização
tempo = []
profundidades = {}  # chave = node_id, valor = lista de profundidades

# Executa simulação
with Simulation(inp_path, rpt_path, out_path) as sim:
    todos_nos = list(Nodes(sim))
    for n in todos_nos:
        profundidades[n.nodeid] = []

    for step in sim:
        tempo.append(sim.current_time)
        for n in todos_nos:
            profundidades[n.nodeid].append(n.depth)

# Calcula pico por nó
picos = {n: max(vals) for n, vals in profundidades.items() if any(vals)}
ordenados = sorted(picos.items(), key=lambda x: x[1], reverse=True)

# Seleciona 5: maior, menor, 3 intermediários
if len(ordenados) >= 5:
    selecionados = [ordenados[0][0]] + [n for n, _ in ordenados[1:-1]][:3] + [ordenados[-1][0]]
else:
    selecionados = [n for n, _ in ordenados]  # usa todos disponíveis se <5


# Estatísticas dos picos
valores_pico = list(picos.values())
estatisticas = {
    'Cenário': [os.path.basename(inp_path).replace(".inp", "")],
    'Pico_Máximo_m': [np.max(valores_pico)],
    'Pico_Mínimo_m': [np.min(valores_pico)],
    'Pico_Médio_m': [np.mean(valores_pico)],
    'Desvio_Padrão_m': [np.std(valores_pico)]
}

# Salva CSV
df_estat = pd.DataFrame(estatisticas)
csv_path = os.path.join(base_dir, f"{estatisticas['Cenário'][0]}_estatisticas_picos.csv")
df_estat.to_csv(csv_path, index=False, float_format="%.4f")

print(f"Estatísticas de pico salvas em: {csv_path}")

# Aumenta em 50% o tamanho das fontes
# mpl.rcParams.update({'font.size': mpl.rcParams['font.size'] * 1.5})
mpl.rcParams.update({'font.size': 20})
# Extrai número do cenário
cenario_nome = os.path.basename(inp_path).replace(".inp", "")
cenario_num = ''.join(filter(str.isdigit, cenario_nome))

# Define cores e plota tudo no mesmo gráfico
cores = ['red', 'blue', 'green', 'orange', 'purple']
plt.figure(figsize=(12, 6))

# Adiciona título à legenda (truque: curva invisível)
plt.plot([], [], color='none', label=f"Scenario {cenario_num}")

# Curvas dos nós selecionados
for i, n in enumerate(selecionados):
    plt.plot(tempo, profundidades[n], label=f"Node {n} (Peak: {picos[n]:.2f} m)", color=cores[i])

# Eixos e formatação
plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
plt.xlabel("Time [hh:mm]")
plt.ylabel("Depth [m]")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

