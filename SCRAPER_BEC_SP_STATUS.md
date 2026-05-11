# Status do Scraper BEC/SP (Bolsa Eletrônica de Compras de São Paulo)

## Última Atualização
Dezembro 2024/2025

## Status Atual: PARCIALMENTE OPERACIONAL

### Descrição do Problema
O portal BEC/SP (www.bec.sp.gov.br) implementou medidas de proteção que dificultam a automação:

1. **CAPTCHA**: A página de pesquisa pública (`pesquisa_publica.aspx`) agora exige CAPTCHA
2. **ViewState**: Uso de ASP.NET ViewState que requer sessão válida
3. **Estrutura Alterada**: Os seletores CSS para navegação foram modificados

### Impacto
- Busca direta no portal BEC/SP retorna resultados limitados
- Metadados como `medicamento` e `objeto` podem aparecer como "Não especificado"
- Performance reduzida devido a tentativas múltiplas de navegação

### Mitigações Implementadas
1. Métodos melhorados de extração de metadados (`_extrair_medicamento`, `_extrair_orgao`, etc.)
2. Fallbacks para múltiplos seletores CSS
3. Integração com PNCP que agrega dados do BEC/SP nacionalmente

### Alternativas
1. **PNCP**: O Portal Nacional de Contratações Públicas (pncp.gov.br) agrega licitações de SP
2. **ComprasNet**: O portal federal também pode conter dados de órgãos estaduais
3. **API Estadual**: Contatar a Secretaria da Fazenda de SP para acesso ao Web Service

### Próximos Passos
1. Monitorar mudanças na estrutura do portal
2. Investigar API/Web Service oficial do BEC/SP
3. Considerar parceria com órgão estadual para acesso programático

### Arquivos Relacionados
- `/app/backend/scrapers/bec_sp_client.py` - Scraper principal
- `/app/backend/services/scraper_service.py` - Integração no serviço

### Contato para Acesso Oficial
- Portal: https://www.bec.sp.gov.br
- Suporte: Disponível no rodapé do portal BEC/SP
