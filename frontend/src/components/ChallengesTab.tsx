import { useEffect, useState } from 'react';
import axios from 'axios';
import { CheckCircle, ShieldAlert, Trophy } from 'lucide-react';

interface ChallengesTabProps {
  userId: string;
}

export default function ChallengesTab({ userId }: ChallengesTabProps) {
  const [activeChallenge, setActiveChallenge] = useState<any>(null);
  const [completedChallenges, setCompletedChallenges] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [isActivated, setIsActivated] = useState(false);

  const fetchChallenges = async () => {
    if (!userId) return;
    setLoading(true);
    setErrorMsg('');
    try {
      const [activeResponse, completedResponse] = await Promise.all([
        axios.get(`http://localhost:8000/api/habit-tracker/active-day-plan?user_id=${encodeURIComponent(userId)}`),
        axios.get(`http://localhost:8000/api/habit-tracker/completed-challenges/${encodeURIComponent(userId)}`)
      ]);
      setActiveChallenge(activeResponse.data);
      setCompletedChallenges(completedResponse.data.completed_challenges || []);
    } catch {
      setErrorMsg('Failed to load challenge data from the server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchChallenges();
  }, [userId]);

  const challengeText = activeChallenge?.day_details?.daily_metric_challenge
    || activeChallenge?.day_details?.notes
    || activeChallenge?.message
    || 'No active challenge. Generate a workout plan to begin.';
  const hasActiveChallenge = Boolean(
    activeChallenge?.day_details
    && !String(activeChallenge.day_details.notes || '').toLowerCase().includes('no active macrocycle')
    && !activeChallenge?.message
  );
  const activationKey = `active_challenge:${userId}:${localIsoDate(new Date())}`;

  useEffect(() => {
    setIsActivated(localStorage.getItem(activationKey) === 'true');

    const syncActivation = () => {
      setIsActivated(localStorage.getItem(activationKey) === 'true');
    };
    window.addEventListener('challenge-activation-changed', syncActivation);
    return () => window.removeEventListener('challenge-activation-changed', syncActivation);
  }, [activationKey]);

  const handleActivationChange = (checked: boolean) => {
    setIsActivated(checked);
    if (checked) {
      localStorage.setItem(activationKey, 'true');
    } else {
      localStorage.removeItem(activationKey);
    }
    window.dispatchEvent(new CustomEvent('challenge-activation-changed'));
  };

  const handleComplete = async () => {
    setSyncMessage('Logging achievement...');
    try {
      const response = await axios.post('http://localhost:8000/api/habit-tracker/complete-active-day', {
        user_id: userId,
        day_number: activeChallenge?.current_active_day || 1,
        challenge_text: challengeText,
      });
      if (response.data.status === 'success') {
        setSyncMessage(response.data.message || 'Challenge completed.');
        setIsActivated(false);
        localStorage.removeItem(activationKey);
        window.dispatchEvent(new CustomEvent('challenge-activation-changed'));
        fetchChallenges();
      }
    } catch {
      setSyncMessage('Failed to log achievement.');
    }
  };

  if (loading) {
    return <div className="text-gray-400 font-medium text-sm animate-pulse">Loading active targets...</div>;
  }

  const challengeRows = [
    ...(hasActiveChallenge ? [{
      id: 'today',
      title: challengeText,
      detail: activeChallenge?.day_details?.target_muscle_split || `Day ${activeChallenge?.current_active_day || 1}`,
      status: isActivated ? 'Active' : 'Pending',
      completedAt: '',
      isToday: true,
    }] : []),
    ...completedChallenges.map((challenge) => ({
      id: challenge._id,
      title: challenge.challenge_text || 'Completed challenge',
      detail: challenge.completed_at ? new Date(challenge.completed_at).toLocaleString() : 'Completed',
      status: 'Completed',
      completedAt: challenge.completed_at,
      isToday: false,
    }))
  ];

  return (
    <div className="max-w-5xl space-y-6">
      {errorMsg && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm rounded-lg flex items-center space-x-2">
          <ShieldAlert size={16} />
          <span>{errorMsg}</span>
        </div>
      )}

      <div className="bg-[#1e1e1e] border border-gray-800 rounded-xl p-5 space-y-4 shadow-xl">
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-xs font-black text-zinc-400 uppercase tracking-widest">Challenge List</h4>
          <Trophy size={18} className="text-amber-400" />
        </div>

        {syncMessage && (
          <div className="text-xs bg-cyan-500/10 text-cyan-400 px-3 py-2 rounded-md border border-cyan-500/20 font-semibold">
            {syncMessage}
          </div>
        )}

        {challengeRows.length === 0 ? (
          <p className="text-sm text-zinc-500">No challenges found. Generate a workout plan to begin.</p>
        ) : (
          <div className="space-y-3">
            {challengeRows.map((challenge) => (
              <div key={challenge.id} className="bg-[#121212] border border-zinc-800 rounded-lg p-4">
                <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
                  <div className="min-w-0 space-y-1">
                    <p className="text-sm text-zinc-100 font-bold leading-relaxed break-words">{challenge.title}</p>
                    <p className="text-xs text-zinc-500">{challenge.detail}</p>
                  </div>
                  <span className={`text-[10px] font-black uppercase tracking-wider px-2.5 py-1 rounded border shrink-0 w-fit ${
                    challenge.status === 'Completed'
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                      : challenge.status === 'Active'
                        ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
                        : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                  }`}>
                    {challenge.status}
                  </span>
                </div>

                {challenge.isToday && (
                  <div className="mt-4 flex flex-col sm:flex-row gap-3">
                    <label className="flex items-center space-x-3 p-3 bg-[#0f0f0f] rounded-lg border border-gray-700 flex-1">
                      <input
                        type="checkbox"
                        checked={isActivated}
                        onChange={(event) => handleActivationChange(event.target.checked)}
                        disabled={!hasActiveChallenge}
                        className="w-5 h-5 rounded accent-cyan-400 cursor-pointer"
                      />
                      <span className="text-sm font-semibold text-gray-300 cursor-pointer">
                        Activate challenge to start tracking
                      </span>
                    </label>
                    <button
                      onClick={handleComplete}
                      disabled={!isActivated || !hasActiveChallenge}
                      className={`font-bold px-5 py-2.5 rounded-lg border transition-all flex items-center justify-center space-x-2 text-sm ${
                        isActivated
                          ? 'bg-emerald-500/10 hover:bg-emerald-500/20 border-emerald-500/30 text-emerald-400'
                          : 'bg-[#0f0f0f] border-gray-800 text-gray-600 cursor-not-allowed'
                      }`}
                    >
                      <CheckCircle size={16} />
                      <span>{isActivated ? 'Mark As Completed' : 'Activate First'}</span>
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function localIsoDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}
