import React, { useState, useEffect } from 'react';
import { 
  BarChart3, 
  FileSearch, 
  Sliders, 
  BookOpen, 
  History, 
  Server, 
  Wifi, 
  WifiOff
} from 'lucide-react';
import { api } from '../api';

interface NavigationSidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  apiBaseUrl: string;
  setApiBaseUrl: (url: string) => void;
}

export default function NavigationSidebar({
  activeTab,
  setActiveTab,
  apiBaseUrl,
  setApiBaseUrl
}: NavigationSidebarProps) {
  const [showConfigBase, setShowConfigBase] = useState(false);
  const [inputUrl, setInputUrl] = useState(apiBaseUrl);
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [checking, setChecking] = useState(false);

  // Checks backend connection
  const checkConnection = async () => {
    setChecking(true);
    try {
      // Test either health or root endpoint
      await api.getHealth();
      setIsOnline(true);
    } catch (e) {
      try {
        await api.getRoot();
        setIsOnline(true);
      } catch (innerErr) {
        setIsOnline(false);
      }
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    checkConnection();
    const interval = setInterval(checkConnection, 15000); // Poll every 15s to keep status accurate
    return () => clearInterval(interval);
  }, [apiBaseUrl]);

  const menuItems = [
    { id: 'dashboard', label: '🏠 Dashboard', icon: BarChart3, desc: 'Aperçu global des usines' },
    { id: 'analyze', label: '📄 Analyser Facture', icon: FileSearch, desc: 'Traitement automatique de PDF' },
    { id: 'config', label: '⚙️ Configuration', icon: Sliders, desc: 'Mappings clients et départements' },
    { id: 'reports', label: '📚 Rapports', icon: BookOpen, desc: 'Rapports budgétaires détaillés' },
    { id: 'history', label: '📈 Historique', icon: History, desc: 'Journaux et audit transactions' }
  ];

  const handleUrlSave = (e: React.FormEvent) => {
    e.preventDefault();
    setApiBaseUrl(inputUrl.trim());
    setShowConfigBase(false);
  };

  return (
    <aside className="w-80 bg-slate-900 text-slate-100 flex flex-col justify-between border-r border-slate-800 shrink-0 h-screen select-none sticky top-0 overflow-y-auto">
      <div className="p-6">
        {/* Yazaki Brand Header */}
        <div className="flex items-center gap-3 mb-8">
          <div className="h-10 w-10 bg-rose-600 rounded-lg flex items-center justify-center font-extrabold text-xl shadow-lg border border-rose-500 text-white select-none">
            Y
          </div>
          <div>
            <h1 className="font-sans font-bold text-lg tracking-tight select-none text-slate-100">YAZAKI IAM</h1>
            <p className="text-xs text-rose-400 font-mono tracking-wider font-bold">FACTURATIONS TELECOM</p>
          </div>
        </div>

        {/* Navigation Options */}
        <p className="text-slate-500 text-[10px] font-mono font-bold tracking-widest uppercase mb-4">MENU PRINCIPAL</p>
        <nav className="space-y-1.5">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                id={`nav-${item.id}`}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-start gap-3.5 p-3 rounded-xl transition-all duration-200 outline-none text-left border ${
                  isActive 
                    ? 'bg-rose-500/10 border-rose-500/30 text-rose-400 shadow-md shadow-rose-950/20' 
                    : 'bg-transparent border-transparent text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                }`}
              >
                <Icon className={`h-5 w-5 shrink-0 ${isActive ? 'text-rose-400' : 'text-slate-500'}`} />
                <div>
                  <div className="text-sm font-semibold">{item.label}</div>
                  <div className="text-[11px] opacity-75 mt-0.5 leading-normal">{item.desc}</div>
                </div>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="p-5 border-t border-slate-800 bg-slate-950/50 space-y-4">
        {/* Real-Time FastAPI Status Widget */}
        <div className="bg-slate-900/80 p-3.5 rounded-2xl border border-slate-800 shadow-inner">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1.5">
              <Server className="h-3.5 w-3.5 text-rose-500" />
              CONNEXION FASTAPI
            </span>
            <button 
              onClick={checkConnection}
              disabled={checking}
              className="text-[10px] text-slate-500 hover:text-rose-400 cursor-pointer animate-pulse font-mono focus:outline-none"
            >
              {checking ? 'Vérif...' : 'Actualiser'}
            </button>
          </div>

          <div className="flex items-center gap-2 p-2 rounded-xl bg-slate-950/80 border border-slate-800/60">
            {isOnline === null ? (
              <div className="h-2 w-2 rounded-full bg-slate-400 animate-ping shrink-0" />
            ) : isOnline ? (
              <Wifi className="h-4.5 w-4.5 text-emerald-400 shrink-0" />
            ) : (
              <WifiOff className="h-4.5 w-4.5 text-rose-500 shrink-0" />
            )}
            <div className="truncate">
              <div className="text-xs font-semibold">
                {isOnline === null ? 'Diagnostic en cours...' : isOnline ? 'Serveur FastAPI Connecté' : 'Serveur inaccessible'}
              </div>
              <p className="text-[10px] text-slate-500 font-mono truncate">
                {apiBaseUrl || 'Chemin relatif (Cloud Run)'}
              </p>
            </div>
          </div>
        </div>

        {/* Api Host Configuration */}
        <div className="p-3 bg-slate-900/40 rounded-xl border border-slate-800/80 text-xs">
          <div className="flex items-center justify-between mb-1 text-slate-400">
            <span className="flex items-center gap-1 font-semibold text-[10px] uppercase font-mono tracking-wider">
              Hôte de l'API
            </span>
            <button 
              onClick={() => {
                setShowConfigBase(!showConfigBase);
                setInputUrl(apiBaseUrl);
              }} 
              className="text-rose-400 hover:text-rose-300 font-mono text-[10px] underline focus:outline-none cursor-pointer"
            >
              {showConfigBase ? 'Fermer' : 'Modifier'}
            </button>
          </div>
          
          {!showConfigBase && (
            <div className="font-mono text-[11px] text-slate-300 truncate bg-slate-950 p-2 rounded border border-slate-800/40">
              {apiBaseUrl || '(Vide: Racine hôtelière)'}
            </div>
          )}

          {showConfigBase && (
            <form onSubmit={handleUrlSave} className="mt-2 space-y-2">
              <p className="text-[9px] text-slate-500 leading-tight">
                Saisissez l'URL de votre serveur FastAPI de développement (ex: <code className="text-rose-300">http://localhost:8000</code>). Laissez vide si hébergé ensemble.
              </p>
              <input 
                type="text" 
                value={inputUrl}
                onChange={(e) => setInputUrl(e.target.value)}
                placeholder="Ex: http://localhost:8000"
                className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-rose-500 font-mono"
              />
              <div className="flex justify-end gap-1.5 text-[10px]">
                <button 
                  type="button" 
                  onClick={() => setShowConfigBase(false)} 
                  className="px-2 py-1 rounded text-slate-400 hover:bg-slate-800 cursor-pointer"
                >
                  Annuler
                </button>
                <button 
                  type="submit" 
                  className="px-2.5 py-1 rounded bg-rose-600 text-white font-medium hover:bg-rose-500 cursor-pointer"
                >
                  Enregistrer
                </button>
              </div>
            </form>
          )}
        </div>

        <div className="text-center pt-2">
          <p className="text-[11px] font-sans text-slate-500">© 2026 YAZAKI Corporation</p>
          <p className="text-[10px] font-mono text-slate-600 mt-0.5">YAZAKI IAM Extractor v2.0</p>
        </div>
      </div>
    </aside>
  );
}
