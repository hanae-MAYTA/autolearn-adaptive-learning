import { useCallback, useEffect, useMemo, useState } from 'react';
import { mockChatHistory } from '../utils/mockData';
import { apiFetch } from '../utils/api';

const STORAGE_KEY = 'autolearn_context_v2';
const STUDENT_ID_KEY = 'student_id';

const fallbackState = {
  assessment: [],
  profile: null,
  modelScores: [],
  dataInfo: { rows: 0, real_data_used: false },
  learningPath: [],
  resources: [],
  quizItems: [],
  modernFeatures: [],
  modelName: '',
  automlEngine: '',
  youtubeLive: false,
  notifications: [],
  learningScore: 0,
  pathProgress: {},
  accuracyTrend: [],
};

function loadStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

// === SYNCHRONISATION STUDENT ID CROSS-SESSION ===
async function syncStudentId() {
  const storedId = localStorage.getItem(STUDENT_ID_KEY);

  if (storedId) {
    // Restaurer l'ID existant dans le backend
    try {
      await apiFetch('/api/student/id', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: storedId }),
      });
    } catch (e) {
      console.warn('Failed to restore student_id:', e);
    }
  } else {
    // Récupérer un nouvel ID et le stocker
    try {
      const data = await apiFetch('/api/student/id');
      if (data.ok && data.student_id) {
        localStorage.setItem(STUDENT_ID_KEY, data.student_id);
      }
    } catch (e) {
      console.warn('Failed to get student_id:', e);
    }
  }
}

export function useFlaskData() {
  const [state, setState] = useState({ ...fallbackState, ...loadStored() });
  const [loading, setLoading] = useState(false);
  const [studentIdReady, setStudentIdReady] = useState(false);

  // 1. Synchroniser le student_id au montage (avant tout appel API)
  useEffect(() => {
    syncStudentId().then(() => setStudentIdReady(true));
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch('/api/context');
      setState(prev => {
        const next = { ...prev, ...data };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        return next;
      });
      return data;
    } catch {
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // 2. Charger les données SEULEMENT après que student_id soit synchronisé
  useEffect(() => {
    if (studentIdReady) {
      refresh();
    }
  }, [studentIdReady, refresh]);

  const savePartial = useCallback((partial) => {
    setState(prev => {
      const next = { ...prev, ...partial };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  // 3. Fonction pour forcer un nouveau quiz avec l'ID étudiant
  const refreshQuiz = useCallback(async () => {
    setLoading(true);
    try {
      const studentId = localStorage.getItem(STUDENT_ID_KEY);
      const data = await apiFetch(`/api/quiz?refresh=1${studentId ? `&student_id=${studentId}` : ''}`);
      if (data.ok) {
        setState(prev => {
          const next = { ...prev, quizItems: data.quizItems };
          localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
          return next;
        });
      }
      return data;
    } catch {
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // 4. Fonction pour soumettre le quiz avec l'ID étudiant
  const submitQuiz = useCallback(async (answers) => {
    setLoading(true);
    try {
      const studentId = localStorage.getItem(STUDENT_ID_KEY);
      const data = await apiFetch('/api/quiz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          answers,
          student_id: studentId // Envoyer l'ID pour cohérence
        }),
      });
      if (data.ok) {
        setState(prev => {
          const next = { ...prev, ...data };
          localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
          return next;
        });
      }
      return data;
    } catch {
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return useMemo(() => {
    const avgScore = state.assessment.length
      ? Math.round((state.assessment.reduce((s, r) => s + r.score_pct, 0) / state.assessment.length) * 10) / 10
      : 0;
    const strengths = state.assessment.filter(r => r.score_pct >= 75).map(r => r.topic);
    const weakTopics = state.assessment.filter(r => r.score_pct < 45).map(r => r.topic);
    // Real data now comes from the backend (/api/context -> accuracyTrend, built
    // from actual quiz-answer history). Empty array = no quiz history yet, which
    // the chart should render as an honest empty state rather than fake data.
    const accuracyTrend = state.accuracyTrend || [];
    const topicMastery = state.assessment.map(r => ({
      topic: r.topic.length > 8 ? r.topic.slice(0, 8) + '.' : r.topic,
      mastery: r.score_pct,
    }));
    return {
      ...state,
      avgScore,
      strengths,
      weakTopics,
      accuracyTrend,
      topicMastery,
      chatHistory: mockChatHistory,
      loading,
      refresh,
      refreshQuiz,      // Nouveau: pour forcer un nouveau quiz
      submitQuiz,       // Nouveau: pour soumettre avec l'ID
      savePartial,
      studentId: localStorage.getItem(STUDENT_ID_KEY),
    };
  }, [state, loading, refresh, refreshQuiz, submitQuiz, savePartial]);
}