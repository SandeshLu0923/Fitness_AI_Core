import { useState, useEffect } from 'react';
import axios from 'axios';
import { Activity, ChevronDown } from 'lucide-react';
import { DailyChallengeCard } from './DashboardWidgets';
import TrainingWindow from './TrainingWindow';

interface WorkoutStats {
  found: boolean;
  exercise_name: string;
  sets_completed: number;
  correct_reps: number;
  incorrect_reps: number;
  total_reps?: number;
  target_sets?: number;
  target_reps_per_set?: number;
  progress_percent?: number;
  exercise_completed?: boolean;
  timestamp: string;
}

interface DashboardTabProps {
  onTriggerDiet: () => void;
  onTriggerWorkout: () => void;
  onTriggerGym: () => void;
  onOpenDiet: () => void;
  onOpenWorkout: () => void;
  userId: string;
  userName: string;
}

const DEFAULT_EXERCISES = [
  { name: "Jumping Jacks", sets: 3, reps: 30, rest_seconds: 60 },
  { name: "Squats", sets: 3, reps: 15, rest_seconds: 90 },
  { name: "Pushups", sets: 3, reps: 15, rest_seconds: 90 },
  { name: "Pullups", sets: 4, reps: 10, rest_seconds: 120 },
  { name: "Situps", sets: 3, reps: 20, rest_seconds: 60 }
];

export default function DashboardTab({ onTriggerDiet, onTriggerWorkout, onTriggerGym, onOpenDiet, onOpenWorkout, userId, userName }: DashboardTabProps) {
  const [exercise, setExercise] = useState<string>('jumping-jacks');
  const [statusMsg, setStatusMsg] = useState('System is idle.');
  const [activePlan, setActivePlan] = useState<any>(null);
  const [planOverview, setPlanOverview] = useState<any>(null);
  const [todaysChallenges, setTodaysChallenges] = useState<any[]>([]);
  const [todaysExercises, setTodaysExercises] = useState<any[]>([]);
  const [plannedExercises, setPlannedExercises] = useState<any[]>([]);
  const [completedWorkouts, setCompletedWorkouts] = useState<any[]>([]);
  const [isChallengeActivated, setIsChallengeActivated] = useState(false);
  const [isTodaySkipped, setIsTodaySkipped] = useState(false);
  const [showTrainingWindow, setShowTrainingWindow] = useState(false);
  const [activeTrainingExercise, setActiveTrainingExercise] = useState<any>(null);
  const [nutritionSummary, setNutritionSummary] = useState<any>(null);
  const [mealInput, setMealInput] = useState('');
  const [nutritionLogging, setNutritionLogging] = useState(false);
  const [nutritionLogMessage, setNutritionLogMessage] = useState('');
  
  const [stats, setStats] = useState<WorkoutStats>({
    found: false,
    exercise_name: 'None',
    sets_completed: 0,
    correct_reps: 0,
    incorrect_reps: 0,
    timestamp: 'N/A'
  });

  const fetchMacrocycleState = async () => {
    try {
      const res = await axios.get(`http://localhost:8000/api/habit-tracker/active-day-plan?user_id=${encodeURIComponent(userId)}`);
      if (res.data && res.data.day_details) {
        setActivePlan(res.data);
        const notes = String(res.data.day_details.notes || '').toLowerCase();
        const hasNoActiveBlock = notes.includes('no active macrocycle') || Boolean(res.data.message);
        if (res.data.day_details.was_skipped) {
          setIsTodaySkipped(true);
          setPlannedExercises([]);
          setTodaysExercises([]);
          setTodaysChallenges([]);
          return;
        }
        setIsTodaySkipped(false);
        const normalizedExercises = normalizeDayExercises(res.data.day_details.exercises || []);
        if (normalizedExercises.length > 0) {
          setPlannedExercises(normalizedExercises);
          setTodaysChallenges([normalizeDayChallenge(res.data.day_details, res.data.current_active_day, res.data.difficulty_multiplier)]);
          return;
        }
        if (!hasNoActiveBlock) {
          setPlannedExercises([]);
          setTodaysExercises([]);
          setTodaysChallenges([]);
          return;
        }
      }
      await fetchLatestWorkoutPlan();
    } catch {
      console.log("[MACROCYCLE_SYNC_OFFLINE] No active program block loaded yet.");
      await fetchLatestWorkoutPlan();
    }
  };

  const fetchDefaultWorkout = async () => {
    try {
      setIsTodaySkipped(false);
      setTodaysChallenges([]);
      const res = await axios.get('http://localhost:8000/api/plans/workout/default/today');
      if (res.data && res.data.workout && res.data.workout.exercises) {
        const normalized = normalizeDayExercises(res.data.workout.exercises);
        setPlannedExercises(normalized);
      }
    } catch {
      console.log("[TODAYS_WORKOUT_FETCH] Using default exercises.");
      setPlannedExercises(DEFAULT_EXERCISES);
    }
  };

  const fetchLatestWorkoutPlan = async () => {
    try {
      setIsTodaySkipped(false);
      const res = await axios.get(`http://localhost:8000/api/plans/workout-plans/${encodeURIComponent(userId)}/latest`);
      const plan = res.data?.plan;
      const todayPlan = extractTodayWorkoutPlan(plan);
      if (todayPlan) {
        const normalized = normalizeDayExercises(todayPlan.exercises || []);
        setPlannedExercises(normalized);
        setTodaysChallenges([normalizePlanChallenge(todayPlan, plan)]);
        return;
      }
      await fetchDefaultWorkout();
    } catch {
      console.log("[LATEST_WORKOUT_PLAN_FETCH] Falling back to default workout.");
      await fetchDefaultWorkout();
    }
  };

  const fetchPlanOverview = async () => {
    try {
      const res = await axios.get(`http://localhost:8000/api/plans/overview/${encodeURIComponent(userId)}`);
      setPlanOverview(res.data);
    } catch {
      console.log("[PLAN_OVERVIEW_FETCH] No plan overview available yet.");
    }
  };

  const fetchLatestStats = async () => {
    try {
      const res = await axios.get(`http://localhost:8000/api/gym-trainer/latest-stats/${userId}`);
      if (res.data && res.data.found) {
        setStats(res.data);
      }
    } catch (err) {
      console.error("[STATS_SYNC_ERROR]", err);
    }
  };

  const fetchCompletedWorkouts = async () => {
    try {
      const res = await axios.get(`http://localhost:8000/api/gym-trainer/completed-workouts/${encodeURIComponent(userId)}`);
      setCompletedWorkouts(res.data.completed_workouts || []);
    } catch (err) {
      console.error("[COMPLETED_WORKOUTS_SYNC_ERROR]", err);
      setCompletedWorkouts([]);
    }
  };

  const fetchNutritionSummary = async () => {
    try {
      const res = await axios.get(`http://localhost:8000/api/dietician/nutrition-summary/${encodeURIComponent(userId)}?days=7`);
      setNutritionSummary(res.data);
    } catch {
      console.log("[NUTRITION_SUMMARY_FETCH] No nutrition intake logs available yet.");
      setNutritionSummary(null);
    }
  };

  const handleLogMeal = async () => {
    const trimmed = mealInput.trim();
    if (!trimmed || nutritionLogging) return;

    setNutritionLogging(true);
    setNutritionLogMessage('');
    try {
      const userInput = isFollowedDietPlanInput(trimmed)
        ? await buildTodayDietPlanMealInput()
        : trimmed;
      const response = await axios.post('http://localhost:8000/api/dietician/log-meal', {
        user_id: userId,
        user_input: userInput
      });
      const calories = response.data?.total_meal_calories;
      setMealInput('');
      setNutritionLogMessage(calories ? `Meal logged: ${calories} kcal` : 'Meal logged.');
      await fetchNutritionSummary();
    } catch (error: any) {
      console.error('[MEAL_LOG_ERROR]', error);
      setNutritionLogMessage(error.response?.data?.detail || 'Failed to log meal.');
    } finally {
      setNutritionLogging(false);
    }
  };

  async function handleLogFollowedDietPlan() {
    if (nutritionLogging) return;
    setMealInput('Followed diet plan');
    setNutritionLogging(true);
    setNutritionLogMessage('');
    try {
      const userInput = await buildTodayDietPlanMealInput();
      const response = await axios.post('http://localhost:8000/api/dietician/log-meal', {
        user_id: userId,
        user_input: userInput
      });
      const calories = response.data?.total_meal_calories;
      setMealInput('');
      setNutritionLogMessage(calories ? `Today's diet plan logged: ${calories} kcal` : "Today's diet plan logged.");
      await fetchNutritionSummary();
    } catch (error: any) {
      console.error('[FOLLOWED_DIET_PLAN_LOG_ERROR]', error);
      setNutritionLogMessage(error.response?.data?.detail || 'Failed to log today\'s diet plan.');
    } finally {
      setNutritionLogging(false);
    }
  }

  function isFollowedDietPlanInput(value: string) {
    return /^(i\s+)?(followed|completed|ate)\s+(the\s+)?(today'?s\s+)?diet\s+plan\.?$/i.test(value.trim());
  }

  async function buildTodayDietPlanMealInput() {
    const response = await axios.get(`http://localhost:8000/api/plans/diet-plans/${encodeURIComponent(userId)}`);
    const plan = response.data?.plans?.[0];
    const today = extractTodayDietDay(plan);
    if (!today || today.meals.length === 0) {
      throw new Error('No meals found in today\'s diet plan.');
    }
    return `User followed today's diet plan exactly. Date: ${today.date || localIsoDate(new Date())}. Meals: ${today.meals.map((meal: any, index: number) => `${mealLabel(meal, index)}: ${mealDetails(meal)}`).join('; ')}.`;
  }

  function extractTodayDietDay(plan: any) {
    if (!plan?.diet_plan) return null;
    const rawPlan = plan.diet_plan;
    const source = rawPlan.weekly_plan && typeof rawPlan.weekly_plan === 'object' ? rawPlan.weekly_plan : rawPlan;
    const startDate = parseLocalDate(plan.start_date || firstDietDay(source)?.date || plan.created_at);
    const days = Array.isArray(source.days)
      ? source.days.map((day: any, index: number) => normalizeDietDay(day, index, startDate))
      : Object.keys(source)
          .filter(key => key.toLowerCase().startsWith('day'))
          .sort((a, b) => extractDayNumber(a) - extractDayNumber(b))
          .map((key, index) => normalizeDietDay(source[key], index, startDate));

    const todayKey = localIsoDate(new Date());
    return days.find((day: any) => day.date === todayKey) || days[0] || null;
  }

  function firstDietDay(source: any) {
    if (Array.isArray(source?.days)) return source.days[0];
    if (!source || typeof source !== 'object') return null;
    const firstKey = Object.keys(source)
      .filter(key => key.toLowerCase().startsWith('day'))
      .sort((a, b) => extractDayNumber(a) - extractDayNumber(b))[0];
    return firstKey ? source[firstKey] : null;
  }

  function normalizeDietDay(day: any, index: number, startDate: Date | null) {
    const date = startDate ? new Date(startDate) : parseLocalDate(day?.date);
    if (date && startDate) date.setDate(date.getDate() + index);
    return {
      date: date ? localIsoDate(date) : undefined,
      meals: Array.isArray(day?.meals) ? day.meals : []
    };
  }

  function mealLabel(meal: any, index: number) {
    if (!meal || typeof meal !== 'object') return `Meal ${index + 1}`;
    return meal.time || meal.meal_type || meal.type || `Meal ${index + 1}`;
  }

  function mealDetails(meal: any) {
    if (typeof meal === 'string') return meal;
    if (!meal || typeof meal !== 'object') return 'meal details not listed';
    if (Array.isArray(meal.items)) return meal.items.join(', ');
    if (Array.isArray(meal.foods)) return meal.foods.join(', ');
    if (meal.name) return meal.name;
    return Object.entries(meal)
      .filter(([key]) => !['time', 'meal_type', 'type'].includes(key))
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`)
      .join(', ') || 'meal details not listed';
  }

  useEffect(() => {
    if (!userId) return;
    fetchLatestStats();
    fetchCompletedWorkouts();
    fetchPlanOverview();
    fetchMacrocycleState();
    fetchNutritionSummary();
  }, [userId]);

  useEffect(() => {
    if (!userId) return;
    const interval = window.setInterval(() => {
      fetchLatestStats();
      fetchCompletedWorkouts();
    }, 5000);
    return () => window.clearInterval(interval);
  }, [userId]);

  useEffect(() => {
    const completedKeys = new Set(completedWorkouts.map((workout) => exerciseKey(workout.exercise_name)));
    const remaining = plannedExercises.filter((item) => !completedKeys.has(exerciseKey(item.name)));
    setTodaysExercises(remaining);
    if (remaining.length > 0 && !remaining.some((item) => exerciseKey(item.name) === exercise)) {
      setExercise(exerciseKey(remaining[0].name));
    }
  }, [plannedExercises, completedWorkouts]);

  useEffect(() => {
    setIsChallengeActivated(isStoredChallengeActivated());
    const syncActivation = () => setIsChallengeActivated(isStoredChallengeActivated());
    window.addEventListener('challenge-activation-changed', syncActivation);
    return () => window.removeEventListener('challenge-activation-changed', syncActivation);
  }, [userId, todaysChallenges]);

  const handleStartTracker = (exerciseType?: string) => {
    const selectedKey = exerciseType ? exerciseKey(exerciseType) : exercise;
    const selectedExercise = plannedExercises.find((item) => exerciseKey(item.name) === selectedKey)
      || todaysExercises.find((item) => exerciseKey(item.name) === selectedKey)
      || DEFAULT_EXERCISES.find((item) => exerciseKey(item.name) === selectedKey)
      || { name: selectedKey, sets: 1, reps: 10 };
    setExercise(exerciseKey(selectedExercise.name));
    setActiveTrainingExercise(selectedExercise);
    setShowTrainingWindow(true);
    setStatusMsg('Opening training window...');
  };

  const handleDietCardClick = () => {
    if (planOverview?.diet?.exists && !planOverview?.diet?.is_completed) {
      onOpenDiet();
      return;
    }
    onTriggerDiet();
  };

  const handleWorkoutCardClick = () => {
    if (planOverview?.workout?.exists && !planOverview?.workout?.is_completed) {
      onOpenWorkout();
      return;
    }
    onTriggerWorkout();
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

  function normalizeDayExercises(exercises: any[]) {
    if (!Array.isArray(exercises)) return [];
    return exercises.map((item: any) => ({
      name: item.name || item.exercise_name || item.exercise || 'Exercise',
      sets: item.sets || item.prescribed_sets || 1,
      reps: item.reps || item.prescribed_reps || item.sets_reps || 'As prescribed',
      rest_seconds: item.rest_seconds || item.rest || 60,
      notes: item.notes || item.trainer_execution_note || ''
    }));
  }

  function activeChallengeKey() {
    const challenge = todaysChallenges[0];
    if (!challenge) return '';
    const date = localIsoDate(new Date());
    return `active_challenge:${userId}:${date}`;
  }

  function isStoredChallengeActivated() {
    const key = activeChallengeKey();
    return key ? localStorage.getItem(key) === 'true' : false;
  }

  function activateChallenge() {
    const key = activeChallengeKey();
    if (!key) return;
    localStorage.setItem(key, 'true');
    setIsChallengeActivated(true);
    window.dispatchEvent(new CustomEvent('challenge-activation-changed'));
  }

  function handleChallengeAction() {
    if (!isChallengeActivated) {
      activateChallenge();
      return;
    }
    handleStartTracker();
  }

  async function handleSkipToday() {
    if (!window.confirm("Skip today's workout and shift it to the next available day?")) return;

    try {
      const response = await axios.post('http://localhost:8000/api/habit-tracker/skip-active-day', {
        user_id: userId,
        reason: 'Skipped from dashboard'
      });
      setStatusMsg(response.data?.message || 'Workout skipped and shifted.');
      localStorage.removeItem(activeChallengeKey());
      setIsChallengeActivated(false);
      await fetchCompletedWorkouts();
      await fetchPlanOverview();
      await fetchMacrocycleState();
      window.dispatchEvent(new CustomEvent('workout-plan-shifted'));
    } catch (error: any) {
      console.error('[SKIP_DAY_ERROR]', error);
      setStatusMsg(error.response?.data?.detail || 'Failed to skip workout.');
    }
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
    const datedDay = days.find((day: any) => day?.date === today);
    if (datedDay) return datedDay;

    const start = parseLocalDate(plan.start_date || days[0]?.date || plan.created_at);
    if (!start) return days[0];
    const diff = Math.floor((parseLocalDate(today)!.getTime() - start.getTime()) / 86400000);
    return days[Math.max(0, Math.min(diff, days.length - 1))];
  }

  function normalizePlanChallenge(dayPlan: any, plan: any) {
    const dayNumber = Number(dayPlan?.__dayNumber || dayPlan?.day_number || dayPlan?.day || 1);
    const challenge = Array.isArray(plan?.daily_challenges)
      ? plan.daily_challenges.find((item: any) => Number(item.day) === dayNumber) || plan.daily_challenges[dayNumber - 1]
      : null;
    return {
      title: challenge?.challenge || `Day ${dayNumber} Challenge`,
      description: challenge?.description || dayPlan?.daily_metric_challenge || 'Complete today\'s workout with controlled form.',
      difficulty: plan?.difficulty_multiplier || 'Medium',
      metrics: challenge ? { reps: challenge.reps, sets: challenge.sets, duration: challenge.duration } : null
    };
  }

  function normalizeDayChallenge(dayDetails: any, currentDay: number, difficulty?: string) {
    const text = dayDetails?.daily_metric_challenge || dayDetails?.challenge || 'Complete today\'s workout with controlled form.';
    return {
      title: `Day ${currentDay || dayDetails?.day_number || 1} Challenge`,
      description: text,
      difficulty: difficulty || 'Medium',
      metrics: null
    };
  }

  function extractDayNumber(value: string) {
    const match = String(value).match(/\d+/);
    return match ? Number(match[0]) : 0;
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

  function localIsoDate(date: Date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function numericTarget(value: any, fallback = 1) {
    if (typeof value === 'number' && Number.isFinite(value)) return Math.max(1, Math.round(value));
    const match = String(value ?? '').match(/\d+/);
    return match ? Math.max(1, Number(match[0])) : fallback;
  }

  function completedWorkoutFor(exerciseItem: any) {
    const key = exerciseKey(exerciseItem?.name);
    const targetSets = numericTarget(exerciseItem?.sets, 1);
    const targetReps = numericTarget(exerciseItem?.reps, 10);
    const targetTotal = targetSets * targetReps;
    return completedWorkouts.find((workout) => {
      if (exerciseKey(workout.exercise_name) !== key) return false;
      const loggedSets = Number(workout.sets_completed || 0);
      const loggedReps = Number(workout.total_reps ?? workout.correct_reps ?? 0);
      return loggedSets >= targetSets && loggedReps >= targetTotal;
    });
  }

  function progressForExercise(exerciseItem: any) {
    const targetSets = numericTarget(exerciseItem?.sets, 1);
    const targetReps = numericTarget(exerciseItem?.reps, 10);
    const targetTotal = targetSets * targetReps;
    const completed = completedWorkoutFor(exerciseItem);
    const liveMatch = stats.found && exerciseKey(stats.exercise_name) === exerciseKey(exerciseItem?.name);
    const doneReps = completed
      ? Number(completed.total_reps ?? completed.correct_reps ?? targetTotal)
      : liveMatch
        ? Number(stats.total_reps || stats.correct_reps || 0)
        : 0;
    const doneSets = completed
      ? Number(completed.sets_completed || targetSets)
      : liveMatch
        ? Number(stats.sets_completed || 0)
        : 0;
    const percent = Math.min(100, Math.round((doneReps / Math.max(targetTotal, 1)) * 100));
    const currentSetReps = completed
      ? targetReps
      : doneReps > 0
        ? Math.min(doneReps - (doneSets * targetReps), targetReps)
        : 0;
    return {
      targetSets,
      targetReps,
      targetTotal,
      doneReps: Math.min(doneReps, targetTotal),
      doneSets: Math.min(doneSets, targetSets),
      currentSetReps,
      percent,
      isCompleted: Boolean(completed) || percent >= 100
    };
  }

  function workoutProgressCard(exerciseItem: any, idx: number, mode: 'active' | 'completed' = 'active') {
    const progress = progressForExercise(exerciseItem);
    const isCompletedMode = mode === 'completed' || progress.isCompleted;
    return (
      <div
        key={`${exerciseKey(exerciseItem.name)}-${idx}`}
        className={`flex-shrink-0 w-full sm:w-[320px] p-4 border rounded-lg bg-[#0f0f0f] transition-all space-y-4 ${
          isCompletedMode ? 'border-green-500/40' : 'border-zinc-800/80 hover:border-cyan-500/40'
        }`}
      >
        <div className="flex items-start gap-3">
          <span className={`h-7 w-7 rounded border text-xs font-black flex items-center justify-center shrink-0 ${
            isCompletedMode
              ? 'bg-green-500/10 border-green-500/30 text-green-400'
              : 'bg-cyan-500/10 border-cyan-500/20 text-cyan-400'
          }`}>
            {idx + 1}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <span className="text-sm font-bold text-zinc-100 block break-words">{exerciseItem.name}</span>
              {isCompletedMode && (
                <span className="text-[10px] bg-green-500/15 text-green-400 border border-green-500/20 rounded px-2 py-0.5 uppercase font-bold">
                  Completed
                </span>
              )}
            </div>
            {exerciseItem.notes && <p className="text-[11px] text-zinc-500 mt-1 line-clamp-2">{exerciseItem.notes}</p>}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          {metricBlock('Sets', `${progress.doneSets}/${progress.targetSets}`)}
          {metricBlock('Reps', `${progress.currentSetReps}/${progress.targetReps}`)}
          {metricBlock('Rest', `${exerciseItem.rest_seconds}s`)}
        </div>

        {isCompletedMode ? (
          <div className="rounded-lg border border-green-500/20 bg-green-500/10 px-3 py-2 text-center text-[10px] font-black uppercase tracking-wider text-green-400">
            Completed
          </div>
        ) : (
          <div className="space-y-1">
            <div className="h-2 bg-zinc-900 rounded-full overflow-hidden border border-zinc-800">
              <div className="h-full bg-cyan-500 transition-all" style={{ width: `${progress.percent}%` }} />
            </div>
            <div className="flex items-center justify-between text-[10px] text-zinc-500">
              <span>{progress.percent}% complete</span>
              <span>{progress.doneReps}/{progress.targetTotal} total reps</span>
            </div>
          </div>
        )}
      </div>
    );
  }

  function metricBlock(label: string, value: any) {
    return (
      <div className="bg-[#161616] px-2 py-2 rounded-lg border border-zinc-800 text-center min-w-0">
        <span className="text-[9px] text-zinc-500 block uppercase tracking-wide">{label}</span>
        <span className="text-sm font-bold text-cyan-400 mt-1 block break-words leading-snug">{String(value ?? 'N/A')}</span>
      </div>
    );
  }

  return (
    <div className="w-full mx-auto space-y-6 font-sans antialiased text-zinc-300">
      
      {/* 👋 PREMIUM MINIMALIST GREETINGS SECTION */}
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 pt-1">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100 tracking-tight">
            Welcome back, <span className="text-zinc-100 font-black">Hello {userName || 'User'}!</span>
          </h1>
          <p className="text-xs text-zinc-500 font-medium mt-0.5">Here is your fitness analysis overview.</p>
        </div>

        {/* Dynamic Action Trigger Card Grid Layout Bar */}
        <div className="grid grid-cols-3 gap-3 w-full lg:w-auto">
          {/* Diet Interaction Card */}
          <div 
            onClick={handleDietCardClick}
            className="flex items-center space-x-4 bg-[#161616] border border-zinc-800 px-5 py-2 rounded-lg shadow-sm cursor-pointer hover:border-cyan-500/40 transition-all"
          >
            <span className="h-1.5 w-1.5 bg-green-400 rounded-full shrink-0"></span>
            <div>
              <p className="text-[10px] font-bold tracking-widest text-zinc-500 uppercase">Nutrition Coach</p>
              <p className="text-xs text-zinc-200 font-black">{planOverview?.diet?.label || 'Plan your Diet'}</p>
            </div>
          </div>
          
          {/* Workout Interaction Card */}
          <div 
            onClick={handleWorkoutCardClick}
            className="flex items-center space-x-4 bg-[#161616] border border-zinc-800 px-5 py-2 rounded-lg shadow-sm cursor-pointer hover:border-cyan-500/40 transition-all"
          >
            <span className="h-1.5 w-1.5 bg-cyan-400 rounded-full shrink-0"></span>
            <div>
              <p className="text-[10px] font-bold tracking-widest text-zinc-500 uppercase">Training Planner</p>
              <p className="text-xs text-zinc-200 font-black">{planOverview?.workout?.label || 'Plan Workout'}</p>
            </div>
          </div>

          {/* Find Gyms Interaction Card */}
          <div 
            onClick={onTriggerGym}
            className="flex items-center space-x-4 bg-[#161616] border border-zinc-800 px-5 py-2 rounded-lg shadow-sm cursor-pointer hover:border-cyan-500/40 transition-all"
          >
            <span className="h-1.5 w-1.5 bg-purple-400 rounded-full shrink-0"></span>
            <div>
              <p className="text-[10px] font-bold tracking-widest text-zinc-500 uppercase">Location Mapper</p>
              <p className="text-xs text-zinc-200 font-black">Find Gyms</p>
            </div>
          </div>
        </div>
      </div>

      <NutritionIntakeOverview
        summary={nutritionSummary}
        mealInput={mealInput}
        onMealInputChange={setMealInput}
        onLogMeal={handleLogMeal}
        onLogFollowedDietPlan={handleLogFollowedDietPlan}
        isLogging={nutritionLogging}
        logMessage={nutritionLogMessage}
      />

      {/* 📊 REAL-TIME WORKOUT TRACKER & ACTIVE DECK GRID LAYER */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-stretch">
        
        {/* Real-Time Gym Trainer Engine Card Module */}
        <div className="lg:col-span-2 bg-[#161616] border border-zinc-800 rounded-lg p-6 flex flex-col justify-center">
          <div className="space-y-4 w-full">
            <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-widest">
              Gym Trainer Tracking Engine
            </h3>

            {/* Target Stance Selector Fields Interface Blocks Panel */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end bg-[#0f0f0f] p-4 rounded-lg border border-zinc-900">
              <div className="sm:col-span-2">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-zinc-500 mb-1.5">Select Exercise</label>
                <select
                  value={todaysExercises.length > 0 ? exercise : ''}
                  onChange={(e) => {
                    setExercise(e.target.value);
                  }}
                  className="w-full bg-[#161616] border border-zinc-800 rounded-lg px-3 py-2 text-sm font-bold text-zinc-300 focus:outline-none focus:border-cyan-500"
                >
                  {todaysExercises.length > 0 ? (
                    todaysExercises.map((ex) => (
                      <option key={ex.name} value={exerciseKey(ex.name)}>
                        {ex.name}
                      </option>
                    ))
                  ) : plannedExercises.length > 0 ? (
                    <option value="">All planned exercises completed</option>
                  ) : (
                    <>
                      <option value="jumping-jacks">Jumping Jacks</option>
                      <option value="squats">Squats</option>
                      <option value="pushups">Pushups</option>
                      <option value="pullups">Pullups</option>
                      <option value="situps">Situps</option>
                    </>
                  )}
                </select>
              </div>
              <button
                onClick={() => handleStartTracker()}
                disabled={todaysExercises.length === 0}
                className={`w-full font-black py-2 rounded-lg text-xs tracking-wider uppercase flex items-center justify-center space-x-2 transition-all font-sans ${
                  todaysExercises.length === 0
                    ? 'bg-zinc-800 text-zinc-600 cursor-not-allowed'
                    : 'bg-cyan-500 hover:bg-cyan-600 text-zinc-950'
                }`}
              >
                <span>Start Workout</span>
              </button>
            </div>
          </div>
        </div>

        {/* Daily Challenge Card Component */}
        <div className="w-full">
          {todaysChallenges && todaysChallenges.length > 0 ? (
            <div className="bg-[#161616] border border-zinc-800 rounded-lg p-6 space-y-4 font-sans">
              <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-widest">
                Today's Challenge
              </h4>
              
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h5 className="text-sm font-bold text-zinc-100">
                    {todaysChallenges[0].title || 'Today Challenge'}
                  </h5>
                  <span className="text-[10px] font-bold px-2 py-1 bg-green-500/20 text-green-400 rounded">
                    {todaysChallenges[0].difficulty || 'Medium'}
                  </span>
                </div>
                
                <p className="text-xs text-zinc-400">{todaysChallenges[0].description}</p>
                
                {/* Metrics */}
                {todaysChallenges[0].metrics && (
                  <div className="grid grid-cols-3 gap-2 pt-2 border-t border-zinc-800">
                    {todaysChallenges[0].metrics.reps && (
                      <div className="bg-[#0f0f0f] px-3 py-2 rounded text-center">
                        <span className="text-[10px] text-zinc-500 block uppercase">Reps</span>
                        <span className="text-sm font-bold text-cyan-400">{todaysChallenges[0].metrics.reps}</span>
                      </div>
                    )}
                    {todaysChallenges[0].metrics.sets && (
                      <div className="bg-[#0f0f0f] px-3 py-2 rounded text-center">
                        <span className="text-[10px] text-zinc-500 block uppercase">Sets</span>
                        <span className="text-sm font-bold text-cyan-400">{todaysChallenges[0].metrics.sets}</span>
                      </div>
                    )}
                    {todaysChallenges[0].metrics.duration && (
                      <div className="bg-[#0f0f0f] px-3 py-2 rounded text-center">
                        <span className="text-[10px] text-zinc-500 block uppercase">Duration</span>
                        <span className="text-sm font-bold text-cyan-400">{todaysChallenges[0].metrics.duration}</span>
                      </div>
                    )}
                  </div>
                )}
                
                <button onClick={handleChallengeAction} className="w-full bg-cyan-500 hover:bg-cyan-600 text-zinc-950 font-bold py-2 rounded-lg text-xs tracking-wider uppercase transition-all mt-3">
                  {isChallengeActivated ? 'Start Challenge' : 'Activate Plan'}
                </button>
              </div>
            </div>
          ) : (
            <DailyChallengeCard 
              dayPlan={activePlan ? activePlan.day_details : null}
              difficultyMultiplier={activePlan ? activePlan.difficulty_multiplier : 'No Active Block'}
              onCompleteDay={async () => { fetchMacrocycleState(); fetchPlanOverview(); }}
              onLaunchCVTracker={handleStartTracker}
            />
          )}
        </div>
      </div>

      {/* ↔️ UPGRADED COMPACT HORIZONTAL SCROLL TRACK */}
      <div className="bg-[#161616] border border-zinc-800 rounded-lg p-6 space-y-4 w-full font-sans">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-widest">
            Today's Workout Plan
          </h4>
          {plannedExercises.length > 0 && plannedExercises.some((item) => !progressForExercise(item).isCompleted) && !isTodaySkipped && (
            <button
              onClick={handleSkipToday}
              className="w-full sm:w-auto bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-zinc-300 font-bold px-4 py-2 rounded-lg text-xs tracking-wider uppercase transition-all"
            >
              Skip Today
            </button>
          )}
        </div>

        {/* Display All Daily Exercises in Horizontal Scrolling Cards */}
        <div className="flex space-x-4 overflow-x-auto pb-3 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent">
          {isTodaySkipped ? (
            <div className="w-full text-center p-8 bg-[#0f0f0f] border border-amber-500/20 rounded-lg">
              <p className="text-sm font-bold text-amber-400 uppercase tracking-wider">Skipped Today</p>
              <p className="text-xs text-zinc-500 mt-2">Today's workout was moved to the next available training slot.</p>
            </div>
          ) : plannedExercises.some((item) => !progressForExercise(item).isCompleted) ? (
            plannedExercises
              .filter((exerciseItem) => !progressForExercise(exerciseItem).isCompleted)
              .map((exerciseItem, idx) => workoutProgressCard(exerciseItem, idx, 'active'))
          ) : (
            <div className="text-zinc-500 text-xs uppercase p-4 italic tracking-wider">
              {plannedExercises.length > 0
                ? "All planned exercises for today are completed."
                : 'No routine active for today. Tap "Plan Workout" to map a training macrocycle!'}
            </div>
          )}
        </div>
      </div>

      {/* ✅ COMPLETED WORKOUTS SECTION */}
      <div className="bg-[#161616] border border-zinc-800 rounded-lg p-6 space-y-4 w-full font-sans">
        <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-widest">
          ✅ Completed Workouts Today
        </h4>

        <div className="space-y-3">
          {plannedExercises.some((item) => progressForExercise(item).isCompleted) ? (
            <div className="flex space-x-4 overflow-x-auto pb-3 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent">
              {plannedExercises
                .filter((exerciseItem) => progressForExercise(exerciseItem).isCompleted)
                .map((exerciseItem, idx) => workoutProgressCard(exerciseItem, idx, 'completed'))}
            </div>
          ) : (
            <div className="text-center py-8 text-zinc-500">
              <p className="text-sm">No workouts completed yet today.</p>
              <p className="text-xs text-zinc-600 mt-2">Start a workout to track your progress!</p>
            </div>
          )}
        </div>
      </div>

      {/* Training Window Modal */}
      {showTrainingWindow && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-4xl max-h-screen overflow-y-auto relative">
            <button
              onClick={() => {
                setShowTrainingWindow(false);
                setActiveTrainingExercise(null);
              }}
              className="absolute top-4 right-4 z-10 bg-zinc-900 hover:bg-zinc-800 text-white rounded-full p-2 transition-colors"
              title="Close"
            >
              ✕
            </button>
            <TrainingWindow
              userId={userId}
              exerciseType={exercise}
              targetSets={numericTarget(activeTrainingExercise?.sets, 1)}
              targetReps={numericTarget(activeTrainingExercise?.reps, 10)}
              onComplete={(stats) => {
                setStats(stats as any);
                setShowTrainingWindow(false);
                setActiveTrainingExercise(null);
                fetchLatestStats();
                fetchCompletedWorkouts();
                fetchMacrocycleState();
              }}
            />
          </div>
        </div>
      )}

      {/* Global Status Banner Information Board Console Footer */}
      <div className="p-3.5 bg-[#161616] rounded-lg border border-zinc-800 flex flex-col sm:flex-row items-start sm:items-center justify-between text-xs font-mono text-zinc-500 gap-2 px-5">
        <div className="flex items-center space-x-2">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse shrink-0"></span>
          <p className="italic text-xs">Status: "{statusMsg}"</p>
        </div>
        {stats.found && (
          <p className="text-[10px] text-zinc-600 uppercase tracking-widest font-mono">Sync Reference Profile ID: {stats.timestamp}</p>
        )}
      </div>

    </div>
  );
}

function NutritionIntakeOverview({
  summary,
  mealInput,
  onMealInputChange,
  onLogMeal,
  onLogFollowedDietPlan,
  isLogging,
  logMessage
}: {
  summary: any;
  mealInput: string;
  onMealInputChange: (value: string) => void;
  onLogMeal: () => void;
  onLogFollowedDietPlan: () => void;
  isLogging: boolean;
  logMessage: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const today = summary?.today || {};
  const target = Number(today.calorie_target || 0);
  const calories = Number(today.calories || 0);
  const remaining = target > 0 ? Math.max(target - calories, 0) : today.remaining_calories;
  const progress = target > 0 ? Math.min(Math.round((calories / target) * 100), 100) : 0;
  const recentLogs = Array.isArray(summary?.recent_logs) ? summary.recent_logs.slice(0, 3) : [];

  return (
    <section className="bg-[#161616] border border-zinc-800 rounded-lg p-5 space-y-4">
      <button
        type="button"
        onClick={() => setExpanded(prev => !prev)}
        className="w-full flex flex-col md:flex-row md:items-center md:justify-between gap-3 text-left"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-3">
          <span className="h-9 w-9 rounded-lg border border-cyan-500/20 bg-cyan-500/10 text-cyan-400 flex items-center justify-center shrink-0">
            <Activity size={17} />
          </span>
          <div>
            <h3 className="text-xs font-bold text-zinc-200 uppercase tracking-widest">Today&apos;s Nutrition Intake</h3>
            <p className="text-xs text-zinc-500 mt-1">Tracked from meals logged through the diet coach.</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">
            {today.meal_count || 0} meals logged
          </span>
          <ChevronDown
            size={16}
            className={`text-zinc-500 transition-transform ${expanded ? 'rotate-180' : ''}`}
          />
        </div>
      </button>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <NutritionMetric label="Calories" value={`${Math.round(calories)} / ${target || 'N/A'}`} />
        <NutritionMetric label="Remaining" value={target > 0 ? Math.round(remaining) : 'N/A'} />
        <NutritionMetric label="Protein" value={`${Math.round(today.protein_g || 0)}g`} />
        <NutritionMetric label="Carbs / Fat" value={`${Math.round(today.carbs_g || 0)}g / ${Math.round(today.fats_g || 0)}g`} />
      </div>

      <div className="space-y-2">
        <div className="h-2 rounded-full bg-zinc-800 overflow-hidden">
          <div className="h-full bg-cyan-500 transition-all" style={{ width: `${progress}%` }} />
        </div>
        {expanded && (
          <>
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-3 pt-2">
          <input
            value={mealInput}
            onChange={(event) => onMealInputChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                onLogMeal();
              }
            }}
            placeholder="Log meal, e.g., 2 idlis with sambar and one banana"
            className="w-full bg-[#0f0f0f] border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-cyan-500"
          />
          <button
            type="button"
            onClick={onLogMeal}
            disabled={!mealInput.trim() || isLogging}
            className={`px-5 py-2 rounded-lg text-xs font-black uppercase tracking-wider transition-all ${
              !mealInput.trim() || isLogging
                ? 'bg-zinc-800 text-zinc-600 cursor-not-allowed'
                : 'bg-cyan-500 hover:bg-cyan-600 text-zinc-950'
            }`}
          >
            {isLogging ? 'Logging...' : 'Log Meal'}
          </button>
        </div>
        <button
          type="button"
          onClick={onLogFollowedDietPlan}
          disabled={isLogging}
          className={`w-full sm:w-auto px-4 py-2 rounded-lg border text-xs font-bold uppercase tracking-wider transition-all ${
            isLogging
              ? 'border-zinc-800 text-zinc-600 cursor-not-allowed'
              : 'border-amber-500/30 bg-amber-500/10 text-amber-300 hover:bg-amber-500/15'
          }`}
        >
          I Followed Today&apos;s Diet Plan
        </button>
        {logMessage && (
          <p className={`text-xs ${logMessage.toLowerCase().includes('failed') ? 'text-rose-400' : 'text-green-400'}`}>
            {logMessage}
          </p>
        )}
        {recentLogs.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
            {recentLogs.map((log: any, index: number) => (
              <div key={`${log.logged_at || index}`} className="bg-[#0f0f0f] border border-zinc-800 rounded-lg p-3 min-w-0">
                <p className="text-xs text-zinc-300 truncate">{log.raw_input || 'Meal log'}</p>
                <p className="text-[11px] text-amber-400 font-bold mt-1">{Math.round(log.calories || 0)} kcal</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-zinc-500">No meals logged today. Log meals with the diet coach to track intake.</p>
        )}
          </>
        )}
      </div>
    </section>
  );
}

function NutritionMetric({ label, value }: { label: string; value: any }) {
  return (
    <div className="bg-[#0f0f0f] border border-zinc-800 rounded-lg p-3 min-w-0">
      <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-bold">{label}</p>
      <p className="text-base text-cyan-400 font-black mt-1 break-words">{value}</p>
    </div>
  );
}
