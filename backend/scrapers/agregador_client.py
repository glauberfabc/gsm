"""
Agregador Client - Integração Real com a Plataforma Agregador
=========================================================

Este cliente acessa a API do Agregador para buscar licitações de múltiplos portais,
incluindo Licitações-e (Banco do Brasil), que é inacessível diretamente.

API Documentação: /app/docs/AGREGADOR_API_REFERENCE.md

PORTAIS COBERTOS PELO AGREGADOR (22 total):
- Licitações-e (Banco do Brasil) ← PRINCIPAL ALVO
- ComprasNet Federal
- PNCP
- ComprasNet Bahia
- BEC/SP
- E muitos outros portais estaduais

CREDENCIAIS:
- As credenciais devem ser configuradas via variáveis de ambiente:
  AGREGADOR_USERNAME e AGREGADOR_PASSWORD
- OU usar as credenciais hardcoded para desenvolvimento (NÃO recomendado em produção)
"""

import aiohttp
import asyncio
import logging
import os
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)


class AgregadorClient:
    """
    Cliente oficial para a API do Agregador.
    Permite acesso a múltiplos portais de licitação via uma única interface.
    """
    
    BASE_URL = "https://gsm.gruposmartmedical.com.br"
    
    # IDs dos portais conhecidos no Agregador
    PORTAL_IDS = {
        "licitacoes_e": None,  # Será descoberto dinamicamente
        "comprasnet": 1,
        "comprasnet_bahia": 8,
        "bec_sp": None,
        "pncp": None,
    }
    
    # Nomes dos portais para matching
    PORTAL_NAMES = {
        "licitacoes-e": "Licitações-e",
        "licitações-e": "Licitações-e",
        "banco do brasil": "Licitações-e",
        "bb": "Licitações-e",
        "comprasnet": "ComprasNet",
        "pncp": "PNCP",
    }
    
    def __init__(self):
        self.fonte = "AGREGADOR"
        self.token = None
        self.refresh_token = None
        self.timeout = aiohttp.ClientTimeout(total=60)
        self.portais_disponiveis = []
        
        # Credenciais - preferir variáveis de ambiente
        self.username = os.environ.get('AGREGADOR_USERNAME', 'claudio@gruposmartmedical.com.br')
        self.password = os.environ.get('AGREGADOR_PASSWORD', 'Mj@08080808')
    
    async def _login(self, session: aiohttp.ClientSession) -> bool:
        """
        Realiza login no Agregador e obtém token JWT.
        
        Returns:
            bool: True se login bem sucedido, False caso contrário
        """
        try:
            url = f"{self.BASE_URL}/users/login"
            payload = {
                "username": self.username,
                "password": self.password
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "GSM-Buscador-Editais/1.0"
            }
            
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success" or data.get("token"):
                        self.token = data.get("token")
                        self.refresh_token = data.get("refreshToken")
                        logger.info(f"✅ [AGREGADOR] Login bem sucedido. Dias restantes: {data.get('daysRemaining', 'N/A')}")
                        return True
                    else:
                        logger.error(f"❌ [AGREGADOR] Login falhou: {data.get('message', 'Erro desconhecido')}")
                        return False
                else:
                    text = await response.text()
                    logger.error(f"❌ [AGREGADOR] Login HTTP {response.status}: {text[:200]}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ [AGREGADOR] Erro no login: {str(e)}")
            return False
    
    async def _obter_portais(self, session: aiohttp.ClientSession) -> List[Dict]:
        """
        Obtém lista de portais disponíveis no Agregador.
        Usado para descobrir o ID do Licitações-e.
        """
        try:
            url = f"{self.BASE_URL}/accesses/portals"
            headers = self._get_auth_headers()
            
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    portais = await response.json()
                    self.portais_disponiveis = portais
                    
                    # Logar portais encontrados
                    logger.info(f"📋 [AGREGADOR] {len(portais)} portais disponíveis:")
                    for portal in portais[:10]:  # Mostrar apenas os 10 primeiros
                        logger.info(f"   - ID {portal.get('id')}: {portal.get('name')}")
                    
                    # Descobrir ID do Licitações-e
                    for portal in portais:
                        nome = portal.get('name', '').lower()
                        if 'licitações-e' in nome or 'licitacoes-e' in nome or 'banco do brasil' in nome:
                            self.PORTAL_IDS['licitacoes_e'] = portal.get('id')
                            logger.info(f"🎯 [AGREGADOR] Portal Licitações-e encontrado: ID {portal.get('id')}")
                    
                    return portais
                else:
                    logger.warning(f"⚠️ [AGREGADOR] Não foi possível obter portais: HTTP {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"❌ [AGREGADOR] Erro ao obter portais: {str(e)}")
            return []
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Retorna headers com autenticação JWT."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "GSM-Buscador-Editais/1.0"
        }
    
    async def buscar_licitacoes(
        self,
        termo_busca: str = None,
        apenas_futuras: bool = True,
        portal_filtro: str = None,  # "licitacoes_e", "comprasnet", etc.
        limit: int = 100,
        pagina: int = 0
    ) -> List[Dict]:
        """
        Busca licitações no Agregador.
        
        Args:
            termo_busca: Termo para filtrar no objeto da licitação
            apenas_futuras: Se True, retorna apenas licitações com data futura
            portal_filtro: Nome do portal para filtrar (ex: "licitacoes_e")
            limit: Número máximo de resultados
            pagina: Página de resultados (0-indexed)
            
        Returns:
            Lista de licitações no formato padronizado GSM
        """
        resultados = []
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # 1. Login
                if not await self._login(session):
                    logger.error("❌ [AGREGADOR] Falha no login, não é possível buscar licitações")
                    return []
                
                # 2. Obter lista de portais (para descobrir IDs)
                await self._obter_portais(session)
                
                # 3. Buscar avisos
                url = f"{self.BASE_URL}/aviso/minhas"
                headers = self._get_auth_headers()
                
                payload = {
                    "pagina": pagina,
                    "interesse": True,  # Filtrar por perfil de interesse
                    "favorito": False,
                    "orgaoFavorito": False,
                    "distribuidores": False,
                    "id": "",
                    "deserto": False,
                    "ordem": [
                        {"orderBy": "dataInicial"},  # Ordenar por data de abertura
                        {"order": "asc"}
                    ],
                    "tipo": []  # Todas as modalidades
                }
                
                logger.info(f"🔍 [AGREGADOR] Buscando licitações... (página {pagina})")
                
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        total_records = data.get('recordsTotal', 0)
                        filtered_records = data.get('recordsFiltered', 0)
                        avisos = data.get('data', [])
                        
                        logger.info(f"📊 [AGREGADOR] Total: {total_records}, Filtrados: {filtered_records}, Página: {len(avisos)}")
                        
                        # 4. Processar cada aviso
                        for aviso in avisos:
                            try:
                                licitacao = self._mapear_aviso(aviso)
                                
                                if licitacao is None:
                                    continue
                                
                                # Filtro por portal
                                if portal_filtro:
                                    portal_nome = aviso.get('portalNome', '').lower()
                                    if portal_filtro.lower() not in portal_nome and \
                                       self.PORTAL_NAMES.get(portal_filtro.lower(), '').lower() not in portal_nome:
                                        continue
                                
                                # Filtro por termo de busca
                                if termo_busca:
                                    objeto = licitacao.get('objeto', '').lower()
                                    if termo_busca.lower() not in objeto:
                                        continue
                                
                                # Filtro apenas futuras
                                if apenas_futuras:
                                    data_final = licitacao.get('data_final')
                                    if data_final:
                                        if isinstance(data_final, str):
                                            try:
                                                data_final = datetime.fromisoformat(data_final.replace('Z', ''))
                                            except:
                                                continue
                                        if isinstance(data_final, datetime) and data_final < datetime.now():
                                            continue
                                
                                resultados.append(licitacao)
                                
                                if len(resultados) >= limit:
                                    break
                                    
                            except Exception as e:
                                logger.warning(f"⚠️ [AGREGADOR] Erro ao mapear aviso: {str(e)}")
                                continue
                        
                        logger.info(f"✅ [AGREGADOR] {len(resultados)} licitações processadas")
                        
                    else:
                        text = await response.text()
                        logger.error(f"❌ [AGREGADOR] Erro HTTP {response.status}: {text[:200]}")
        
        except Exception as e:
            logger.error(f"❌ [AGREGADOR] Erro na busca: {str(e)}")
        
        return resultados
    
    def _mapear_aviso(self, aviso: Dict) -> Optional[Dict]:
        """
        Mapeia um aviso do Agregador para o formato padronizado GSM.
        
        Campos do Agregador (descobertos via engenharia reversa):
        - id, refer, objeto, portal, portalNome, pregao, uasgNome
        - url, dataEnvioEmail, dataInicial, dataFinal, dataPublicacao
        - uasg, orgao (pode ser None), uf (nome completo), tipo, isSrp, iminencia (boolean!)
        
        Returns:
            Dict no formato GSM ou None se inválido
        """
        try:
            # Extrair datas (formato: "DD/MM/YYYY HH:MM:SS")
            data_inicial = self._parse_date(aviso.get('dataInicial'))
            data_final = self._parse_date(aviso.get('dataFinal'))
            data_publicacao = self._parse_date(aviso.get('dataPublicacao'))
            
            # Calcular iminência em DIAS (o Agregador retorna boolean, precisamos calcular)
            iminencia_dias = None
            if data_final:
                delta = (data_final - datetime.now()).days
                iminencia_dias = max(0, delta)
            
            # Determinar status
            status = self._determinar_status(data_final, iminencia_dias)
            
            # Extrair estado (UF) - o Agregador retorna nome completo
            uf_completo = aviso.get('uf', '')
            uf_sigla = self._extrair_uf_sigla(uf_completo)
            
            # Extrair itens se disponíveis
            itens = []
            if aviso.get('item'):
                for item in aviso.get('item', []):
                    itens.append({
                        "numero": item.get('codigo', item.get('numero', 0)),
                        "descricao": item.get('descricao', item.get('objeto', '')),
                        "quantidade": item.get('quantidade'),
                        "unidade": item.get('unidade'),
                        "valor_estimado": item.get('valor')
                    })
            
            # Determinar órgão (pode ser None)
            orgao = aviso.get('uasgNome') or aviso.get('orgao') or 'Não informado'
            
            # Determinar se é SRP (pode ser string "Sim"/"Não" ou boolean)
            is_srp = aviso.get('isSrp')
            if isinstance(is_srp, str):
                is_srp = is_srp.lower() == 'sim'
            
            # Construir licitação no formato GSM
            licitacao = {
                "id": str(uuid.uuid4()),
                "fonte_id": str(aviso.get('id', '')),
                "fonte": f"AGREGADOR/{aviso.get('portalNome', 'Desconhecido')}",
                "fonte_nome": aviso.get('portalNome', 'Agregador'),
                "medicamento": (aviso.get('objeto') or '')[:100],
                "objeto": aviso.get('objeto') or '',
                "estado": uf_sigla,
                "status": status,
                "orgao_licitante": orgao,
                "modalidade": aviso.get('tipo') or 'Não informado',
                "numero_processo": aviso.get('pregao') or '',
                "numero_pregao": aviso.get('pregao') or '',
                "uasg": str(aviso.get('uasg') or ''),
                "esfera": self._determinar_esfera(aviso),
                "data_abertura": data_inicial.isoformat() if data_inicial else None,
                "data_final": data_final.isoformat() if data_final else None,
                "data_publicacao": data_publicacao.isoformat() if data_publicacao else None,
                "data_referencia": datetime.now().isoformat(),
                "link_origem": aviso.get('url') or '',
                "link_documento": self._extrair_link_edital(aviso),
                "is_srp": is_srp,
                "iminencia": iminencia_dias,
                "itens": itens,
                "tags": self._extrair_tags(aviso, iminencia_dias),
                "is_mock": False,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            return licitacao
            
        except Exception as e:
            logger.warning(f"⚠️ [AGREGADOR] Erro ao mapear aviso {aviso.get('id')}: {str(e)}")
            return None
    
    def _extrair_uf_sigla(self, uf_completo: str) -> str:
        """Converte nome do estado para sigla UF."""
        if not uf_completo:
            return ''
        
        uf_map = {
            'acre': 'AC', 'alagoas': 'AL', 'amapá': 'AP', 'amazonas': 'AM',
            'bahia': 'BA', 'ceará': 'CE', 'distrito federal': 'DF', 'espírito santo': 'ES',
            'goiás': 'GO', 'maranhão': 'MA', 'mato grosso': 'MT', 'mato grosso do sul': 'MS',
            'minas gerais': 'MG', 'pará': 'PA', 'paraíba': 'PB', 'paraná': 'PR',
            'pernambuco': 'PE', 'piauí': 'PI', 'rio de janeiro': 'RJ', 'rio grande do norte': 'RN',
            'rio grande do sul': 'RS', 'rondônia': 'RO', 'roraima': 'RR', 'santa catarina': 'SC',
            'são paulo': 'SP', 'sergipe': 'SE', 'tocantins': 'TO'
        }
        
        uf_lower = uf_completo.lower().strip()
        return uf_map.get(uf_lower, uf_completo[:2].upper())
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Converte string de data para datetime."""
        if not date_str:
            return None
        
        try:
            date_str = str(date_str).strip()
            
            # Formato ISO comum
            if 'T' in date_str:
                return datetime.fromisoformat(date_str.replace('Z', ''))
            # Formato DD/MM/YYYY HH:MM:SS (formato do Agregador)
            elif '/' in date_str and ':' in date_str:
                return datetime.strptime(date_str, '%d/%m/%Y %H:%M:%S')
            # Formato DD/MM/YYYY
            elif '/' in date_str:
                return datetime.strptime(date_str, '%d/%m/%Y')
            return None
        except Exception as e:
            logger.debug(f"Erro ao parsear data '{date_str}': {e}")
            return None
    
    def _determinar_status(self, data_final: Optional[datetime], iminencia: Optional[int]) -> str:
        """Determina o status da licitação baseado na data e iminência."""
        if data_final is None:
            return "Ativa"
        
        agora = datetime.now()
        
        if data_final < agora:
            return "Encerrada"
        
        if iminencia is not None:
            if iminencia == 0:
                return "HOJE"
            elif iminencia <= 3:
                return "Urgente"
            elif iminencia <= 7:
                return "Em Proposta"
        
        return "FUTURA"
    
    def _determinar_esfera(self, aviso: Dict) -> str:
        """Determina a esfera administrativa (Federal, Estadual, Municipal)."""
        portal = (aviso.get('portalNome') or '').lower()
        orgao = (aviso.get('orgao') or '').lower()
        uasg_nome = (aviso.get('uasgNome') or '').lower()
        
        # Combinar órgão e uasgNome para melhor detecção
        orgao_completo = f"{orgao} {uasg_nome}"
        
        if 'federal' in portal or ('comprasnet' in portal and 'bahia' not in portal):
            return "Federal"
        elif 'municipal' in orgao_completo or 'prefeitura' in orgao_completo:
            return "Municipal"
        else:
            return "Estadual"
    
    def _extrair_link_edital(self, aviso: Dict) -> Optional[str]:
        """Extrai link direto para o edital se disponível."""
        anexos = aviso.get('anexo', [])
        if anexos:
            for anexo in anexos:
                nome = anexo.get('nome', '').lower()
                if 'edital' in nome or '.pdf' in nome:
                    return anexo.get('url')
        return None
    
    def _extrair_tags(self, aviso: Dict, iminencia_dias: Optional[int] = None) -> List[str]:
        """Extrai tags relevantes do aviso."""
        tags = []
        objeto = (aviso.get('objeto') or '').lower()
        
        # Tags de saúde
        keywords_saude = ['medicament', 'farmac', 'hospital', 'saúde', 'saude', 'médic', 'medic',
                         'insulina', 'vacina', 'seringa', 'insumo', 'laborat', 'oncolog', 'cirurg']
        if any(kw in objeto for kw in keywords_saude):
            tags.append('saude')
        
        # Tags de urgência (baseado nos dias calculados)
        if iminencia_dias is not None and iminencia_dias <= 3:
            tags.append('urgente')
        
        # Tag SRP
        is_srp = aviso.get('isSrp')
        if isinstance(is_srp, str):
            is_srp = is_srp.lower() == 'sim'
        if is_srp:
            tags.append('srp')
        
        return tags
    
    async def buscar_licitacoes_e(
        self,
        termo_busca: str = None,
        apenas_futuras: bool = True,
        limit: int = 50
    ) -> List[Dict]:
        """
        Busca específica no portal Licitações-e (Banco do Brasil) via Agregador.
        
        Este é o método principal para acessar o Licitações-e, que está bloqueado
        para acesso direto por Cloudflare.
        
        Args:
            termo_busca: Filtrar por termo no objeto
            apenas_futuras: Apenas licitações com data futura
            limit: Máximo de resultados
            
        Returns:
            Lista de licitações do Licitações-e
        """
        logger.info("🏦 [AGREGADOR] Buscando no portal Licitações-e (Banco do Brasil)...")
        
        return await self.buscar_licitacoes(
            termo_busca=termo_busca,
            apenas_futuras=apenas_futuras,
            portal_filtro="licitações-e",
            limit=limit
        )


# Instância singleton para uso no scraper_service
agregador_client = AgregadorClient()


# Função de teste
async def test_agregador():
    """Função de teste para validar a integração."""
    client = AgregadorClient()
    
    print("=" * 60)
    print("🧪 TESTE DE INTEGRAÇÃO AGREGADOR")
    print("=" * 60)
    
    # Teste 1: Busca geral
    print("\n📋 Teste 1: Busca geral de licitações")
    resultados = await client.buscar_licitacoes(
        apenas_futuras=True,
        limit=10
    )
    print(f"   Encontradas: {len(resultados)} licitações")
    
    for r in resultados[:3]:
        print(f"   - [{r.get('fonte')}] {r.get('objeto', 'N/A')[:50]}...")
        print(f"     Status: {r.get('status')}, Iminência: {r.get('iminencia')} dias")
    
    # Teste 2: Busca específica Licitações-e
    print("\n🏦 Teste 2: Busca no Licitações-e")
    licitacoes_e = await client.buscar_licitacoes_e(
        apenas_futuras=True,
        limit=10
    )
    print(f"   Encontradas: {len(licitacoes_e)} licitações do Licitações-e")
    
    for r in licitacoes_e[:3]:
        print(f"   - {r.get('objeto', 'N/A')[:50]}...")
        print(f"     Órgão: {r.get('orgao_licitante')}")
        print(f"     Data Limite: {r.get('data_final')}")
    
    print("\n" + "=" * 60)
    print("✅ TESTE CONCLUÍDO")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_agregador())
