import React, { useState, useEffect } from 'react';
import { 
  Map, Play, Lock, CheckCircle, ChevronRight, ExternalLink, 
  BookOpen, Video, Layers, Clock, Award, TrendingUp, 
  BookMarked, GraduationCap, Target, BarChart3, CirclePlay,
  AlertCircle, X, Eye, RotateCcw, Star, Sparkles, Zap,
  ArrowRight, PlayCircle, LockKeyhole, BookText
} from 'lucide-react';
import { useFlaskData } from '../hooks/useFlaskData';
import { apiFetch } from '../utils/api';
import VideoPlayerModal from '../components/VideoPlayerModal';

// ─── THEME COLORS (Matching AutoLearn dark theme) ───────
const THEME = {
  bg: '#0b1121',           // Deep dark background
  card: '#151e32',         // Card background
  cardHover: '#1a2542',    // Card hover
  border: 'rgba(255,255,255,0.08)',  // Borders
  borderHover: 'rgba(255,255,255,0.15)',
  text: '#e2e8f0',         // Primary text
  textMuted: '#94a3b8',    // Muted text
  textDark: '#64748b',     // Very muted
  cyan: '#06b6d4',         // Cyan accent
  cyanGlow: 'rgba(6,182,212,0.15)',
  violet: '#8b5cf6',       // Violet accent
  violetGlow: 'rgba(139,92,246,0.15)',
  emerald: '#10b98163',      // Success
  emeraldGlow: 'rgba(16,185,129,0.15)',
  amber: '#f59e0b',        // Warning/in-progress
  amberGlow: 'rgba(245,158,11,0.15)',
  red: '#ef4444',          // Error
  gradient: 'linear-gradient(135deg, #06b6d4 0%, #8b5cf6 100%)',
};

// ─── STATUS CONFIG ───────────────────────────────────────
const STATUS_CONFIG = {
  completed:    { 
    icon: CheckCircle, 
    color: THEME.emerald, 
    bg: THEME.emeraldGlow, 
    border: 'rgba(16,185,129,0.3)',
    label: 'Completed',
    glow: 'shadow-[0_0_20px_rgba(16,185,129,0.2]'
  },
  'in-progress':{ 
    icon: Clock, 
    color: THEME.amber, 
    bg: THEME.amberGlow, 
    border: 'rgba(245,158,11,0.3)',
    label: 'In Progress',
    glow: 'shadow-[0_0_20px_rgba(245,158,11,0.2]'
  },
  recommended:  { 
    icon: CirclePlay, 
    color: THEME.cyan, 
    bg: THEME.cyanGlow, 
    border: 'rgba(6,182,212,0.3)',
    label: 'Ready to Start',
    glow: 'shadow-[0_0_20px_rgba(6,182,212,0.2]'
  },
  locked:       { 
    icon: LockKeyhole, 
    color: '#475569', 
    bg: 'rgba(71,85,105,0.08)', 
    border: 'rgba(71,85,105,0.2)',
    label: 'Locked',
    glow: ''
  },
};

const LEVEL_CONFIG = {
  beginner:     { color: '#4ade80', label: 'Beginner',    icon: BookOpen },
  intermediate: { color: '#fbbf24', label: 'Intermediate', icon: TrendingUp },
  advanced:     { color: '#f87171', label: 'Advanced',    icon: Award },
};

const VIDEO_STATUS = {
  completed:    { color: THEME.emerald, bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', icon: CheckCircle },
  'in-progress':{ color: THEME.amber,   bg: 'bg-amber-500/10',   border: 'border-amber-500/20',   icon: Clock },
  new:          { color: THEME.cyan,    bg: 'bg-cyan-500/10',    border: 'border-cyan-500/20',    icon: PlayCircle },
};

// ─── SUB-COMPONENTS ─────────────────────────────────────

function StatCard({ icon: Icon, label, value, subtext, color, glow }) {
  return (
    <div className="relative group">
      <div 
        className="relative rounded-2xl border p-5 transition-all duration-300 hover:scale-[1.02]"
        style={{ 
          background: THEME.card,
          borderColor: THEME.border,
        }}
      >
        {/* Glow effect on hover */}
        <div 
          className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 -z-10 blur-xl"
          style={{ background: glow }}
        />
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider" style={{ color: THEME.textDark }}>{label}</p>
            <p className="text-2xl font-bold mt-1" style={{ color: THEME.text }}>{value}</p>
            {subtext && <p className="text-xs mt-1" style={{ color: THEME.textMuted }}>{subtext}</p>}
          </div>
          <div 
            className="p-2.5 rounded-xl"
            style={{ background: `${color}15` }}
          >
            <Icon size={20} style={{ color }} />
          </div>
        </div>
      </div>
    </div>
  );
}

function ProgressBar({ current, total, percentage }) {
  return (
    <div 
      className="rounded-2xl border p-5"
      style={{ 
        background: THEME.card,
        borderColor: THEME.border,
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Target size={16} style={{ color: THEME.cyan }} />
          <span className="text-sm font-semibold" style={{ color: THEME.text }}>Overall Progress</span>
        </div>
        <span className="text-sm font-bold font-mono" style={{ color: THEME.cyan }}>{percentage}%</span>
      </div>
      <div className="w-full h-2.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.05)' }}>
        <div 
          className="h-full rounded-full transition-all duration-700 ease-out relative"
          style={{ 
            width: `${percentage}%`,
            background: percentage >= 80 
              ? `linear-gradient(90deg, ${THEME.emerald}, #34d399af)` 
              : percentage >= 50 
                ? `linear-gradient(90deg, ${THEME.cyan}, #67e8f9)`
                : `linear-gradient(90deg, ${THEME.amber}, #fbbf24)`
          }}
        >
          <div className="absolute inset-0 bg-white/20 animate-pulse" />
        </div>
      </div>
      <div className="flex justify-between mt-2">
        <span className="text-xs" style={{ color: THEME.textDark }}>{current} of {total} topics completed</span>
        <span className="text-xs font-medium" style={{ color: percentage >= 80 ? THEME.emerald : percentage >= 50 ? THEME.cyan : THEME.amber }}>
          {percentage >= 80 ? ' Excellent!' : percentage >= 50 ? ' Keep going!' : ' Just started'}
        </span>
      </div>
    </div>
  );
}

function TopicNode({ node, isSelected, onSelect }) {
  const cfg = STATUS_CONFIG[node.status] || STATUS_CONFIG.locked;
  const levelCfg = LEVEL_CONFIG[node.level] || LEVEL_CONFIG.beginner;
  const StatusIcon = cfg.icon;
  const LevelIcon = levelCfg.icon;
  const isLocked = node.status === 'locked';
  
  return (
    <button
      onClick={() => !isLocked && onSelect(node)}
      disabled={isLocked}
      className={`relative w-full text-left rounded-xl border transition-all duration-300 group ${
        isSelected 
          ? 'scale-[1.02]' 
          : isLocked
            ? 'opacity-50 cursor-not-allowed'
            : 'hover:scale-[1.01]'
      }`}
      style={{ 
        background: isSelected ? `${THEME.cyan}08` : THEME.card,
        borderColor: isSelected ? `${THEME.cyan}40` : isLocked ? 'rgba(255,255,255,0.05)' : THEME.border,
        boxShadow: isSelected ? `0 0 30px ${THEME.cyanGlow}` : 'none',
      }}
    >
      {/* Left accent stripe */}
      <div 
        className="absolute left-0 top-3 bottom-3 w-1 rounded-full"
        style={{ background: cfg.color, opacity: isSelected ? 1 : 0.6 }}
      />
      
      <div className="p-4 pl-5">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5">
              <span 
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider border"
                style={{ 
                  color: levelCfg.color, 
                  background: `${levelCfg.color}10`,
                  borderColor: `${levelCfg.color}25`
                }}
              >
                <LevelIcon size={10} />
                {levelCfg.label}
              </span>
              <span 
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider"
                style={{ 
                  color: cfg.color,
                  background: cfg.bg,
                  border: `1px solid ${cfg.border}`,
                }}
              >
                <StatusIcon size={10} />
                {cfg.label}
              </span>
            </div>
            <h3 className={`font-semibold text-sm truncate ${
              isSelected ? 'text-white' : isLocked ? 'text-slate-500' : 'text-slate-200'
            }`}>
              {node.topic}
            </h3>
            {node.prerequisites?.length > 0 && (
              <p className="text-[10px] mt-0.5 truncate" style={{ color: THEME.textDark }}>
                Requires: {node.prerequisites.join(', ')}
              </p>
            )}
          </div>
          
          <div 
            className="flex-shrink-0 ml-3 w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ 
              background: isSelected ? `${THEME.cyan}20` : 'rgba(255,255,255,0.05)',
              border: isSelected ? `1px solid ${THEME.cyan}30` : '1px solid transparent',
            }}
          >
            <span className={`text-xs font-bold ${isSelected ? 'text-cyan-400' : 'text-slate-500'}`}>
              #{node.order}
            </span>
          </div>
        </div>
      </div>
    </button>
  );
}

function VideoItem({ video, status, onClick }) {
  const vidStatus = status || { status: 'new', pct: 0 };
  const isCompleted = vidStatus.status === 'completed';
  const isInProgress = vidStatus.status === 'in-progress';
  const cfg = VIDEO_STATUS[vidStatus.status] || VIDEO_STATUS.new;
  const StatusIcon = cfg.icon;
  
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-xl border transition-all duration-200 group relative overflow-hidden ${
        isCompleted 
          ? '' 
          : isInProgress
            ? ''
            : ''
      }`}
      style={{
        background: isCompleted ? 'rgba(16,185,129,0.05)' : isInProgress ? 'rgba(245,158,11,0.05)' : THEME.card,
        borderColor: isCompleted ? 'rgba(16,185,129,0.2)' : isInProgress ? 'rgba(245,158,11,0.2)' : THEME.border,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = isCompleted ? 'rgba(16,185,129,0.4)' : isInProgress ? 'rgba(245,158,11,0.4)' : `${THEME.cyan}40`;
        e.currentTarget.style.background = isCompleted ? 'rgba(16,185,129,0.08)' : isInProgress ? 'rgba(245,158,11,0.08)' : `${THEME.cyan}08`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = isCompleted ? 'rgba(16,185,129,0.2)' : isInProgress ? 'rgba(245,158,11,0.2)' : THEME.border;
        e.currentTarget.style.background = isCompleted ? 'rgba(16,185,129,0.05)' : isInProgress ? 'rgba(245,158,11,0.05)' : THEME.card;
      }}
    >
      <div className="p-3.5 flex items-start gap-3">
        {/* Thumbnail / Icon */}
        <div 
          className="flex-shrink-0 w-14 h-10 rounded-lg flex items-center justify-center relative overflow-hidden"
          style={{ 
            background: isCompleted ? 'rgba(16,185,129,0.15)' : isInProgress ? 'rgba(245,158,11,0.15)' : 'rgba(6,182,212,0.15)',
          }}
        >
          <StatusIcon size={18} style={{ color: cfg.color }} />
          {/* Play overlay */}
          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <Play size={16} className="text-white" fill="white" />
          </div>
        </div>
        
        <div className="flex-1 min-w-0">
          <h4 className={`text-sm font-medium truncate transition-colors ${
            isCompleted ? 'text-emerald-400' : 'text-slate-200 group-hover:text-cyan-400'
          }`}>
            {video.title}
          </h4>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[11px]" style={{ color: THEME.textDark }}>{video.channel}</span>
            {video.duration && (
              <span 
                className="text-[10px] px-1.5 py-0.5 rounded"
                style={{ background: 'rgba(255,255,255,0.05)', color: THEME.textMuted }}
              >
                {video.duration}
              </span>
            )}
          </div>
          
          {/* Progress indicator */}
          {isInProgress && (
            <div className="mt-2">
              <div className="flex items-center justify-between text-[10px] mb-1">
                <span className="text-amber-400 font-medium">{vidStatus.pct}% watched</span>
                <span style={{ color: THEME.textDark }}>Continue watching</span>
              </div>
              <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.05)' }}>
                <div 
                  className="h-full rounded-full transition-all relative"
                  style={{ 
                    width: `${vidStatus.pct}%`,
                    background: `linear-gradient(90deg, ${THEME.amber}, #fbbf24)`
                  }}
                >
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-white shadow-lg" />
                </div>
              </div>
            </div>
          )}
          
          {isCompleted && (
            <div className="mt-1.5 flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
              <CheckCircle size={12} />
              <span>Completed</span>
              <Sparkles size={10} className="ml-1" />
            </div>
          )}
        </div>
        
        <div className="flex-shrink-0 self-center">
          <div 
            className="w-8 h-8 rounded-full flex items-center justify-center transition-all group-hover:scale-110"
            style={{
              background: isCompleted ? 'rgba(16,185,129,0.2)' : isInProgress ? 'rgba(245,158,11,0.2)' : 'rgba(6,182,212,0.2)',
              border: `1px solid ${isCompleted ? 'rgba(16,185,129,0.3)' : isInProgress ? 'rgba(245,158,11,0.3)' : 'rgba(6,182,212,0.3)'}`,
            }}
          >
            <ArrowRight size={14} style={{ color: cfg.color }} />
          </div>
        </div>
      </div>
    </button>
  );
}

function CourseItem({ course, onClick }) {
  return (
    <a
      href={course.url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={onClick}
      className="block rounded-xl border p-3.5 transition-all duration-200 group relative overflow-hidden"
      style={{ 
        background: THEME.card,
        borderColor: THEME.border,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = `${THEME.violet}40`;
        e.currentTarget.style.background = `${THEME.violet}08`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = THEME.border;
        e.currentTarget.style.background = THEME.card;
      }}
    >
      <div className="flex items-start gap-3">
        <div 
          className="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center"
          style={{ background: `${THEME.violet}15` }}
        >
          <BookMarked size={18} style={{ color: THEME.violet }} />
        </div>
        <div className="flex-1 min-w-0"> 
          <h4 className="text-sm font-medium text-slate-200 group-hover:text-violet-400 transition-colors truncate">
            {course.title}
          </h4>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[11px]" style={{ color: THEME.textDark }}>{course.provider}</span>
            {course.rating && (
              <span className="flex items-center gap-0.5 text-[11px] text-amber-400">
                <Star size={10} fill="currentColor" />
                {course.rating}
              </span>
            )}
            {course.certificate && (
              <span 
                className="text-[9px] px-1.5 py-0.5 rounded font-medium"
                style={{ background: 'rgba(245,158,11,0.15)', color: THEME.amber, border: '1px solid rgba(245,158,11,0.25)' }}
              >
                CERT
              </span>
            )}
          </div>
        </div>
        <ExternalLink size={14} className="text-slate-600 group-hover:text-violet-400 flex-shrink-0 mt-1 transition-colors" />
      </div>
    </a>
  );
}

// ─── MAIN COMPONENT ─────────────────────────────────────

export default function LearningPathPage() {
  const { learningPath, profile, learningScore, refresh } = useFlaskData();
  const [selected, setSelected] = useState(null);
  const [saving, setSaving] = useState(false);
  const [topicResources, setTopicResources] = useState(null);
  const [videoModal, setVideoModal] = useState({ open: false, video: null });
  const [errorMessage, setErrorMessage] = useState('');
  const [videoProgress, setVideoProgress] = useState({});
  const [activeTab, setActiveTab] = useState('videos');

  // Auto-select first available topic
  useEffect(() => {
    const rec = learningPath.find(s => s.status === 'recommended') || 
                learningPath.find(s => s.status !== 'locked');
    if (rec && !selected) setSelected(rec);
  }, [learningPath]);

  // Load video progress
  useEffect(() => {
    const loadVideoProgress = async () => {
      try {
        const data = await apiFetch('/api/path/video/progress');
        setVideoProgress(data || {});
      } catch (err) {
        console.error('Failed to load video progress:', err);
      }
    };
    loadVideoProgress();
  }, [learningPath]);

  const getVideoStatus = (videoUrl) => {
    const progress = videoProgress[videoUrl];
    if (!progress) return { status: 'new', pct: 0 };
    if (progress.completed || progress.watched_pct >= 80) return { status: 'completed', pct: 100 };
    return { status: 'in-progress', pct: progress.watched_pct };
  };

  const updateStatus = async (topic, status) => {
    setSaving(true);
    setErrorMessage('');
    try {
      await apiFetch('/api/path/step/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, status }),
      });
      await refresh();
    } catch (err) {
      setErrorMessage(err.message || 'Unable to update the step.');
    } finally {
      setSaving(false);
    }
  };

  const fetchTopicResources = async (topic) => {
    if (!topic) { setTopicResources(null); return; }
    try {
      const data = await apiFetch(`/api/path/resources?topic=${encodeURIComponent(topic)}`);
      setTopicResources(data.resources || null);
    } catch (error) {
      setTopicResources(null);
    }
  };

  useEffect(() => {
    if (selected) fetchTopicResources(selected.topic);
  }, [selected]);

  const handleOpenVideo = async (video) => {
    setErrorMessage('');
    setVideoModal({ open: true, video });
    if (!video) return;
    try {
      await apiFetch('/api/path/video/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: selected.topic, url: video.url, event: 'start' }),
      });
      await refresh();
    } catch (err) {
      setErrorMessage(err.message || 'Unable to start video tracking.');
    }
  };

  const handleTrackVideo = async ({ watched_seconds, watched_pct, event }) => {
    if (!selected || !videoModal.video) return;
    
    setVideoProgress(prev => ({
      ...prev,
      [videoModal.video.url]: {
        watched_pct,
        watched_seconds,
        completed: watched_pct >= 80,
      }
    }));
    
    try {
      await apiFetch('/api/path/video/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: selected.topic,
          url: videoModal.video.url,
          watched_seconds,
          watched_pct,
          event,
        }),
      });
      await refresh();
    } catch (err) {
      setErrorMessage(err.message || 'Unable to track video progress.');
    }
  };

  const handleCourseAction = async (course, action) => {
    if (!selected) return;
    try {
      await apiFetch('/api/path/course/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: selected.topic, url: course.url, action }),
      });
      await refresh();
    } catch (err) {
      setErrorMessage(err.message || 'Unable to track course action.');
    }
  };

  const displayedResources = topicResources || selected;
  const completedCount = learningPath.filter(s => s.status === 'completed').length;
  // ✅ FIX : In Progress compte aussi l'activité vidéo/course
  const inProgressCount = learningPath.filter(s => 
    s.status === 'in-progress' || 
    (s.video_progress > 0 && s.status !== 'completed') ||
    (s.course_progress > 0 && s.status !== 'completed')
  ).length;
  const completionPct = profile?.pathMetrics?.topic_completion_pct ?? 
    (learningPath.length ? Math.round((completedCount / learningPath.length) * 100) : 0);

  // ✅ FIX : Plus d'onglet Datasets
  const tabs = [
    { id: 'videos', label: 'Videos', icon: Video, count: displayedResources?.videos?.length || 0 },
    { id: 'courses', label: 'Courses', icon: BookText, count: displayedResources?.courses?.length || 0 },
  ];

  return (
    <div className="min-h-screen" style={{ background: THEME.bg }}>
      {/* Top Header */}
      <div style={{ 
        background: 'linear-gradient(180deg, rgba(15,23,42,0.95) 0%, rgba(11,17,33,0.98) 100%)',
        borderBottom: `1px solid ${THEME.border}`,
      }}>
        <div className="max-w-7xl mx-auto px-6 py-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div 
                className="w-10 h-10 rounded-xl flex items-center justify-center"
                style={{ 
                  background: `linear-gradient(135deg, ${THEME.cyan}20, ${THEME.violet}20)`,
                  border: `1px solid ${THEME.cyan}30`,
                }}
              >
                <GraduationCap size={22} style={{ color: THEME.cyan }} />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">Learning Path</h1>
                <p className="text-sm" style={{ color: THEME.textMuted }}>Your personalized curriculum — follow the sequence to master each topic</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-[10px] uppercase tracking-wider font-medium" style={{ color: THEME.textDark }}>Learning Score</p>
                <p className="text-lg font-bold font-mono" style={{ color: THEME.cyan }}>{learningScore}%</p>
              </div>
              <div 
                className="w-12 h-12 rounded-full flex items-center justify-center"
                style={{ 
                  background: `linear-gradient(135deg, ${THEME.cyan}15, ${THEME.violet}15)`,
                  border: `2px solid ${THEME.cyan}30`,
                }}
              >
                <Zap size={20} style={{ color: THEME.cyan }} />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard 
            icon={BookOpen} 
            label="Total Topics" 
            value={learningPath.length} 
            subtext="In your curriculum"
            color={THEME.cyan}
            glow={THEME.cyanGlow}
          />
          <StatCard 
            icon={CheckCircle} 
            label="Completed" 
            value={completedCount} 
            subtext={`${Math.round((completedCount / Math.max(learningPath.length, 1)) * 100)}% success rate`}
            color={THEME.emerald}
            glow={THEME.emeraldGlow}
          />
          <StatCard 
            icon={Clock} 
            label="In Progress" 
            value={inProgressCount} 
            subtext="Active learning"
            color={THEME.amber}
            glow={THEME.amberGlow}
          />
          <StatCard 
            icon={Target} 
            label="Next Milestone" 
            value={`${Math.max(0, 80 - completionPct)}%`} 
            subtext="To reach 80% completion"
            color={THEME.violet}
            glow={THEME.violetGlow}
          />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          {/* Left Sidebar — Topic List */}
          <div className="xl:col-span-4 space-y-4">
            <ProgressBar 
              current={completedCount} 
              total={learningPath.length} 
              percentage={completionPct}
            />
            
            <div 
              className="rounded-2xl border overflow-hidden"
              style={{ 
                background: THEME.card,
                borderColor: THEME.border,
              }}
            >
              <div 
                className="px-5 py-4 border-b flex items-center gap-2"
                style={{ borderColor: THEME.border }}
              >
                <Map size={16} style={{ color: THEME.cyan }} />
                <h2 className="text-sm font-bold uppercase tracking-wider text-white">Curriculum Topics</h2>
              </div>
              <div className="p-3 space-y-2 max-h-[600px] overflow-y-auto custom-scrollbar">
                {learningPath.map((step) => (
                  <TopicNode
                    key={step.topic}
                    node={step}
                    isSelected={selected?.topic === step.topic}
                    onSelect={setSelected}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Right Panel — Topic Detail */}
          <div className="xl:col-span-8">
            {selected ? (
              <div className="space-y-5">
                {/* Topic Header Card */}
                <div 
                  className="rounded-2xl border overflow-hidden relative"
                  style={{ 
                    background: THEME.card,
                    borderColor: THEME.border,
                  }}
                >
                  {/* Top gradient accent */}
                  <div 
                    className="h-1 w-full"
                    style={{ 
                      background: `linear-gradient(90deg, ${THEME.cyan}, ${THEME.violet})` 
                    }}
                  />
                  <div className="p-6">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <span 
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wide"
                            style={{ 
                              color: LEVEL_CONFIG[selected.level]?.color || THEME.cyan,
                              background: `${LEVEL_CONFIG[selected.level]?.color || THEME.cyan}15`,
                              border: `1px solid ${LEVEL_CONFIG[selected.level]?.color || THEME.cyan}30`,
                            }}
                          >
                            {React.createElement(LEVEL_CONFIG[selected.level]?.icon || BookOpen, { size: 14 })}
                            {LEVEL_CONFIG[selected.level]?.label || selected.level}
                          </span>
                          <span 
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wide"
                            style={{ 
                              color: STATUS_CONFIG[selected.status]?.color || THEME.cyan,
                              background: STATUS_CONFIG[selected.status]?.bg,
                              border: `1px solid ${STATUS_CONFIG[selected.status]?.border || THEME.cyan}40`,
                            }}
                          >
                            {React.createElement(STATUS_CONFIG[selected.status]?.icon || CirclePlay, { size: 12 })}
                            {STATUS_CONFIG[selected.status]?.label || selected.status}
                          </span>
                        </div>
                        <h2 className="text-2xl font-bold text-white capitalize">{selected.topic}</h2>
                        <p className="text-sm mt-1" style={{ color: THEME.textMuted }}>Step #{selected.order} in your learning journey</p>
                      </div>
                      
                      {/* Action Buttons */}
                      <div className="flex gap-2">
                        {selected.status !== 'completed' && (
                          <button
                            disabled={saving}
                            onClick={() => updateStatus(selected.topic, 'completed')}
                            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-105 disabled:opacity-50"
                            style={{ 
                              background: `linear-gradient(135deg, ${THEME.emerald}, #05279647)`,
                              color: 'white',
                            }}
                          >
                            <CheckCircle size={16} />
                            Mark Complete
                          </button>
                        )}
                        {selected.status === 'locked' && (
                          <button
                            disabled={saving}
                            onClick={() => updateStatus(selected.topic, 'in-progress')}
                            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-105 disabled:opacity-50"
                            style={{ 
                              background: `linear-gradient(135deg, ${THEME.cyan}, ${THEME.violet})`,
                              color: 'white',
                            }}
                          >
                            <Play size={16} />
                            Start Learning
                          </button>
                        )}
                        {selected.status === 'completed' && (
                          <button
                            onClick={() => updateStatus(selected.topic, 'recommended')}
                            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-105"
                            style={{ 
                              background: 'rgba(255,255,255,0.05)',
                              color: THEME.textMuted,
                              border: `1px solid ${THEME.border}`,
                            }}
                          >
                            <RotateCcw size={16} />
                            Reset
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Error Message */}
                    {errorMessage && (
                      <div 
                        className="mt-4 flex items-center gap-2 p-3 rounded-lg text-sm"
                        style={{ 
                          background: 'rgba(239,68,68,0.1)', 
                          border: '1px solid rgba(239,68,68,0.2)',
                          color: '#f87171',
                        }}
                      >
                        <AlertCircle size={16} />
                        {errorMessage}
                      </div>
                    )}

                    {/* Prerequisites */}
                    {selected.prerequisites?.length > 0 && (
                      <div className="mt-4 flex items-center gap-2 text-sm" style={{ color: THEME.textMuted }}>
                        <LockKeyhole size={14} />
                        <span>Prerequisites:</span>
                        <div className="flex gap-1.5">
                          {selected.prerequisites.map(p => (
                            <span 
                              key={p} 
                              className="px-2 py-0.5 rounded-md text-xs font-medium capitalize"
                              style={{ 
                                background: 'rgba(255,255,255,0.05)', 
                                color: THEME.textMuted,
                                border: `1px solid ${THEME.border}`,
                              }}
                            >
                              {p}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Mini Project */}
                {selected.project && (
                  <div 
                    className="rounded-2xl border p-5 relative overflow-hidden"
                    style={{ 
                      background: `linear-gradient(135deg, ${THEME.violet}08, rgba(139,92,246,0.03))`,
                      borderColor: `${THEME.violet}25`,
                    }}
                  >
                    <div 
                      className="absolute top-0 right-0 w-32 h-32 opacity-10"
                      style={{ 
                        background: `radial-gradient(circle, ${THEME.violet}, transparent 70%)`,
                      }}
                    />
                    <div className="flex items-center gap-2 mb-2 relative z-10">
                      <Award size={18} style={{ color: THEME.violet }} />
                      <h3 className="text-sm font-bold uppercase tracking-wider" style={{ color: THEME.violet }}>Mini Project</h3>
                    </div>
                    <p className="text-sm leading-relaxed relative z-10" style={{ color: THEME.textMuted }}>{selected.project}</p>
                  </div>
                )}

                {/* Resources Tabs */}
                <div 
                  className="rounded-2xl border overflow-hidden"
                  style={{ 
                    background: THEME.card,
                    borderColor: THEME.border,
                  }}
                >
                  {/* Tab Header */}
                  <div className="flex border-b" style={{ borderColor: THEME.border }}>
                    {tabs.map(tab => (
                      <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className="flex items-center gap-2 px-5 py-3.5 text-sm font-medium transition-all relative"
                        style={{ 
                          color: activeTab === tab.id ? THEME.cyan : THEME.textDark,
                          borderBottom: activeTab === tab.id ? `2px solid ${THEME.cyan}` : '2px solid transparent',
                          background: activeTab === tab.id ? `${THEME.cyan}08` : 'transparent',
                        }}
                      >
                        <tab.icon size={16} />
                        {tab.label}
                        {tab.count > 0 && (
                          <span 
                            className="ml-1 px-1.5 py-0.5 rounded-md text-[10px] font-bold"
                            style={{ 
                              background: activeTab === tab.id ? `${THEME.cyan}20` : 'rgba(255,255,255,0.05)',
                              color: activeTab === tab.id ? THEME.cyan : THEME.textDark,
                            }}
                          >
                            {tab.count}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>

                  {/* Tab Content */}
                  <div className="p-5">
                    {/* Videos Tab */}
                    {activeTab === 'videos' && (
                      <div className="space-y-3">
                        {displayedResources?.videos?.length > 0 ? (
                          displayedResources.videos.map((v, i) => (
                            <VideoItem
                              key={i}
                              video={v}
                              status={getVideoStatus(v.url)}
                              onClick={() => handleOpenVideo(v)}
                            />
                          ))
                        ) : (
                          <div className="text-center py-10" style={{ color: THEME.textDark }}>
                            <Video size={32} className="mx-auto mb-2 opacity-30" />
                            <p className="text-sm">No videos available for this topic</p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Courses Tab */}
                    {activeTab === 'courses' && (
                      <div className="space-y-3">
                        {displayedResources?.courses?.length > 0 ? (
                          displayedResources.courses.map((c, i) => (
                            <CourseItem
                              key={i}
                              course={c}
                              onClick={() => handleCourseAction(c, 'click')}
                            />
                          ))
                        ) : (
                          <div className="text-center py-10" style={{ color: THEME.textDark }}>
                            <BookText size={32} className="mx-auto mb-2 opacity-30" />
                            <p className="text-sm">No courses available for this topic</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div 
                className="rounded-2xl border p-12 text-center"
                style={{ 
                  background: THEME.card,
                  borderColor: THEME.border,
                }}
              >
                <Map size={48} className="mx-auto mb-4 opacity-20" style={{ color: THEME.textDark }} />
                <h3 className="text-lg font-semibold text-white">Select a Topic</h3>
                <p className="text-sm mt-1" style={{ color: THEME.textDark }}>Choose a topic from the sidebar to view its resources</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Video Modal */}
      <VideoPlayerModal
        open={videoModal.open}
        video={videoModal.video}
        onClose={() => setVideoModal({ open: false, video: null })}
        onWatchUpdate={handleTrackVideo}
      />

      {/* Custom Scrollbar Styles */}
      <style>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255,255,255,0.1);
          border-radius: 3px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255,255,255,0.2);
        }
      `}</style>
    </div>
  );
}