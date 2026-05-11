import { useState, useEffect } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const DEFAULT_COMPANIES = [
  { id: 'c1', name: 'HC IMPORTACOES EXPORTACOES LTDA', cnpj: '31.958.700/0001-17', ie: '084.050.99-3', address: 'Rua Domingos Dadalto, 127, Galpao 03, Rio Branco, Cariacica - ES', phone: '(11) 3164-4607', whatsapp: '(11) 99989-2696', email: 'claudio@gruposmartmedical.com.br', timbrado: null, timbradoNome: 'HC.docx' },
  { id: 'c2', name: 'Smart Medical - Matriz SP', cnpj: '11.111.111/0001-11', ie: '', address: '', phone: '', whatsapp: '', email: '', timbrado: null, timbradoNome: '' },
  { id: 'c3', name: 'Smart Medical - Filial SC', cnpj: '22.222.222/0001-22', ie: '', address: '', phone: '', whatsapp: '', email: '', timbrado: null, timbradoNome: '' },
  { id: 'c4', name: 'GSM Distribuidora Eireli', cnpj: '33.333.333/0001-33', ie: '', address: '', phone: '', whatsapp: '', email: '', timbrado: null, timbradoNome: '' },
  ...Array.from({length: 6}, (_, i) => ({ id: `c${i+5}`, name: '', cnpj: '', ie: '', address: '', phone: '', whatsapp: '', email: '', timbrado: null, timbradoNome: '' }))
];

export function useCompanies() {
  const [companies, setCompanies] = useState(DEFAULT_COMPANIES);
  const [editingCompanyId, setEditingCompanyId] = useState(null);
  const [editCompanyForm, setEditCompanyForm] = useState({});
  const [showEmpresaModal, setShowEmpresaModal] = useState(false);

  useEffect(() => {
    axios.get(`${API}/empresas`).then(res => {
      const empresasDB = res.data.empresas || [];
      if (empresasDB.length > 0) {
        const merged = empresasDB.map(emp => ({
          ...emp,
          timbrado: null,
          timbradoNome: emp.timbrado_nome || ''
        }));
        for (let i = empresasDB.length; i < 10; i++) {
          merged.push({ id: `c${i+1}`, name: '', cnpj: '', ie: '', address: '', phone: '', whatsapp: '', email: '', timbrado: null, timbradoNome: '' });
        }
        setCompanies(merged.slice(0, 10));
      }
    }).catch(() => {});
  }, []);

  const startEditCompany = (company) => {
    setEditingCompanyId(company.id);
    setEditCompanyForm({ ...company });
  };

  const cancelEditCompany = () => {
    setEditingCompanyId(null);
    setEditCompanyForm({});
  };

  const saveCompany = async () => {
    const companyToSave = { ...editCompanyForm };
    const timbradoFile = companyToSave.timbrado;
    const timbradoRemovido = companyToSave.timbradoRemovido;

    setCompanies(prev => prev.map(c =>
      c.id === editingCompanyId ? {
        ...companyToSave,
        timbradoNome: timbradoRemovido ? '' : (timbradoFile?.name || companyToSave.timbradoNome)
      } : c
    ));

    try {
      const empresaData = {
        id: companyToSave.id,
        name: companyToSave.name || '',
        cnpj: companyToSave.cnpj || '',
        ie: companyToSave.ie || '',
        address: companyToSave.address || '',
        phone: companyToSave.phone || '',
        whatsapp: companyToSave.whatsapp || '',
        email: companyToSave.email || ''
      };

      await axios.post(`${API}/empresas/salvar`, empresaData);

      if (timbradoRemovido) {
        try {
          await axios.delete(`${API}/empresas/${companyToSave.id}/timbrado`);
          setCompanies(prev => prev.map(c =>
            c.id === editingCompanyId ? { ...c, timbrado: null, timbradoNome: '' } : c
          ));
        } catch (e) {
          console.error('Erro ao excluir timbrado:', e);
        }
      } else if (timbradoFile instanceof File) {
        const formData = new FormData();
        formData.append('timbrado', timbradoFile);

        await axios.post(`${API}/empresas/${companyToSave.id}/timbrado`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });

        setCompanies(prev => prev.map(c =>
          c.id === editingCompanyId ? { ...c, timbradoNome: timbradoFile.name } : c
        ));
      }

      alert('Empresa salva com sucesso!');
    } catch (err) {
      console.error('Erro ao salvar empresa:', err);
      alert('Erro ao salvar no servidor. Dados mantidos localmente.');
    }

    setEditingCompanyId(null);
    setEditCompanyForm({});
  };

  return {
    companies, setCompanies,
    editingCompanyId, setEditingCompanyId,
    editCompanyForm, setEditCompanyForm,
    showEmpresaModal, setShowEmpresaModal,
    startEditCompany, cancelEditCompany, saveCompany,
  };
}
