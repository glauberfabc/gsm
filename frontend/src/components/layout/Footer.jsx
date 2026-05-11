import React from 'react';
import { BriefcaseBusiness } from 'lucide-react';

export function Footer() {
  return (
    <footer className="p-10 bg-white border-t-2 border-slate-200 mt-auto">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
        <div className="flex items-center gap-6">
          <div className="rounded-xl overflow-hidden">
            <img src="https://customer-assets.emergentagent.com/job_edital-seeker/artifacts/m5l6jiyo_LOGO-2-2048x828.png" alt="Grupo Smart Medical" className="h-12 w-auto" />
          </div>
        </div>
        <span className="flex items-center gap-4 text-blue-600 bg-blue-50 px-8 py-4 rounded-full border-2 border-blue-100 font-black tracking-wider uppercase">
          <BriefcaseBusiness size={24}/> v73.1 - Sistema Proprietario GSM
        </span>
      </div>
    </footer>
  );
}
