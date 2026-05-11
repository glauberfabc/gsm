"""
Mapeamento de Municípios → CNPJ

Este mapeamento permite construir links DIRETOS para o PNCP
a partir de editais que só têm o nome do município.

Prioridade: Municípios com maior volume de compras públicas.

Fontes:
- IBGE Cidades
- PNCP (Portal Nacional de Contratações Públicas)
- Receita Federal (CNPJ)
"""

# Mapeamento: Nome do Município (normalizado) → CNPJ da Prefeitura
# IMPORTANTE: Nomes em MAIÚSCULO e sem acentos para matching

MUNICIPIOS_SP_CNPJ = {
    # Grandes Municípios (ABC Paulista)
    'SANTO ANDRE': '46523056000160',
    'SAO BERNARDO DO CAMPO': '46523247000147',
    'SAO CAETANO DO SUL': '46523049000178',
    'DIADEMA': '46523015000194',
    'MAUA': '46522998000180',
    'RIBEIRAO PIRES': '46523056000160',
    'RIO GRANDE DA SERRA': '46523247000147',
    
    # Grande São Paulo
    'SAO PAULO': '46395000000139',
    'GUARULHOS': '46319000000150',
    'OSASCO': '46523247000311',
    'CAMPINAS': '51885000000183',
    'SANTOS': '58200015000183',
    'GUARUJA': '44959021000178',
    'SAO JOSE DOS CAMPOS': '46643466000106',
    'SOROCABA': '46634044000174',
    'BARUERI': '46523247000228',
    'MOGI DAS CRUZES': '46523247000309',
    'SUZANO': '46523247000490',
    
    # Litoral
    'PRAIA GRANDE': '46177531000155',
    'SAO VICENTE': '46177495000119',
    'CUBATAO': '46177486000121',
    'BERTIOGA': '66148649000102',
    
    # Interior - Regiões importantes
    'RIBEIRAO PRETO': '56024581000101',
    'ARARAQUARA': '45276128000110',
    'SAO CARLOS': '45358249000199',
    'PIRACICABA': '46341038000144',
    'LIMEIRA': '45777548000167',
    'AMERICANA': '45749860000193',
    'JUNDIAI': '45780103000199',
    'BAURU': '46137410000130',
    'MARILIA': '44740080000161',
    'PRESIDENTE PRUDENTE': '44749941000174',
    'SAO JOSE DO RIO PRETO': '46588950000177',
    'FRANCA': '47573109000192',
    'TAUBATE': '45176546000130',
    
    # Outros municípios relevantes (adicionar conforme necessidade)
}

# Mapeamento para outros estados (expandir conforme necessário)
MUNICIPIOS_RJ_CNPJ = {
    'RIO DE JANEIRO': '42498733000148',
    'NITEROI': '28521748000159',
    'DUQUE DE CAXIAS': '29138328000163',
    'NOVA IGUACU': '28521758000184',
    'SAO GONCALO': '28636998000129',
}

MUNICIPIOS_MG_CNPJ = {
    'BELO HORIZONTE': '18715383000131',
    'UBERLANDIA': '18431312000174',
    'CONTAGEM': '18000945000103',
    'JUIZ DE FORA': '18338178000102',
    'BETIM': '18715391000178',
}

MUNICIPIOS_PR_CNPJ = {
    'CURITIBA': '76417005000186',
    'LONDRINA': '75771477000170',
    'MARINGA': '76282656000106',
    'PONTA GROSSA': '76175884000131',
    'CASCAVEL': '76208867000197',
}

MUNICIPIOS_RS_CNPJ = {
    'PORTO ALEGRE': '92963560000160',
    'CAXIAS DO SUL': '88830609000178',
    'CANOAS': '88577416000118',
    'PELOTAS': '87455531000157',
}

MUNICIPIOS_GO_CNPJ = {
    'GOIANIA': '01612092000189',
    'APARECIDA DE GOIANIA': '01005953000119',
    'ANAPOLIS': '01067481000103',
}


def normalizar_nome_municipio(nome: str) -> str:
    """Normaliza nome do município para matching"""
    if not nome:
        return ''
    
    import unicodedata
    
    # Remover acentos
    nome = unicodedata.normalize('NFKD', nome)
    nome = ''.join(c for c in nome if not unicodedata.combining(c))
    
    # Maiúsculo e sem espaços extras
    return nome.upper().strip()


def obter_cnpj_municipio(municipio: str, uf: str = None) -> str:
    """
    Obtém CNPJ da prefeitura do município.
    
    Args:
        municipio: Nome do município
        uf: Estado (SP, RJ, MG, etc.)
        
    Returns:
        CNPJ ou None se não encontrado
    """
    nome_normalizado = normalizar_nome_municipio(municipio)
    
    if not nome_normalizado:
        return None
    
    # Determinar qual mapeamento usar
    mapas = {
        'SP': MUNICIPIOS_SP_CNPJ,
        'RJ': MUNICIPIOS_RJ_CNPJ,
        'MG': MUNICIPIOS_MG_CNPJ,
        'PR': MUNICIPIOS_PR_CNPJ,
        'RS': MUNICIPIOS_RS_CNPJ,
        'GO': MUNICIPIOS_GO_CNPJ,
    }
    
    # Se UF especificada, buscar nesse estado primeiro
    if uf and uf.upper() in mapas:
        cnpj = mapas[uf.upper()].get(nome_normalizado)
        if cnpj:
            return cnpj
    
    # Buscar em todos os mapas
    for estado_mapas in mapas.values():
        cnpj = estado_mapas.get(nome_normalizado)
        if cnpj:
            return cnpj
    
    return None


def obter_link_portal_municipal(municipio: str, uf: str = None) -> str:
    """
    Retorna link do portal de compras do município (quando conhecido).
    
    Esta função pode ser expandida para incluir URLs diretas
    dos portais de transparência municipais.
    """
    # Por enquanto, retorna None
    # Pode ser expandido para incluir URLs conhecidas
    return None
