/**
 * Custom Hook: useMacrocycleTracker
 * Encapsulates macrocycle generation and daily challenge tracking
 */

import { useState, useCallback } from "react";
import { post, get } from "../api/apiClient";

export interface MacrocycleDay {
  day_number: number;
  focus: string;
  exercises: Array<{ name: string; sets: number; reps: number }>;
  challenge: string;
  difficulty_rating: number;
}

export interface WeeklyMacrocyclePlan {
  block_duration_days: number;
  schedule: MacrocycleDay[];
  current_difficulty_multiplier: number;
}

export interface ActiveDayPlan {
  current_active_day: number;
  difficulty_multiplier: number;
  day_details: MacrocycleDay;
}

export function useMacrocycleTracker() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<WeeklyMacrocyclePlan | null>(null);
  const [activeDayPlan, setActiveDayPlan] = useState<ActiveDayPlan | null>(null);

  const generateWeeklyBlock = useCallback(async (userId: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await get<WeeklyMacrocyclePlan>(
        `/api/habit-tracker/generate-weekly-block?user_id=${userId}`
      );

      if (response.status === "error") {
        throw new Error(response.message || "Failed to generate weekly block");
      }

      setPlan(response.data || null);
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const confirmMacrocycle = useCallback(
    async (userId: string, macrocycle: WeeklyMacrocyclePlan) => {
      setLoading(true);
      setError(null);
      try {
        const response = await post<{ status: string; message: string }>(
          "/api/habit-tracker/confirm-macrocycle",
          {
            user_id: userId,
            action: "update",
            macrocycle_payload: macrocycle,
          }
        );

        if (response.status === "error") {
          throw new Error(response.message || "Failed to confirm macrocycle");
        }

        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const getActiveDayPlan = useCallback(async (userId: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await get<ActiveDayPlan>(
        `/api/habit-tracker/active-day-plan?user_id=${userId}`
      );

      if (response.status === "error") {
        throw new Error(response.message || "Failed to fetch active day plan");
      }

      setActiveDayPlan(response.data || null);
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const completeActiveDay = useCallback(
    async (userId: string, dayNumber: number, challengeText: string) => {
      setLoading(true);
      setError(null);
      try {
        const response = await post<{
          status: string;
          message: string;
          macrocycle_finished: boolean;
        }>("/api/habit-tracker/complete-active-day", {
          user_id: userId,
          day_number: dayNumber,
          challenge_text: challengeText,
        });

        if (response.status === "error") {
          throw new Error(
            response.message || "Failed to complete active day"
          );
        }

        return response.data;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return {
    loading,
    error,
    plan,
    activeDayPlan,
    generateWeeklyBlock,
    confirmMacrocycle,
    getActiveDayPlan,
    completeActiveDay,
  };
}
