import React from 'react';

export function HighlightText({ text, highlight }) {
  if (!text) return '';
  if (!highlight || !highlight.trim()) return text;

  try {
    const textStr = String(text);
    const highlightLower = highlight.trim().toLowerCase();

    const stopWords = ['de', 'do', 'da', 'dos', 'das', 'para', 'com', 'sem', 'por', 'sol', 'inj'];
    const todasPalavras = highlightLower.split(/\s+/).filter(t => t.length >= 3);
    const palavrasChave = todasPalavras.filter(t => !stopWords.includes(t));
    const palavraPrincipal = palavrasChave[0] || todasPalavras[0] || '';

    if (!palavraPrincipal) return text;

    const escapedAll = todasPalavras.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const regex = new RegExp(`(${escapedAll.join('|')})`, 'gi');

    const parts = textStr.split(regex);
    if (parts.length === 1) return text;

    return (
      <span>
        {parts.map((part, i) => {
          if (!part) return null;
          const partLower = part.toLowerCase();
          const isMatch = todasPalavras.some(t => partLower === t);

          if (isMatch) {
            const isPrincipal = partLower === palavraPrincipal || palavrasChave.includes(partLower);
            if (isPrincipal) {
              return <mark key={`hl-${i}`} className="bg-yellow-300 px-0.5 font-black text-slate-900">{part}</mark>;
            }
            return <mark key={`hl-${i}`} className="bg-blue-100 px-0.5 font-semibold text-blue-800">{part}</mark>;
          }
          return <span key={`txt-${i}`}>{part}</span>;
        })}
      </span>
    );
  } catch (e) {
    console.error('Erro no highlight:', e);
    return text;
  }
}
