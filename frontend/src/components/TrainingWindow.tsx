import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Download, Monitor, Play, Send, Smartphone, Square } from 'lucide-react';

interface TrainingStats {
  exercise_name: string;
  correct_reps: number;
  incorrect_reps: number;
  total_reps: number;
  sets_completed: number;
  target_sets?: number;
  target_reps_per_set?: number;
  current_set?: number;
  current_set_reps?: number;
  target_total_reps?: number;
  progress_percent?: number;
  exercise_completed?: boolean;
  accuracy: number;
  timestamp: string;
}

interface TrainingWindowProps {
  userId: string;
  exerciseType?: string;
  targetSets?: number;
  targetReps?: number;
  onComplete?: (stats: TrainingStats) => void;
}

export default function TrainingWindow({ userId, exerciseType = 'squat', targetSets = 1, targetReps = 10, onComplete }: TrainingWindowProps) {
  const [isTraining, setIsTraining] = useState(false);
  const [stats, setStats] = useState<TrainingStats | null>(null);
  const [feedback, setFeedback] = useState<string>('Ready to start training');
  const [loading, setLoading] = useState(false);
  const [companionLaunched, setCompanionLaunched] = useState(false);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const completionHandledRef = useRef(false);
  const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const localTrackerUrl = import.meta.env.VITE_LOCAL_TRACKER_URL || 'http://127.0.0.1:8000';
  const desktopCompanionUrl = import.meta.env.VITE_DESKTOP_COMPANION_URL || '';
  const mobileCompanionUrl = import.meta.env.VITE_MOBILE_COMPANION_URL || '';
  const hasCompanionDownloads = Boolean(desktopCompanionUrl || mobileCompanionUrl);
  const localTrackerRequest = { skipApiRewrite: true } as any;

  const finalizeWorkout = async (finalStats: TrainingStats) => {
    if (completionHandledRef.current) return;
    completionHandledRef.current = true;
    try {
      await axios.post(
        `${apiBaseUrl}/api/gym-trainer/log-completed-workout`,
        {
          user_id: userId,
          exercise_name: finalStats.exercise_name,
          sets_completed: finalStats.sets_completed,
          correct_reps: finalStats.correct_reps,
          incorrect_reps: finalStats.incorrect_reps,
          target_sets: finalStats.target_sets || targetSets,
          target_reps_per_set: finalStats.target_reps_per_set || targetReps,
          notes: `Session completed with ${finalStats.accuracy}% accuracy`
        }
      );
      try {
        await axios.post(
          `${apiBaseUrl}/api/performance/score`,
          {
            session_data: {
              session_id: `${userId}-${Date.now()}`,
              duration_seconds: 60,
              rest_seconds: 60,
            },
            landmarks_history: [],
          },
          {
            params: {
              user_id: userId,
              exercise_type: finalStats.exercise_name || exerciseType,
              reps_completed: finalStats.total_reps || 0,
              reps_correct: finalStats.correct_reps || 0,
            },
          }
        );
      } catch (performanceError) {
        console.warn('Could not log performance score:', performanceError);
      }
      setFeedback('Workout logged successfully.');
      onComplete?.(finalStats);
    } catch (e) {
      console.warn('Could not log to backend:', e);
      setFeedback('Workout tracked locally');
    }
  };

  // Start training session
  const startTraining = async () => {
    try {
      setLoading(true);
      completionHandledRef.current = false;
      
      // Manual launch approach - rely on user confirmation
      if (!companionLaunched) {
        setFeedback('Please confirm you have launched the companion app.');
        setLoading(false);
        return;
      }
      
      setFeedback('Initializing tracker...');
      
      // Start the vision session
      try {
        await axios.post(
          `${localTrackerUrl}/api/gym-trainer/start`,
          {
            user_id: userId,
            exercise_type: exerciseType.toLowerCase(),
            target_sets: Math.max(1, Number(targetSets) || 1),
            target_reps_per_set: Math.max(1, Number(targetReps) || 10),
          },
          localTrackerRequest,
        );
        setIsTraining(true);
        setFeedback('OpenCV tracking started. Switch to the native tracker window.');
        if (!pollIntervalRef.current) {
          startPolling();
        }
      } catch (trackerError) {
        console.error('Failed to start tracker:', trackerError);
        setFeedback('Tracker failed to start. Stopping companion app...');
        // Stop companion if tracker fails
        await axios.post(`${apiBaseUrl}/api/gym-trainer/companion/stop`).catch(() => {});
        setFeedback('Could not start tracker. Please try again.');
      }
    } catch (error: any) {
      console.error('Failed to start training:', error);
      setFeedback('Failed to start training. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Stop training session
  const stopTraining = async () => {
    try {
      setIsTraining(false);
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      setFeedback('Stopping OpenCV tracker...');

      try {
        await axios.post(`${localTrackerUrl}/api/gym-trainer/stop`, { user_id: userId }, localTrackerRequest);
        setFeedback('OpenCV tracker stop signal sent.');
      } catch (stopError) {
        console.warn('Failed to stop backend tracker:', stopError);
        setFeedback('Could not stop backend tracker cleanly. Close the native window manually.');
      }
      
      // Stop the companion app
      try {
        await axios.post(`${apiBaseUrl}/api/gym-trainer/companion/stop`);
        setFeedback('Desktop companion stopped.');
      } catch (companionStopError) {
        console.warn('Failed to stop companion app:', companionStopError);
      }
      
      // Log the completed workout if we have stats
      if (stats) {
        const expectedTotal = (stats.target_sets || targetSets) * (stats.target_reps_per_set || targetReps);
        if (!stats.exercise_completed && (stats.total_reps || 0) < expectedTotal) {
          setFeedback(`Stopped at ${stats.total_reps || 0}/${expectedTotal} reps. Complete the target to save this exercise.`);
          return;
        }
        try {
          await axios.post(
            `${apiBaseUrl}/api/gym-trainer/log-completed-workout`,
            {
              user_id: userId,
              exercise_name: stats.exercise_name,
              sets_completed: stats.sets_completed,
              correct_reps: stats.correct_reps,
              incorrect_reps: stats.incorrect_reps,
              target_sets: stats.target_sets || targetSets,
              target_reps_per_set: stats.target_reps_per_set || targetReps,
              notes: `Session completed with ${stats.accuracy}% accuracy`
            }
          );
          setFeedback('✅ Workout logged successfully!');
          try {
            await axios.post(
              `${apiBaseUrl}/api/performance/score`,
              {
                session_data: {
                  session_id: `${userId}-${Date.now()}`,
                  duration_seconds: 60,
                  rest_seconds: 60,
                },
                landmarks_history: [],
              },
              {
                params: {
                  user_id: userId,
                  exercise_type: stats.exercise_name || exerciseType,
                  reps_completed: stats.total_reps || 0,
                  reps_correct: stats.correct_reps || 0,
                },
              }
            );
          } catch (performanceError) {
            console.warn('Could not log performance score:', performanceError);
          }
          if (onComplete) {
            onComplete(stats);
          }
        } catch (e) {
          console.warn('Could not log to backend:', e);
          setFeedback('Workout tracked locally');
        }
      }
    } catch (error) {
      console.error('Error stopping training:', error);
      setFeedback('Error ending session');
    }
  };

  // Poll for latest stats
  const startPolling = () => {
    pollIntervalRef.current = setInterval(async () => {
      try {
        const response = await axios.get(`${localTrackerUrl}/api/gym-trainer/latest-stats/${userId}`, localTrackerRequest);
        
        if (response.data.found) {
          const nextStats: TrainingStats = {
            exercise_name: response.data.exercise_name,
            correct_reps: response.data.correct_reps,
            incorrect_reps: response.data.incorrect_reps,
            total_reps: response.data.total_reps,
            sets_completed: response.data.sets_completed,
            target_sets: response.data.target_sets,
            target_reps_per_set: response.data.target_reps_per_set,
            current_set: response.data.current_set,
            current_set_reps: response.data.current_set_reps,
            target_total_reps: response.data.target_total_reps,
            progress_percent: response.data.progress_percent,
            exercise_completed: response.data.exercise_completed,
            accuracy: response.data.accuracy,
            timestamp: response.data.timestamp
          };
          setStats(nextStats);
          
          // Update feedback based on accuracy
          if (response.data.feedback) {
            setFeedback(response.data.feedback);
          } else if (response.data.accuracy > 90) {
            setFeedback('Excellent form! Keep it up!');
          } else if (response.data.accuracy > 70) {
            setFeedback('Good form. Minor adjustments needed.');
          } else if (response.data.accuracy > 50) {
            setFeedback('Check your form. Watch the feedback indicators.');
          } else {
            setFeedback('Focus on your form. Adjust position.');
          }
          if (response.data.exercise_completed) {
            setIsTraining(false);
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            setFeedback('Target completed. Workout is ready to save.');
            await axios.post(`${localTrackerUrl}/api/gym-trainer/stop`, { user_id: userId }, localTrackerRequest).catch(() => null);
            await finalizeWorkout(nextStats);
          }
        }
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 1000); // Poll every second
  };

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  return (
    <div className="w-full bg-gradient-to-br from-[#0f0f0f] to-[#1a1a1a] border border-zinc-800 rounded-lg shadow-2xl overflow-hidden">
      
      {/* Header */}
      <div className="bg-gradient-to-r from-cyan-600/20 to-blue-600/20 border-b border-zinc-800 px-6 py-4">
        <h3 className="text-lg font-bold text-cyan-400 uppercase tracking-widest">
          {isTraining ? '🔴 LIVE TRAINING' : '⏱️ Training Window'}
        </h3>
        <p className="text-xs text-zinc-400 mt-1">
          Exercise: <span className="text-cyan-400 font-semibold uppercase">{exerciseType}</span>
          <span className="ml-3 text-zinc-500">Target: {targetSets} sets x {targetReps} reps</span>
        </p>
      </div>

      {/* Main Content */}
      <div className="p-6 space-y-6">
        
        {/* Video Preview Area */}
        <div className="relative w-full h-64 md:h-96 bg-gradient-to-br from-zinc-900 to-black rounded-lg border border-zinc-800 flex items-center justify-center overflow-hidden group">
          {isTraining ? (
            <div className="flex flex-col items-center justify-center text-center text-cyan-300">
              <div className="h-32 w-32 rounded-full border-4 border-cyan-500/30 border-t-cyan-500 animate-spin mb-4" />
              <p className="text-lg font-semibold">OpenCV tracker is running</p>
              <p className="text-sm text-zinc-400 mt-2">Switch to the native desktop tracker window to view live video.</p>
            </div>
          ) : (
            <div className="text-center space-y-3 z-10">
              <Play size={48} className="mx-auto text-zinc-600" />
              <p className="text-zinc-400 font-medium">Click Start to begin training</p>
              <p className="text-xs text-zinc-500">Ensure good lighting and camera angle</p>
            </div>
          )}
        </div>

        {/* Companion App Status */}
        <div className="bg-zinc-950/70 border border-zinc-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-bold text-cyan-400 uppercase tracking-widest">Companion App</div>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={companionLaunched}
                  onChange={(e) => setCompanionLaunched(e.target.checked)}
                  className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-cyan-500 focus:ring-cyan-500 focus:ring-offset-zinc-900"
                />
                <span className="text-xs text-zinc-300">I have launched the companion app</span>
              </label>
            </div>
          </div>
          
          <p className="text-xs text-zinc-500">
            Launch the companion app from your desktop shortcut or system tray icon, then check the box above to confirm.
          </p>
          
          {hasCompanionDownloads && (
            <div className="space-y-2">
              <p className="text-xs text-zinc-400 italic">
                Don't have the companion app? Download it from the link below.
              </p>
              {desktopCompanionUrl && (
                <a
                  href={desktopCompanionUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-2 text-xs font-bold uppercase tracking-wider text-zinc-200 hover:border-cyan-500/50 hover:text-cyan-300"
                >
                  <Monitor size={15} />
                  <Download size={14} />
                  Download Desktop Tracker
                </a>
              )}
            </div>
          )}
        </div>

        {/* Real-time Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 text-center">
            <div className="text-xs text-zinc-500 font-mono uppercase tracking-wider mb-2">Correct Reps</div>
            <div className="text-3xl font-black text-cyan-400">{stats?.current_set_reps ?? stats?.correct_reps ?? 0}</div>
            <div className="text-[10px] text-zinc-500 mt-1">of {stats?.target_reps_per_set || targetReps} this set</div>
          </div>
          
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 text-center">
            <div className="text-xs text-zinc-500 font-mono uppercase tracking-wider mb-2">Incorrect</div>
            <div className="text-3xl font-black text-orange-400">{stats?.incorrect_reps || 0}</div>
          </div>
          
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 text-center">
            <div className="text-xs text-zinc-500 font-mono uppercase tracking-wider mb-2">Sets</div>
            <div className="text-3xl font-black text-purple-400">{stats?.sets_completed || 0}</div>
            <div className="text-[10px] text-zinc-500 mt-1">of {stats?.target_sets || targetSets}</div>
          </div>
          
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 text-center">
            <div className="text-xs text-zinc-500 font-mono uppercase tracking-wider mb-2">Accuracy</div>
            <div className={`text-3xl font-black ${stats && stats.accuracy > 80 ? 'text-green-400' : stats && stats.accuracy > 60 ? 'text-yellow-400' : 'text-red-400'}`}>
              {stats?.accuracy || 0}%
            </div>
          </div>
        </div>

        {/* Feedback Section */}
        <div className="bg-gradient-to-r from-cyan-500/10 to-blue-500/10 border border-cyan-500/30 rounded-lg p-4 space-y-2">
          <div className="text-xs font-bold text-cyan-400 uppercase tracking-widest">Live Feedback</div>
          <p className={`text-sm font-semibold ${isTraining ? 'text-cyan-300' : 'text-zinc-400'}`}>
            {feedback}
          </p>
          
          {/* Form Indicators */}
          <div className="grid grid-cols-3 gap-2 mt-3">
            <div className="flex items-center space-x-2 text-xs">
              <div className="h-2 w-2 rounded-full bg-cyan-500 animate-pulse" />
              <span className="text-zinc-400">Posture: Good</span>
            </div>
            <div className="flex items-center space-x-2 text-xs">
              <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-zinc-400">Range: Full</span>
            </div>
            <div className="flex items-center space-x-2 text-xs">
              <div className="h-2 w-2 rounded-full bg-orange-500 animate-pulse" />
              <span className="text-zinc-400">Tempo: Steady</span>
            </div>
          </div>
        </div>

        {/* Total Reps Display */}
        <div className="bg-zinc-800/40 rounded-lg p-4 border border-zinc-700/60 text-center">
          <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Total Reps Completed</p>
          <p className="text-4xl font-black text-cyan-400 font-mono">{stats?.total_reps || 0}</p>
          <div className="mt-3 h-2 bg-zinc-900 rounded-full overflow-hidden border border-zinc-800">
            <div
              className="h-full bg-cyan-500 transition-all"
              style={{ width: `${Math.min(stats?.progress_percent || 0, 100)}%` }}
            />
          </div>
          <p className="text-[10px] text-zinc-500 mt-2">{Math.round(stats?.progress_percent || 0)}% complete</p>
        </div>

        {/* Control Buttons */}
        <div className="flex gap-3 pt-4">
          <button
            onClick={isTraining ? stopTraining : startTraining}
            disabled={loading}
            className={`flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-bold uppercase tracking-wider transition-all text-sm ${
              isTraining
                ? 'bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-500/20'
                : 'bg-cyan-600 hover:bg-cyan-700 text-white shadow-lg shadow-cyan-500/20'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {isTraining ? (
              <>
                <Square size={18} />
                Stop Training
              </>
            ) : (
              <>
                <Play size={18} />
                {loading ? 'Starting...' : 'Start Training'}
              </>
            )}
          </button>

          {isTraining && (
            <button
              onClick={stopTraining}
              className="px-6 py-3 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg font-bold uppercase tracking-wider transition-all text-sm flex items-center gap-2"
            >
              <Send size={18} />
              <span className="hidden sm:inline">Log & End</span>
            </button>
          )}
        </div>

        {/* Status Info */}
        <div className="text-xs text-zinc-500 text-center pt-2">
          {isTraining && (
            <p>🟢 Live Tracking Active • Polling every 1 second</p>
          )}
          {stats && (
            <p>Last update: {new Date(stats.timestamp).toLocaleTimeString()}</p>
          )}
        </div>
      </div>
    </div>
  );
}
