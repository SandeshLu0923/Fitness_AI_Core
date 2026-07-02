import type { ReactNode } from 'react';
import { Trash2 } from 'lucide-react';

function formatPlanLabel(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
}

function renderPlanValue(value: any, depth = 0): ReactNode {
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-zinc-600">None listed</span>;
    }

    return (
      <ul className={`space-y-1 ${depth > 0 ? 'ml-4 list-disc' : 'list-disc list-inside'}`}>
        {value.map((item, idx) => (
          <li key={idx} className="text-zinc-300">
            {typeof item === 'object' && item !== null ? renderPlanValue(item, depth + 1) : String(item)}
          </li>
        ))}
      </ul>
    );
  }

  if (typeof value === 'object' && value !== null) {
    return (
      <div className={`space-y-2 ${depth > 0 ? 'ml-3 border-l border-zinc-800 pl-3' : ''}`}>
        {Object.entries(value).map(([key, nestedValue]) => (
          <div key={key} className="space-y-1">
            <div className="font-semibold text-zinc-300">{formatPlanLabel(key)}</div>
            <div className="text-zinc-400">{renderPlanValue(nestedValue, depth + 1)}</div>
          </div>
        ))}
      </div>
    );
  }

  return <span>{String(value)}</span>;
}

/**
 * Grocery List Card Component
 * Displays list of grocery items for a meal/diet plan
 */
export function GroceryListCard({ 
  items = [],
  onDelete 
}: { 
  items: string[];
  onDelete?: () => void;
}) {
  return (
    <div className="bg-[#0f0f0f] border border-emerald-500/20 rounded-xl p-4 space-y-3 shadow-xl w-full">
      <div className="flex items-center justify-between border-b border-zinc-900 pb-2">
        <span className="text-[11px] font-black tracking-wider text-emerald-400 uppercase">
          🛒 Grocery List
        </span>
      </div>

      <div className="text-[10px]">
        {items && items.length > 0 ? (
          <ol className="text-zinc-400 space-y-1 list-decimal list-inside max-h-[200px] overflow-y-auto">
            {items.map((item, idx) => (
              <li key={idx} className="text-zinc-300">{item}</li>
            ))}
          </ol>
        ) : (
          <div className="text-zinc-600 text-center py-4 italic">No items listed</div>
        )}
      </div>

      {onDelete && (
        <div className="pt-2 border-t border-zinc-900 flex justify-end">
          <button 
            onClick={onDelete}
            className="text-zinc-500 hover:text-rose-400 transition-colors text-xs font-bold flex items-center gap-1"
          >
            <Trash2 size={12} />
            Remove
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Diet Plan Card Component
 * Displays meal breakdown and nutrition details
 */
export function DietPlanCard({ 
  dietPlan,
  groceryList,
  onUpdate,
  onCancel
}: { 
  dietPlan: any;
  groceryList?: string[];
  onUpdate?: () => void;
  onCancel?: () => void;
}) {
  return (
    <div className="bg-[#0f0f0f] border border-cyan-500/30 rounded-xl p-4 space-y-3 shadow-xl w-full">
      <div className="flex items-center justify-between border-b border-zinc-900 pb-2">
        <span className="text-[11px] font-black tracking-wider text-cyan-400 uppercase">
          🥗 Diet Plan
        </span>
      </div>

      <div className="text-[10px] space-y-3">
        {dietPlan && (
          <div>
            <h4 className="text-[11px] font-bold text-zinc-300 mb-2">📋 Meal Breakdown:</h4>
            <div className="text-zinc-400 space-y-2">
              {renderPlanValue(dietPlan)}
            </div>
          </div>
        )}

        {groceryList && groceryList.length > 0 && (
          <div>
            <h4 className="text-[11px] font-bold text-zinc-300 mb-2">📝 Item Count:</h4>
            <p className="text-zinc-400">{groceryList.length} items in grocery list</p>
          </div>
        )}
      </div>

      {(onUpdate || onCancel) && (
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-zinc-900">
          {onCancel && (
            <button 
              onClick={onCancel}
              className="bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-[10px] font-bold py-2 px-3 rounded transition-colors"
            >
              ✕ Cancel
            </button>
          )}
          {onUpdate && (
            <button 
              onClick={onUpdate}
              className="bg-cyan-600 hover:bg-cyan-700 text-white text-[10px] font-bold py-2 px-3 rounded transition-colors col-span={onCancel ? 1 : 2}"
            >
              ✓ Save Plan
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Workout Plan Card Component
 * Displays workout archetype, difficulty, and daily challenges
 */
export function WorkoutPlanCard({ 
  archetype,
  difficultyMultiplier,
  dailyChallenges = [],
  onUpdate,
  onCancel
}: { 
  archetype: string;
  difficultyMultiplier: string;
  dailyChallenges: any[];
  onUpdate?: () => void;
  onCancel?: () => void;
}) {
  return (
    <div className="bg-[#0f0f0f] border border-purple-500/30 rounded-xl p-4 space-y-3 shadow-xl w-full">
      <div className="flex items-center justify-between border-b border-zinc-900 pb-2">
        <span className="text-[11px] font-black tracking-wider text-purple-400 uppercase">
          💪 Workout Plan
        </span>
      </div>

      <div className="text-[10px] space-y-3">
        <div className="flex gap-2">
          <span className="bg-purple-500/20 text-purple-400 px-2 py-1 rounded text-[9px] font-bold">
            {archetype}
          </span>
          <span className="bg-pink-500/20 text-pink-400 px-2 py-1 rounded text-[9px] font-bold">
            {difficultyMultiplier}
          </span>
        </div>

        {dailyChallenges && dailyChallenges.length > 0 && (
          <div>
            <h4 className="text-[11px] font-bold text-zinc-300 mb-2">📅 Daily Challenges ({dailyChallenges.length} days):</h4>
            <ol className="text-zinc-400 space-y-1 list-decimal list-inside max-h-[150px] overflow-y-auto">
              {dailyChallenges.slice(0, 5).map((challenge, idx) => (
                <li key={idx} className="text-zinc-300 text-[9px]">
                  Day {idx + 1}: {challenge.title || challenge.challenge || 'Challenge'}
                </li>
              ))}
              {dailyChallenges.length > 5 && (
                <li className="text-zinc-500 italic text-[9px]">... and {dailyChallenges.length - 5} more days</li>
              )}
            </ol>
          </div>
        )}
      </div>

      {(onUpdate || onCancel) && (
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-zinc-900">
          {onCancel && (
            <button 
              onClick={onCancel}
              className="bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-[10px] font-bold py-2 px-3 rounded transition-colors"
            >
              ✕ Cancel
            </button>
          )}
          {onUpdate && (
            <button 
              onClick={onUpdate}
              className="bg-purple-600 hover:bg-purple-700 text-white text-[10px] font-bold py-2 px-3 rounded transition-colors col-span={onCancel ? 1 : 2}"
            >
              ✓ Save Plan
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Combined Plan Display Component
 * Shows grocery list, diet plan, and workout plan separately
 */
export function PlanDisplayCard({ planData, onUpdate, onCancel }: {
  planData: any;
  onUpdate?: () => void;
  onCancel?: () => void;
}) {
  if (!planData) return null;

  return (
    <div className="space-y-3 w-full">
      {/* Diet Plan */}
      {planData.diet_plan && (
        <>
          <DietPlanCard 
            dietPlan={planData.diet_plan}
            groceryList={planData.grocery_list}
            onCancel={onCancel}
          />
          {/* Grocery List as separate card */}
          {planData.grocery_list && planData.grocery_list.length > 0 && (
            <GroceryListCard items={planData.grocery_list} />
          )}
          {onUpdate && (
            <button 
              onClick={onUpdate}
              className="w-full bg-cyan-600 hover:bg-cyan-700 text-white text-[10px] font-bold py-2 px-3 rounded transition-colors"
            >
              ✓ Save Diet Plan
            </button>
          )}
        </>
      )}

      {/* Workout Plan */}
      {planData.workout_plan && (
        <>
          <WorkoutPlanCard 
            archetype={planData.archetype || 'General'}
            difficultyMultiplier={planData.difficulty_multiplier || 'Medium'}
            dailyChallenges={planData.daily_challenges || []}
            onCancel={onCancel}
            onUpdate={onUpdate}
          />
        </>
      )}
    </div>
  );
}
