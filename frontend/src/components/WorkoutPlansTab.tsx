import { useState, useEffect } from 'react';
import { Dumbbell, Trash2, Calendar } from 'lucide-react';
import axios from 'axios';

interface WorkoutPlan {
  _id: string;
  user_id: string;
  workout_plan: any;
  daily_challenges: any[];
  archetype: string;
  difficulty_multiplier: string;
  created_at: string;
  is_active: boolean;
  total_days: number;
}

interface WorkoutPlansTabProps {
  userId: string;
}

export default function WorkoutPlansTab({ userId }: WorkoutPlansTabProps) {
  const [workoutPlans, setWorkoutPlans] = useState<WorkoutPlan[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<WorkoutPlan | null>(null);

  useEffect(() => {
    fetchWorkoutPlans();
  }, [userId]);

  const fetchWorkoutPlans = async () => {
    setLoading(true);
    try {
      const response = await axios.get(
        `http://localhost:8000/api/plans/workout-plans/${userId}`
      );
      setWorkoutPlans(response.data.plans || []);
    } catch (err) {
      console.error('Failed to fetch workout plans:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeletePlan = async (planId: string) => {
    if (window.confirm('Delete this workout plan?')) {
      try {
        await axios.delete(
          `http://localhost:8000/api/plans/workout-plans/${planId}`
        );
        setWorkoutPlans(prev => prev.filter(p => p._id !== planId));
        setSelectedPlan(null);
      } catch (err) {
        console.error('Failed to delete plan:', err);
      }
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#161616] rounded-lg border border-zinc-800">
      {/* Header */}
      <div className="h-14 px-4 border-b border-zinc-800 flex items-center justify-between bg-[#1a1a1a] shrink-0">
        <div className="flex items-center space-x-2">
          <Dumbbell size={16} className="text-cyan-400" />
          <h3 className="text-sm font-bold text-zinc-200">My Workout Plans</h3>
        </div>
        <span className="text-xs bg-zinc-800 text-zinc-400 px-2 py-1 rounded">
          {workoutPlans.length} saved
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden flex gap-4 p-4">
        {/* Plans List */}
        <div className="w-1/3 border border-zinc-800 rounded-lg p-3 overflow-y-auto space-y-2">
          {loading ? (
            <div className="text-center text-zinc-500 text-xs py-4">Loading...</div>
          ) : workoutPlans.length === 0 ? (
            <div className="text-center text-zinc-500 text-xs py-4">
              No workout plans yet. Create one in chat!
            </div>
          ) : (
            workoutPlans.map(plan => (
              <button
                key={plan._id}
                onClick={() => setSelectedPlan(plan)}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  selectedPlan?._id === plan._id
                    ? 'bg-cyan-500/10 border-cyan-500/30'
                    : 'bg-zinc-900/50 border-zinc-800 hover:border-zinc-700'
                }`}
              >
                <div className="text-[11px] font-bold text-zinc-300">
                  {new Date(plan.created_at).toLocaleDateString()}
                </div>
                <div className="text-[10px] text-zinc-400 mt-1 space-y-0.5">
                  <div>📅 {plan.total_days}-day plan</div>
                  <div>💪 {plan.archetype}</div>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Plan Details */}
        <div className="w-2/3 border border-zinc-800 rounded-lg p-4 overflow-y-auto bg-zinc-900/30">
          {selectedPlan ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-bold text-zinc-200">{selectedPlan.archetype}</h4>
                  <p className="text-xs text-zinc-400">{selectedPlan.difficulty_multiplier}</p>
                </div>
                <button
                  onClick={() => handleDeletePlan(selectedPlan._id)}
                  className="p-1.5 hover:bg-red-500/20 text-red-400 rounded transition-colors"
                  title="Delete plan"
                >
                  <Trash2 size={16} />
                </button>
              </div>

              <div className="bg-cyan-500/10 border border-cyan-500/20 p-2 rounded-lg text-[10px] text-cyan-300">
                <div className="flex items-center gap-2">
                  <Calendar size={14} />
                  <span className="font-semibold">{selectedPlan.total_days}-Day Training Macrocycle</span>
                </div>
              </div>

              <div>
                <h5 className="text-xs font-bold text-cyan-400 mb-2">📅 Daily Challenges:</h5>
                <ol className="text-[9px] text-zinc-300 space-y-1 bg-zinc-900/50 p-3 rounded list-decimal list-inside max-h-[300px] overflow-y-auto">
                  {selectedPlan.daily_challenges.map((challenge, idx) => (
                    <li key={idx} className="text-zinc-200">
                      <span className="font-semibold text-cyan-400">Day {idx + 1}:</span> {challenge.challenge || challenge.daily_metric_challenge}
                    </li>
                  ))}
                </ol>
              </div>

              {selectedPlan.workout_plan && (
                <div>
                  <h5 className="text-xs font-bold text-cyan-400 mb-2">🏋️ Plan Details:</h5>
                  <div className="text-[9px] text-zinc-300 bg-zinc-900/50 p-3 rounded max-h-[200px] overflow-y-auto">
                    <pre className="font-mono whitespace-pre-wrap break-words">
                      {JSON.stringify(selectedPlan.workout_plan, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
              Select a plan to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
