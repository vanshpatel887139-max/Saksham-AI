import { useState, useRef, useEffect } from 'react';
import { useApp, useI18n } from '../store/AppContext';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { Bot, X, Send, Sparkles } from 'lucide-react';

const SUGGESTIONS = [
  'Which courses do I need?',
  'Create a study plan for me',
  'How do I prepare for interviews?',
  'Explain CPI and inflation',
];

export default function AssistantWidget() {
  const { chatMessages, sendAssistantMessage, language } = useApp();
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, typing, open]);

  const send = async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg) return;
    setInput('');
    setTyping(true);
    await sendAssistantMessage(msg);
    setTyping(false);
  };

  return (
    <>
      {/* floating launcher */}
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-saffron-500 hover:bg-saffron-600 text-white shadow-lg shadow-saffron-500/30 flex items-center justify-center z-40 transition-transform hover:scale-105 cursor-pointer"
          title={t('AI Assistant', 'AI सहायक')}
        >
          <Sparkles size={22} />
        </button>
      ) : (
        <div className="fixed bottom-6 right-6 w-96 max-w-[calc(100vw-2rem)] h-[540px] max-h-[calc(100vh-2rem)] bg-white rounded-2xl shadow-2xl border border-navy-200 flex flex-col z-40 overflow-hidden">
          <div className="bg-gradient-to-r from-navy-800 to-navy-900 px-4 py-3 flex items-center gap-3 text-white">
            <div className="w-9 h-9 rounded-full bg-saffron-500 flex items-center justify-center"><Bot size={18} /></div>
            <div className="flex-1">
              <p className="text-sm font-semibold">{t('SakshamAI Assistant', 'सक्षम एआई सहायक')}</p>
              <p className="text-[10px] text-navy-300">{language === 'hi' ? 'ऑनलाइन • प्रश्न पूछें' : 'Online • Ask me anything'}</p>
            </div>
            <button onClick={() => setOpen(false)} className="p-1 hover:bg-navy-700 rounded cursor-pointer"><X size={16} /></button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-navy-50/50">
            {chatMessages.length === 0 && (
              <div className="bg-white rounded-xl p-4 border border-navy-100 text-xs text-navy-600">
                <p className="font-medium text-navy-800 mb-1">
                  {t('Respected Officer — welcome to SakshamAI, the Karmayogi skill assistant for the official statistical system.', 'माननीय अधिकारी — साक्षमएआई में आपका स्वागत है, आधिकारिक सांख्यिकी प्रणाली के लिए कर्मयोगी कौशल सहायक।')}
                </p>
                <p className="mt-1">{t('I can assist with skill gap analysis, course recommendations on iGOT Karmayogi & NSSTA, study plans, interview preparation and statistics concepts.', 'मैं कौशल अंतर विश्लेषण, आईगॉट कर्मयोगी और एनएसएसटीए कोर्स अनुशंसा, अध्ययन योजना, साक्षात्कार तैयारी और सांख्यिकी अवधारणाओं में सहायता कर सकता हूं।')}</p>
              </div>
            )}
            {chatMessages.map(m => (
              <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] px-3 py-2 rounded-2xl ${
                  m.role === 'user' ? 'bg-saffron-500 text-white rounded-br-sm' : 'bg-white border border-navy-100 rounded-bl-sm text-navy-700 chat-md'
                }`}>
                  {m.role === 'assistant' && (
                    <span className={`inline-flex items-center gap-1 mb-1 mr-1.5 px-1.5 py-0.5 rounded-full text-[9px] font-semibold uppercase ${
                      m.source === 'llm' ? 'bg-green-100 text-green-700' : 'bg-navy-100 text-navy-500'
                    }`}>
                      <Sparkles size={9} /> {m.source === 'llm' ? 'AI' : 'KB'}
                    </span>
                  )}
                  {m.role === 'user' ? m.content : (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkBreaks]}
                      components={{ p: ({ children }) => <p className="my-1 first:mt-0 last:mb-0">{children}</p> }}
                    >
                      {m.content.replace(/<br\s*\/?>/gi, '\n')}
                    </ReactMarkdown>
                  )}
                </div>
              </div>
            ))}
            {typing && (
              <div className="flex justify-start">
                <div className="bg-white border border-navy-100 px-3 py-2 rounded-2xl rounded-bl-sm">
                  <span className="inline-flex gap-1">
                    <span className="w-1.5 h-1.5 bg-navy-300 rounded-full animate-bounce" />
                    <span className="w-1.5 h-1.5 bg-navy-300 rounded-full animate-bounce [animation-delay:0.1s]" />
                    <span className="w-1.5 h-1.5 bg-navy-300 rounded-full animate-bounce [animation-delay:0.2s]" />
                  </span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="px-3 pt-2 pb-1 flex flex-wrap gap-1.5 border-t border-navy-100">
            {SUGGESTIONS.map(s => (
              <button key={s} onClick={() => send(s)} className="px-2.5 py-1 bg-navy-50 text-navy-600 rounded-full text-[10px] hover:bg-saffron-50 hover:text-saffron-700 cursor-pointer">
                {s}
              </button>
            ))}
          </div>

          <div className="p-3 border-t border-navy-100 flex items-center gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send()}
              placeholder={t('Ask about skill gaps, courses, study plans…', 'स्किल गैप, कोर्स, अध्ययन योजना के बारे में पूछें…')}
              className="flex-1 px-3 py-2 border border-navy-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-saffron-400"
            />
            <button onClick={() => send()} className="w-9 h-9 rounded-xl bg-navy-700 text-white flex items-center justify-center hover:bg-navy-800 cursor-pointer">
              <Send size={16} />
            </button>
          </div>
        </div>
      )}
    </>
  );
}