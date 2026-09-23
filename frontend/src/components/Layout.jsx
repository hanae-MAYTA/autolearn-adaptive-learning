import React from 'react';
import { Outlet, Link, NavLink, useNavigate } from 'react-router-dom';
import { Brain, RotateCcw } from 'lucide-react';
import { apiFetch } from '../utils/api';

export default function Layout() {
  const navigate = useNavigate();

  const resetAll = async () => {
    await apiFetch('/api/reset', { method: 'POST' });
    sessionStorage.clear();
    navigate('/');
    window.location.reload();
  };

  return (
    <div className="min-h-screen text-white">
      <header className="sticky top-0 z-40 backdrop-blur-xl border-b border-white/10 bg-slate-950/70">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-4">
          <Link to="/" className="flex items-center gap-3 font-display font-bold text-lg"><Brain className="text-cyan-400" size={22} />AutoLearn</Link>
          <nav className="hidden md:flex items-center gap-4 text-sm">
            <NavLink to="/goals">Goals</NavLink>
            <NavLink to="/start">Start</NavLink>
            <NavLink to="/quiz">Quiz</NavLink>
            <NavLink to="/dashboard">Dashboard</NavLink>
            <NavLink to="/path">Path</NavLink>
            <NavLink to="/resources">Resources</NavLink>
            <NavLink to="/tutor">Tutor</NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <button className="btn-cyber" onClick={resetAll}><RotateCcw size={14} /></button>
          </div>
        </div>
      </header>
      <main><Outlet /></main>
    </div>
  );
}