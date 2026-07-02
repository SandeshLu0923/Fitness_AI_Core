import React from 'react';
import { Send } from 'lucide-react';

interface ChatInputFormProps {
  inputMessage: string;
  setInputMessage: (msg: string) => void;
  loading: boolean;
  onSubmit: (e: React.FormEvent) => void;
}

export default function ChatInputForm({
  inputMessage,
  setInputMessage,
  loading,
  onSubmit,
}: ChatInputFormProps) {
  return (
    <form onSubmit={onSubmit} className="p-4 border-t border-zinc-800 bg-zinc-900/40 shrink-0">
      <div className="relative flex items-center">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          disabled={loading}
          placeholder="Ask about macros, tracking stats, or program blocks..."
          className="w-full bg-[#161616] border border-zinc-800 rounded-xl pl-4 pr-10 py-2.5 text-xs font-medium text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-cyan-500/60 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!inputMessage.trim() || loading}
          className="absolute right-2 p-1.5 text-zinc-500 hover:text-cyan-400 disabled:text-zinc-800 transition-colors"
        >
          <Send size={13} className="stroke-[2.5]" />
        </button>
      </div>
    </form>
  );
}
