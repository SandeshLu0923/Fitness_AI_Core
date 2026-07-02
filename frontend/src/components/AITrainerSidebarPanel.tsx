import { useState, useEffect, useRef } from 'react';
import axios from 'axios'; // ◄ ADDED AXIOS IMPORT TO FIX TS(2304) FOR LINES 155 AND 197
import { Send, Pin, PinOff, History, X, Search, User, Bot } from 'lucide-react';
import { PlanDisplayCard } from './PlanCards';

const PLAN_ACTION_TRIGGER = '[TRIGGER_PLAN_ACTIONS]';

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
  showButtons?: boolean;
  actionType?: 'workout' | 'diet' | 'plan';
  isProposalCard?: boolean;
  proposalData?: MacrocyclePayload;
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
  isPinnedLoaded?: boolean;
}

const stripPlanActionTrigger = (text: string) =>
  text.replace(PLAN_ACTION_TRIGGER, '').trim();

const normalizePinnedChat = (item: any) => ({
  id: item.id || item._id,
  text: item.text || item.message_text || item.chat_message || '',
  pinned_at: item.pinned_at,
  sender: item.sender || 'buddy'
});

const createSessionId = () =>
  `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const sessionRowKey = (session: any, idx: number) =>
  [
    session._id,
    session.session_id,
    session.updated_at,
    session.created_at,
    idx
  ].filter(Boolean).join(':');

const normalizeChatText = (text: string) =>
  text
    .replace(PLAN_ACTION_TRIGGER, '')
    .replace(/\s+-\s+\*\*/g, '\n- **')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

function renderInlineMarkdown(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={idx} className="font-bold text-zinc-100">{part.slice(2, -2)}</strong>;
    }
    return <span key={idx}>{part}</span>;
  });
}

function ChatText({ text, loading }: { text: string; loading?: boolean }) {
  const normalizedText = normalizeChatText(text);
  if (!normalizedText) {
    return loading ? <span className="animate-pulse text-zinc-600">...</span> : null;
  }

  return (
    <div className="space-y-2">
      {normalizedText.split('\n').map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={idx} className="h-1" />;

        const numberedMatch = trimmed.match(/^(\d+)[.)]\s+(.*)$/);
        if (trimmed.startsWith('- ')) {
          return (
            <div key={idx} className="flex gap-2">
              <span className="mt-1 h-1 w-1 rounded-full bg-zinc-500 shrink-0" />
              <div>{renderInlineMarkdown(trimmed.slice(2))}</div>
            </div>
          );
        }
        if (numberedMatch) {
          return (
            <div key={idx} className="flex gap-2">
              <span className="text-zinc-500 font-mono shrink-0">{numberedMatch[1]}.</span>
              <div>{renderInlineMarkdown(numberedMatch[2])}</div>
            </div>
          );
        }
        if (/^\*\*[^*]+\*\*$/.test(trimmed)) {
          return <div key={idx} className="pt-1 font-black text-zinc-100">{trimmed.slice(2, -2)}</div>;
        }

        return <p key={idx}>{renderInlineMarkdown(trimmed)}</p>;
      })}
    </div>
  );
}

export default function AITrainerSidebarPanel({ 
  userId, 
  onClose, 
  incomingTrigger 
}: { 
  userId: string; 
  onClose?: () => void; 
  incomingTrigger: string | null;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [showPinnedDrawer, setShowPinnedDrawer] = useState<boolean>(false);
  const [pinnedList, setPinnedList] = useState<any[]>([]);
  const [showSessionsDrawer, setShowSessionsDrawer] = useState<boolean>(false);
  const [recentSessions, setRecentSessions] = useState<any[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>(() => createSessionId());
  const chatEndRef = useRef<HTMLDivElement>(null);

  const safeUserId = encodeURIComponent(userId.trim());

  useEffect(() => {
    if (incomingTrigger) {
      if (incomingTrigger.startsWith('__trigger_diet_plan__')) {
        handleSendTextMessage("__trigger_diet_plan__");
      } else if (incomingTrigger.startsWith('__trigger_workout_plan__')) {
        handleSendTextMessage("__trigger_workout_plan__");
      }
    }
  }, [incomingTrigger]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendTextMessage = async (forcedText?: string) => {
    const targetText = forcedText || inputMessage.trim();
    if (!targetText || loading) return;

    if (!forcedText) setInputMessage('');
    
    let displayUserText = targetText;
    let category: 'workout' | 'diet' | undefined = undefined;

    if (targetText === "__trigger_diet_plan__") {
      displayUserText = "Requesting a casual diet plan overview...";
      category = 'diet';
    } else if (targetText === "__trigger_workout_plan__") {
      displayUserText = "Requesting a 7-day workout plan...";
      category = 'workout';
    }

    const userMsgId = Date.now().toString();
    const buddyMsgId = (Date.now() + 1).toString();

    setMessages(prev => [...prev, { id: userMsgId, sender: 'user', text: displayUserText }]);
    setLoading(true);
    setMessages(prev => [...prev, { id: buddyMsgId, sender: 'buddy', text: '' }]);

    try {
      const response = await axios.post('http://localhost:8000/api/gym-buddy/chat', {
        user_id: userId.trim(),
        user_message: targetText,
        session_id: activeSessionId
      });

      const jsonData = response.data;
      const displayText = stripPlanActionTrigger(jsonData.motivational_reply || '');
      let isPlan = false;
      let planData: any = null;
      const requiresPlanUpdate =
        Boolean(jsonData.requires_confirmation_buttons) ||
        String(jsonData.motivational_reply || '').includes(PLAN_ACTION_TRIGGER);
      const responseActionType = (jsonData.confirmation_action_type || category || 'plan') as 'workout' | 'diet' | 'plan';

      if (jsonData.diet_plan && Object.keys(jsonData.diet_plan).length > 0) {
        isPlan = true;
        planData = {
          ...jsonData,
          type: 'diet',
          diet_plan: jsonData.diet_plan,
          grocery_list: jsonData.grocery_list || []
        };
      } else if (jsonData.workout_plan && Object.keys(jsonData.workout_plan).length > 0) {
        isPlan = true;
        planData = {
          ...jsonData,
          type: 'workout',
          workout_plan: jsonData.workout_plan,
          daily_challenges: jsonData.daily_challenges || [],
          archetype: jsonData.archetype || 'general',
          difficulty_multiplier: jsonData.difficulty_multiplier || 'intermediate'
        };
      }

      setMessages(prev => prev.map(m => m.id === buddyMsgId ? {
        ...m,
        text: displayText,
        showButtons: isPlan || requiresPlanUpdate,
        actionType: isPlan ? (planData?.type ? planData.type : category) : responseActionType,
        isPlanMessage: isPlan,
        planData: isPlan ? planData : undefined
      } : m));
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail || err.response?.data?.message || err.message;
      setMessages(prev => prev.map(m => m.id === buddyMsgId ? {
        ...m,
        text: errorDetail?.includes('413')
          ? 'The chat request was too large. Please start a new chat and try again.'
          : 'Failed to connect to the AI coach. Please try again.'
      } : m));
    } finally {
      setLoading(false);
    }
  };

  const pinChat = async (message: Message) => {
    try {
      const response = await axios.post('http://localhost:8000/api/plans/pin-chat', {
        user_id: userId.trim(),
        chat_message: message.text,
        sender: message.sender
      });
      const pinId = response.data.pin_id;
      setMessages(prev => prev.map(m => m.id === message.id ? { ...m, pinId } : m));
      alert('Chat pinned for 7 days!');

      // Refresh pinned list immediately if the drawer is open
      if (showPinnedDrawer) {
        await fetchPinnedChats();
      }
    } catch (err) {
      console.error('Failed to pin chat:', err);
      alert('Failed to pin chat');
    }
  };

  const fetchPinnedChats = async () => {
    const res = await axios.get(`http://localhost:8000/api/plans/pinned-chats/${safeUserId}`);
    setPinnedList((res.data.chats || []).map(normalizePinnedChat));
    setShowPinnedDrawer(true);
  };

  const fetchRecentSessions = async () => {
    try {
      // Fetch from chat_sessions collection
      const response = await axios.get(`http://localhost:8000/api/plans/chat-sessions/${safeUserId}`);
      setRecentSessions(response.data.sessions || []);
      setShowSessionsDrawer(true);
    } catch (err) {
      console.log('[SESSIONS_FETCH] No sessions found yet', err);
      setRecentSessions([]);
      setShowSessionsDrawer(true);
    }
  };

  const loadPinnedMessage = (pinned: any) => {
    const normalizedPinned = normalizePinnedChat(pinned);
    // Load the pinned message into the chat
    const loadedMessage: Message = {
      id: `pinned-${normalizedPinned.id}`,
      sender: normalizedPinned.sender === 'user' ? 'user' : 'buddy',
      text: normalizedPinned.text,
      isPlanMessage: false,
      pinId: normalizedPinned.id,
      isPinnedLoaded: true
    };
    setMessages([loadedMessage]);
    setShowPinnedDrawer(false);
  };

  const unpinChat = async (message: Message) => {
    if (!message.pinId) return;

    try {
      await axios.post('http://localhost:8000/api/plans/unpin-chat', {
        user_id: userId.trim(),
        pin_id: message.pinId
      });
      setPinnedList(prev => prev.filter(item => normalizePinnedChat(item).id !== message.pinId));
      setMessages(prev => prev.filter(item => item.id !== message.id));
    } catch (err) {
      console.error('Failed to unpin chat:', err);
      alert('Failed to unpin chat');
    }
  };

  const loadSession = (session: any) => {
    if (session.messages && session.messages.length > 0) {
      setActiveSessionId(session.session_id || session._id || createSessionId());
      // Load the session messages into the chat
      const loadedMessages = session.messages.map((msg: any, idx: number) => ({
        id: `loaded-${session._id || session.session_id || activeSessionId}-${msg.timestamp || idx}-${idx}`,
        sender: msg.sender || 'buddy',
        text: msg.text || msg.message || '',
        isPlanMessage: false
      }));
      setMessages(loadedMessages);
      setShowSessionsDrawer(false);
    }
  };

  const startNewSession = () => {
    setActiveSessionId(createSessionId());
    setMessages([]);
    setInputMessage('');
  };

  const handlePlanUpdate = async (message: Message, action: 'update' | 'cancel') => {
    if (action === 'cancel') {
      setMessages(prev => prev.map(m => m.id === message.id ? { ...m, showButtons: false } : m));
      return;
    }

    try {
      if (message.planData?.type === 'diet') {
        // Save diet plan with grocery list
        const response = await axios.post('http://localhost:8000/api/plans/save-diet-plan', {
          user_id: userId.trim(),
          diet_plan: message.planData.diet_plan || {},
          grocery_list: message.planData.grocery_list || [],
          notes: ''
        });
        console.log('[DIET_PLAN_SAVE] Success:', response.data);
        alert('✓ Diet plan and grocery list saved successfully!');
      } else if (message.planData?.type === 'workout') {
        // Save workout plan with daily challenges
        const response = await axios.post('http://localhost:8000/api/plans/save-workout-plan', {
          user_id: userId.trim(),
          workout_plan: message.planData.workout_plan || {},
          daily_challenges: message.planData.daily_challenges || [],
          archetype: message.planData.archetype || 'general',
          difficulty_multiplier: message.planData.difficulty_multiplier || 'intermediate'
        });
        console.log('[WORKOUT_PLAN_SAVE] Success:', response.data);
        alert('✓ Workout plan with daily challenges saved successfully!');
        window.dispatchEvent(new CustomEvent('workout-plan-saved', { detail: { userId: userId.trim() } }));
      } else {
        const response = await axios.post('http://localhost:8000/api/gym-buddy/serialize-and-commit', {
          user_id: userId.trim(),
          action_type: message.actionType || 'plan',
          approved_chat_plan: message.text
        });
        console.log('[APPROVED_PLAN_SAVE] Success:', response.data);
        alert('Plan saved successfully!');
        if ((message.actionType || 'plan') === 'workout' || String(message.text).toLowerCase().includes('workout plan')) {
          window.dispatchEvent(new CustomEvent('workout-plan-saved', { detail: { userId: userId.trim() } }));
        }
      }
      // Hide buttons after successful save
      setMessages(prev => prev.map(m => m.id === message.id ? { ...m, showButtons: false } : m));
    } catch (err: any) {
      console.error('[PLAN_UPDATE_ERROR] Failed to save plan:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to save plan';
      alert('✗ Error: ' + errorMsg);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#161616] overflow-hidden relative scrollbar-none">
      {/* HEADER TOOLBAR BAR */}
      <div className="h-16 px-5 border-b border-zinc-800 flex items-center justify-between bg-[#1a1a1a] shrink-0">
        <div className="flex items-center space-x-2">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
          <h3 className="text-xs font-black tracking-widest text-zinc-200 uppercase">AI Fitness Coach</h3>
        </div>
        <div className="flex items-center space-x-1">
          <button onClick={async () => {
            try {
              await fetchPinnedChats();
            } catch (error: any) {
              console.error('[PINNED_MESSAGES_ERROR]', error);
              alert('Failed to load pinned messages. Please try again.');
            }
          }} className="p-2 text-zinc-400 hover:text-cyan-400 transition-colors" title="View pinned messages"><Pin size={14} /></button>
          <button onClick={startNewSession} className="p-2 text-zinc-400 hover:text-cyan-400 transition-colors" title="New chat"><Search size={14} /></button>
          <button onClick={fetchRecentSessions} className="p-2 text-zinc-400 hover:text-purple-400 transition-colors" title="Recent chat sessions"><History size={14} /></button>
          {onClose && <button onClick={onClose} className="p-2 text-zinc-400 hover:text-rose-400 transition-colors"><X size={14} /></button>}
        </div>
      </div>

      {/* CHAT HUB CONVERSATION SCREEN */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5 relative scrollbar-none">
        {messages.length === 0 && (
          <div className="h-full flex flex-col justify-center py-6 space-y-8 select-none animate-fadeIn">
            <div className="space-y-2">
              <h1 className="text-3xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-cyan-400 to-purple-500">Hello, Jack</h1>
              <h2 className="text-2xl font-bold text-zinc-500 tracking-tight leading-none">How can I help you today?</h2>
            </div>
            <div className="space-y-2.5 max-w-[95%]">
              <button onClick={() => handleSendTextMessage("What workout program structure fits my metrics today?")} className="w-full text-left bg-[#1e1e1e] border border-zinc-800/80 p-3.5 rounded-xl text-xs font-semibold text-zinc-300 hover:bg-zinc-800 hover:border-zinc-700 transition-all block">What program fits my metrics today?</button>
              <button onClick={() => handleSendTextMessage("Explain progressive overload rules to me.")} className="w-full text-left bg-[#1e1e1e] border border-zinc-800/80 p-3.5 rounded-xl text-xs font-semibold text-zinc-300 hover:bg-zinc-800 hover:border-zinc-700 transition-all block">Explain progressive overload levels.</button>
            </div>
          </div>
        )}

                {/* Traditional Scrolling Conversation Bubbles Render Mapping */}
        {messages.map((msg) => {
          const isUser = msg.sender === 'user';
          return (
            <div key={msg.id} className={`flex gap-3 max-w-[88%] ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}>
              <div className={`h-7 w-7 rounded-full shrink-0 flex items-center justify-center border text-xs ${isUser ? 'bg-zinc-800 border-zinc-700 text-zinc-300' : 'bg-cyan-500/10 border-cyan-500/20 text-cyan-400'}`}>
                {isUser ? <User size={12} /> : <Bot size={12} />}
              </div>
              <div className="space-y-3 w-full group relative">
                <div className={`rounded-xl p-3 text-xs leading-relaxed shadow-sm border ${isUser ? 'bg-zinc-900 border-zinc-800 text-zinc-200 rounded-tr-none' : 'bg-[#1e1e1e] border-zinc-800 text-zinc-300 rounded-tl-none'}`}>
                  <ChatText text={msg.text} loading={loading && !msg.text} />
                </div>

                {/* PIN BUTTON FOR ALL MESSAGES */}
                {!isUser && !msg.isPlanMessage && !msg.isProposalCard && (
                  <button 
                    onClick={() => pinChat(msg)}
                    className="absolute -right-6 top-3 p-1 text-zinc-600 hover:text-cyan-400 opacity-0 group-hover:opacity-100 transition-all"
                    title="Pin this chat for 7 days"
                  >
                    <Pin size={12} className={msg.pinId ? "rotate-45 text-cyan-400" : "rotate-45"} />
                  </button>
                )}

                {/* PLAN MESSAGE CARD (Diet or Workout) - Using PlanDisplayCard Component */}
                {!isUser && msg.isPlanMessage && msg.planData && (
                  <PlanDisplayCard 
                    planData={msg.planData}
                    onUpdate={msg.showButtons ? () => handlePlanUpdate(msg, 'update') : undefined}
                    onCancel={msg.showButtons ? () => handlePlanUpdate(msg, 'cancel') : undefined}
                  />
                )}

                {/* UNPIN OPTION FOR A LOADED PINNED CHAT */}
                {msg.isPinnedLoaded && msg.pinId && (
                  <button
                    onClick={() => unpinChat(msg)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-zinc-800 text-zinc-400 rounded-md text-[11px] font-bold uppercase bg-transparent hover:text-rose-300 hover:border-rose-500/30"
                  >
                    <PinOff size={12} />
                    Unpin
                  </button>
                )}

                {/* WORKOUT INTERACTIVE DETAILS WIDGET PREVIEW */}
                {!isUser && msg.isProposalCard && msg.proposalData && (
                  <div className="bg-[#0f0f0f] border border-zinc-800 rounded-xl p-4 space-y-3 shadow-xl w-full">
                    <div className="flex items-center justify-between border-b border-zinc-900 pb-2 text-[11px] font-black uppercase text-zinc-400">
                      <span>Routine Proposal Block</span>
                      <span className="text-cyan-400 text-[9px]">{msg.proposalData.current_difficulty_multiplier || 'N/A'}</span>
                    </div>
                    <div className="space-y-2 max-h-[220px] overflow-y-auto scrollbar-none text-[11px]">
                      {Array.isArray(msg.proposalData.schedule) && msg.proposalData.schedule.length > 0 ? (
                        msg.proposalData.schedule.map((day: any) => (
                          <div key={day.day_number} className="bg-[#161616] p-2.5 rounded border border-zinc-800">
                            <div className="font-bold text-zinc-300">Day {day.day_number} • {day.target_muscle_split}</div>
                            {Array.isArray(day.exercises) && day.exercises.map((ex: any, idx: number) => (
                              <div key={idx} className="text-zinc-400 pl-2 mt-0.5">• {ex.exercise_name} ({ex.prescribed_sets}x{ex.prescribed_reps})</div>
                            ))}
                          </div>
                        ))
                      ) : (
                        <div className="text-zinc-500 text-[11px]">No schedule details available yet.</div>
                      )}
                    </div>
                  </div>
                )}

                {/* INTERACTIVE STATE ACTION CHOICE BUTTONS STRIP */}
                {!isUser && msg.showButtons && msg.actionType && msg.isPlanMessage && (
                  <div className="flex items-center space-x-2 pt-1 animate-fadeIn">
                    <button 
                      onClick={() => handlePlanUpdate(msg, 'cancel')}
                      className="px-3 py-1.5 border border-zinc-800 text-zinc-400 rounded-md text-[11px] font-bold uppercase bg-transparent hover:text-zinc-200 hover:border-rose-500/30"
                    >
                      Cancel
                    </button>
                    <button 
                      onClick={() => handlePlanUpdate(msg, 'update')}
                      className="px-4 py-1.5 bg-cyan-500 hover:bg-cyan-600 text-zinc-950 rounded-md text-[11px] font-black uppercase shadow-md"
                    >
                      Save & Update
                    </button>
                  </div>
                )}

                {/* PLAN ACTION BUTTONS FOR CONVERSATIONAL 7-DAY PLANS */}
                {!isUser && msg.showButtons && msg.actionType && !msg.isPlanMessage && !msg.isProposalCard && (
                  <div className="flex items-center space-x-2 pt-1 animate-fadeIn">
                    <button 
                      onClick={() => handlePlanUpdate(msg, 'cancel')}
                      className="px-3 py-1.5 border border-zinc-800 text-zinc-400 rounded-md text-[11px] font-bold uppercase bg-transparent hover:text-zinc-200 hover:border-rose-500/30"
                    >
                      Cancel
                    </button>
                    <button 
                      onClick={() => handlePlanUpdate(msg, 'update')}
                      className="px-4 py-1.5 bg-cyan-500 hover:bg-cyan-600 text-zinc-950 rounded-md text-[11px] font-black uppercase shadow-md"
                    >
                      Save & Update
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
        <div ref={chatEndRef} />
      </div>

      {/* BOOKMARKS DRAW OVERLAY MATRIX */}
      {showPinnedDrawer && (
        <div className="absolute inset-0 z-50 bg-[#161616] flex flex-col animate-slideUp">
          <div className="h-16 px-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900">
            <span className="text-xs font-black uppercase tracking-widest text-cyan-400 flex items-center gap-1.5">
              <Pin size={12} /> Bookmarked Notes
            </span>
            <button onClick={() => setShowPinnedDrawer(false)} className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-200">
              <X size={14} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {pinnedList.length === 0 ? (
              <div className="text-center text-zinc-600 text-xs font-mono py-10">No pinned logs chunks active.</div>
            ) : (
              pinnedList.map((item: any) => {
                const pinned = normalizePinnedChat(item);
                return (
                <button
                  key={pinned.id}
                  onClick={() => loadPinnedMessage(pinned)}
                  className="w-full bg-zinc-900/60 p-3 rounded-lg border border-zinc-800 text-left hover:border-cyan-500/40 transition-all hover:bg-zinc-900/80"
                >
                  <div className="text-[11px] leading-relaxed text-zinc-300">"{pinned.text}"</div>
                  <div className="text-[9px] text-zinc-600 font-mono mt-2 uppercase">Pinned on: {new Date(pinned.pinned_at).toLocaleDateString()}</div>
                </button>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* RECENT SESSIONS DRAWER */}
      {showSessionsDrawer && (
        <div className="absolute inset-0 z-50 bg-[#161616] flex flex-col animate-slideUp">
          <div className="h-16 px-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900">
            <span className="text-xs font-black uppercase tracking-widest text-purple-400 flex items-center gap-1.5">
              <History size={12} /> Recent Chat Sessions
            </span>
            <button onClick={() => setShowSessionsDrawer(false)} className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-200">
              <X size={14} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {recentSessions.length === 0 ? (
              <div className="text-center text-zinc-600 text-xs font-mono py-10">No chat sessions found. Start a new chat to create sessions.</div>
            ) : (
              recentSessions.map((session: any, idx: number) => (
                <button
                  key={sessionRowKey(session, idx)}
                  onClick={() => loadSession(session)}
                  className="w-full bg-zinc-900/60 p-3 rounded-lg border border-zinc-800 text-left hover:border-purple-500/40 transition-all hover:bg-zinc-900/80"
                >
                  <div className="text-[11px] font-bold text-purple-400 mb-1 truncate">{session.title || `Session ${idx + 1}`}</div>
                  <div className="text-[10px] text-zinc-400 mb-2">{session.message_count || 0} messages</div>
                  {session.preview && <div className="text-[10px] text-zinc-500 mb-2 line-clamp-2">{session.preview}</div>}
                  <div className="text-[9px] text-zinc-600">
                    Updated: {new Date(session.updated_at || session.created_at).toLocaleDateString()}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}

      {/* CONSOLE INPUT FORM KEYBOARD STRIP BAR */}
      <form onSubmit={(e) => { e.preventDefault(); handleSendTextMessage(); }} className="p-4 border-t border-zinc-800 bg-zinc-900/40 shrink-0">
        <div className="relative flex items-center">
          <input 
            type="text" 
            value={inputMessage} 
            onChange={(e) => setInputMessage(e.target.value)} 
            disabled={loading} 
            placeholder="Chat casually with buddy or tap dashboard widgets..." 
            className="w-full bg-[#161616] border border-zinc-800 rounded-xl pl-4 pr-10 py-2.5 text-xs font-medium text-zinc-200 focus:outline-none focus:border-cyan-500/60" 
          />
          <button 
            type="submit" 
            disabled={!inputMessage.trim() || loading} 
            className="absolute right-2 p-1.5 text-zinc-500 hover:text-cyan-400 transition-colors"
          >
            <Send size={13} />
          </button>
        </div>
      </form>

    </div>
  );
}
