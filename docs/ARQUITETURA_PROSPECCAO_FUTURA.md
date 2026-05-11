# Arquitetura de Prospecção de Licitações Futuras - GSM

## 1. Mapa de Componentes (Original)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (React)                               │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ SearchPanel │  │ FilterPanel │  │ ResultsGrid │  │ CardDetail  │    │
│  │  - termo    │  │  - status   │  │  - cartões  │  │  - objeto   │    │
│  │  - região   │  │  - data     │  │  - paginação│  │  - docs     │    │
│  └─────────────┘  │  - modalid. │  └─────────────┘  │  - timeline │    │
│                   │  - futuras  │                    └─────────────┘    │
│                   └─────────────┘                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          BACKEND (FastAPI)                              │
├─────────────────────────────────────────────────────────────────────────┤
│  POST /api/search                                                       │
│  ├── Query: {medicamento, apenas_futuras, status_filtro, ...}          │
│  └── Response: {total, licitacoes[], pagination}                        │
│                                                                         │
│  GET /api/health                                                        │
│  └── Response: {fontes[], status_geral, ultima_atualizacao}            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      SCRAPER SERVICE (Orquestrador)                     │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │ PNCP Client  │  │ ComprasNet   │  │ CSV Importers │                  │
│  │ (Nacional)   │  │ (Federal)    │  │ (Estaduais)   │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
│         │                │                   │                          │
│         └────────────────┼───────────────────┘                          │
│                          ▼                                              │
│              ┌─────────────────────┐                                    │
│              │ Agregador/Deduper   │                                    │
│              └─────────────────────┘                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          MONGODB (Persistência)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  Collection: licitacoes                                                 │
│  Índices: estado_uf, status, data_abertura, fonte                      │
└─────────────────────────────────────────────────────────────────────────┘
```

## 2. Diagrama de Navegação

```
┌─────────────────┐
│   Home/Landing  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Busca Inicial  │────▶│ Filtros Avançados│
│  - termo        │     │ - apenas_futuras │
│  - região       │     │ - status         │
└────────┬────────┘     │ - modalidade     │
         │              │ - esfera         │
         ▼              └────────┬─────────┘
┌─────────────────┐              │
│  Resultados     │◀─────────────┘
│  (Cards/Grid)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Detalhe Card   │────▶│  Documentos/PDF │
│  - objeto       │     │  - edital       │
│  - órgão        │     │  - anexos       │
│  - datas        │     └─────────────────┘
│  - status       │
│  - link_origem  │
└─────────────────┘
```

## 3. Padrões de Estado e Dados

### 3.1 Estados de Licitação (Padronizados)

```javascript
const STATUS_LICITACAO = {
  // FUTUROS/ABERTOS (Prospecção - Prioridade Alta)
  'Agendado': { cor: 'blue', prioridade: 1, prospeccao: true },
  'Publicado': { cor: 'cyan', prioridade: 2, prospeccao: true },
  'Aberto': { cor: 'green', prioridade: 3, prospeccao: true },
  'Em Proposta': { cor: 'lime', prioridade: 4, prospeccao: true },
  'Em Andamento': { cor: 'yellow', prioridade: 5, prospeccao: true },
  
  // EM EXECUÇÃO
  'Em Licitação': { cor: 'orange', prioridade: 6, prospeccao: false },
  'Ativa': { cor: 'teal', prioridade: 7, prospeccao: false },
  
  // FINALIZADOS
  'Homologado': { cor: 'purple', prioridade: 8, prospeccao: false },
  'Adjudicado': { cor: 'indigo', prioridade: 9, prospeccao: false },
  'Encerrado': { cor: 'gray', prioridade: 10, prospeccao: false },
  'Concluído': { cor: 'gray', prioridade: 11, prospeccao: false },
  
  // CANCELADOS
  'Cancelado': { cor: 'red', prioridade: 12, prospeccao: false },
  'Revogado': { cor: 'red', prioridade: 13, prospeccao: false },
  'Deserto': { cor: 'red', prioridade: 14, prospeccao: false },
  'Fracassado': { cor: 'red', prioridade: 15, prospeccao: false },
};
```

### 3.2 Schema de Dados (Licitação)

```typescript
interface Licitacao {
  // Identificação
  id: string;                    // UUID gerado
  fonte_id: string;              // ID na fonte original
  fonte: string;                 // 'PNCP', 'ComprasNet', 'ES-CSV', etc.
  fonte_nome: string;            // Nome legível da fonte
  
  // Localização
  estado: string;                // UF (ex: 'ES')
  estado_uf: string;             // UF redundante para compatibilidade
  esfera: 'Federal' | 'Estadual' | 'Municipal';
  
  // Órgão
  orgao_licitante: string;       // Nome do órgão
  uasg?: string;                 // Código UASG (federal)
  
  // Processo
  numero_processo: string;       // Número do processo
  numero_pregao?: string;        // Número do pregão (se aplicável)
  modalidade: string;            // Tipo de licitação
  
  // Objeto
  titulo_licitacao?: string;     // Título curto
  objeto: string;                // Descrição completa
  medicamento?: string;          // Medicamento identificado (se aplicável)
  
  // Status (CRÍTICO PARA PROSPECÇÃO)
  status: string;                // Ver STATUS_LICITACAO
  status_aquisicao?: string;     // Status alternativo
  
  // Datas (CRÍTICAS PARA PROSPECÇÃO)
  data_publicacao?: Date;        // Data de publicação
  data_abertura?: Date;          // Data de abertura de propostas
  data_inicial?: Date;           // Data de início
  data_final?: Date;             // Data limite/encerramento
  data_limite?: Date;            // Alias para data_final
  data_referencia: Date;         // Data de referência do scraping
  
  // Links
  link_origem: string;           // URL da página de detalhes
  link_documento?: string;       // Link direto para PDF/edital
  
  // Metadados
  registro_preco?: boolean;      // Se é registro de preços
  tipo_licitacao?: string;       // Tipo específico
  valor_referencia?: number;     // Valor estimado
  valor_homologado?: number;     // Valor final
  itens: ItemLicitacao[];        // Itens da licitação
  tags: string[];                // Tags para filtro
  
  // Controle
  is_mock: boolean;              // Se é dado simulado
  created_at: Date;
  updated_at: Date;
}
```

## 4. API REST (Backend Genérico)

### 4.1 Endpoints Principais

```yaml
# Busca de Licitações
POST /api/search:
  request:
    medicamento?: string       # Termo de busca
    estado?: string           # Filtro por UF
    tags?: string[]           # Filtro por tags
    apenas_reais?: boolean    # Excluir mocks
    apenas_futuras?: boolean  # PROSPECÇÃO: apenas abertas/futuras
    status_filtro?: string    # Filtro por status específico
    modalidade_filtro?: string[]  # Filtro por modalidades
    esfera_filtro?: string    # Federal/Estadual/Municipal
    data_limite_inicio?: date # Data mínima
    data_limite_fim?: date    # Data máxima
    page?: number             # Paginação
    per_page?: number         # Itens por página
  response:
    total: number
    medicamento: string
    licitacoes: Licitacao[]
    pagination:
      page: number
      per_page: number
      total_pages: number
      has_next: boolean
      has_prev: boolean

# Saúde do Sistema
GET /api/health:
  response:
    fontes: FonteStatus[]
    status_geral: 'healthy' | 'degraded' | 'unhealthy'
    ultima_atualizacao: datetime
    total_licitacoes: number

# Estatísticas
GET /api/stats:
  response:
    por_estado: Record<string, number>
    por_modalidade: Record<string, number>
    por_status: Record<string, number>
    total: number
```

### 4.2 Lógica de Prospecção (Filtros PROATIVOS)

```python
# Aplicado NA REQUISIÇÃO aos scrapers/APIs, não pós-filtro

def filtros_prospeccao(apenas_futuras: bool):
    if not apenas_futuras:
        return {}
    
    hoje = datetime.now()
    
    return {
        # Filtro 1: Data de abertura >= hoje
        'dataAberturaPropostaInicial': hoje.strftime('%Y%m%d'),
        
        # Filtro 2: Status indica processo ativo
        'situacaoCompra': ['Publicado', 'Aberta', 'Divulgada'],
        
        # Filtro 3: Ordenar por data mais próxima primeiro
        'ordenacao': 'dataAberturaPropostaAscendente'
    }
```

## 5. Código Exemplo (Autoral)

### 5.1 Hook React para Busca com Prospecção

```typescript
// hooks/useLicitacaoSearch.ts
import { useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface SearchParams {
  medicamento?: string;
  apenasFuturas?: boolean;
  status?: string;
  page?: number;
  perPage?: number;
}

interface SearchResult {
  total: number;
  licitacoes: Licitacao[];
  pagination: Pagination;
}

export function useLicitacaoSearch() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<SearchResult | null>(null);

  const search = useCallback(async (params: SearchParams) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await api.post<SearchResult>('/api/search', {
        medicamento: params.medicamento,
        apenas_futuras: params.apenasFuturas ?? true, // DEFAULT: prospecção ativa
        status_filtro: params.status,
        page: params.page ?? 1,
        per_page: params.perPage ?? 20,
      });
      
      setData(response.data);
      return response.data;
    } catch (err) {
      setError(err as Error);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { search, loading, error, data };
}
```

### 5.2 Componente de Card de Licitação

```tsx
// components/LicitacaoCard.tsx
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { CalendarIcon, BuildingIcon, MapPinIcon } from 'lucide-react';

interface LicitacaoCardProps {
  licitacao: Licitacao;
  onClick?: () => void;
}

const STATUS_COLORS: Record<string, string> = {
  'Agendado': 'bg-blue-500',
  'Publicado': 'bg-cyan-500',
  'Aberto': 'bg-green-500',
  'Em Proposta': 'bg-lime-500',
  'Em Andamento': 'bg-yellow-500',
  'Encerrado': 'bg-gray-500',
  'Cancelado': 'bg-red-500',
};

export function LicitacaoCard({ licitacao, onClick }: LicitacaoCardProps) {
  const statusColor = STATUS_COLORS[licitacao.status] || 'bg-gray-400';
  
  // Calcular urgência (dias até abertura)
  const diasAteAbertura = licitacao.data_abertura 
    ? Math.ceil((new Date(licitacao.data_abertura).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;
  
  return (
    <Card 
      className="cursor-pointer hover:shadow-lg transition-shadow"
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <Badge className={statusColor}>{licitacao.status}</Badge>
          <span className="text-sm text-muted-foreground">
            {licitacao.fonte}
          </span>
        </div>
      </CardHeader>
      
      <CardContent>
        <h3 className="font-semibold text-lg line-clamp-2 mb-2">
          {licitacao.titulo_licitacao || licitacao.objeto?.slice(0, 100)}
        </h3>
        
        <div className="space-y-1 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <BuildingIcon className="h-4 w-4" />
            <span className="line-clamp-1">{licitacao.orgao_licitante}</span>
          </div>
          
          <div className="flex items-center gap-2">
            <MapPinIcon className="h-4 w-4" />
            <span>{licitacao.estado_uf} - {licitacao.esfera}</span>
          </div>
          
          {licitacao.data_abertura && (
            <div className="flex items-center gap-2">
              <CalendarIcon className="h-4 w-4" />
              <span>
                Abertura: {new Date(licitacao.data_abertura).toLocaleDateString('pt-BR')}
                {diasAteAbertura !== null && diasAteAbertura > 0 && (
                  <Badge variant="outline" className="ml-2">
                    {diasAteAbertura} dias
                  </Badge>
                )}
              </span>
            </div>
          )}
        </div>
        
        <div className="flex gap-1 mt-3 flex-wrap">
          <Badge variant="secondary">{licitacao.modalidade}</Badge>
          {licitacao.registro_preco && (
            <Badge variant="outline">Registro de Preços</Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

### 5.3 Serviço Python para Prospecção

```python
# services/prospeccao_service.py
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ProspeccaoService:
    """
    Serviço de prospecção de licitações futuras
    
    Responsável por:
    1. Aplicar filtros proativos nas requisições
    2. Classificar status de forma padronizada
    3. Calcular urgência e prioridade
    """
    
    # Status que indicam processo FUTURO/ABERTO
    STATUS_PROSPECCAO = {
        'Agendado', 'Publicado', 'Aberto', 'Em Proposta', 
        'Em Andamento', 'Divulgado', 'Recebendo Propostas'
    }
    
    # Status que indicam processo ENCERRADO (excluir na prospecção)
    STATUS_ENCERRADO = {
        'Encerrado', 'Concluído', 'Homologado', 'Adjudicado',
        'Cancelado', 'Revogado', 'Anulado', 'Deserto', 'Fracassado'
    }
    
    def filtrar_prospeccao(
        self, 
        licitacoes: List[Dict],
        apenas_futuras: bool = True,
        dias_limite: int = 30
    ) -> List[Dict]:
        """
        Filtra licitações para prospecção
        
        Args:
            licitacoes: Lista de licitações
            apenas_futuras: Se True, filtra apenas processos futuros/abertos
            dias_limite: Incluir processos iniciados até X dias atrás
        """
        if not apenas_futuras:
            return licitacoes
        
        hoje = datetime.now()
        data_minima = hoje - timedelta(days=dias_limite)
        resultados = []
        
        for lic in licitacoes:
            # 1. Filtrar por STATUS
            status = lic.get('status', '').strip()
            if any(s.lower() in status.lower() for s in self.STATUS_ENCERRADO):
                continue
            
            # 2. Filtrar por DATA (se disponível)
            data_abertura = lic.get('data_abertura')
            if data_abertura:
                if isinstance(data_abertura, str):
                    try:
                        data_abertura = datetime.fromisoformat(data_abertura.replace('Z', ''))
                    except:
                        data_abertura = None
                
                if data_abertura and data_abertura < data_minima:
                    continue
            
            # 3. Calcular urgência
            lic['urgencia'] = self._calcular_urgencia(lic)
            
            resultados.append(lic)
        
        # Ordenar por urgência (mais urgentes primeiro)
        resultados.sort(key=lambda x: x.get('urgencia', 999))
        
        return resultados
    
    def _calcular_urgencia(self, licitacao: Dict) -> int:
        """
        Calcula urgência baseada em dias até a data limite
        
        Retorna:
            int: Dias até a data limite (menor = mais urgente)
        """
        hoje = datetime.now()
        
        # Prioridade: data_final > data_limite > data_abertura
        for campo in ['data_final', 'data_limite', 'data_abertura']:
            data = licitacao.get(campo)
            if data:
                if isinstance(data, str):
                    try:
                        data = datetime.fromisoformat(data.replace('Z', ''))
                    except:
                        continue
                
                dias = (data - hoje).days
                return max(0, dias)
        
        return 999  # Sem data = baixa urgência
    
    def classificar_status(
        self,
        situacao_api: Optional[str],
        data_abertura: Optional[datetime],
        data_final: Optional[datetime]
    ) -> str:
        """
        Classifica status de forma padronizada para prospecção
        """
        hoje = datetime.now()
        
        # 1. Se data de abertura é no futuro = Agendado
        if data_abertura and data_abertura > hoje:
            return 'Agendado'
        
        # 2. Se data final é no futuro = Aberto
        if data_final and data_final > hoje:
            if data_abertura and data_abertura <= hoje:
                return 'Aberto'
            return 'Agendado'
        
        # 3. Se data final passou = Encerrado
        if data_final and data_final <= hoje:
            return 'Encerrado'
        
        # 4. Usar situação da API
        if situacao_api:
            situacao_lower = situacao_api.lower()
            
            if any(s in situacao_lower for s in ['publicad', 'divulgad', 'aberto']):
                return 'Aberto'
            elif any(s in situacao_lower for s in ['proposta', 'recebendo']):
                return 'Em Proposta'
            elif 'andamento' in situacao_lower:
                return 'Em Andamento'
            elif any(s in situacao_lower for s in ['encerrad', 'concluíd', 'homolog']):
                return 'Encerrado'
            elif any(s in situacao_lower for s in ['cancelad', 'revogad', 'anulad']):
                return 'Cancelado'
        
        return 'Em Licitação'
```

## 6. Resumo das Melhorias Implementadas

| Componente | Antes | Depois |
|------------|-------|--------|
| **PNCP Client** | Filtro pós-busca | Filtros proativos na requisição |
| **CSV Importers** | Sem filtro de prospecção | Filtro por status + data |
| **Status** | Classificação simples | Hierarquia de prospecção |
| **API /search** | `apenas_futuras` não passado | Parâmetro propagado para scrapers |

## 7. Próximos Passos

1. **Implementar no Frontend**: Adicionar toggle "Apenas Abertas/Futuras" nos filtros
2. **Dashboard de Prospecção**: Criar view específica para oportunidades urgentes
3. **Notificações**: Alertas para novas licitações abertas
4. **Métricas**: Tracking de conversão (visualização → proposta)
