import { useState, useEffect } from 'react';
import { BarChart3, LayoutDashboard, History, Trophy, MapPin, Settings, Bell, MessageSquare, User, ChefHat, LogOut } from 'lucide-react';
import SettingsTab from './components/SettingsTab';
import GymTab from './components/GymTab';
import ChallengesTab from './components/ChallengesTab';
import DashboardTab from './components/DashboardTab'; 
import WorkoutHistoryTab from './components/WorkoutHistoryTab';
import DietPlansTab from './components/DietPlansTab';
import AITrainerSidebarPanel from './components/AITrainerSidebarPanel';
import LoginRegisterPage from './components/LoginRegisterPage';
import ProfileCompletion from './components/ProfileCompletion';
import AdminDashboardTab from './components/AdminDashboardTab';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [profilePending, setProfilePending] = useState<boolean>(false);
  const [userId, setUserId] = useState<string>('');
  const [userName, setUserName] = useState<string>('');
  const [userRole, setUserRole] = useState<'user' | 'admin'>('user');
  const [token, setToken] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'dashboard' | 'history' | 'challenges' | 'gym' | 'diet-plans' | 'settings' | 'admin'>('dashboard');
  const [isChatOpen, setIsChatOpen] = useState<boolean>(false);
  const [chatTriggerMsg, setChatTriggerMsg] = useState<string | null>(null);
  const [isProfileOpen, setIsProfileOpen] = useState<boolean>(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState<boolean>(false);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [gymNearbyRequest, setGymNearbyRequest] = useState(0);

  // Check for existing session on mount
  useEffect(() => {
    validateStoredSession();
  }, []);

  const validateStoredSession = async () => {
    clearLegacyAuthStorage();
    const storedToken = sessionStorage.getItem('auth_token');
    const storedUserId = sessionStorage.getItem('user_id');
    const storedUserRole = (sessionStorage.getItem('user_role') || 'user') as 'user' | 'admin';
    const profilePend = sessionStorage.getItem('profile_pending');

    if (!storedToken || !storedUserId) return;

    try {
      const endpoint = storedUserRole === 'admin'
        ? 'http://localhost:8000/api/auth/admin/me'
        : 'http://localhost:8000/api/auth/me';
      const response = await fetch(endpoint, {
        headers: { Authorization: `Bearer ${storedToken}` }
      });
      if (!response.ok) {
        clearSessionAuthStorage();
        return;
      }
      const currentUser = await response.json();
      const resolvedRole = currentUser.role === 'admin' ? 'admin' : 'user';

      setToken(storedToken);
      setUserId(currentUser.user_id || storedUserId);
      setUserName(currentUser.name || sessionStorage.getItem('user_name') || 'User');
      setUserRole(resolvedRole);
      setActiveTab(resolvedRole === 'admin' ? 'admin' : 'dashboard');
      setIsAuthenticated(true);
      setProfilePending(resolvedRole === 'admin' ? false : profilePend === 'true');
      sessionStorage.setItem('user_id', currentUser.user_id || storedUserId);
      sessionStorage.setItem('user_name', currentUser.name || sessionStorage.getItem('user_name') || 'User');
      sessionStorage.setItem('user_email', currentUser.email || sessionStorage.getItem('user_email') || '');
      sessionStorage.setItem('user_role', resolvedRole);
    } catch {
      clearSessionAuthStorage();
    }
  };

  const handleAuthSuccess = (newToken: string, newUserId: string, newName: string, _email: string, role: string = 'user') => {
    const normalizedRole = role === 'admin' ? 'admin' : 'user';
    setToken(newToken);
    setUserId(newUserId);
    setUserName(newName);
    setUserRole(normalizedRole);
    setActiveTab(normalizedRole === 'admin' ? 'admin' : 'dashboard');
    setIsAuthenticated(true);
    // Check if this is a new registration (profile pending)
    if (normalizedRole === 'user' && sessionStorage.getItem('profile_pending') === 'true') {
      setProfilePending(true);
    } else {
      setProfilePending(false);
    }
  };

  const handleProfileComplete = () => {
    setProfilePending(false);
    sessionStorage.removeItem('profile_pending');
  };

  const handleLogout = () => {
    clearSessionAuthStorage();
    clearLegacyAuthStorage();
    setIsAuthenticated(false);
    setProfilePending(false);
    setUserId('');
    setUserName('');
    setUserRole('user');
    setToken('');
  };

  const clearSessionAuthStorage = () => {
    sessionStorage.removeItem('auth_token');
    sessionStorage.removeItem('user_id');
    sessionStorage.removeItem('user_name');
    sessionStorage.removeItem('user_email');
    sessionStorage.removeItem('user_role');
    sessionStorage.removeItem('profile_pending');
  };

  const clearLegacyAuthStorage = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('user_name');
    localStorage.removeItem('user_email');
    localStorage.removeItem('user_role');
    localStorage.removeItem('profile_pending');
  };

  const fetchNotifications = async () => {
    if (!userId) return;
    try {
      const response = await fetch(`http://localhost:8000/api/plans/notifications/${encodeURIComponent(userId)}`);
      const data = await response.json();
      const readIds = getReadNotificationIds(userId);
      const unread = Array.isArray(data.notifications)
        ? data.notifications.filter((item: any) => !readIds.has(item.id))
        : [];
      setNotifications(unread);
    } catch (error) {
      console.error('Failed to load notifications:', error);
      setNotifications([]);
    }
  };

  useEffect(() => {
    if (!userId) return;
    fetchNotifications();
  }, [userId, activeTab]);

  const handleNotificationAction = (item: any) => {
    markNotificationRead(userId, item.id);
    setNotifications(prev => prev.filter(notification => notification.id !== item.id));
    setIsNotificationsOpen(false);
    const action = item.action;
    if (action === 'open_diet') {
      setActiveTab('diet-plans');
    } else if (action === 'open_workout' || action === 'open_history') {
      setActiveTab('history');
    } else if (action === 'plan_diet' || action === 'plan_next_diet') {
      setChatTriggerMsg(`__trigger_diet_plan__:${Date.now()}`);
      setIsChatOpen(true);
    } else if (action === 'plan_workout' || action === 'plan_next_workout') {
      setChatTriggerMsg(`__trigger_workout_plan__:${Date.now()}`);
      setIsChatOpen(true);
    }
  };

  const getReadNotificationIds = (targetUserId: string) => {
    try {
      return new Set(JSON.parse(localStorage.getItem(`read_notifications:${targetUserId}`) || '[]'));
    } catch {
      return new Set<string>();
    }
  };

  const markNotificationRead = (targetUserId: string, notificationId: string) => {
    if (!targetUserId || !notificationId) return;
    const readIds = getReadNotificationIds(targetUserId);
    readIds.add(notificationId);
    localStorage.setItem(`read_notifications:${targetUserId}`, JSON.stringify(Array.from(readIds).slice(-100)));
  };

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <LoginRegisterPage onAuthSuccess={handleAuthSuccess} />;
  }

  // Show profile completion if needed
  if (profilePending && userRole === 'user') {
    return (
      <ProfileCompletion
        userId={userId}
        userName={userName}
        token={token}
        onProfileComplete={handleProfileComplete}
      />
    );
  }

  // ◄ RESTORED THE STATIC ARRAY DATA MATRIX THAT WAS CAUSING TS(2552)
  const navigationItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'history', label: 'Workout History', icon: History },
    { id: 'challenges', label: 'Challenges', icon: Trophy },
    { id: 'gym', label: 'Find Gym', icon: MapPin },
    { id: 'diet-plans', label: 'Diet Plans', icon: ChefHat },
    { id: 'settings', label: 'Settings', icon: Settings },
  ] as const;

  if (userRole === 'admin') {
    return (
      <div className="flex h-screen bg-[#121212] text-gray-100 font-sans antialiased overflow-hidden">
        <aside className="w-64 bg-[#1e1e1e] border-r border-gray-800 flex flex-col shrink-0 hidden lg:flex">
          <div className="p-6 border-b border-gray-800">
            <h1 className="text-xl font-black tracking-widest text-cyan-400">FITNESS AI ADMIN</h1>
          </div>
          <nav className="flex-1 p-4 space-y-2">
            <button className="w-full flex items-center space-x-3 px-4 py-3 rounded-lg font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <BarChart3 size={20} />
              <span>Admin Overview</span>
            </button>
          </nav>
        </aside>
        <main className="flex-1 flex flex-col min-w-0 h-full overflow-y-auto bg-[#121212]">
          <header className="h-16 bg-[#1e1e1e] border-b border-gray-800 flex items-center justify-between px-6 lg:px-8 shrink-0">
            <div className="flex items-center space-x-2">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400"></span>
              <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-200">Admin Overview</h2>
            </div>
            <div className="relative">
              <button
                onClick={() => setIsProfileOpen(!isProfileOpen)}
                className="p-2 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-400 border border-cyan-500/40 rounded-lg transition-all flex items-center space-x-2"
                title="Admin Profile"
              >
                <User size={13} className="stroke-[2.5]" />
                <span className="text-xs font-medium hidden sm:inline">{userName}</span>
              </button>
              {isProfileOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-[#1e1e1e] border border-zinc-700 rounded-lg shadow-lg z-50 animate-fadeIn">
                  <div className="p-3 border-b border-zinc-700">
                    <p className="text-xs font-medium text-cyan-400">{userName}</p>
                    <p className="text-xs text-zinc-500">{sessionStorage.getItem('user_email')}</p>
                    <p className="text-[10px] text-purple-400 uppercase tracking-wider mt-1">Admin</p>
                  </div>
                  <button
                    onClick={() => {
                      handleLogout();
                      setIsProfileOpen(false);
                    }}
                    className="w-full flex items-center space-x-2 px-4 py-2.5 text-sm text-red-400 hover:bg-red-500/10 transition-colors rounded-b-lg"
                  >
                    <LogOut size={14} />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          </header>
          <div className="p-4 lg:p-8 max-w-[1400px] w-full mx-auto h-full">
            <AdminDashboardTab />
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#121212] text-gray-100 font-sans antialiased overflow-hidden">
      {/* Sidebar Navigation Panel Layout */}
      <aside className="w-64 bg-[#1e1e1e] border-r border-gray-800 flex flex-col shrink-0 hidden lg:flex">
        <div className="p-6 border-b border-gray-800">
          <h1 className="text-xl font-black tracking-widest text-cyan-400">FITNESS AI CORE</h1>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg font-medium transition-all duration-150 ${
                  isActive 
                    ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' 
                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                }`}
              >
                <Icon size={20} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      {/* ────────────────────────────────────────────────────────
          ↔️ MAIN WORKSPACE CONTROLLER CORE SPLIT MATRIX (Issue #4 Fix)
          Desktop: Content + Chat Side-by-Side
          Mobile: Full Screen Chat Overlay
          ──────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-row min-w-0 relative overflow-hidden h-full">
        
        {/* Left Side Sub-Shell: Primary Tab Content Port View */}
        <main className="flex-1 flex flex-col min-w-0 h-full overflow-y-auto bg-[#121212] scrollbar-none">
          {/* Master Application Header Frame */}
          <header className="h-16 bg-[#1e1e1e] border-b border-gray-800 flex items-center justify-between px-6 lg:px-8 shrink-0">
            <div className="flex items-center space-x-2">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400"></span>
              <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-200">
                {activeTab.replace('-', ' ')} Overview
              </h2>
            </div>

            <div className="flex items-center space-x-2.5">
              <div className="relative">
                <button
                  onClick={() => {
                    setIsNotificationsOpen(!isNotificationsOpen);
                    fetchNotifications();
                  }}
                  className="relative p-2 bg-[#141414] hover:bg-[#222] border border-gray-800 rounded-lg text-zinc-400 transition-colors"
                  title="Notifications"
                >
                  <Bell size={14} className="stroke-[2.5]" />
                  {notifications.length > 0 && (
                    <span className="absolute -top-1 -right-1 h-4 min-w-4 px-1 rounded-full bg-cyan-500 text-[9px] font-black text-zinc-950 flex items-center justify-center">
                      {notifications.length}
                    </span>
                  )}
                </button>
                {isNotificationsOpen && (
                  <div className="absolute right-0 mt-2 w-80 max-w-[calc(100vw-2rem)] bg-[#1e1e1e] border border-zinc-700 rounded-lg shadow-lg z-50 animate-fadeIn overflow-hidden">
                    <div className="p-3 border-b border-zinc-700 flex items-center justify-between">
                      <p className="text-xs font-bold text-zinc-200 uppercase tracking-wider">Notifications</p>
                      <span className="text-[10px] text-zinc-500">{notifications.length} active</span>
                    </div>
                    <div className="max-h-96 overflow-y-auto">
                      {notifications.length === 0 ? (
                        <div className="p-4 text-xs text-zinc-500">No fitness notifications right now.</div>
                      ) : (
                        notifications.map((item) => (
                          <button
                            key={item.id}
                            onClick={() => handleNotificationAction(item)}
                            className="w-full text-left p-3 border-b border-zinc-800 last:border-b-0 hover:bg-zinc-800/60 transition-colors"
                          >
                            <div className="flex items-start gap-3">
                              <span className={`mt-1 h-2 w-2 rounded-full shrink-0 ${
                                item.severity === 'success' ? 'bg-green-400' : item.severity === 'warning' ? 'bg-amber-400' : 'bg-cyan-400'
                              }`} />
                              <div className="space-y-1">
                                <p className="text-xs font-bold text-zinc-200">{item.title}</p>
                                <p className="text-[11px] leading-relaxed text-zinc-500">{item.message}</p>
                              </div>
                            </div>
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Toggable Split View Command Button Component */}
              <button 
                onClick={() => setIsChatOpen(!isChatOpen)}
                className={`flex items-center space-x-2 px-3 py-1.5 border rounded-lg text-xs font-bold transition-all duration-200 ${
                  isChatOpen 
                    ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40' 
                    : 'bg-[#141414] hover:bg-[#222] border-gray-800 text-zinc-300'
                }`}
                title="Chat AI Trainer"
              >
                <MessageSquare size={13} className="text-cyan-400 stroke-[2.5]" />
                <span className="tracking-wide">Chat AI Trainer</span>
              </button>

              {/* User Profile Dropdown - Touch-friendly (Issue #2 Fix) */}
              <div className="relative">
                <button 
                  onClick={() => setIsProfileOpen(!isProfileOpen)}
                  className="p-2 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-400 border border-cyan-500/40 rounded-lg transition-all flex items-center space-x-2" 
                  title="User Profile"
                >
                  <User size={13} className="stroke-[2.5]" />
                  <span className="text-xs font-medium hidden sm:inline">{userName}</span>
                </button>
                
                {/* Dropdown Menu - Click/Tap to Toggle */}
                {isProfileOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-[#1e1e1e] border border-zinc-700 rounded-lg shadow-lg z-50 animate-fadeIn">
                    <div className="p-3 border-b border-zinc-700">
                      <p className="text-xs font-medium text-cyan-400">{userName}</p>
                      <p className="text-xs text-zinc-500">{sessionStorage.getItem('user_email')}</p>
                    </div>
                    <button
                      onClick={() => {
                        handleLogout();
                        setIsProfileOpen(false);
                      }}
                      className="w-full flex items-center space-x-2 px-4 py-2.5 text-sm text-red-400 hover:bg-red-500/10 transition-colors rounded-b-lg"
                    >
                      <LogOut size={14} />
                      <span>Sign Out</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          </header>

          {/* Workspace Display Viewports Content Deck */}
          <div className="p-4 lg:p-8 max-w-[1400px] w-full mx-auto h-full">
            {activeTab === 'dashboard' && (
              <DashboardTab 
                onTriggerDiet={() => { setChatTriggerMsg(`__trigger_diet_plan__:${Date.now()}`); setIsChatOpen(true); }}
                onTriggerWorkout={() => { setChatTriggerMsg(`__trigger_workout_plan__:${Date.now()}`); setIsChatOpen(true); }}
                onTriggerGym={() => { setActiveTab('gym'); setGymNearbyRequest(Date.now()); }}
                onOpenDiet={() => setActiveTab('diet-plans')}
                onOpenWorkout={() => setActiveTab('history')}
                userId={userId}
                userName={userName}
              />
            )}
            {activeTab === 'history' && <WorkoutHistoryTab userId={userId} />}
            {activeTab === 'challenges' && <ChallengesTab userId={userId} />}
            {activeTab === 'gym' && <GymTab userId={userId} nearbyRequestToken={gymNearbyRequest} />}
            {activeTab === 'diet-plans' && <DietPlansTab userId={userId} />}
            {activeTab === 'admin' && <AdminDashboardTab />}
            {activeTab === 'settings' && <SettingsTab />}
          </div>
        </main>

        {/* Right Side Sub-Shell: AI Chat Panel - Responsive Layout (Issue #4 Fix) */}
        {/* Desktop: Visible side pane | Mobile: Full screen overlay */}
        
        {/* Mobile Overlay - Full Screen (sm screens) */}
        {isChatOpen && (
          <div className="fixed inset-0 z-[9999] lg:hidden bg-[#161616] flex flex-col border-t border-zinc-800 overflow-hidden animate-slideUp">
            <AITrainerSidebarPanel 
              userId={userId} 
              onClose={() => setIsChatOpen(false)} 
              incomingTrigger={chatTriggerMsg} 
            />
          </div>
        )}
        
        {/* Desktop Split Pane - Visible side-by-side (lg+ screens) */}
        <div className={`hidden lg:flex lg:flex-col w-[400px] xl:w-[450px] h-full border-l border-zinc-800 bg-[#161616] shrink-0 overflow-hidden ${!isChatOpen ? 'lg:hidden' : ''}`}>
          <AITrainerSidebarPanel 
            userId={userId} 
            onClose={() => setIsChatOpen(false)} 
            incomingTrigger={chatTriggerMsg} 
          />
        </div>

      </div>
    </div>
  );
}
