import { useState, useEffect } from 'react';
import axios from 'axios';

interface ProgressItem {
  name: string;
  current: number;
  target: number;
}

interface TableExercise {
  rank: number;
  name: string;
  count: number;
}

interface WorkoutPlan {
  _id: string;
  user_id: string;
  workout_plan: any;
  daily_challenges: any[];
  archetype: string;
  difficulty_multiplier: string;
  created_at: string;
}

interface GoalDay {
  key: string;
  label: string;
  exercises: any[];
  challenge?: any;
  isRestDay?: boolean;
  wasSkipped?: boolean;
  movedToDayNumber?: number;
  date?: string;
}

const DEFAULT_EXERCISES = [
  { name: "Jumping Jacks", sets: 3, reps: 30, rest_seconds: 60 },
  { name: "Squats", sets: 3, reps: 15, rest_seconds: 90 },
  { name: "Pushups", sets: 3, reps: 15, rest_seconds: 90 },
  { name: "Pullups", sets: 4, reps: 10, rest_seconds: 120 },
  { name: "Situps", sets: 3, reps: 20, rest_seconds: 60 }
];

export default function WorkoutHistoryTab({ userId = 'runner_jack' }: { userId?: string }) {
  const [historySubTab, setHistorySubTab] = useState<'today' | 'weekly' | 'monthly' | 'goals'>('today');
  const [workoutPlans, setWorkoutPlans] = useState<WorkoutPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [activeGoalSchedule, setActiveGoalSchedule] = useState<GoalDay[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Stats state - now using proper variables
  const [weeklyStats, setWeeklyStats] = useState<any>(null);
  const [monthlyStats, setMonthlyStats] = useState<any>(null);
  const [todayStats, setTodayStats] = useState<any>(null);
  const [completedWorkouts, setCompletedWorkouts] = useState<any[]>([]);
  const [todayPlanExercises, setTodayPlanExercises] = useState<any[]>([]);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [weekDays, setWeekDays] = useState<any[]>([]);

  // --- Helper Functions ---
  const getWeekDays = () => {
    const today = new Date();
    const weekStart = new Date(today);
    const mondayOffset = (today.getDay() + 6) % 7;
    weekStart.setDate(today.getDate() - mondayOffset);
    
    const days = [];
    const dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    
    for (let i = 0; i < 7; i++) {
      const d = new Date(weekStart);
      d.setDate(d.getDate() + i);
      days.push({
        label: dayLabels[i],
        date: d,
        dateStr: localIsoDate(d)
      });
    }
    return days;
  };

  const getCalendarDays = (date: Date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = (firstDay.getDay() + 6) % 7;
    
    const days = [];
    // Add empty cells for days before month starts
    for (let i = 0; i < startingDayOfWeek; i++) {
      days.push({ dayNumber: '', active: false });
    }
    // Add days of month
    for (let i = 1; i <= daysInMonth; i++) {
      days.push({ dayNumber: i.toString(), active: false, dateStr: `${year}-${String(month + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}` });
    }
    return days;
  };

  const processExerciseData = (stats: any) => {
    const rows = stats?.exercises || stats?.exercise_totals || [];
    if (!rows.length) return [];
    return rows
      .sort((a: any, b: any) => (b.total_reps || 0) - (a.total_reps || 0))
      .map((ex: any, idx: number) => ({
        rank: idx + 1,
        name: ex.name || ex.exercise || 'Unknown',
        count: ex.total_reps || 0
      }))
      .slice(0, 5);
  };

  function exerciseKey(name: string) {
    const value = String(name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    if (['squat', 'squats', 'bodyweight-squats'].includes(value)) return 'squat';
    if (['pushup', 'pushups', 'push-up', 'push-ups'].includes(value)) return 'pushup';
    if (['pullup', 'pullups', 'pull-up', 'pull-ups'].includes(value)) return 'pullup';
    if (['situp', 'situps', 'sit-up', 'sit-ups'].includes(value)) return 'situp';
    if (['jumping-jack', 'jumping-jacks'].includes(value)) return 'jumping-jacks';
    return value;
  }

  function numericTarget(value: any, fallback = 1) {
    if (typeof value === 'number' && Number.isFinite(value)) return Math.max(1, Math.round(value));
    const match = String(value ?? '').match(/\d+/);
    return match ? Math.max(1, Number(match[0])) : fallback;
  }

  function normalizeExerciseProgress(exercise: any): ProgressItem {
    const name = getExerciseName(exercise);
    const sets = numericTarget(exercise?.sets ?? exercise?.prescribed_sets, 1);
    const reps = numericTarget(exercise?.reps ?? exercise?.prescribed_reps ?? exercise?.sets_reps, 10);
    const target = sets * reps;
    const completed = completedWorkouts.find((workout) => exerciseKey(workout.exercise_name) === exerciseKey(name));
    return {
      name,
      current: Math.min(Number(completed?.total_reps ?? completed?.correct_reps ?? 0), target),
      target,
    };
  }

  const todayGoalDay = activeGoalSchedule.find((day) => String(day.date || '').split('T')[0] === localIsoDate(new Date()))
    || activeGoalSchedule.find((day) => !day.wasSkipped)
    || null;
  const progressSourceExercises = todayGoalDay?.exercises?.length ? todayGoalDay.exercises : todayPlanExercises;

  const todayProgressData: ProgressItem[] = progressSourceExercises.length
    ? progressSourceExercises.map(normalizeExerciseProgress)
    : todayStats?.exercises?.map((ex: any) => ({
        name: ex.name,
        current: ex.current_reps || ex.total_reps || 0,
        target: ex.target_reps || 150
      })) || [];

  // --- Weekly Stats Dataset (from real data) ---
  const weeklyExerciseData: TableExercise[] = weeklyStats ? processExerciseData(weeklyStats) : [];

  const weeklyDaysCompletion = weekDays.map((day: any) => ({
    label: day.label,
    completed: weeklyStats?.days_active?.[day.dateStr] || false,
    dateStr: day.dateStr
  }));
  const weeklyCompletedDays = weeklyStats?.completed_workout_days ?? weeklyDaysCompletion.filter((day) => day.completed).length;
  const weeklyPlannedDays = weeklyStats?.planned_workout_days ?? 7;

  // --- Monthly Stats Dataset (from real data) ---
  const monthlyExerciseData: TableExercise[] = monthlyStats ? processExerciseData(monthlyStats) : [];

  // 🌍 FIXED: Standard localized English days header columns
  const calendarDaysHeader = ["M", "T", "W", "T", "F", "S", "S"];
  
  // 🟢 FIXED: Dynamic calendar from current month
  const calendarCells = getCalendarDays(currentMonth).map(cell => ({
    ...cell,
    active: cell.dateStr ? (monthlyStats?.days_active?.[cell.dateStr] || false) : false
  }));

  // 🎯 GOALS SETTING - Extract from selected workout plan
  const selectedPlan = workoutPlans.find(p => p._id === selectedPlanId);
  const weeklyWorkoutPlan = activeGoalSchedule.length > 0
    ? activeGoalSchedule
    : selectedPlan
      ? normalizeWeeklyWorkoutPlan(selectedPlan)
      : [];

  function normalizeActiveSchedule(schedule: any[]): GoalDay[] {
    if (!Array.isArray(schedule)) return [];
    const today = localIsoDate(new Date());
    return schedule.map((day: any, index: number) => ({
      key: `active_day_${day.day_number || index + 1}`,
      label: day.day_name || day.focus || `Day ${day.day_number || index + 1}`,
      exercises: Array.isArray(day.exercises) ? day.exercises : [],
      isRestDay: Boolean(day.is_rest_day),
      wasSkipped: Boolean(day.was_skipped) && String(day.date || '').split('T')[0] <= today,
      movedToDayNumber: day.moved_to_day_number,
      date: day.date
    }));
  }

  function localIsoDate(date: Date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function parseLocalDate(value: string | undefined) {
    if (!value) return null;
    const datePart = String(value).split('T')[0];
    const parts = datePart.split('-').map(Number);
    if (parts.length === 3 && parts.every(Number.isFinite)) {
      return new Date(parts[0], parts[1] - 1, parts[2]);
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function extractDayNumber(value: string) {
    const match = String(value).match(/\d+/);
    return match ? Number(match[0]) : 0;
  }

  function extractTodayWorkoutPlan(plan: any) {
    if (!plan?.workout_plan) return null;
    const planData = plan.workout_plan;
    const source = planData.weekly_plan && typeof planData.weekly_plan === 'object' ? planData.weekly_plan : planData;
    const days = Array.isArray(source.days)
      ? source.days.map((day: any, index: number) => ({ ...day, __dayNumber: Number(day.day || day.day_number || index + 1) }))
      : Object.keys(source)
          .filter(key => key.toLowerCase().startsWith('day'))
          .sort((a, b) => extractDayNumber(a) - extractDayNumber(b))
          .map((key, index) => ({ ...source[key], __dayNumber: extractDayNumber(key) || index + 1 }));

    if (!Array.isArray(days) || days.length === 0) return null;
    const today = localIsoDate(new Date());
    const datedDay = days.find((day: any) => String(day?.date || '').split('T')[0] === today);
    if (datedDay) return datedDay;

    const start = parseLocalDate(plan.start_date || days[0]?.date || plan.created_at);
    if (!start) return days[0];
    const diff = Math.floor((parseLocalDate(today)!.getTime() - start.getTime()) / 86400000);
    return days[Math.max(0, Math.min(diff, days.length - 1))];
  }

  function normalizeWeeklyWorkoutPlan(plan: WorkoutPlan): GoalDay[] {
    const fallbackLabels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    const startDate = getPlanStartDate(plan);
    const labelForIndex = (index: number, fallback?: string) => {
      if (!startDate) return fallback || fallbackLabels[index] || `Day ${index + 1}`;
      const current = new Date(startDate);
      current.setDate(current.getDate() + index);
      return current.toLocaleDateString('en-US', { weekday: 'long' });
    };
    const rawPlan = plan.workout_plan || {};
    const source = rawPlan.weekly_plan || rawPlan;

    if (Array.isArray(source.days)) {
      return source.days.map((dayData: any, index: number) => ({
        key: `day_${dayData.day || index + 1}`,
        label: labelForIndex(index, dayData.focus || dayData.day_name),
        exercises: Array.isArray(dayData.exercises) ? dayData.exercises : [],
        challenge: plan.daily_challenges?.find((item: any) => Number(item.day) === (dayData.day || index + 1)) || plan.daily_challenges?.[index]
      }));
    }

    return Array.from({ length: 7 }, (_, index) => {
      const dayNumber = index + 1;
      const dayKey = `day_${dayNumber}`;
      const dayData = source[dayKey] || source[fallbackLabels[index]] || {};
      const rawExercises = Array.isArray(dayData)
        ? dayData
        : Array.isArray(dayData.exercises)
          ? dayData.exercises
          : [];

      return {
        key: dayKey,
        label: labelForIndex(index, dayData.day_name || fallbackLabels[index]),
        exercises: rawExercises,
        challenge: plan.daily_challenges?.find((item: any) => Number(item.day) === dayNumber) || plan.daily_challenges?.[index]
      };
    });
  }

  function getPlanStartDate(plan: WorkoutPlan) {
    const rawPlan = plan.workout_plan || {};
    const source = rawPlan.weekly_plan || rawPlan;
    const firstDay = Array.isArray(source.days) ? source.days[0] : source.day_1;
    const dateValue = firstDay?.date || (plan as any).start_date || plan.created_at;
    if (!dateValue) return null;
    const parsed = new Date(dateValue);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function getExerciseName(exercise: any) {
    if (typeof exercise === 'string') return exercise;
    return exercise.exercise_name || exercise.exercise || exercise.name || 'Exercise';
  }

  function getExerciseTarget(exercise: any) {
    if (typeof exercise === 'string') return '';
    const sets = exercise.sets ?? exercise.prescribed_sets;
    const reps = exercise.reps ?? exercise.prescribed_reps;
    if (sets !== undefined && sets !== null && reps !== undefined && reps !== null) {
      return `${sets} x ${reps}`;
    }
    if (exercise.sets_reps) return exercise.sets_reps;
    return '';
  }

  const fetchWorkoutPlans = async () => {
    if (!userId) return;

    try {
      setLoading(true);
      const latestResponse = await axios.get(`http://localhost:8000/api/plans/workout-plans/${userId}/latest`);
      const latestPlan = latestResponse.data?.plan;

      if (latestPlan) {
        setWorkoutPlans([latestPlan]);
        setSelectedPlanId(latestPlan._id);
        return;
      }

      const response = await axios.get(`http://localhost:8000/api/plans/workout-plans/${userId}`);
      const plans = response.data.plans || [];
      setWorkoutPlans(plans);
      if (plans.length > 0) {
        setSelectedPlanId(plans[0]._id);
      } else {
        setSelectedPlanId(null);
      }
    } catch (error) {
      console.error('Failed to load workout plans:', error);
      setWorkoutPlans([]);
      setSelectedPlanId(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchActiveGoalSchedule = async () => {
    if (!userId) return;
    try {
      const response = await axios.get(`http://localhost:8000/api/habit-tracker/active-schedule?user_id=${encodeURIComponent(userId)}`);
      setActiveGoalSchedule(normalizeActiveSchedule(response.data?.schedule || []));
    } catch (error) {
      console.error('Failed to load active goal schedule:', error);
      setActiveGoalSchedule([]);
    }
  };

  // Fetch weekly stats
  const fetchWeeklyStats = async () => {
    try {
      const response = await axios.get(`http://localhost:8000/api/gym-trainer/weekly-stats/${userId}`);
      setWeeklyStats(response.data);
    } catch (error) {
      console.error('Failed to load weekly stats:', error);
    }
  };

  // Fetch monthly stats
  const fetchMonthlyStats = async () => {
    try {
      const response = await axios.get(`http://localhost:8000/api/gym-trainer/monthly-stats/${userId}`);
      setMonthlyStats(response.data);
    } catch (error) {
      console.error('Failed to load monthly stats:', error);
    }
  };

  // Fetch today's stats
  const fetchTodayStats = async () => {
    try {
      const response = await axios.get(`http://localhost:8000/api/gym-trainer/latest-stats/${userId}`);
      setTodayStats(response.data);
    } catch (error) {
      console.error('Failed to load today stats:', error);
    }
  };

  const fetchTodayPlan = async () => {
    try {
      const response = await axios.get(`http://localhost:8000/api/habit-tracker/active-day-plan?user_id=${encodeURIComponent(userId)}`);
      const exercises = response.data?.day_details?.was_skipped
        ? []
        : response.data?.day_details?.exercises || [];
      if (Array.isArray(exercises) && exercises.length > 0) {
        setTodayPlanExercises(exercises);
        return;
      }

      const latestResponse = await axios.get(`http://localhost:8000/api/plans/workout-plans/${encodeURIComponent(userId)}/latest`);
      const latestPlan = latestResponse.data?.plan;
      const todayPlan = extractTodayWorkoutPlan(latestPlan);
      if (todayPlan?.exercises?.length) {
        setTodayPlanExercises(todayPlan.exercises);
        return;
      }

      setTodayPlanExercises(DEFAULT_EXERCISES);
    } catch {
      setTodayPlanExercises(DEFAULT_EXERCISES);
    }
  };

  const fetchCompletedWorkouts = async () => {
    try {
      const response = await axios.get(`http://localhost:8000/api/gym-trainer/completed-workouts/${encodeURIComponent(userId)}`);
      setCompletedWorkouts(response.data?.completed_workouts || []);
    } catch (error) {
      console.error('Failed to load completed workouts:', error);
      setCompletedWorkouts([]);
    }
  };

  // Load workout plans from database
  useEffect(() => {
    setWeekDays(getWeekDays());
    fetchTodayStats();
    fetchTodayPlan();
    fetchCompletedWorkouts();
    fetchWeeklyStats();
    fetchMonthlyStats();
  }, [userId]);

  useEffect(() => {
    if (!userId) return;
    fetchWorkoutPlans();
    fetchActiveGoalSchedule();
  }, [userId]);

  useEffect(() => {
    if (historySubTab === 'goals' && userId) {
      fetchWorkoutPlans();
      fetchActiveGoalSchedule();
    }
  }, [historySubTab, userId]);

  useEffect(() => {
    const handlePlanSaved = () => {
      fetchWorkoutPlans();
      fetchActiveGoalSchedule();
    };

    window.addEventListener('workout-plan-saved', handlePlanSaved);
    window.addEventListener('workout-plan-shifted', handlePlanSaved);
    return () => {
      window.removeEventListener('workout-plan-saved', handlePlanSaved);
      window.removeEventListener('workout-plan-shifted', handlePlanSaved);
    };
  }, [userId]);

  return (
    <div className="w-full mx-auto space-y-6 font-sans antialiased text-zinc-300">
      
      {/* HEADER TITLE */}
      <div className="text-center py-1">
        <h3 className="text-base font-bold text-zinc-100 uppercase tracking-widest">
          Workout Plan and Statistics
        </h3>
      </div>

      {/* SUB-TAB NAV BAR */}
      <div className="flex border-b border-zinc-800/80 overflow-x-auto scrollbar-none">
        {['today', 'weekly', 'monthly', 'goals'].map((tab) => {
          const labels: Record<string, string> = {
            today: "Today's Progress",
            weekly: "Weekly Stats",
            monthly: "Monthly Stats",
            goals: "Goal Plan"
          };
          const isActive = historySubTab === tab;
          return (
            <button 
              key={tab}
              onClick={() => setHistorySubTab(tab as any)}
              className={`px-5 py-2 text-xs font-bold uppercase tracking-wider border-t border-x rounded-t-lg transition-colors shrink-0 ${
                isActive 
                  ? 'bg-[#161616] border-zinc-800 border-b-transparent text-cyan-400 font-extrabold' 
                  : 'bg-transparent border-transparent text-zinc-500 hover:text-zinc-300'
              }`}
            >
              {labels[tab]}
            </button>
          );
        })}
      </div>

      {/* ────────────────────────────────────────────────────────
          📊 VIEW 1: TODAY'S PROGRESS PANEL
          ──────────────────────────────────────────────────────── */}
      {historySubTab === 'today' && (
        <div className="bg-[#161616] border border-zinc-800 rounded-lg p-6 space-y-6 shadow-xl">
          <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-widest">
            Today's Exercise Progress
          </h4>
          <div className="space-y-6">
            {todayProgressData.map((item, index) => {
              const percentage = Math.min(Math.round((item.current / item.target) * 100), 100);
              return (
                <div key={index} className="space-y-2 border-b border-zinc-900/40 pb-4 last:border-0 last:pb-0">
                  <div className="flex justify-between items-end text-sm">
                    <span className="font-bold text-zinc-200">{item.name}</span>
                    <span className="font-mono text-zinc-400 text-xs">
                      {item.current} <span className="text-zinc-700">/</span> {item.target} reps
                    </span>
                  </div>
                  <div className="w-full bg-[#0d0d0d] h-5 rounded-full overflow-hidden border border-zinc-800 relative flex items-center">
                    <div className="h-full bg-zinc-700 transition-all duration-500" style={{ width: `${percentage}%` }} />
                    <span className="absolute inset-0 flex items-center justify-center text-[10px] font-mono font-bold text-zinc-200 pointer-events-none">
                      {percentage}% Complete
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────
          📊 VIEW 2: WEEKLY STATS PANEL
          ──────────────────────────────────────────────────────── */}
      {historySubTab === 'weekly' && (
        <div className="bg-[#161616] border border-zinc-800 rounded-lg p-6 space-y-6 shadow-xl">
          <div className="space-y-4">
            <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Weekly Exercise Progress</h4>
            <div className="bg-[#0f0f0f] border border-zinc-800/80 rounded-lg p-4 space-y-4">
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-zinc-300 uppercase tracking-wide">Workout Days Per Week:</span>
                <span className="font-mono font-bold text-cyan-400 text-sm">{weeklyCompletedDays} / {weeklyPlannedDays}</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 border-t border-zinc-800/60 pt-3">
                <div>
                  <p className="text-[10px] font-bold text-zinc-600 uppercase tracking-wider">Completion</p>
                  <p className="text-sm font-mono font-bold text-zinc-200">{weeklyStats?.completion_percentage ?? 0}%</p>
                </div>
                <div>
                  <p className="text-[10px] font-bold text-zinc-600 uppercase tracking-wider">Active Days</p>
                  <p className="text-sm font-mono font-bold text-cyan-400">{weeklyCompletedDays} / {weeklyPlannedDays}</p>
                </div>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between border-t border-zinc-800/60 pt-3 gap-3">
                <span className="text-[11px] font-bold text-zinc-500 uppercase tracking-wider">Weekly Exercise Progress:</span>
                <div className="flex space-x-2">
                  {weeklyDaysCompletion.map((day, idx) => (
                    <div key={idx} className="flex flex-col items-center space-y-1">
                      <div className={`h-6 w-6 rounded-full border flex items-center justify-center ${day.completed ? 'border-cyan-400 bg-cyan-500/10' : 'border-zinc-800'}`}>
                        {day.completed && <span className="h-1.5 w-1.5 bg-cyan-400 rounded-full"></span>}
                      </div>
                      <span className="text-[9px] font-mono text-zinc-500 font-bold uppercase">{day.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <div className="space-y-3">
            <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Weekly Stats Log</h4>
            <div className="overflow-x-auto bg-[#0f0f0f] border border-zinc-800/80 rounded-lg">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-500 font-bold uppercase tracking-wider text-[10px]">
                    <th className="p-3 w-12 text-center">No.</th>
                    <th className="p-3">Exercise Type</th>
                    <th className="p-3 text-right pr-6">Count</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900/60 font-medium text-zinc-300">
                                    {weeklyExerciseData.map((row) => (
                    <tr key={row.rank} className="hover:bg-zinc-800/20 transition-colors">
                      <td className="p-3 text-center text-zinc-500 font-mono">{row.rank}</td>
                      <td className="p-3 text-zinc-200 font-semibold">{row.name}</td>
                      <td className="p-3 text-right pr-6 font-mono font-bold text-cyan-400">{row.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────
          📊 VIEW 3: MONTHLY STATS PANEL (CLEAN TRUE CALENDAR)
          ──────────────────────────────────────────────────────── */}
      {historySubTab === 'monthly' && (
        <div className="bg-[#161616] border border-zinc-800 rounded-lg p-6 space-y-6 shadow-xl font-sans animate-fadeIn">
          <div className="space-y-4">
            <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Monthly Exercise Progress</h4>
            <div className="bg-[#0f0f0f] border border-zinc-800/80 rounded-lg p-4 space-y-4">
              
              {/* 🌍 FIXED: Date header formatted strictly to English parameters */}
              <div className="flex justify-between items-center px-2">
                <button 
                  onClick={() => {
                    const newMonth = new Date(currentMonth);
                    newMonth.setMonth(newMonth.getMonth() - 1);
                    setCurrentMonth(newMonth);
                  }}
                  className="text-zinc-600 hover:text-zinc-400 font-bold text-sm select-none"
                >
                  &larr;
                </button>
                <span className="text-xs font-black text-zinc-200 uppercase tracking-wider">
                  {currentMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                </span>
                <button 
                  onClick={() => {
                    const newMonth = new Date(currentMonth);
                    newMonth.setMonth(newMonth.getMonth() + 1);
                    setCurrentMonth(newMonth);
                  }}
                  className="text-zinc-600 hover:text-zinc-400 font-bold text-sm select-none"
                >
                  &rarr;
                </button>
              </div>

              <div className="border-t border-zinc-800/60 pt-3 space-y-2">
                <div className="flex justify-between items-center text-xs px-2 mb-3">
                  <span className="font-bold text-zinc-400">Monthly Workout Stats:</span>
                  <span className="font-mono font-bold text-cyan-400 text-sm">
                    {monthlyStats?.days_active ? Object.values(monthlyStats.days_active).filter((v: any) => v).length : 0} / {new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0).getDate()} Days Active
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 px-2 mb-3">
                  <div>
                    <p className="text-[10px] font-bold text-zinc-600 uppercase tracking-wider">Completion</p>
                    <p className="text-sm font-mono font-bold text-zinc-200">{monthlyStats?.completion_percentage ?? 0}%</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-bold text-zinc-600 uppercase tracking-wider">Active Days</p>
                    <p className="text-sm font-mono font-bold text-cyan-400">
                      {monthlyStats?.days_active ? Object.values(monthlyStats.days_active).filter((v: any) => v).length : 0}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-7 gap-1.5 text-center">
                  {calendarDaysHeader.map((header, hIdx) => (
                    <span key={hIdx} className="text-[10px] font-bold text-zinc-600 uppercase">{header}</span>
                  ))}
                  
                  {/* 🌍 FIXED: Non-workout days rendering transparently without border shapes boxes */}
                  {calendarCells.map((cell, cIdx) => (
                    <div 
                      key={cIdx} 
                      className={`h-8 flex flex-col justify-between p-1 rounded transition-all ${
                        cell.dayNumber === "" 
                          ? 'bg-transparent' 
                          : cell.active 
                            ? 'border border-cyan-500/20 bg-cyan-500/5 text-cyan-400 font-extrabold shadow-sm' 
                            : 'bg-transparent text-zinc-700'
                      }`}
                    >
                      <span className="text-[9px] font-mono">{cell.dayNumber}</span>
                      {cell.active && <span className="h-0.5 w-full bg-cyan-500/40 rounded-full"></span>}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Monthly Stats Log</h4>
            <div className="overflow-x-auto bg-[#0f0f0f] border border-zinc-800/80 rounded-lg">
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-500 font-bold uppercase tracking-wider text-[10px]">
                    <th className="p-3 w-12 text-center">No.</th>
                    <th className="p-3">Exercise Type</th>
                    <th className="p-3 text-right pr-6">Count</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900/60 font-medium text-zinc-300">
                  {monthlyExerciseData.map((row) => (
                    <tr key={row.rank} className="hover:bg-zinc-800/20 transition-colors text-xs">
                      <td className="p-3 text-center text-zinc-500 font-mono">{row.rank}</td>
                      <td className="p-3 text-zinc-200 font-semibold">{row.name}</td>
                      <td className="p-3 text-right pr-6 font-mono font-bold text-cyan-400">{row.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────
          📊 VIEW 4: WEEKLY WORKOUT PLAN (SIMPLIFIED)
          ──────────────────────────────────────────────────────── */}
      {historySubTab === 'goals' && (
        <div className="bg-[#161616] border border-zinc-800 rounded-lg p-6 space-y-6 shadow-xl font-sans">
          
          <div className="space-y-1">
            <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Goal Plan</h4>
            <p className="text-[11px] text-zinc-500 font-medium">Your daily workout plan for the active week</p>
          </div>

          {loading ? (
            <div className="text-center py-8 text-zinc-500">Loading workout plan...</div>
          ) : !selectedPlan ? (
            <div className="bg-[#0f0f0f] p-6 rounded-xl border border-zinc-900 text-center text-zinc-500 text-sm">
              No workout plan available. Generate one in chat to get started!
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {weeklyWorkoutPlan.map((day) => (
                <div key={day.key} className="bg-[#0f0f0f] border border-zinc-800 rounded-lg p-4 space-y-3">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-3">
                      <h5 className="text-sm font-bold text-cyan-400 uppercase tracking-wider break-words">{day.label}</h5>
                      {day.wasSkipped && (
                        <span className="text-[10px] font-black uppercase tracking-wider px-2 py-1 rounded border border-amber-500/30 bg-amber-500/10 text-amber-400 shrink-0">
                          Skipped
                        </span>
                      )}
                    </div>
                    {day.wasSkipped && day.movedToDayNumber && (
                      <p className="text-[11px] text-amber-400/80">
                        Workout moved to Day {day.movedToDayNumber}.
                      </p>
                    )}
                  </div>
                  {day.exercises.length > 0 ? (
                    <div className="space-y-2">
                      {day.exercises.map((exercise: any, idx: number) => {
                        const exerciseName = getExerciseName(exercise);
                        const target = getExerciseTarget(exercise);
                        return (
                          <div key={idx} className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 p-2 bg-zinc-900/40 rounded border-l-2 border-cyan-500/40">
                            <span className="text-xs text-zinc-300 font-medium break-words">{exerciseName}</span>
                            {target && <span className="text-[10px] font-mono text-zinc-500 text-right break-words max-w-[180px]">{target}</span>}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-xs text-zinc-600 italic py-2">
                      {day.wasSkipped ? 'Skipped day' : 'Rest day'}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

    </div>
  );
}
