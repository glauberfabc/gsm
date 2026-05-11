import React from 'react';
import { Zap, Building, Plus, CheckCircle, AlertTriangle, DollarSign, FileArchive, Upload, X, Eye, Search, Loader2, Radar, Hash, Edit2, FileText, Trash2 } from 'lucide-react';

export function DamaTab({
  damaStep, editalFiles, setEditalFiles, damaEmpresa, setDamaEmpresa,
  damaMoeda, setDamaMoeda, damaProcessing,
  damaZipBlob, damaStats,
  damaExtraindo, damaItensGrid, setDamaItensGrid,
  damaPalavraChave, setDamaPalavraChave,
  damaItemNumero, setDamaItemNumero,
  damaItemValor, damaItemValorRaw,
  handleValorChange, extrairItensPorPalavraChave, visualizarEdital,
  resetDAMA, processarDAMASimplificado,
  companies,
  showEmpresaModal, setShowEmpresaModal,
  editingCompanyId, setEditingCompanyId,
  editCompanyForm, setEditCompanyForm,
  saveCompany,
}) {
  return (
    <div className="space-y-8">
      {/* Modal de Cadastro de Empresas */}
      {showEmpresaModal && (
        <EmpresaModal
          editingCompanyId={editingCompanyId}
          editCompanyForm={editCompanyForm}
          setEditCompanyForm={setEditCompanyForm}
          saveCompany={saveCompany}
          onClose={() => { setShowEmpresaModal(false); setEditingCompanyId(null); setEditCompanyForm({}); }}
        />
      )}

      {damaStep === 'upload' && (
        <UploadStep
          editalFiles={editalFiles} setEditalFiles={setEditalFiles}
          damaEmpresa={damaEmpresa} setDamaEmpresa={setDamaEmpresa}
          damaMoeda={damaMoeda} setDamaMoeda={setDamaMoeda}
          damaProcessing={damaProcessing}
          damaExtraindo={damaExtraindo}
          damaItensGrid={damaItensGrid} setDamaItensGrid={setDamaItensGrid}
          damaPalavraChave={damaPalavraChave} setDamaPalavraChave={setDamaPalavraChave}
          damaItemNumero={damaItemNumero} setDamaItemNumero={setDamaItemNumero}
          damaItemValor={damaItemValor} damaItemValorRaw={damaItemValorRaw}
          handleValorChange={handleValorChange}
          extrairItensPorPalavraChave={extrairItensPorPalavraChave}
          visualizarEdital={visualizarEdital}
          processarDAMASimplificado={processarDAMASimplificado}
          companies={companies}
          setShowEmpresaModal={setShowEmpresaModal}
          setEditingCompanyId={setEditingCompanyId}
          setEditCompanyForm={setEditCompanyForm}
        />
      )}

      {damaStep === 'success' && (
        <SuccessStep damaZipBlob={damaZipBlob} damaStats={damaStats} resetDAMA={resetDAMA} />
      )}
    </div>
  );
}

function EmpresaModal({ editingCompanyId, editCompanyForm, setEditCompanyForm, saveCompany, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-auto">
        <div className="p-8 space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-black text-slate-800 uppercase flex items-center gap-3">
              <Building size={28} className="text-purple-600"/> {editingCompanyId ? 'Editar Empresa' : 'Cadastrar Empresa'}
            </h2>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={28}/></button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {[
              { key: 'name', label: 'Razao Social *', span: 2, placeholder: 'Nome da empresa' },
              { key: 'cnpj', label: 'CNPJ *', span: 1, placeholder: '00.000.000/0000-00' },
              { key: 'ie', label: 'Inscricao Estadual', span: 1, placeholder: 'Inscricao Estadual' },
              { key: 'address', label: 'Endereco Completo', span: 2, placeholder: 'Rua, numero, bairro, cidade - UF' },
              { key: 'phone', label: 'Telefone', span: 1, placeholder: '(00) 0000-0000' },
              { key: 'whatsapp', label: 'WhatsApp', span: 1, placeholder: '(00) 00000-0000' },
              { key: 'email', label: 'E-mail', span: 2, placeholder: 'contato@empresa.com.br', type: 'email' },
            ].map(f => (
              <div key={f.key} className={f.span === 2 ? 'col-span-2' : ''}>
                <label className="text-xs font-bold text-slate-500 uppercase">{f.label}</label>
                <input type={f.type || 'text'} value={editCompanyForm[f.key] || ''} 
                  onChange={(e) => setEditCompanyForm({...editCompanyForm, [f.key]: e.target.value})}
                  className="w-full py-3 px-4 border-2 rounded-xl focus:border-purple-500 outline-none" placeholder={f.placeholder}/>
              </div>
            ))}
            <div className="col-span-2 bg-purple-50 p-6 rounded-2xl border-2 border-purple-200">
              <label className="text-sm font-black text-purple-700 uppercase flex items-center gap-2 mb-3">
                <FileText size={18}/> Papel Timbrado Oficial (.docx) *
              </label>
              <p className="text-xs text-purple-600 mb-4">O arquivo deve conter a tag <code className="bg-purple-200 px-2 py-1 rounded">{'{{TEXTO_DAMA}}'}</code> onde a proposta sera inserida.</p>
              {(editCompanyForm.timbrado || editCompanyForm.timbradoNome) ? (
                <div className="bg-white p-4 rounded-xl border-2 border-emerald-300 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <CheckCircle size={24} className="text-emerald-600"/>
                    <div>
                      <p className="font-bold text-emerald-700">{editCompanyForm.timbrado?.name || editCompanyForm.timbradoNome}</p>
                      <p className="text-xs text-slate-500">Timbrado cadastrado</p>
                    </div>
                  </div>
                  <button type="button" onClick={() => setEditCompanyForm({...editCompanyForm, timbrado: null, timbradoNome: '', timbradoRemovido: true})}
                    className="bg-red-100 text-red-600 px-4 py-2 rounded-lg font-bold text-sm hover:bg-red-200 flex items-center gap-2">
                    <Trash2 size={16}/> Excluir
                  </button>
                </div>
              ) : (
                <label className="border-2 border-dashed border-purple-300 bg-white p-6 rounded-xl text-center cursor-pointer hover:bg-purple-100 transition-all block">
                  <input type="file" accept=".docx" className="hidden"
                    onChange={(e) => setEditCompanyForm({...editCompanyForm, timbrado: e.target.files?.[0], timbradoNome: e.target.files?.[0]?.name, timbradoRemovido: false})}/>
                  <Upload size={32} className="mx-auto text-purple-400 mb-2"/>
                  <p className="text-slate-500">Clique para selecionar o .docx</p>
                </label>
              )}
            </div>
          </div>
          <div className="flex gap-4 pt-4">
            <button onClick={async () => { await saveCompany(); onClose(); }}
              disabled={!editCompanyForm.name || !editCompanyForm.cnpj}
              className="flex-1 bg-purple-600 text-white py-4 rounded-xl font-black uppercase hover:bg-purple-700 disabled:opacity-50 flex items-center justify-center gap-2">
              <CheckCircle size={20}/> Salvar Empresa
            </button>
            <button onClick={onClose} className="px-8 bg-slate-200 text-slate-600 py-4 rounded-xl font-bold uppercase hover:bg-slate-300">Cancelar</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function UploadStep({
  editalFiles, setEditalFiles, damaEmpresa, setDamaEmpresa,
  damaMoeda, setDamaMoeda, damaProcessing, damaExtraindo,
  damaItensGrid, setDamaItensGrid,
  damaPalavraChave, setDamaPalavraChave,
  damaItemNumero, setDamaItemNumero,
  damaItemValor, damaItemValorRaw,
  handleValorChange, extrairItensPorPalavraChave, visualizarEdital,
  processarDAMASimplificado, companies,
  setShowEmpresaModal, setEditingCompanyId, setEditCompanyForm,
}) {
  return (
    <div className="grid lg:grid-cols-2 gap-8">
      <div className="bg-white p-10 rounded-3xl shadow-xl border border-slate-200 space-y-6">
        <h2 className="text-2xl font-black text-slate-800 uppercase flex items-center gap-3">
          <Zap size={28} className="text-purple-600"/> DAMA IA v73.1 - Motor de Propostas
        </h2>

        {/* Empresa */}
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <label className="text-sm font-black text-slate-500 uppercase flex items-center gap-2"><Building size={16}/> 1. Empresa Proponente</label>
            <button onClick={() => { setShowEmpresaModal(true); setEditingCompanyId(null); setEditCompanyForm({ id: `c${Date.now()}` }); }}
              className="text-xs bg-purple-100 text-purple-700 px-3 py-2 rounded-lg font-bold hover:bg-purple-200 flex items-center gap-1">
              <Plus size={14}/> Nova Empresa
            </button>
          </div>
          <div className="space-y-2 max-h-48 overflow-auto">
            {companies.filter(c => c.name).length === 0 ? (
              <div className="bg-orange-50 p-4 rounded-xl text-orange-700 text-sm"><AlertTriangle size={16} className="inline mr-2"/>Nenhuma empresa cadastrada. Clique em "Nova Empresa".</div>
            ) : companies.filter(c => c.name).map(c => (
              <div key={`emp-list-${c.id}`} className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${damaEmpresa === c.id ? 'border-purple-500 bg-purple-50' : 'border-slate-200 hover:border-slate-300'}`}
                onClick={() => setDamaEmpresa(c.id)}>
                <div className="flex justify-between items-start">
                  <div className="flex-grow">
                    <div className="flex items-center gap-2">
                      <input type="radio" name="empresa" checked={damaEmpresa === c.id} onChange={() => setDamaEmpresa(c.id)} className="accent-purple-600"/>
                      <p className="font-bold text-slate-800">{c.name}</p>
                    </div>
                    <p className="text-xs text-slate-500 ml-5">{c.cnpj}</p>
                    {c.timbradoNome
                      ? <p className="text-xs text-emerald-600 ml-5 flex items-center gap-1 mt-1"><CheckCircle size={12}/> Timbrado: {c.timbradoNome}</p>
                      : <p className="text-xs text-orange-500 ml-5 flex items-center gap-1 mt-1"><AlertTriangle size={12}/> Sem timbrado</p>}
                  </div>
                  <button onClick={(e) => { e.stopPropagation(); setEditingCompanyId(c.id); setEditCompanyForm({...c}); setShowEmpresaModal(true); }}
                    className="text-slate-400 hover:text-purple-600 p-2"><Edit2 size={16}/></button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Moeda */}
        <div className="space-y-3">
          <label className="text-sm font-black text-slate-500 uppercase flex items-center gap-2"><DollarSign size={16}/> 2. Moeda da Proposta</label>
          <select value={damaMoeda} onChange={(e) => setDamaMoeda(e.target.value)}
            className="w-full py-4 px-4 bg-slate-50 border-2 border-slate-200 rounded-xl font-semibold text-base focus:border-purple-500 outline-none">
            <option value="BRL">R$ Real (BRL)</option>
            <option value="USD">$ Dolar (USD)</option>
          </select>
        </div>

        {/* Upload PDF */}
        <div className="space-y-3">
          <label className="text-sm font-black text-slate-500 uppercase flex items-center gap-2"><FileArchive size={16}/> 3. PDF(s) do Edital Oficial</label>
          <label className="border-3 border-dashed border-indigo-200 bg-indigo-50/50 p-6 rounded-2xl text-center cursor-pointer hover:bg-indigo-100 transition-all block">
            <input type="file" accept=".pdf" multiple className="hidden" onChange={(e) => { setEditalFiles(prev => [...prev, ...Array.from(e.target.files || [])]); }}/>
            <Upload size={32} className="mx-auto text-indigo-400 mb-2"/>
            <p className="font-bold text-slate-600">{editalFiles.length > 0 ? `${editalFiles.length} arquivo(s) selecionado(s)` : 'Clique para selecionar PDF(s)'}</p>
          </label>
          {editalFiles.length > 0 && (
            <div className="space-y-3">
              <div className="space-y-2 max-h-24 overflow-auto">
                {editalFiles.map((file, idx) => (
                  <div key={`pdf-${idx}-${file.name}`} className="flex items-center justify-between bg-white p-2 rounded-lg border">
                    <span className="text-sm text-slate-700 truncate flex-1">{file.name}</span>
                    <button type="button" onClick={() => setEditalFiles(prev => prev.filter((_, i) => i !== idx))} className="text-red-500 hover:text-red-700 ml-2"><X size={16}/></button>
                  </div>
                ))}
              </div>
              <button type="button" onClick={visualizarEdital}
                className="w-full bg-blue-100 text-blue-700 py-3 rounded-xl font-bold text-sm uppercase flex items-center justify-center gap-2 hover:bg-blue-200">
                <Eye size={18}/> Visualizar Edital Subido
              </button>
            </div>
          )}
        </div>

        {/* Palavra-Chave */}
        <div className="space-y-3">
          <label className="text-sm font-black text-slate-500 uppercase flex items-center gap-2"><Search size={16}/> 4. Palavra(s)-Chave para Filtrar Itens</label>
          <p className="text-xs text-slate-400">Separe multiplos termos por virgula.</p>
          <div className="flex gap-2">
            <input type="text" value={damaPalavraChave} onChange={(e) => setDamaPalavraChave(e.target.value)}
              className="flex-grow py-4 px-4 bg-slate-50 border-2 border-slate-200 rounded-xl font-bold text-lg focus:border-purple-500 outline-none"
              placeholder="Ex: Canabidiol, Insulina, Prolia"/>
            <button type="button" onClick={extrairItensPorPalavraChave}
              disabled={!editalFiles.length || !damaPalavraChave.trim() || damaExtraindo}
              className="bg-indigo-600 text-white px-6 py-4 rounded-xl font-bold uppercase flex items-center gap-2 hover:bg-indigo-700 disabled:opacity-50">
              {damaExtraindo ? <><Loader2 className="animate-spin" size={20}/> Extraindo...</> : <><Radar size={20}/> Extrair Itens</>}
            </button>
          </div>
        </div>

        {/* Grid de Itens */}
        {damaItensGrid.length > 0 && (
          <ItemsGrid damaItensGrid={damaItensGrid} setDamaItensGrid={setDamaItensGrid}
            damaMoeda={damaMoeda} handleValorChange={handleValorChange} />
        )}

        {/* Fallback manual */}
        {damaItensGrid.length === 0 && (
          <div className="space-y-3 bg-slate-50 p-4 rounded-xl">
            <label className="text-sm font-black text-slate-500 uppercase flex items-center gap-2"><Hash size={16}/> Ou Digite Manualmente</label>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-400 font-bold">N do Item</label>
                <input type="text" value={damaItemNumero} onChange={(e) => setDamaItemNumero(e.target.value)}
                  className="w-full py-3 px-4 bg-white border-2 border-slate-200 rounded-xl font-bold focus:border-purple-500 outline-none"
                  placeholder="Ex: 1, 2, 15..."/>
              </div>
              <div>
                <label className="text-xs text-slate-400 font-bold">Valor Unitario</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 font-black text-purple-600 bg-purple-100 px-2 py-1 rounded text-sm">{damaMoeda === 'BRL' ? 'R$' : '$'}</span>
                  <input type="text" value={damaItemValor} onChange={(e) => handleValorChange(e)}
                    className="w-full py-3 pl-14 pr-4 bg-white border-2 border-slate-200 rounded-xl font-bold focus:border-purple-500 outline-none"
                    placeholder={damaMoeda === 'BRL' ? '100,00' : '100.00'}/>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Gerar Kit */}
        <button onClick={processarDAMASimplificado}
          disabled={editalFiles.length === 0 || !companies.find(c => c.id === damaEmpresa)?.timbradoNome || damaProcessing ||
            (damaItensGrid.length === 0 && (!damaItemNumero || !damaItemValorRaw)) ||
            (damaItensGrid.length > 0 && damaItensGrid.filter(i => i.selecionado && i.valorRaw).length === 0)}
          className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-5 rounded-2xl font-black uppercase text-lg shadow-xl hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3">
          {damaProcessing ? <><Loader2 className="animate-spin" size={24}/> GERANDO PROPOSTA...</> : <><Zap size={24}/> GERAR KIT LICITACAO</>}
        </button>

        {damaItensGrid.length > 0 && (
          <div className={`text-sm text-center p-2 rounded-lg ${damaItensGrid.filter(i => i.selecionado && i.valorRaw).length > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-orange-100 text-orange-700'}`}>
            {damaItensGrid.filter(i => i.selecionado && i.valorRaw).length > 0
              ? `${damaItensGrid.filter(i => i.selecionado && i.valorRaw).length} item(ns) pronto(s) para gerar`
              : 'Preencha o valor de pelo menos um item selecionado'}
          </div>
        )}
        {!companies.find(c => c.id === damaEmpresa)?.timbradoNome && companies.filter(c => c.name).length > 0 && (
          <p className="text-sm text-orange-600 text-center">A empresa selecionada nao tem timbrado. Clique em editar para adicionar.</p>
        )}
        {damaProcessing && (
          <div className="text-center text-sm text-slate-500">
            <p>Etapas: Analise IA - Geracao de Proposta - Injecao no Timbrado - ZIP</p>
            <p className="text-purple-600 font-bold mt-1">Aguarde, isto pode levar ate 2 minutos...</p>
          </div>
        )}
      </div>

      {/* Painel Direito - Instrucoes */}
      <InstructionPanel />
    </div>
  );
}

function ItemsGrid({ damaItensGrid, setDamaItensGrid, damaMoeda, handleValorChange }) {
  return (
    <div className="space-y-3">
      <label className="text-sm font-black text-emerald-600 uppercase flex items-center gap-2">
        <CheckCircle size={16}/> {damaItensGrid.length} Itens Encontrados - Preencha os valores
      </label>
      <div className="border-2 border-emerald-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-emerald-50">
            <tr>
              <th className="px-3 py-2 text-left font-bold text-slate-600">Sel</th>
              <th className="px-3 py-2 text-left font-bold text-slate-600"># Item</th>
              <th className="px-3 py-2 text-left font-bold text-slate-600">Descricao</th>
              <th className="px-3 py-2 text-left font-bold text-slate-600">Valor ({damaMoeda === 'BRL' ? 'R$' : '$'})</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {damaItensGrid.map((item) => (
              <tr key={item.id} className={`hover:bg-slate-50 ${item.selecionado && item.valorRaw ? 'bg-emerald-50' : ''}`}>
                <td className="px-3 py-2">
                  <input type="checkbox" checked={item.selecionado}
                    onChange={(e) => setDamaItensGrid(prev => prev.map(i => i.id === item.id ? {...i, selecionado: e.target.checked} : i))}
                    className="accent-emerald-600 w-5 h-5"/>
                </td>
                <td className="px-3 py-2 font-bold text-slate-800">{item.numero}</td>
                <td className="px-3 py-2 text-slate-600 max-w-xs truncate" title={item.descricao}>{item.descricao}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1">
                    <span className="text-xs font-bold text-purple-600">{damaMoeda === 'BRL' ? 'R$' : '$'}</span>
                    <input type="text" value={item.valor} onChange={(e) => handleValorChange(e, item.id)}
                      className={`w-28 py-2 px-3 border-2 rounded-lg font-bold outline-none ${item.valorRaw ? 'bg-emerald-50 border-emerald-300' : 'bg-slate-50 border-slate-200'} focus:border-emerald-500`}
                      placeholder={damaMoeda === 'BRL' ? '100,00' : '100.00'}/>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500 text-center">Preencha o valor dos itens que deseja participar e clique em GERAR KIT</p>
    </div>
  );
}

function SuccessStep({ damaZipBlob, damaStats, resetDAMA }) {
  return (
    <div className="bg-white p-16 rounded-3xl shadow-xl border-4 border-emerald-200 text-center space-y-8">
      <div className="text-emerald-500"><CheckCircle size={100} className="mx-auto"/></div>
      <h3 className="text-4xl font-black text-slate-800 uppercase">Kit Licitacao Pronto!</h3>
      {damaStats && (
        <div className="bg-slate-50 p-6 rounded-2xl text-left max-w-md mx-auto">
          <p className="text-sm text-slate-600"><strong>Arquivo(s):</strong> {damaStats.numero_processo}</p>
          <p className="text-sm text-slate-600"><strong>Itens:</strong> {damaStats.itens_processados}</p>
          <p className="text-sm text-slate-600"><strong>Empresa:</strong> {damaStats.empresa}</p>
          {damaStats.valor_total && <p className="text-sm text-slate-600"><strong>Valor Total:</strong> {damaStats.valor_total}</p>}
          <p className="text-sm text-slate-600"><strong>Moeda:</strong> {damaStats.moeda}</p>
          {damaStats.palavraChave && damaStats.palavraChave !== '-' && <p className="text-sm text-slate-600"><strong>Filtro:</strong> {damaStats.palavraChave}</p>}
        </div>
      )}
      <div className="space-y-6">
        {damaZipBlob ? (
          <a href={damaZipBlob} download={damaStats?.zipFilename || 'kit_licitacao.zip'} data-testid="download-zip-btn"
            className="inline-block bg-emerald-600 text-white px-16 py-6 rounded-2xl font-black text-xl uppercase shadow-xl hover:bg-emerald-700">
            BAIXAR KIT .ZIP
          </a>
        ) : (
          <div className="bg-red-100 text-red-700 px-8 py-4 rounded-xl font-bold">ZIP nao disponivel. Tente gerar novamente.</div>
        )}
        <p className="text-sm text-slate-500">Clique no botao verde para baixar o kit completo</p>
        <button type="button" onClick={resetDAMA} data-testid="nova-proposta-btn"
          className="bg-slate-200 text-slate-600 px-12 py-4 rounded-xl font-bold uppercase hover:bg-slate-300">Nova Proposta</button>
      </div>
    </div>
  );
}

function InstructionPanel() {
  const steps = [
    { num: '1', color: 'bg-purple-600', title: 'Cadastre suas empresas', desc: 'Com papel timbrado (.docx) contendo {{TEXTO_DAMA}}' },
    { num: '2', color: 'bg-purple-600', title: 'Suba o PDF do edital', desc: 'Use o botao "Visualizar" para conferir' },
    { num: '3', color: 'bg-indigo-600', title: 'Digite a Palavra-Chave', desc: 'Ex: "Canabidiol" - A IA filtra os itens', titleClass: 'text-indigo-300' },
    { num: '4', color: 'bg-purple-600', title: 'Preencha os valores', desc: 'No grid de itens encontrados pela IA' },
    { num: 'OK', color: 'bg-emerald-600', title: 'Kit completo gerado!', desc: 'Proposta + declaracoes injetadas no timbrado', titleClass: 'text-emerald-400' },
  ];

  return (
    <div className="bg-gradient-to-br from-slate-800 to-slate-900 p-8 rounded-3xl shadow-xl text-white space-y-6">
      <h3 className="text-sm font-black text-purple-400 uppercase tracking-widest mb-4">Motor de Inteligencia v73.1</h3>
      <div className="space-y-4">
        {steps.map((s, i) => (
          <div key={i} className="flex items-start gap-3">
            <div className={`w-8 h-8 ${s.color} rounded-full flex items-center justify-center text-sm font-black`}>{s.num}</div>
            <div>
              <p className={`font-bold ${s.titleClass || ''}`}>{s.title}</p>
              <p className="text-sm text-slate-400">{s.desc}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-8 pt-6 border-t border-slate-700">
        <p className="text-xs text-slate-500 uppercase font-bold mb-3">Documentos Gerados</p>
        <div className="grid grid-cols-2 gap-4 text-center">
          <div className="bg-slate-700/50 p-3 rounded-xl"><p className="text-2xl font-black text-purple-400">1</p><p className="text-xs text-slate-400">Proposta Comercial</p></div>
          <div className="bg-slate-700/50 p-3 rounded-xl"><p className="text-2xl font-black text-emerald-400">3</p><p className="text-xs text-slate-400">Declaracoes</p></div>
        </div>
      </div>
    </div>
  );
}
