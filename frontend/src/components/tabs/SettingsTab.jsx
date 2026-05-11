import React from 'react';
import { Building, PenTool, CheckCircle, AlertTriangle, AlertCircle, FileDown, Upload } from 'lucide-react';

export function SettingsTab({
  companies,
  editingCompanyId,
  editCompanyForm, setEditCompanyForm,
  startEditCompany, cancelEditCompany, saveCompany,
}) {
  return (
    <div className="space-y-8">
      <div className="text-center mb-10">
        <h2 className="text-4xl font-black text-slate-800 uppercase tracking-tight">Configuracoes</h2>
        <p className="text-slate-500 text-lg font-medium uppercase tracking-wider">Gestao de 10 Empresas para Faturamento</p>
      </div>
      
      <div className="grid gap-4">
        {companies.map((company, idx) => (
          <div key={`company-${company.id}`} className="bg-white p-6 rounded-2xl shadow-md border-2 border-slate-100 hover:border-indigo-300 transition-all">
            {editingCompanyId === company.id ? (
              <EditForm
                editCompanyForm={editCompanyForm}
                setEditCompanyForm={setEditCompanyForm}
                cancelEditCompany={cancelEditCompany}
                saveCompany={saveCompany}
              />
            ) : (
              <ViewCard company={company} idx={idx} startEditCompany={startEditCompany} />
            )}
          </div>
        ))}
      </div>
      
      <div className="bg-amber-50 border-2 border-amber-200 rounded-2xl p-6 mt-8">
        <div className="flex items-start gap-4">
          <AlertCircle size={24} className="text-amber-600 mt-1"/>
          <div>
            <h4 className="font-black text-amber-800 uppercase text-sm">Empresas para DAMA IA</h4>
            <p className="text-amber-700 text-sm mt-1">
              As empresas cadastradas aqui serao usadas na geracao de propostas comerciais do modulo DAMA IA. 
              Certifique-se de que CNPJ, Inscricao Estadual e endereco estejam corretos.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function EditForm({ editCompanyForm, setEditCompanyForm, cancelEditCompany, saveCompany }) {
  const fields = [
    { key: 'name', label: 'Razao Social', placeholder: 'Nome da Empresa', colSpan: false },
    { key: 'cnpj', label: 'CNPJ', placeholder: '00.000.000/0001-00', colSpan: false },
    { key: 'ie', label: 'Inscricao Estadual', placeholder: 'IE', colSpan: false },
    { key: 'email', label: 'Email', placeholder: 'email@empresa.com', type: 'email', colSpan: false },
    { key: 'address', label: 'Endereco Completo', placeholder: 'Rua, Numero, Bairro, Cidade - UF', colSpan: true },
    { key: 'phone', label: 'Telefone', placeholder: '(00) 0000-0000', colSpan: false },
    { key: 'whatsapp', label: 'WhatsApp', placeholder: '(00) 00000-0000', colSpan: false },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {fields.map(({ key, label, placeholder, type, colSpan }) => (
          <div key={key} className={colSpan ? 'md:col-span-2' : ''}>
            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">{label}</label>
            <input type={type || 'text'} className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl font-semibold focus:border-indigo-500 outline-none"
              value={editCompanyForm[key] || ''} onChange={(e) => setEditCompanyForm({...editCompanyForm, [key]: e.target.value})} placeholder={placeholder}/>
          </div>
        ))}
        <div className="md:col-span-2">
          <label className="block text-xs font-bold text-purple-600 uppercase mb-1 flex items-center gap-2">
            <FileDown size={14}/> Papel Timbrado (.docx) - Para DAMA IA
          </label>
          <div className="flex items-center gap-4">
            <label className="flex-grow border-2 border-dashed border-purple-200 bg-purple-50/50 px-4 py-3 rounded-xl text-center cursor-pointer hover:bg-purple-100 transition-all">
              <input type="file" accept=".docx" className="hidden"
                onChange={(e) => { const file = e.target.files?.[0]; if (file) setEditCompanyForm({...editCompanyForm, timbrado: file, timbradoNome: file.name}); }}/>
              <span className="font-semibold text-slate-600 flex items-center justify-center gap-2">
                <Upload size={18} className="text-purple-500"/> {editCompanyForm.timbradoNome || 'Clique para enviar template Word'}
              </span>
            </label>
            {editCompanyForm.timbradoNome && <CheckCircle size={24} className="text-emerald-500 flex-shrink-0"/>}
          </div>
          <p className="text-xs text-slate-400 mt-1">O documento deve conter a tag <code className="bg-slate-100 px-1 rounded">{'{{TEXTO_DAMA}}'}</code> onde a proposta sera inserida</p>
        </div>
      </div>
      <div className="flex gap-3 justify-end pt-2">
        <button onClick={cancelEditCompany} className="px-6 py-3 bg-slate-200 text-slate-700 rounded-xl font-bold text-sm hover:bg-slate-300">Cancelar</button>
        <button onClick={saveCompany} className="px-8 py-3 bg-emerald-600 text-white rounded-xl font-black text-sm uppercase hover:bg-emerald-700 flex items-center gap-2">
          <CheckCircle size={18}/> Salvar Empresa
        </button>
      </div>
    </div>
  );
}

function ViewCard({ company, idx, startEditCompany }) {
  return (
    <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
      <div className="flex items-center gap-4">
        <div className={`p-4 rounded-2xl ${company.name ? 'bg-indigo-100 text-indigo-600' : 'bg-slate-100 text-slate-400'}`}>
          <Building size={28}/>
        </div>
        <div>
          <h3 className="text-lg font-black text-slate-800 uppercase">{company.name || `Empresa ${idx + 1} (Vazio)`}</h3>
          <p className="text-sm text-slate-500 font-semibold">CNPJ: {company.cnpj || 'Nao cadastrado'} {company.ie && `| IE: ${company.ie}`}</p>
          {company.address && <p className="text-xs text-slate-400 mt-1">{company.address}</p>}
          {company.email && <p className="text-xs text-indigo-500 mt-1">{company.email}</p>}
          {company.timbradoNome ? (
            <p className="text-xs text-purple-600 mt-1 flex items-center gap-1"><CheckCircle size={12}/> Timbrado: {company.timbradoNome}</p>
          ) : company.name && (
            <p className="text-xs text-orange-500 mt-1 flex items-center gap-1"><AlertTriangle size={12}/> Sem papel timbrado cadastrado</p>
          )}
        </div>
      </div>
      <button onClick={() => startEditCompany(company)}
        className="bg-slate-800 text-white px-6 py-3 rounded-xl font-bold text-sm uppercase flex items-center gap-2 hover:bg-indigo-600 transition-colors">
        <PenTool size={16}/> Editar
      </button>
    </div>
  );
}
