/**
 * Custom Hook: useWorkoutTracker
 * Encapsulates workout session management logic
 */

import { useState, useCallback } from "react";
import { post, type ApiResponse } from "../api/apiClient";

export interface WorkoutStats {
  found: boolean;
  exercise_name?: string;
  sets_completed?: number;
  correct_reps?: number;
  incorrect_reps?: number;
  timestamp?: string;
}

export function useWorkoutTracker() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<WorkoutStats | null>(null);

  const startTracking = useCallback(
    async (userId: string, exerciseType: string) => {
      setLoading(true);
      setError(null);
      try {
        const response = await post<{ status: string; message: string }>(
          "/api/gym-trainer/start",
          {
            user_id: userId,
            exercise_type: exerciseType,
          }
        );

        if (response.status === "error") {
          throw new Error(response.message || "Failed to start tracking");
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

  const fetchLatestStats = useCallback(
    async (userId: string) => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `/api/gym-trainer/latest-stats/${userId}`
        ).then((res) => res.json() as Promise<ApiResponse<WorkoutStats>>);

        if (response.status === "error") {
          throw new Error(response.message || "Failed to fetch stats");
        }

        setStats(response.data || null);
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
    stats,
    startTracking,
    fetchLatestStats,
  };
}
