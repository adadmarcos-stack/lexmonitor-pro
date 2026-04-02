import os

def get_env(nome):
    valor = os.getenv(nome)
    if not valor:
        raise Exception(f"Variável {nome} não configurada")
    return valor

def main():
    print("Iniciando monitor real da OAB...")

    oab_numero = get_env("OAB_NUMERO")
    oab_uf = get_env("OAB_UF")
    oab_cpf = get_env("OAB_CPF")
    oab_identidade = get_env("OAB_IDENTIDADE")

    print(f"OAB: {oab_numero}/{oab_uf}")
    print("CPF e identidade carregados com sucesso")

    # aqui entra seu scraping depois

if __name__ == "__main__":
    main()
