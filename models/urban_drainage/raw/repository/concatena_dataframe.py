import pandas as pd
import os

# Caminho da pasta com os cenários
base_path = r"C:\Users\wpcal\Dropbox\Arquivos Pacheco 02_05_2022\Programacao\Ambiente_VirtualCS\Marcella\cenarios"

# Lista de cenários (01 até 11, com zero à esquerda até o 09)
cenarios = [f"{i:02d}" for i in range(1, 12)]

# Lista para armazenar os DataFrames
lista_df = []

# Loop pelos arquivos
for c in cenarios:
    arquivo = os.path.join(base_path, f"cenario_{c}.csv")
    df = pd.read_csv(arquivo)
    df["CENARIO"] = c   # adiciona coluna identificando o cenário (como string "01", "02", ...)
    lista_df.append(df)

# Concatena todos os DataFrames
dataset = pd.concat(lista_df, ignore_index=True)

# Exporta para CSV final (opcional)
saida = os.path.join(base_path, "cenarios_unificados.csv")
dataset.to_csv(saida, index=False)

print("Dataset unificado criado com sucesso!")
