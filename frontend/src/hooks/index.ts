/**
 * Custom React Hooks
 * Centralized business logic and API interactions
 */

export { useWorkoutTracker } from "./useWorkoutTracker";
export type { WorkoutStats } from "./useWorkoutTracker";

export { useDietLogging } from "./useDietLogging";
export type {
  FoodItem,
  MealAnalysis,
  GroceryItem,
  GroceryList,
} from "./useDietLogging";

export { useMacrocycleTracker } from "./useMacrocycleTracker";
export type {
  MacrocycleDay,
  WeeklyMacrocyclePlan,
  ActiveDayPlan,
} from "./useMacrocycleTracker";

export { useGymBuddyChat } from "./useGymBuddyChat";
export type {
  ChatMessage,
  CasualChatResponse,
  PinnedMessage,
} from "./useGymBuddyChat";
