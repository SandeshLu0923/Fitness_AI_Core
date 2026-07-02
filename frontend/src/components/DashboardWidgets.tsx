import { useState } from 'react';

// ==========================================
// STRICT TYPES FOR UNIFIED PIPELINE COMPLIANCE
// ==========================================
export interface ExerciseItem {
  exercise_name: string;
  prescribed_sets: number;
  prescribed_reps: string;
  trainer_execution_note: string;
}

export interface DayDetails {
  day_number: number;
  target_muscle_split: string;
  is_rest_day: boolean;
  exercises: ExerciseItem[];
  daily_metric_challenge: string;
}

interface DailyChallengeCardProps {
  dayPlan: DayDetails | null;
  difficultyMultiplier: string;
  onCompleteDay: (challengeText: string) => Promise<void>;
  onLaunchCVTracker?: (exerciseType: string) => void;
}

interface WeeklyProgressLogProps {
  schedule: DayDetails[];
  currentActiveDay: number;
}

// ==========================================
// 1. REACTIVE DAILY CHALLENGE COMPONENT CARD
// ==========================================
export function DailyChallengeCard({ 
  dayPlan, 
  difficultyMultiplier, 
  onCompleteDay,
  onLaunchCVTracker 
}: DailyChallengeCardProps) {
  const [isActivated, setIsActivated] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!dayPlan) {
    return (
      <div className="bg-[#161616] border border-zinc-800 rounded-lg p-6 h-full flex items-center justify-center font-sans text-zinc-500 text-xs uppercase tracking-wider min-h-[220px]">
        No active training block loaded
      </div>
    );
  }

  const handleStartChallengeAction = () => {
    if (onLaunchCVTracker && dayPlan.exercises.length > 0) {
      const targetExercise = dayPlan.exercises[0].exercise_name.toLowerCase();
      onLaunchCVTracker(targetExercise.includes("squat") ? "squat" : "pushup");
    }
  };

  const handleMarkComplete = async () => {
    setIsSubmitting(true);
    try {
        await onCompleteDay(dayPlan.daily_metric_challenge);
        setIsActivated(false);
    } catch (err) {
        console.error("Failed to log challenge completion", err);
    } finally {
        setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-[#161616] border border-zinc-800 rounded-lg p-6 h-full flex flex-col justify-between font-sans">
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-widest">
            Day {dayPlan.day_number} Challenge • <span className="text-cyan-400 font-mono text-[10px]">{difficultyMultiplier}</span>
          </h4>
          <div className="flex items-center space-x-2 text-[11px] font-bold tracking-wider uppercase">
            <button 
              onClick={() => setIsActivated(!isActivated)}
              className={`transition-colors ${isActivated ? 'text-cyan-400 font-extrabold' : 'text-zinc-400 hover:text-zinc-200'}`}
            >
              {isActivated ? 'Activated' : 'Activate Plan'}
            </button>
          </div>
        </div>

        <div className="space-y-1.5">
          <p className="text-sm font-black text-zinc-100">{dayPlan.target_muscle_split}</p>
          <p className="text-xs text-zinc-400 leading-relaxed font-normal">
            {dayPlan.daily_metric_challenge}
          </p>
        </div>

        <div className="pt-2 flex flex-col gap-2">
          {!dayPlan.is_rest_day && (
            <button
              onClick={handleStartChallengeAction}
              disabled={!isActivated}
              className={`w-full flex items-center justify-center space-x-2 py-2.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all border ${
                isActivated 
                  ? 'bg-zinc-900 text-zinc-200 border-zinc-700 hover:bg-zinc-800 font-bold shadow-md' 
                  : 'bg-zinc-900/40 text-zinc-600 border-zinc-800/80 cursor-not-allowed font-medium'
              }`}
            >
              <span>Launch Desktop Tracker</span>
            </button>
          )}

          <button
            onClick={handleMarkComplete}
            disabled={!isActivated || isSubmitting}
            className={`w-full flex items-center justify-center space-x-2 py-2.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all border ${
              isActivated 
                ? 'bg-cyan-500 hover:bg-cyan-600 text-zinc-950 border-cyan-400 font-black shadow-md' 
                : 'bg-zinc-900/40 text-zinc-600 border-zinc-800/80 cursor-not-allowed font-medium'
              }`}
          >
            <span>{isSubmitting ? 'Logging...' : 'Mark Day Complete'}</span>
          </button>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-zinc-800/60 flex items-center justify-between text-[11px] font-mono tracking-wider uppercase">
        <div className="text-cyan-400 font-bold">Reward: Progress Multiplier Level Up</div>
        <span className="text-zinc-600">{isActivated ? 'Active' : 'Awaiting'}</span>
      </div>
    </div>
  );
}

// ==========================================
// 2. DYNAMIC WEEKLY PROGRESS GRAPH LOGGER TABLE
// ==========================================
export function WeeklyProgressLog({ schedule, currentActiveDay }: WeeklyProgressLogProps) {
  return (
    <div className="bg-[#161616] border border-zinc-800 rounded-lg p-6 font-sans">
      <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-widest mb-4">
        Active Training Macrocycle Block Schedule
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm border-collapse">
          <thead>
            <tr className="border-b border-zinc-800 text-zinc-500 font-bold uppercase tracking-wider text-[11px]">
              <th className="pb-3 font-bold">Timeline Status</th>
              <th className="pb-3 font-bold">Target Muscle Split Focus</th>
              <th className="pb-3 text-center font-bold">Daily Focus</th>
              <th className="pb-3 text-right font-bold">Challenge Prescription</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/40 font-medium text-zinc-300">
            {schedule && schedule.map((day) => {
              const isCurrent = day.day_number === currentActiveDay;
              const isPast = day.day_number < currentActiveDay;
              
              return (
                <tr key={day.day_number} className={isCurrent ? 'bg-zinc-900/30' : ''}>
                  <td className="py-3 text-[11px] uppercase font-mono tracking-wider">
                    {isCurrent && <span className="text-cyan-400 font-bold">● Current Day {day.day_number}</span>}
                    {isPast && <span className="text-zinc-600">✓ Day {day.day_number}</span>}
                    {!isCurrent && !isPast && <span className="text-zinc-600">○ Day {day.day_number}</span>}
                  </td>
                  <td className={`py-3 text-sm font-semibold ${isCurrent ? 'text-zinc-100' : 'text-zinc-400'}`}>
                    {day.target_muscle_split}
                  </td>
                  <td className="py-3 text-center text-xs text-zinc-500 font-mono uppercase">
                    {day.is_rest_day ? 'Recovery Rest' : `${day.exercises ? day.exercises.length : 0} Exercises`}
                  </td>
                  <td className="py-3 text-right text-xs text-zinc-400 font-medium italic">
                    {day.daily_metric_challenge}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
