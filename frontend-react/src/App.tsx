import { useState, useCallback } from 'react';
import { Sidebar } from './components/Sidebar';
import { InputView } from './components/InputView';
import { ProcessingView } from './components/ProcessingView';
import { ResultsView } from './components/ResultsView';

type ViewState = 'input' | 'processing' | 'results' | 'error';

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [view, setView] = useState<ViewState>('input');
  const [errorStatus, setErrorStatus] = useState('');
  const [preferences, setPreferences] = useState({
    cloud_provider: 'all',
    max_debate_rounds: 3,
    detail_level: 'detailed',
  });

  const handleSessionCreated = useCallback((id: string) => {
    setSessionId(id);
    setView('processing');
  }, []);

  const handleComplete = useCallback(() => {
    setView('results');
  }, []);

  const handleError = useCallback((status: string) => {
    setErrorStatus(status);
    setView('error');
  }, []);

  const handleNewSession = useCallback(() => {
    setSessionId(null);
    setView('input');
    setErrorStatus('');
  }, []);

  const handleSelectSession = useCallback((id: string) => {
    setSessionId(id);
    setView('results');
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar
        currentSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        preferences={preferences}
        onPreferencesChange={setPreferences}
      />

      <main className="flex-1 overflow-hidden flex flex-col">
        {view === 'input' && (
          <div className="flex-1 overflow-y-auto">
            <InputView onSessionCreated={handleSessionCreated} preferences={preferences} />
          </div>
        )}

        {view === 'processing' && sessionId && (
          <ProcessingView
            sessionId={sessionId}
            onComplete={handleComplete}
            onError={handleError}
          />
        )}

        {view === 'results' && sessionId && (
          <div className="flex-1 overflow-y-auto">
            <ResultsView sessionId={sessionId} />
          </div>
        )}

        {view === 'error' && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <span className="text-4xl block mb-4">{errorStatus === 'cancelled' ? '⏹️' : '❌'}</span>
              <h2 className="text-xl font-bold text-slate-900 mb-2">
                Session {errorStatus === 'cancelled' ? 'Cancelled' : 'Failed'}
              </h2>
              <p className="text-slate-500 mb-6">
                Session <code className="bg-slate-100 px-2 py-0.5 rounded text-sm">{sessionId}</code> ended
                with status: <strong>{errorStatus}</strong>
              </p>
              <button
                onClick={handleNewSession}
                className="px-6 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-500 transition-colors"
              >
                🔄 Start New Session
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
