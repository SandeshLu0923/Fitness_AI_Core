/**
 * Custom Hook: useGymBuddyChat
 * Encapsulates chat interaction with AI gym buddy
 */

import { useState, useCallback } from "react";
import { post, get } from "../api/apiClient";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

export interface CasualChatResponse {
  motivational_reply: string;
  requires_confirmation_buttons: boolean;
  confirmation_action_type?: "workout" | "diet" | "plan" | null;
  plan_action_trigger?: string | null;
}

export interface PinnedMessage {
  id: string;
  text: string;
  pinned_at: string;
}

export function useGymBuddyChat() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pinnedMessages, setPinnedMessages] = useState<PinnedMessage[]>([]);

  const sendMessage = useCallback(
    async (userId: string, userMessage: string) => {
      setLoading(true);
      setError(null);
      try {
        const response = await post<CasualChatResponse>(
          "/api/gym-buddy/chat",
          {
            user_id: userId,
            user_message: userMessage,
          }
        );

        if (response.status === "error") {
          throw new Error(response.message || "Failed to send message");
        }

        // Add user message and bot response to chat history
        setMessages((prev) => [
          ...prev,
          { role: "user", content: userMessage, timestamp: new Date().toISOString() },
          {
            role: "assistant",
            content: response.data?.motivational_reply || "",
            timestamp: new Date().toISOString(),
          },
        ]);

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

  const serializeAndCommit = useCallback(
    async (userId: string, actionType: "workout" | "diet" | "plan", approvedChatPlan?: string) => {
      setLoading(true);
      setError(null);
      try {
        const response = await post<{ status: string; message: string }>(
          "/api/gym-buddy/serialize-and-commit",
          {
            user_id: userId,
            action_type: actionType,
            approved_chat_plan: approvedChatPlan,
          }
        );

        if (response.status === "error") {
          throw new Error(response.message || "Failed to serialize chat");
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

  const pinMessage = useCallback(
    async (userId: string, messageText: string) => {
      setLoading(true);
      setError(null);
      try {
        const response = await post<{ status: string; message: string }>(
          "/api/gym-buddy/pin",
          {
            user_id: userId,
            message_text: messageText,
          }
        );

        if (response.status === "error") {
          throw new Error(response.message || "Failed to pin message");
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

  const fetchPinnedMessages = useCallback(async (userId: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await get<PinnedMessage[]>(
        `/api/gym-buddy/pinned-list/${userId}`
      );

      if (response.status === "error") {
        throw new Error(response.message || "Failed to fetch pinned messages");
      }

      setPinnedMessages(response.data || []);
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    loading,
    error,
    messages,
    pinnedMessages,
    sendMessage,
    serializeAndCommit,
    pinMessage,
    fetchPinnedMessages,
  };
}
