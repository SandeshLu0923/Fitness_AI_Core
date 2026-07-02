import React from 'react';
import { User, Bot, Pin } from 'lucide-react';

interface ExerciseItem {
  exercise_name: string;
  prescribed_sets: number;
  prescribed_reps: string;
  trainer_execution_note: string;
}

interface DayBlock {
  day_number: number;
  target_muscle_split: string;
  is_rest_day: boolean;
  exercises: ExerciseItem[];
  daily_metric_challenge: string;
}

interface MacrocyclePayload {
  user_fitness_archetype: string;
  trainer_coaching_voice: string;
  current_difficulty_multiplier: string;
  schedule: DayBlock[];
}

interface Message {
  id: string;
  sender: 'user' | 'buddy';
  text: string;
  isProposalCard?: boolean;
  proposalData?: MacrocyclePayload;
  showButtons?: boolean;
  actionType?: 'workout' | 'diet';
  isPlanMessage?: boolean;
  planData?: {
    type: 'diet' | 'workout';
    diet_plan?: any;
    grocery_list?: string[];
    workout_plan?: any;
    daily_challenges?: any[];
    archetype?: string;
    difficulty_multiplier?: string;
  };
  pinId?: string;
}

interface ChatMessageTimelineProps {
  messages: Message[];
  loading: boolean;
  chatEndRef: React.RefObject<HTMLDivElement | null>;
  pinChat: (message: Message) => void;
  handleActionConfirm: (actionType: 'update' | 'cancel', payload: MacrocyclePayload) => void;
  handlePlanUpdate: (message: Message, action: 'update' | 'cancel') => void;
}

export default function ChatMessageTimeline({
  messages,
  loading,
  chatEndRef,
  pinChat,
  handleActionConfirm,
  handlePlanUpdate,
}: ChatMessageTimelineProps) {
  return (
    <div className="flex-1 overflow-y-auto p-5 space-y-5 relative scrollbar-hide">
      {messages.map((msg) => {
        const isUser = msg.sender === 'user';
        return (
          <div key={msg.id} className={`flex gap-3 max-w-[88%] ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}>
            <div className={`h-7 w-7 rounded-full shrink-0 flex items-center justify-center border text-xs ${isUser ? 'bg-zinc-800 border-zinc-700 text-zinc-300' : 'bg-cyan-500/10 border-cyan-500/20 text-cyan-400'}`}>
              {isUser ? <User size={12} /> : <Bot size={12} />}
            </div>
            
            <div className="space-y-2.5 w-full group relative">
              <div className={`rounded-xl p-3 text-xs leading-relaxed shadow-sm border ${isUser ? 'bg-zinc-900 border-zinc-800 text-zinc-200 rounded-tr-none' : 'bg-[#1e1e1e] border-zinc-800 text-zinc-300 rounded-tl-none'}`}>
                {msg.text}
              </div>

              {/* Pin button for ALL messages */}
              {!msg.isPlanMessage && !msg.isProposalCard && (
                <button 
                  onClick={() => pinChat(msg)}
                  className="absolute -right-7 top-2 p-1 text-zinc-600 hover:text-cyan-400 opacity-0 group-hover:opacity-100 transition-all"
                  title="Pin this chat for 7 days"
                >
                  <Pin size={11} className={msg.pinId ? "rotate-45 text-cyan-400" : "rotate-45"} />
                </button>
              )}

              {/* Plan Message Card (Diet or Workout) */}
              {!isUser && msg.isPlanMessage && msg.planData && (
                <div className="bg-[#0f0f0f] border border-cyan-500/30 rounded-xl p-4 space-y-3 shadow-xl w-full">
                  <div className="flex items-center justify-between border-b border-zinc-900 pb-2">
                    <span className="text-[11px] font-black tracking-wider text-cyan-400 uppercase">
                      {msg.planData.type === 'diet' ? '🥗 Diet Plan & Grocery List' : '💪 Workout Plan'}
                    </span>
                  </div>

                  {msg.planData.type === 'diet' ? (
                    <div className="space-y-2.5">
                      <div>
                        <h4 className="text-[11px] font-bold text-zinc-300 mb-1">📋 Diet Plan:</h4>
                        <div className="text-[10px] text-zinc-400 bg-zinc-900/50 p-2 rounded max-h-[120px] overflow-y-auto">
                          {JSON.stringify(msg.planData.diet_plan, null, 2)}
                        </div>
                      </div>
                      <div>
                        <h4 className="text-[11px] font-bold text-zinc-300 mb-1">🛒 Grocery List:</h4>
                        <div className="text-[10px] text-zinc-400 space-y-1">
                          {msg.planData.grocery_list?.map((item, idx) => (
                            <div key={idx} className="flex items-center gap-2">
                              <span className="text-cyan-400">•</span> {item}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      <div className="flex gap-2 text-[10px]">
                        <span className="bg-cyan-500/20 text-cyan-400 px-2 py-1 rounded">
                          {msg.planData.archetype}
                        </span>
                        <span className="bg-purple-500/20 text-purple-400 px-2 py-1 rounded">
                          {msg.planData.difficulty_multiplier}
                        </span>
                      </div>
                      <div>
                        <h4 className="text-[11px] font-bold text-zinc-300 mb-2">📅 Daily Challenges:</h4>
                        <div className="space-y-1 max-h-[150px] overflow-y-auto">
                          {msg.planData.daily_challenges?.map((challenge, idx) => (
                            <div key={idx} className="text-[10px] text-zinc-300 bg-zinc-900/50 p-1.5 rounded">
                              <span className="text-cyan-400 font-bold">Day {idx + 1}:</span> {challenge.challenge || challenge.daily_metric_challenge}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {msg.showButtons && (
                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-zinc-900">
                      <button 
                        onClick={() => handlePlanUpdate(msg, 'update')}
                        className="bg-cyan-600 hover:bg-cyan-700 text-white text-[10px] font-bold py-2 px-3 rounded transition-colors"
                      >
                        ✓ Update Plan
                      </button>
                      <button 
                        onClick={() => handlePlanUpdate(msg, 'cancel')}
                        className="bg-zinc-700 hover:bg-zinc-600 text-zinc-200 text-[10px] font-bold py-2 px-3 rounded transition-colors"
                      >
                        ✕ Cancel
                      </button>
                    </div>
                  )}
                </div>
              )}

              {!isUser && msg.isProposalCard && msg.proposalData && (
                <div className="bg-[#0f0f0f] border border-zinc-800 rounded-xl p-4 space-y-3 shadow-xl w-full">
                  <div className="flex items-center justify-between border-b border-zinc-900 pb-2">
                    <span className="text-[11px] font-black tracking-wider text-zinc-400 uppercase">Training Program Split</span>
                    <span className="text-[9px] font-black text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 rounded uppercase">
                      {msg.proposalData.current_difficulty_multiplier}
                    </span>
                  </div>

                  <div className="space-y-2.5 max-h-[240px] overflow-y-auto pr-1 scrollbar-hide text-[11px]">
                    {msg.proposalData.schedule.map((day) => (
                      <div key={day.day_number} className="bg-[#161616] p-2.5 rounded-lg border border-zinc-800/60">
                        <div className="font-bold text-zinc-200 flex justify-between">
                          <span>Day {day.day_number} • {day.target_muscle_split}</span>
                          <span className="text-zinc-500 uppercase font-mono text-[9px]">{day.is_rest_day ? 'Rest' : 'Active'}</span>
                        </div>
                        {day.exercises.map((ex, idx) => (
                          <div key={idx} className="text-zinc-400 mt-1 pl-1.5 border-l border-zinc-800">
                            • <span className="text-zinc-300">{ex.exercise_name}</span> ({ex.prescribed_sets}x{ex.prescribed_reps})
                          </div>
                        ))}
                        <div className="mt-1.5 text-[9px] text-cyan-400/90 font-mono">🎯 Challenge: {day.daily_metric_challenge}</div>
                      </div>
                    ))}
                  </div>

                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <button 
                      onClick={() => handleActionConfirm('cancel', msg.proposalData!)}
                      className="py-1.5 border border-zinc-800 text-zinc-400 hover:text-zinc-200 font-bold text-[11px] uppercase tracking-wider rounded-lg transition-all"
                    >
                      Discard
                    </button>
                    <button 
                      onClick={() => handleActionConfirm('update', msg.proposalData!)}
                      className="py-1.5 bg-cyan-500 hover:bg-cyan-600 text-zinc-950 font-black text-[11px] uppercase tracking-wider rounded-lg transition-all"
                    >
                      Update App
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })}
      {loading && <div className="text-xs text-zinc-600 font-mono animate-pulse pl-10">Buddy is thinking...</div>}
      <div ref={chatEndRef} />
    </div>
  );
}
