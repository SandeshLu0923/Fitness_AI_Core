import { useEffect, useMemo, useState } from 'react';
import { CalendarDays, ChefHat, ShoppingBasket, Trash2 } from 'lucide-react';
import axios from 'axios';

interface DietPlan {
  _id: string;
  user_id: string;
  diet_plan: any;
  grocery_list: string[];
  notes: string;
  created_at: string;
  is_active: boolean;
}

interface DietPlansTabProps {
  userId: string;
}

interface DietDay {
  key: string;
  title: string;
  date?: string;
  calories?: string;
  meals: any[];
}

type ViewMode = 'today' | 'day' | 'grocery';

export default function DietPlansTab({ userId }: DietPlansTabProps) {
  const [dietPlans, setDietPlans] = useState<DietPlan[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<DietPlan | null>(null);
  const [selectedDayKey, setSelectedDayKey] = useState<string>('');
  const [viewMode, setViewMode] = useState<ViewMode>('today');

  useEffect(() => {
    fetchDietPlans();
  }, [userId]);

  const selectedDays = useMemo(
    () => selectedPlan ? normalizeDietDays(selectedPlan) : [],
    [selectedPlan]
  );
  const todayDay = findTodayDay(selectedDays) || selectedDays[0] || null;
  const selectedDay = selectedDays.find(day => day.key === selectedDayKey) || todayDay;

  useEffect(() => {
    if (todayDay) {
      setSelectedDayKey(todayDay.key);
    }
  }, [todayDay?.key]);

  const fetchDietPlans = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`http://localhost:8000/api/plans/diet-plans/${userId}`);
      const plans = response.data.plans || [];
      setDietPlans(plans);
      setSelectedPlan(plans[0] || null);
    } catch (err) {
      console.error('Failed to fetch diet plans:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeletePlan = async (planId: string) => {
    if (!window.confirm('Delete this diet plan?')) return;

    try {
      await axios.delete(`http://localhost:8000/api/plans/diet-plans/${planId}`);
      setDietPlans(prev => prev.filter(plan => plan._id !== planId));
      setSelectedPlan(null);
      setViewMode('today');
    } catch (err) {
      console.error('Failed to delete plan:', err);
    }
  };

  const openDay = (day: DietDay) => {
    setSelectedDayKey(day.key);
    setViewMode(day.key === todayDay?.key ? 'today' : 'day');
  };

  return (
    <div className="h-full flex flex-col bg-[#161616] rounded-lg border border-zinc-800 overflow-hidden">
      <div className="h-14 px-4 border-b border-zinc-800 flex items-center justify-between bg-[#1a1a1a] shrink-0">
        <div className="flex items-center space-x-2">
          <ChefHat size={16} className="text-amber-400" />
          <h3 className="text-sm font-bold text-zinc-200">My Diet Plans</h3>
        </div>
        <span className="text-xs bg-zinc-800 text-zinc-400 px-2 py-1 rounded">
          {dietPlans.length} saved
        </span>
      </div>

      <div className="flex-1 min-h-0 overflow-hidden flex flex-col lg:flex-row gap-4 p-4">
        <div className="w-full lg:w-72 border border-zinc-800 rounded-lg p-3 overflow-y-auto space-y-3 shrink-0">
          <div>
            <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider mb-2">Current Diet Plan</p>
            {loading ? (
              <div className="text-center text-zinc-500 text-xs py-4">Loading...</div>
            ) : dietPlans.length === 0 ? (
              <div className="text-center text-zinc-500 text-xs py-4">
                No diet plans yet. Create one in chat.
              </div>
            ) : (
              dietPlans.map(plan => (
                <button
                  key={plan._id}
                  onClick={() => {
                    setSelectedPlan(plan);
                    setViewMode('today');
                  }}
                  className={`w-full text-left p-3 rounded-lg border transition-all ${
                    selectedPlan?._id === plan._id
                      ? 'bg-amber-500/10 border-amber-500/30'
                      : 'bg-zinc-900/50 border-zinc-800 hover:border-zinc-700'
                  }`}
                >
                  <div className="text-[11px] font-bold text-zinc-300">
                    {new Date(plan.created_at).toLocaleDateString()}
                  </div>
                  <div className="text-[10px] text-zinc-400 mt-1">
                    {normalizeDietDays(plan).length} days + {plan.grocery_list.length} groceries
                  </div>
                </button>
              ))
            )}
          </div>

          {selectedPlan && (
            <div className="space-y-2">
              <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Open View</p>
              <button
                onClick={() => setViewMode('today')}
                className={viewButtonClass(viewMode === 'today')}
              >
                <CalendarDays size={13} />
                <span>Today&apos;s Diet</span>
              </button>
              <button
                onClick={() => setViewMode('grocery')}
                className={viewButtonClass(viewMode === 'grocery')}
              >
                <ShoppingBasket size={13} />
                <span>Grocery List</span>
              </button>
            </div>
          )}

          {selectedDays.length > 0 && (
            <div className="space-y-2">
              <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Select Day</p>
              <div className="grid grid-cols-2 gap-2">
                {selectedDays.map((day, index) => (
                  <button
                    key={day.key}
                    onClick={() => openDay(day)}
                    className={`p-2 rounded border text-left transition-all ${
                      selectedDay?.key === day.key && viewMode !== 'grocery'
                        ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                        : 'bg-zinc-900/40 border-zinc-800 text-zinc-400 hover:border-zinc-700'
                    }`}
                  >
                    <span className="block text-[10px] font-bold">Day {index + 1}</span>
                    <span className="block text-[9px] truncate">{day.title}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex-1 min-w-0 border border-zinc-800 rounded-lg p-4 overflow-y-auto bg-zinc-900/30">
          {selectedPlan ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h4 className="font-bold text-zinc-200">
                    {viewMode === 'grocery' ? 'Grocery List' : 'Day-wise Diet Plan'}
                  </h4>
                  <p className="text-[11px] text-zinc-500 mt-1">
                    Plan created {new Date(selectedPlan.created_at).toLocaleDateString()}
                  </p>
                </div>
                <button
                  onClick={() => handleDeletePlan(selectedPlan._id)}
                  className="p-1.5 hover:bg-red-500/20 text-red-400 rounded transition-colors"
                  title="Delete plan"
                >
                  <Trash2 size={16} />
                </button>
              </div>

              {viewMode === 'grocery' ? (
                <GroceryList items={selectedPlan.grocery_list} />
              ) : (
                <div className="space-y-4">
                  {todayDay && (
                    <div className="border border-amber-500/30 bg-amber-500/5 rounded-lg p-4">
                      <p className="text-[10px] font-bold text-amber-400 uppercase tracking-wider mb-3">Today&apos;s Diet Plan</p>
                      <DietDayCard day={todayDay} />
                    </div>
                  )}
                  {selectedDay && selectedDay.key !== todayDay?.key && (
                    <DietDayCard day={selectedDay} />
                  )}
                  {!selectedDay && (
                    <div className="text-sm text-zinc-500 bg-zinc-900/50 p-4 rounded-lg border border-zinc-800">
                      No day-wise meals were found in this plan.
                    </div>
                  )}
                </div>
              )}

              {selectedPlan.notes && (
                <div>
                  <h5 className="text-xs font-bold text-zinc-400 mb-2">Notes</h5>
                  <p className="text-[10px] text-zinc-300 bg-zinc-900/50 p-3 rounded">
                    {selectedPlan.notes}
                  </p>
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

function DietDayCard({ day }: { day: DietDay }) {
  return (
    <div className="bg-[#0f0f0f] border border-zinc-800 rounded-lg p-4 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
        <div>
          <h5 className="text-base font-bold text-zinc-100">{day.title}</h5>
          {day.date && <p className="text-[11px] text-zinc-500 mt-1">{new Date(`${day.date}T00:00:00`).toLocaleDateString()}</p>}
        </div>
        {day.calories && (
          <span className="w-fit text-[10px] px-2 py-1 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
            Calories: {day.calories}
          </span>
        )}
      </div>

      {day.meals.length === 0 ? (
        <p className="text-xs text-zinc-600 italic">No meals listed for this day.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {day.meals.map((meal, mealIndex) => (
            <div key={mealIndex} className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-3 space-y-2 min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
                {mealTitle(meal, mealIndex)}
              </p>
              <p className="text-xs text-zinc-300 leading-relaxed break-words">{renderMealItems(meal)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function GroceryList({ items }: { items: string[] }) {
  return (
    <div className="bg-[#0f0f0f] border border-zinc-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center gap-2">
        <ShoppingBasket size={15} className="text-amber-400" />
        <h5 className="text-xs font-bold text-zinc-200 uppercase tracking-wider">Grocery List</h5>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-zinc-500">No grocery items listed.</p>
      ) : (
        <ol className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-x-6 gap-y-2 text-xs text-zinc-300 list-decimal list-inside">
          {items.map((item, idx) => (
            <li key={idx} className="leading-relaxed break-words">{item}</li>
          ))}
        </ol>
      )}
    </div>
  );
}

function normalizeDietDays(plan: DietPlan): DietDay[] {
  const planData = plan.diet_plan;
  if (!planData || typeof planData !== 'object') return [];
  const source = planData.weekly_plan && typeof planData.weekly_plan === 'object'
    ? planData.weekly_plan
    : planData;
  const startDate = getLocalPlanStartDate(plan);

  if (Array.isArray(source.days)) {
    return source.days.map((day: any, index: number) => normalizeDay(day, `day_${index + 1}`, index, startDate));
  }

  return Object.keys(source)
    .filter(key => key.toLowerCase().startsWith('day'))
    .sort((a, b) => extractDayNumber(a) - extractDayNumber(b))
    .map((key, index) => normalizeDay(source[key], key, index, startDate));
}

function normalizeDay(day: any, key: string, index: number, startDate: Date | null): DietDay {
  const fallbackName = `Day ${index + 1}`;
  const derivedDate = deriveDateForIndex(day?.date, startDate, index);
  const derivedTitle = derivedDate
    ? derivedDate.toLocaleDateString('en-US', { weekday: 'long' })
    : fallbackName;

  if (!day || typeof day !== 'object') {
    return { key, title: derivedTitle, date: toLocalIsoDate(derivedDate), meals: [] };
  }

  return {
    key,
    title: derivedTitle,
    date: toLocalIsoDate(derivedDate),
    calories: day.custom_calories || day.calories || day.daily_calories,
    meals: Array.isArray(day.meals) ? day.meals : []
  };
}

function findTodayDay(days: DietDay[]) {
  const today = toLocalIsoDate(new Date());
  return days.find(day => day.date === today) || null;
}

function getLocalPlanStartDate(plan: DietPlan) {
  const rawPlan = plan.diet_plan || {};
  const source = rawPlan.weekly_plan && typeof rawPlan.weekly_plan === 'object' ? rawPlan.weekly_plan : rawPlan;
  const firstDay = Array.isArray(source.days) ? source.days[0] : source.day_1;
  return parseLocalDate((plan as any).start_date || firstDay?.date || plan.created_at);
}

function deriveDateForIndex(rawDate: string | undefined, startDate: Date | null, index: number) {
  if (startDate) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + index);
    return date;
  }
  return parseLocalDate(rawDate);
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

function toLocalIsoDate(date: Date | null) {
  if (!date) return undefined;
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function extractDayNumber(key: string) {
  const match = key.match(/\d+/);
  return match ? Number(match[0]) : 99;
}

function viewButtonClass(active: boolean) {
  return `w-full flex items-center gap-2 px-3 py-2 rounded border text-xs font-bold transition-all ${
    active
      ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
      : 'bg-zinc-900/40 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
  }`;
}

function mealTitle(meal: any, index: number) {
  if (!meal || typeof meal !== 'object') return `Meal ${index + 1}`;
  return meal.time || meal.meal_type || meal.type || `Meal ${index + 1}`;
}

function renderMealItems(meal: any) {
  if (typeof meal === 'string') return meal;
  if (!meal || typeof meal !== 'object') return 'Meal details not listed';
  if (Array.isArray(meal.items)) return meal.items.join(', ');
  if (Array.isArray(meal.foods)) return meal.foods.join(', ');
  if (meal.name) return meal.name;

  return Object.entries(meal)
    .filter(([key]) => !['time', 'meal_type', 'type'].includes(key))
    .map(([key, value]) => `${formatLabel(key)}: ${Array.isArray(value) ? value.join(', ') : String(value)}`)
    .join(' | ') || 'Meal details not listed';
}

function formatLabel(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
}
