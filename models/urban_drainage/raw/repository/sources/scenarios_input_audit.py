import pandas as pd
import os

## Sistema de auditoria rápida da qualidade e integridade dos dados de entrada de cenários

base_path = r"C:\Users\wpcal\Dropbox\Arquivos Pacheco 02_05_2022\Programacao\Ambiente_VirtualCS\Marcella\cenarios"
cenarios = [f"cenario_{i:02d}" for i in range(1, 12)]

# Dicionário de unidades para cada variável (ajuste conforme necessário)
unidades = {
    'NOME': '-',
    'AREA': 'm²',
    'DECL': '%',
    'DURC': 'min',
    'VCHU': 'mm',
    'IMPV': '%',
    'TIPO': '-',
    'DIAM': 'm',
    'LESC': 'm',
    'PMAX': 'm',
    'VAZT': 'm³/s',
    'VTOT': '10^6 L',
    'RAZA': '-',
    'KSAT': 'mm/h',
    'SUCC': 'mm',
    'UINI': 'fração',
    'PROS': 'm',
    'ALTC': 'm',
    'CLBO': '-'
}


def gerar_relatorio_conferencia(cenario):
    try:
        caminho_csv = os.path.join(base_path, f"{cenario}.csv")

        if not os.path.exists(caminho_csv):
            return f"Arquivo CSV não encontrado para {cenario}"

        df = pd.read_csv(caminho_csv)

        relatorio = f"Relatório de Conferência - {cenario}\n"
        relatorio += "-" * 70 + "\n"
        relatorio += "| Código Variável | 1º valor          | Quantidade de valores | Unidade   | Nº colunas vazias |\n"
        relatorio += "-" * 70 + "\n"

        for coluna in df.columns:
            if coluna == 'ID':
                continue

            # Obter informações da coluna
            primeiro_valor = str(df[coluna].iloc[0]) if not pd.isna(df[coluna].iloc[0]) else "VAZIO"
            qtd_valores = df[coluna].count()
            qtd_vazias = len(df) - qtd_valores
            unidade = unidades.get(coluna, 'desconhecida')

            # Formatar linha do relatório
            linha = f"| {coluna:<15} | {primeiro_valor:<18} | {qtd_valores:<21} | {unidade:<8} | {qtd_vazias:<17} |\n"
            relatorio += linha

        # Salvar relatório em arquivo txt
        relatorio_path = os.path.join(base_path, f"{cenario}_relatorio_conferencia.txt")
        with open(relatorio_path, 'w', encoding='utf-8') as f:
            f.write(relatorio)

        return f"Relatório gerado com sucesso: {relatorio_path}"

    except Exception as e:
        return f"Erro ao gerar relatório para {cenario}: {str(e)}"


# Gerar relatórios para todos os cenários
for cenario in cenarios:
    resultado = gerar_relatorio_conferencia(cenario)
    print(resultado)