/**
 * Custom Hook: useDietLogging
 * Encapsulates meal logging and grocery list generation logic
 */

import { useState, useCallback } from "react";
import { post } from "../api/apiClient";

export interface FoodItem {
  food_name: string;
  quantity: string;
  estimated_calories: number;
  protein_g: number;
  carbs_g: number;
  fats_g: number;
}

export interface MealAnalysis {
  extracted_foods: FoodItem[];
  total_meal_calories: number;
  nutritional_advice: string;
}

export interface GroceryItem {
  item_name: string;
  estimated_quantity: string;
  category: string;
  purpose: string;
}

export interface GroceryList {
  dietary_focus: string;
  items: GroceryItem[];
  meal_prep_tip: string;
}

export function useDietLogging() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mealData, setMealData] = useState<MealAnalysis | null>(null);
  const [groceryData, setGroceryData] = useState<GroceryList | null>(null);

  const logMeal = useCallback(async (userId: string, mealInput: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await post<MealAnalysis>("/api/dietician/log-meal", {
        user_id: userId,
        user_input: mealInput,
      });

      if (response.status === "error") {
        throw new Error(response.message || "Failed to log meal");
      }

      setMealData(response.data || null);
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const generateGroceryList = useCallback(
    async (userId: string, preferences: string = "None") => {
      setLoading(true);
      setError(null);
      try {
        const response = await post<GroceryList>(
          "/api/dietician/generate-grocery-list",
          {
            user_id: userId,
            preferences_or_allergies: preferences,
          }
        );

        if (response.status === "error") {
          throw new Error(response.message || "Failed to generate grocery list");
        }

        setGroceryData(response.data || null);
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
    mealData,
    groceryData,
    logMeal,
    generateGroceryList,
  };
}
