import { useState } from 'react';
import { Mail, Lock, User, Eye, EyeOff } from 'lucide-react';
import axios from 'axios';

interface LoginRegisterPageProps {
  onAuthSuccess: (token: string, userId: string, name: string, email: string, role: string) => void;
}

export default function LoginRegisterPage({ onAuthSuccess }: LoginRegisterPageProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [authMode, setAuthMode] = useState<'user' | 'admin'>('user');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  // Login form
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Register form
  const [registerName, setRegisterName] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerPasswordConfirm, setRegisterPasswordConfirm] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const endpoint = authMode === 'admin'
        ? 'http://localhost:8000/api/auth/admin/login'
        : 'http://localhost:8000/api/auth/login';
      const response = await axios.post(endpoint, {
        email: loginEmail,
        password: loginPassword
      });

      const { token, user_id, name, email, role = authMode } = response.data;
      sessionStorage.setItem('auth_token', token);
      sessionStorage.setItem('user_id', user_id);
      sessionStorage.setItem('user_name', name);
      sessionStorage.setItem('user_email', email);
      sessionStorage.setItem('user_role', role);
      sessionStorage.removeItem('profile_pending');
      clearLegacyAuthStorage();

      onAuthSuccess(token, user_id, name, email, role);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (registerPassword !== registerPasswordConfirm) {
      setError('Passwords do not match');
      return;
    }

    if (registerPassword.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setLoading(true);

    try {
      const response = await axios.post('http://localhost:8000/api/auth/register', {
        name: registerName,
        email: registerEmail,
        password: registerPassword
      });

      const { token, user_id, name, email, role = 'user' } = response.data;
      sessionStorage.setItem('auth_token', token);
      sessionStorage.setItem('user_id', user_id);
      sessionStorage.setItem('user_name', name);
      sessionStorage.setItem('user_email', email);
      sessionStorage.setItem('user_role', role);
      sessionStorage.setItem('profile_pending', 'true');
      clearLegacyAuthStorage();

      onAuthSuccess(token, user_id, name, email, role);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-[#121212] text-gray-100 font-sans">
      {/* Left Side - Brand Section */}
      <div className="hidden lg:flex w-1/2 bg-gradient-to-br from-cyan-600 via-cyan-500 to-blue-600 flex-col justify-center items-center p-12 relative overflow-hidden">
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-20 left-20 w-40 h-40 bg-white rounded-full blur-3xl"></div>
          <div className="absolute bottom-20 right-20 w-40 h-40 bg-blue-400 rounded-full blur-3xl"></div>
        </div>
        
        <div className="relative z-10 text-center space-y-6">
          <h1 className="text-5xl font-black tracking-tight text-white">FITNESS AI CORE</h1>
          <p className="text-xl text-cyan-100">Your Personal AI Fitness Coach</p>
          <div className="pt-8 space-y-4 text-sm text-cyan-50">
            <div className="flex items-center space-x-3">
              <div className="w-2 h-2 bg-white rounded-full"></div>
              <span>AI-Powered Workout Plans</span>
            </div>
            <div className="flex items-center space-x-3">
              <div className="w-2 h-2 bg-white rounded-full"></div>
              <span>Personalized Nutrition Guide</span>
            </div>
            <div className="flex items-center space-x-3">
              <div className="w-2 h-2 bg-white rounded-full"></div>
              <span>Real-time Form Feedback</span>
            </div>
            <div className="flex items-center space-x-3">
              <div className="w-2 h-2 bg-white rounded-full"></div>
              <span>Challenge Tracking</span>
            </div>
          </div>
        </div>
      </div>

      {/* Right Side - Auth Form */}
      <div className="flex-1 flex flex-col justify-center items-center p-8 lg:p-12">
        <div className="w-full max-w-md space-y-8">
          {/* Mobile Brand */}
          <div className="lg:hidden text-center mb-8">
            <h1 className="text-3xl font-black tracking-tight text-cyan-400">FITNESS AI</h1>
          </div>

          {/* Form Header */}
          <div className="space-y-2">
            <h2 className="text-3xl font-black text-white">
              {authMode === 'admin' ? 'Admin Access' : isLogin ? 'Welcome Back' : 'Create Account'}
            </h2>
            <p className="text-zinc-400">
              {authMode === 'admin'
                ? 'Sign in to monitor platform analytics'
                : isLogin 
                ? 'Sign in to access your fitness journey' 
                : 'Join thousands getting fit with AI'}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 rounded-lg bg-[#1e1e1e] border border-zinc-800 p-1">
            <button
              type="button"
              onClick={() => {
                setAuthMode('user');
                setError('');
              }}
              className={`py-2 rounded-md text-xs font-bold uppercase tracking-wider transition-all ${
                authMode === 'user' ? 'bg-cyan-500 text-zinc-950' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              User
            </button>
            <button
              type="button"
              onClick={() => {
                setAuthMode('admin');
                setIsLogin(true);
                setError('');
              }}
              className={`py-2 rounded-md text-xs font-bold uppercase tracking-wider transition-all ${
                authMode === 'admin' ? 'bg-cyan-500 text-zinc-950' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Admin
            </button>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Auth Form */}
          <form onSubmit={isLogin || authMode === 'admin' ? handleLogin : handleRegister} className="space-y-4">
            {!isLogin && authMode === 'user' && (
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">Full Name</label>
                <div className="relative">
                  <User className="absolute left-3 top-3 text-zinc-500" size={18} />
                  <input
                    type="text"
                    value={registerName}
                    onChange={(e) => setRegisterName(e.target.value)}
                    placeholder="John Doe"
                    required
                    className="w-full bg-[#1e1e1e] border border-zinc-700 rounded-lg pl-10 pr-4 py-3 text-white focus:outline-none focus:border-cyan-500 transition-colors"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-3 text-zinc-500" size={18} />
                <input
                  type="email"
                  value={isLogin || authMode === 'admin' ? loginEmail : registerEmail}
                  onChange={(e) => isLogin || authMode === 'admin' ? setLoginEmail(e.target.value) : setRegisterEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="w-full bg-[#1e1e1e] border border-zinc-700 rounded-lg pl-10 pr-4 py-3 text-white focus:outline-none focus:border-cyan-500 transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 text-zinc-500" size={18} />
                <input
                  type={showPassword ? "text" : "password"}
                  value={isLogin || authMode === 'admin' ? loginPassword : registerPassword}
                  onChange={(e) => isLogin || authMode === 'admin' ? setLoginPassword(e.target.value) : setRegisterPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full bg-[#1e1e1e] border border-zinc-700 rounded-lg pl-10 pr-10 py-3 text-white focus:outline-none focus:border-cyan-500 transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-3 text-zinc-500 hover:text-zinc-300"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {!isLogin && authMode === 'user' && (
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">Confirm Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-3 text-zinc-500" size={18} />
                  <input
                    type={showPassword ? "text" : "password"}
                    value={registerPasswordConfirm}
                    onChange={(e) => setRegisterPasswordConfirm(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="w-full bg-[#1e1e1e] border border-zinc-700 rounded-lg pl-10 pr-10 py-3 text-white focus:outline-none focus:border-cyan-500 transition-colors"
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:opacity-50 text-white font-bold py-3 rounded-lg transition-all duration-200"
            >
              {loading ? 'Processing...' : authMode === 'admin' ? 'Sign In as Admin' : isLogin ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          {/* Toggle */}
          {authMode === 'user' && (
          <div className="text-center">
            <span className="text-zinc-400">
              {isLogin ? "Don't have an account? " : 'Already have an account? '}
              <button
                onClick={() => {
                  setIsLogin(!isLogin);
                  setError('');
                }}
                className="text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
              >
                {isLogin ? 'Sign Up' : 'Sign In'}
              </button>
            </span>
          </div>
          )}
        </div>
      </div>
    </div>
  );
}

function clearLegacyAuthStorage() {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('user_id');
  localStorage.removeItem('user_name');
  localStorage.removeItem('user_email');
  localStorage.removeItem('user_role');
  localStorage.removeItem('profile_pending');
}
