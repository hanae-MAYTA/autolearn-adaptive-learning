import React, { useEffect, useRef, useState } from 'react';

export default function VideoPlayerModal({ open, video, onClose, onWatchUpdate }) {
  const playerRef = useRef(null);
  const intervalRef = useRef(null);
  const maxReachedRef = useRef(0); // أقصى وقت حقيقي وصله الطالب
  const [watchedPct, setWatchedPct] = useState(0);
  const [alreadyCompleted, setAlreadyCompleted] = useState(false);
  const [warningMsg, setWarningMsg] = useState('');

  // Reset à chaque ouverture/fermeture
  useEffect(() => {
    if (!open) {
      setWatchedPct(0);
      setAlreadyCompleted(false);
      setWarningMsg('');
      maxReachedRef.current = 0;
      clearInterval(intervalRef.current);
      playerRef.current?.destroy?.();
      playerRef.current = null;
    }
  }, [open]);

  // Extraire l'ID YouTube depuis l'URL
  const getYouTubeId = (url) => {
    const match = url?.match(/(?:v=|youtu\.be\/)([^&?/]+)/);
    return match ? match[1] : null;
  };

  const handleProgress = (pct) => {
    setWatchedPct(pct);
    const event = pct >= 80 ? 'complete' : 'progress';
    onWatchUpdate({ watched_pct: pct, watched_seconds: Math.round(maxReachedRef.current), event });

    if (pct >= 80 && !alreadyCompleted) {
      setAlreadyCompleted(true);
    }
  };

  // Initialiser le lecteur YouTube
  useEffect(() => {
    if (!open || !video?.url) return;

    const videoId = getYouTubeId(video.url);
    if (!videoId) return;

    const initPlayer = () => {
      // Nettoyer l'ancien player si existant
      if (playerRef.current) {
        playerRef.current.destroy();
        playerRef.current = null;
      }

      playerRef.current = new window.YT.Player('yt-player', {
        videoId,
        playerVars: {
          autoplay: 1,
          rel: 0,
          modestbranding: 1,
        },
        events: {
          onReady: (e) => {
            e.target.playVideo();
          },
          onStateChange: (e) => {
            // Vidéo terminée naturellement
            if (e.data === window.YT.PlayerState.ENDED) {
              handleProgress(100);
              clearInterval(intervalRef.current);
            }
          },
        },
      });

      // ✅ Tracker toutes les secondes + bloquer le skip
      intervalRef.current = setInterval(() => {
        const player = playerRef.current;
        if (!player?.getCurrentTime) return;

        const current = player.getCurrentTime();
        const duration = player.getDuration();
        if (!duration) return;

        // ⛔ Anti-cheat : si l'étudiant saute +10 secondes → on le ramène
        if (current > maxReachedRef.current + 10) {
          player.seekTo(maxReachedRef.current, true);
          setWarningMsg('⛔ Skipping is not allowed! Please watch the video normally.');
          setTimeout(() => setWarningMsg(''), 3000);
          return;
        }

        // ✅ Mettre à jour le max temps réel atteint
        maxReachedRef.current = Math.max(maxReachedRef.current, current);

        const pct = Math.round((maxReachedRef.current / duration) * 100);
        handleProgress(pct);
      }, 1000);
    };

    // Charger YouTube IFrame API si pas encore chargée
    if (window.YT?.Player) {
      initPlayer();
    } else {
      const tag = document.createElement('script');
      tag.src = 'https://www.youtube.com/iframe_api';
      document.body.appendChild(tag);
      window.onYouTubeIframeAPIReady = initPlayer;
    }

    return () => {
      clearInterval(intervalRef.current);
    };
  }, [open, video]);

  if (!open || !video) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80">
      <div className="w-full max-w-2xl rounded-3xl bg-slate-950 border border-white/10 shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <div>
            <div className="text-sm font-semibold text-white truncate max-w-xs">{video.title}</div>
            <div className="text-xs text-slate-400">{video.channel}</div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-lg">✕</button>
        </div>

        {/* Lecteur YouTube intégré */}
        <div className="bg-black w-full" style={{ aspectRatio: '16/9' }}>
          <div id="yt-player" style={{ width: '100%', height: '100%' }} />
        </div>

        {/* Avertissement anti-cheat */}
        {warningMsg && (
          <div className="px-5 py-2 bg-red-500/10 border-t border-red-500/20 text-red-400 text-sm text-center">
            {warningMsg}
          </div>
        )}

        {/* Barre de progression automatique */}
        <div className="px-5 py-4 border-t border-white/10 space-y-3">
          
          {/* Progress bar */}
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-400">Progression</span>
              <span className="text-cyan-400 font-mono">{watchedPct}%</span>
            </div>
            <div className="w-full h-2 rounded-full bg-white/10">
              <div
                className="h-2 rounded-full transition-all duration-500"
                style={{
                  width: `${watchedPct}%`,
                  background: watchedPct >= 80
                    ? 'linear-gradient(90deg, #4ade80, #22d3ee)'
                    : 'linear-gradient(90deg, #6366f1, #00d4ff)',
                }}
              />
            </div>
          </div>

          {/* Message de statut */}
          {alreadyCompleted ? (
            <div className="text-center text-green-400 text-sm font-semibold">
               Video completed! Progress updated automatically.
            </div>
          ) : (
            <div className="text-center text-slate-400 text-xs">
              {watchedPct < 80
                ? `Watch at least 80% to validate — ${80 - watchedPct}% remaining`
                : ' Validating...'}
            </div>
          )}

          {/* Info anti-cheat visible */}
          <div className="text-center text-slate-600 text-[10px]">
             Skipping is disabled — progress is tracked automatically
          </div>
        </div>

      </div>
    </div>
  );
}