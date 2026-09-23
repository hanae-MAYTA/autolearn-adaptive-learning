import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Brain, ChevronLeft, ChevronRight, CheckCircle, Clock,
  AlertCircle, RefreshCcw, XCircle, ArrowRight, Trophy,
  Target, BookOpen
} from 'lucide-react';
import { useFlaskData } from '../hooks/useFlaskData';
import { apiFetch } from '../utils/api';

export default function QuizPage() {
  const navigate = useNavigate();
  const { quizItems, savePartial, refresh } = useFlaskData();
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Results state
  const [quizResults, setQuizResults] = useState(null);   // assessment array from backend
  const [showResults, setShowResults] = useState(false);  // show results screen

  const loadQuiz = async (forceNew = false) => {
    setLoading(true);
    setError('');
    try {
      const data = await apiFetch(`/api/quiz${forceNew ? '?refresh=1' : ''}`);
      savePartial({ quizItems: data.quizItems });
      setAnswers({});
      setCurrentQ(0);
      setShowResults(false);
      setQuizResults(null);
    } catch (err) {
      setError(err.message || 'Unable to load quiz.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!quizItems?.length) loadQuiz(false);
  }, []);

  const total = quizItems?.length || 0;
  const progress = total ? (Object.keys(answers).length / total) * 100 : 0;
  const answeredAll = total > 0 && Object.keys(answers).length === total;

  const difficultyConfig = {
    beginner:     { label: 'Beginner',     color: '#4ade80', pct: 30 },
    intermediate: { label: 'Intermediate', color: '#fbbf24', pct: 60 },
    advanced:     { label: 'Advanced',     color: '#f87171', pct: 90 },
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!answeredAll) return;
    setSubmitted(true);
    setError('');
    try {
      const data = await apiFetch('/api/quiz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers }),
      });
      savePartial(data);
      await refresh();

      // Build per-question correctness from quizItems + answers + assessment
      const assessment = data.assessment || [];
      setQuizResults({ assessment, answers: { ...answers }, graded: data.graded || {} });
      setShowResults(true);
      setSubmitted(false);
    } catch (err) {
      setSubmitted(false);
      setError(err.message || 'Quiz submission failed.');
    }
  };

  // ─── LOADING ────────────────────────────────────────────────────────────────
  if (loading && !total) {
    return <div className="px-6 py-8 max-w-2xl mx-auto text-slate-300">Loading quiz...</div>;
  }

  // ─── NO QUIZ ────────────────────────────────────────────────────────────────
  if (!total) {
    return (
      <div className="px-6 py-8 max-w-2xl mx-auto">
        <div className="glass-card p-8 text-center space-y-4">
          <div className="text-white text-lg font-display">No quiz generated yet</div>
          <div className="text-slate-500 text-sm">Start with your syllabus first.</div>
          {error && <div className="text-red-400 text-sm">{error}</div>}
          <button onClick={() => navigate('/start')} className="btn-cyber-solid">Go to Start</button>
        </div>
      </div>
    );
  }

  // ─── SUBMITTING SPINNER ──────────────────────────────────────────────────────
  if (submitted) {
    return (
      <div className="px-6 py-8 max-w-2xl mx-auto text-center">
        <div className="glass-card p-10">
          <div className="w-20 h-20 rounded-full bg-cyan-400/10 border border-cyan-400/30 flex items-center justify-center mx-auto mb-6 animate-pulse">
            <Brain size={36} className="text-cyan-400" />
          </div>
          <h2 className="font-display font-bold text-2xl text-white mb-3">Calculating Results...</h2>
          <p className="text-slate-400">Analyzing your answers</p>
        </div>
      </div>
    );
  }

  // ─── RESULTS SCREEN ──────────────────────────────────────────────────────────
  if (showResults && quizResults) {
    const { assessment, answers: savedAnswers, graded } = quizResults;
    const avgScore = assessment.length
      ? Math.round(assessment.reduce((s, r) => s + r.score_pct, 0) / assessment.length)
      : 0;

    // Grading is done server-side (answers are not sent to the browser before submission).
    const questionResults = quizItems.map((q) => {
      const key = `${q.topic}_${q.index}`;
      const result = graded[key] || {};
      return {
        ...q,
        key,
        userAnswer: savedAnswers[key],
        isCorrect: Boolean(result.is_correct),
        answer: result.correct_option,
        explanation: result.explanation,
      };
    });

    const correctCount = questionResults.filter(r => r.isCorrect).length;
    const incorrectItems = questionResults.filter(r => !r.isCorrect);

    return (
      <div className="px-6 py-8 max-w-3xl mx-auto space-y-6">

        {/* ── Header ── */}
        <div className="text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-slate-400 text-xs font-mono mb-4">
            QUIZ COMPLETE · RESULTS
          </div>
          <h1 className="font-display font-bold text-3xl text-white mb-1">Your Quiz Results</h1>
          <p className="text-slate-400 text-sm">Review your answers and learn from your mistakes</p>
        </div>

        {/* ── Score Card ── */}
        <div className="glass-card p-6">
          <div className="flex items-center justify-around gap-4 flex-wrap">
            {/* Big Score */}
            <div className="text-center">
              <div
                className="font-display font-bold text-6xl mb-1"
                style={{ color: avgScore >= 75 ? '#4ade80' : avgScore >= 45 ? '#fbbf24' : '#f87171' }}
              >
                {avgScore}%
              </div>
              <div className="text-slate-400 text-sm">Overall Score</div>
            </div>

            {/* Correct / Incorrect */}
            <div className="flex gap-6">
              <div className="text-center">
                <div className="flex items-center gap-1.5 justify-center mb-1">
                  <CheckCircle size={18} className="text-green-400" />
                  <span className="font-display font-bold text-2xl text-green-400">{correctCount}</span>
                </div>
                <div className="text-slate-500 text-xs">Correct</div>
              </div>
              <div className="text-center">
                <div className="flex items-center gap-1.5 justify-center mb-1">
                  <XCircle size={18} className="text-red-400" />
                  <span className="font-display font-bold text-2xl text-red-400">{incorrectItems.length}</span>
                </div>
                <div className="text-slate-500 text-xs">Incorrect</div>
              </div>
              <div className="text-center">
                <div className="flex items-center gap-1.5 justify-center mb-1">
                  <Target size={18} className="text-purple-400" />
                  <span className="font-display font-bold text-2xl text-purple-400">{total}</span>
                </div>
                <div className="text-slate-500 text-xs">Total</div>
              </div>
            </div>
          </div>

          {/* Per-topic scores */}
          {assessment.length > 0 && (
            <div className="mt-5 pt-5 border-t border-white/10">
              <div className="text-xs text-slate-400 mb-3 font-mono uppercase tracking-wider">Score by Topic</div>
              <div className="space-y-2">
                {assessment.map((r) => (
                  <div key={r.topic} className="flex items-center gap-3">
                    <span className="text-slate-300 text-sm w-32 truncate capitalize">{r.topic}</span>
                    <div className="flex-1 difficulty-track">
                      <div
                        className="difficulty-fill transition-all"
                        style={{
                          width: `${r.score_pct}%`,
                          background: r.score_pct >= 75 ? '#4ade80' : r.score_pct >= 45 ? '#fbbf24' : '#f87171',
                        }}
                      />
                    </div>
                    <span
                      className="text-sm font-mono font-bold w-12 text-right"
                      style={{ color: r.score_pct >= 75 ? '#4ade80' : r.score_pct >= 45 ? '#fbbf24' : '#f87171' }}
                    >
                      {r.score_pct}%
                    </span>
                    <span className="text-xs text-slate-500 w-20">{r.predicted_level}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── All Questions Review ── */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <BookOpen size={16} className="text-cyan-400" />
            <h2 className="font-display font-semibold text-white text-lg">Question Review</h2>
          </div>

          <div className="space-y-4">
            {questionResults.map((q, idx) => (
              <div
                key={q.key}
                className="glass-card p-5"
                style={{
                  borderColor: q.isCorrect ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.2)',
                  borderWidth: 1,
                  borderStyle: 'solid',
                }}
              >
                {/* Question header */}
                <div className="flex items-start gap-3 mb-4">
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 font-mono text-sm font-bold"
                    style={{
                      background: q.isCorrect ? 'rgba(74,222,128,0.15)' : 'rgba(248,113,113,0.15)',
                      color: q.isCorrect ? '#4ade80' : '#f87171',
                    }}
                  >
                    {idx + 1}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className="px-2 py-0.5 rounded-full bg-purple-400/10 border border-purple-400/20 text-purple-400 text-xs font-mono uppercase">
                        {q.topic}
                      </span>
                      {q.isCorrect ? (
                        <span className="flex items-center gap-1 text-green-400 text-xs font-semibold">
                          <CheckCircle size={12} /> Correct
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-red-400 text-xs font-semibold">
                          <XCircle size={12} /> Incorrect
                        </span>
                      )}
                    </div>
                    <p className="text-white font-display font-semibold leading-snug">{q.q}</p>
                  </div>
                </div>

                {/* Options */}
                <div className="space-y-2 ml-11">
                  {q.options.map((opt, oi) => {
                    const isCorrectOpt = opt === q.answer;
                    const isUserChoice = opt === q.userAnswer;

                    let optStyle = 'border-white/10 text-slate-400';
                    if (isCorrectOpt) optStyle = 'border-green-400/50 bg-green-400/10 text-green-300';
                    else if (isUserChoice && !isCorrectOpt) optStyle = 'border-red-400/50 bg-red-400/10 text-red-300';

                    return (
                      <div
                        key={oi}
                        className={`flex items-center gap-3 px-4 py-2.5 rounded-lg border text-sm transition-all ${optStyle}`}
                      >
                        <span className="font-mono text-xs opacity-60">{String.fromCharCode(65 + oi)}.</span>
                        <span className="flex-1">{opt}</span>
                        {isCorrectOpt && <CheckCircle size={14} className="text-green-400 flex-shrink-0" />}
                        {isUserChoice && !isCorrectOpt && <XCircle size={14} className="text-red-400 flex-shrink-0" />}
                      </div>
                    );
                  })}
                </div>

                {/* Error explanation for wrong answers */}
                {!q.isCorrect && (
                  <div className="ml-11 mt-3 flex items-start gap-2 px-3 py-2.5 rounded-lg bg-amber-400/5 border border-amber-400/20">
                    <AlertCircle size={14} className="text-amber-400 flex-shrink-0 mt-0.5" />
                    <p className="text-amber-300 text-xs leading-relaxed">
                      <span className="font-semibold">Correct answer: </span>
                      <span className="text-white">{q.answer}</span>
                      {q.userAnswer
                        ? <span className="text-slate-400"> · You answered: <span className="text-red-300">{q.userAnswer}</span></span>
                        : <span className="text-slate-400"> · You did not answer this question.</span>
                      }
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* ── Action Buttons ── */}
        <div className="flex items-center justify-between gap-4 pt-2 pb-8">
          <button
            onClick={() => loadQuiz(true)}
            className="btn-cyber flex items-center gap-2"
          >
            <RefreshCcw size={14} /> Retry Quiz
          </button>
          <button
            onClick={() => navigate('/dashboard')}
            className="btn-cyber-solid flex items-center gap-2"
          >
            <Trophy size={15} /> Go to Dashboard <ArrowRight size={14} />
          </button>
        </div>
      </div>
    );
  }

  // ─── QUIZ FORM ───────────────────────────────────────────────────────────────
  return (
    <div className="px-6 py-8 max-w-3xl mx-auto">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-slate-400 text-xs font-mono mb-4">
            STEP 3 OF 4 · KNOWLEDGE ASSESSMENT
          </div>
          <h1 className="font-display font-bold text-2xl text-white">Adaptive Knowledge Quiz</h1>
          <p className="text-slate-400 text-sm mt-1">Unique questions are generated from your selected syllabus topics.</p>
        </div>
        <button type="button" onClick={() => loadQuiz(true)} className="btn-cyber flex items-center gap-2">
          <RefreshCcw size={14} /> New Quiz
        </button>
      </div>

      <div className="glass-card p-4 mb-6 flex items-center gap-6">
        <div className="flex-1">
          <div className="flex items-center justify-between text-xs mb-2">
            <span className="text-slate-400">Overall Progress</span>
            <span className="text-cyan-400 font-mono font-medium">{Object.keys(answers).length}/{total}</span>
          </div>
          <div className="difficulty-track">
            <div
              className="difficulty-fill bg-gradient-to-r from-cyan-400 to-purple-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
        <div className="text-center">
          <div className="font-display font-bold text-white text-2xl">{currentQ + 1}</div>
          <div className="text-slate-500 text-xs">of {total}</div>
        </div>
        <div className="flex items-center gap-1.5 text-slate-400 text-xs">
          <Clock size={12} />
          <span>~{Math.ceil(total * 1.5)} min</span>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        {quizItems.map((q, idx) => {
          const qKey = `${q.topic}_${q.index}`;
          return (
            <div key={qKey} style={{ display: idx === currentQ ? 'block' : 'none' }}>
              <div className="glass-card p-6 mb-4">
                <div className="flex items-center justify-between mb-4">
                  <span className="px-3 py-1 rounded-full bg-purple-400/10 border border-purple-400/20 text-purple-400 text-xs font-semibold font-mono uppercase tracking-wider">
                    {q.topic}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">Difficulty</span>
                    <div className="flex items-center gap-1.5">
                      <div className="w-20 difficulty-track">
                        <div
                          className="difficulty-fill"
                          style={{
                            width: `${difficultyConfig[q.difficulty || 'beginner'].pct}%`,
                            background: difficultyConfig[q.difficulty || 'beginner'].color,
                          }}
                        />
                      </div>
                      <span className="text-xs font-medium" style={{ color: difficultyConfig[q.difficulty || 'beginner'].color }}>
                        {difficultyConfig[q.difficulty || 'beginner'].label}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex gap-3 mb-5">
                  <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center flex-shrink-0 font-mono text-sm font-bold text-white">
                    {idx + 1}
                  </div>
                  <h2 className="font-display font-semibold text-white text-lg leading-snug">{q.q}</h2>
                </div>

                <div className="space-y-3">
                  {q.options.map((opt, oi) => (
                    <div key={oi} className="quiz-option">
                      <input
                        type="radio"
                        name={qKey}
                        value={opt}
                        id={`${qKey}_${oi}`}
                        checked={answers[qKey] === opt}
                        onChange={() => setAnswers(a => ({ ...a, [qKey]: opt }))}
                      />
                      <label htmlFor={`${qKey}_${oi}`}>
                        <div className="radio-dot">
                          {answers[qKey] === opt && <div className="w-2 h-2 rounded-full bg-dark-300" />}
                        </div>
                        <span className="font-mono text-xs text-slate-500 mr-1">{String.fromCharCode(65 + oi)}.</span>
                        {opt}
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        })}

        {error && <div className="mb-3 text-red-400 text-sm">{error}</div>}

        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setCurrentQ(q => Math.max(0, q - 1))}
            disabled={currentQ === 0}
            className="btn-cyber flex items-center gap-2 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronLeft size={16} />Previous
          </button>

          <div className="flex gap-1.5">
            {quizItems.map((q, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setCurrentQ(i)}
                className={`w-2 h-2 rounded-full transition-all ${
                  i === currentQ ? 'w-6 bg-cyan-400' :
                  answers[`${q.topic}_${q.index}`] ? 'bg-green-400/70' : 'bg-white/20'
                }`}
              />
            ))}
          </div>

          {currentQ < total - 1 ? (
            <button
              type="button"
              onClick={() => setCurrentQ(q => q + 1)}
              className="btn-cyber flex items-center gap-2"
            >
              Next<ChevronRight size={16} />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!answeredAll}
              className={`btn-cyber-solid flex items-center gap-2 ${!answeredAll ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <Brain size={15} />Submit Quiz
            </button>
          )}
        </div>

        {!answeredAll && currentQ === total - 1 && (
          <div className="mt-3 flex items-center gap-2 text-yellow-400 text-xs justify-center">
            <AlertCircle size={12} />
            <span>{total - Object.keys(answers).length} question(s) unanswered. Please answer all to submit.</span>
          </div>
        )}
      </form>
    </div>
  );
}