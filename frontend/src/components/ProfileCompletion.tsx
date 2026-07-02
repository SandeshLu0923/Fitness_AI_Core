import { useState } from 'react';
import { MapPin, ChevronRight } from 'lucide-react';
import axios from 'axios';

interface ProfileCompletionProps {
  userId: string;
  userName: string;
  token: string;
  onProfileComplete: () => void;
}

export default function ProfileCompletion({ userId, userName, token, onProfileComplete }: ProfileCompletionProps) {
  const [age, setAge] = useState<number | ''>('');
  const [weight, setWeight] = useState<number | ''>('');
  const [height, setHeight] = useState<number | ''>('');
  const [latitude, setLatitude] = useState<number>(0);
  const [longitude, setLongitude] = useState<number>(0);
  const [locationGot, setLocationGot] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [gettingLocation, setGettingLocation] = useState(false);

  const handleGetLocation = () => {
    setGettingLocation(true);
    setError('');

    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setLatitude(position.coords.latitude);
          setLongitude(position.coords.longitude);
          setLocationGot(true);
          setGettingLocation(false);
        },
        () => {
          setError('Unable to get location. Please enable location access.');
          setGettingLocation(false);
        }
      );
    } else {
      setError('Geolocation is not supported by your browser.');
      setGettingLocation(false);
    }
  };

  const handleComplete = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!age || !weight || !height) {
      setError('Please fill in all required fields');
      return;
    }

    if (Number(age) < 13 || Number(age) > 120) {
      setError('Age must be between 13 and 120');
      return;
    }

    if (Number(weight) < 20 || Number(weight) > 300) {
      setError('Weight must be between 20 and 300 kg');
      return;
    }

    if (Number(height) < 100 || Number(height) > 250) {
      setError('Height must be between 100 and 250 cm');
      return;
    }

    setLoading(true);

    try {
      await axios.post(
        `http://localhost:8000/api/auth/profile/complete?user_id=${userId}`,
        {
          age: Number(age),
          weight_kg: Number(weight),
          height_cm: Number(height),
          latitude,
          longitude
        },
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      sessionStorage.removeItem('profile_pending');
      onProfileComplete();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to complete profile. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-[#121212] text-gray-100 font-sans overflow-hidden">
      {/* Left Side - Onboarding Info */}
      <div className="hidden lg:flex w-1/2 bg-gradient-to-br from-purple-600 via-purple-500 to-pink-600 flex-col justify-center items-center p-12 relative overflow-hidden">
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-20 left-20 w-40 h-40 bg-white rounded-full blur-3xl"></div>
          <div className="absolute bottom-20 right-20 w-40 h-40 bg-pink-400 rounded-full blur-3xl"></div>
        </div>

        <div className="relative z-10 text-center space-y-8">
          <div>
            <h1 className="text-5xl font-black tracking-tight text-white mb-4">Let's Get Started!</h1>
            <p className="text-xl text-purple-100">Complete your profile for a personalized fitness experience</p>
          </div>

          <div className="space-y-6 text-left">
            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-white/20 flex items-center justify-center">
                <span className="text-2xl font-black">📊</span>
              </div>
              <div>
                <h3 className="font-bold text-white mb-1">Personalized Plans</h3>
                <p className="text-purple-100 text-sm">Get workout and diet plans tailored to your body metrics</p>
              </div>
            </div>

            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-white/20 flex items-center justify-center">
                <span className="text-2xl font-black">📍</span>
              </div>
              <div>
                <h3 className="font-bold text-white mb-1">Location-Based Gyms</h3>
                <p className="text-purple-100 text-sm">Find gyms and fitness centers near you</p>
              </div>
            </div>

            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-white/20 flex items-center justify-center">
                <span className="text-2xl font-black">🎯</span>
              </div>
              <div>
                <h3 className="font-bold text-white mb-1">AI Coaching</h3>
                <p className="text-purple-100 text-sm">Get real-time feedback on your fitness journey</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Side - Profile Form */}
      <div className="flex-1 flex flex-col justify-center items-center p-8 lg:p-12">
        <div className="w-full max-w-md space-y-8">
          {/* Header */}
          <div className="space-y-2">
            <h2 className="text-3xl font-black text-white">Welcome, {userName}!</h2>
            <p className="text-zinc-400">Tell us a bit about yourself to get started</p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Profile Form */}
          <form onSubmit={handleComplete} className="space-y-5">
            {/* Age */}
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">
                Age <span className="text-red-400">*</span>
              </label>
              <input
                type="number"
                min="13"
                max="120"
                value={age}
                onChange={(e) => setAge(e.target.value ? Number(e.target.value) : '')}
                placeholder="e.g., 25"
                required
                className="w-full bg-[#1e1e1e] border border-zinc-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-purple-500 transition-colors"
              />
              <p className="text-xs text-zinc-500 mt-1">Must be between 13 and 120</p>
            </div>

            {/* Weight */}
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">
                Weight (kg) <span className="text-red-400">*</span>
              </label>
              <input
                type="number"
                min="20"
                max="300"
                step="0.5"
                value={weight}
                onChange={(e) => setWeight(e.target.value ? Number(e.target.value) : '')}
                placeholder="e.g., 75"
                required
                className="w-full bg-[#1e1e1e] border border-zinc-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-purple-500 transition-colors"
              />
              <p className="text-xs text-zinc-500 mt-1">Between 20 and 300 kg</p>
            </div>

            {/* Height */}
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">
                Height (cm) <span className="text-red-400">*</span>
              </label>
              <input
                type="number"
                min="100"
                max="250"
                step="0.5"
                value={height}
                onChange={(e) => setHeight(e.target.value ? Number(e.target.value) : '')}
                placeholder="e.g., 180"
                required
                className="w-full bg-[#1e1e1e] border border-zinc-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-purple-500 transition-colors"
              />
              <p className="text-xs text-zinc-500 mt-1">Between 100 and 250 cm</p>
            </div>

            {/* Location */}
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">Location</label>
              <button
                type="button"
                onClick={handleGetLocation}
                disabled={gettingLocation || locationGot}
                className={`w-full flex items-center justify-center space-x-2 px-4 py-3 rounded-lg font-medium transition-all ${
                  locationGot
                    ? 'bg-green-500/20 text-green-400 border border-green-500/50'
                    : 'bg-[#1e1e1e] border border-zinc-700 text-zinc-300 hover:border-purple-500'
                } disabled:opacity-50`}
              >
                <MapPin size={18} />
                <span>
                  {gettingLocation
                    ? 'Getting location...'
                    : locationGot
                    ? `Location set (${latitude.toFixed(2)}, ${longitude.toFixed(2)})`
                    : 'Get My Location'}
                </span>
              </button>
              <p className="text-xs text-zinc-500 mt-1">Optional - helps find nearby gyms</p>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center space-x-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 disabled:opacity-50 text-white font-bold py-3 rounded-lg transition-all duration-200 mt-8"
            >
              <span>{loading ? 'Completing...' : 'Complete Profile'}</span>
              {!loading && <ChevronRight size={18} />}
            </button>
          </form>

          {/* Skip Option */}
          <div className="text-center">
            <button
              onClick={onProfileComplete}
              className="text-zinc-400 hover:text-zinc-300 text-sm transition-colors"
            >
              Skip for now
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
