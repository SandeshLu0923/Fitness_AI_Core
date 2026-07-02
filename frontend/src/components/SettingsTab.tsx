import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface ProfileData {
  user_id: string;
  age: number;
  weight_kg: number;
  height_cm: number;
  fitness_goal: string;
  activity_level: string;
  latitude: number;
  longitude: number;
}

export default function SettingsTab() {
  const userId = sessionStorage.getItem('user_id') || 'runner_jack';
  const userName = sessionStorage.getItem('user_name') || 'User';

  const [profile, setProfile] = useState<ProfileData>({
    user_id: userId,
    age: 25,
    weight_kg: 70,
    height_cm: 175,
    fitness_goal: 'Muscle Gain',
    activity_level: 'Active',
    latitude: 0,
    longitude: 0,
  });

  const [isLoading, setIsLoading] = useState(true);

  const [syncStatus, setSyncStatus] = useState<{ type: 'idle' | 'success' | 'error'; message: string }>({
    type: 'idle',
    message: '',
  });

  // Automatically fetch existing profile details on tab load
  useEffect(() => {
    const fetchProfileData = async () => {
      setIsLoading(true);
      try {
        const res = await axios.get(`http://localhost:8000/api/profile/${userId}`);
        if (res.data) {
          setProfile(prev => ({
            ...prev,
            ...res.data,
            user_id: userId  // Ensure user_id is set correctly
          }));
        }
      } catch (err: any) {
        console.log('[PROFILE_FETCH]', err.response?.status === 404 ? 'No profile found yet' : 'Error fetching profile');
      } finally {
        setIsLoading(false);
      }
    };

    fetchProfileData();
  }, [userId]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    // Don't allow changing user_id
    if (name === 'user_id') return;
    
    setProfile((prev) => ({
      ...prev,
      [name]: ['age', 'weight_kg', 'height_cm', 'latitude', 'longitude'].includes(name) ? Number(value) : value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSyncStatus({ type: 'idle', message: 'Saving profile...' });

    try {
      const response = await axios.post('http://localhost:8000/api/profile/upsert', {
        ...profile,
        user_id: userId  // Always use the current user_id
      });
      if (response.data.status === 'success') {
        setSyncStatus({ type: 'success', message: '✓ Profile updated successfully in database!' });
        setTimeout(() => setSyncStatus({ type: 'idle', message: '' }), 3000);
      }
    } catch (err: any) {
      setSyncStatus({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to save profile. Please try again.'
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Loading State */}
      {isLoading && (
        <div className="bg-[#1e1e1e] border border-blue-500/30 rounded-xl p-6 text-center text-blue-400">
          <div className="inline-block animate-spin h-5 w-5 border-2 border-blue-400 border-t-transparent rounded-full mb-2"></div>
          <p className="text-sm">Loading your profile data...</p>
        </div>
      )}

      {/* Profile Configuration Section */}
      <div className="max-w-2xl bg-[#1e1e1e] border border-gray-800 rounded-xl p-8 shadow-xl">
        <div className="mb-6">
          <h3 className="text-xl font-bold text-cyan-400">User Profile Configuration</h3>
          <p className="text-gray-400 text-sm mt-1">Update your personal details and fitness preferences. Changes are saved to the database.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">User Name (Read-Only)</label>
              <input
                type="text"
                name="name"
                value={userName}
                readOnly
                disabled
                className="w-full bg-[#0f0f0f] border border-gray-700 rounded-lg px-4 py-2.5 text-gray-500 cursor-not-allowed"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Age (Years)</label>
              <input
                type="number"
                name="age"
                value={profile.age}
                onChange={handleInputChange}
                className="w-full bg-[#121212] border border-gray-800 rounded-lg px-4 py-2.5 text-gray-200 focus:outline-none focus:border-cyan-500 transition-colors"
                min="1"
                max="120"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Weight (kg)</label>
              <input
                type="number"
                name="weight_kg"
                value={profile.weight_kg}
                onChange={handleInputChange}
                className="w-full bg-[#121212] border border-gray-800 rounded-lg px-4 py-2.5 text-gray-200 focus:outline-none focus:border-cyan-500 transition-colors"
                min="1"
                step="0.5"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Height (cm)</label>
              <input
                type="number"
                name="height_cm"
                value={profile.height_cm}
                onChange={handleInputChange}
                className="w-full bg-[#121212] border border-gray-800 rounded-lg px-4 py-2.5 text-gray-200 focus:outline-none focus:border-cyan-500 transition-colors"
                min="1"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Primary Exercise Goal</label>
              <select
                name="fitness_goal"
                value={profile.fitness_goal}
                onChange={handleInputChange}
                className="w-full bg-[#121212] border border-gray-800 rounded-lg px-4 py-2.5 text-gray-200 focus:outline-none focus:border-cyan-500 transition-colors"
              >
                <option value="Muscle Gain">Muscle Gain / Hypertrophy</option>
                <option value="Weight Loss">Weight Loss / Fat Burning</option>
                <option value="Maintenance">General Fitness Maintenance</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Activity Level</label>
              <select
                name="activity_level"
                value={profile.activity_level}
                onChange={handleInputChange}
                className="w-full bg-[#121212] border border-gray-800 rounded-lg px-4 py-2.5 text-gray-200 focus:outline-none focus:border-cyan-500 transition-colors"
              >
                <option value="Sedentary">Sedentary (Desk Job)</option>
                <option value="Moderate">Moderate (3-4 workouts/wk)</option>
                <option value="Active">Highly Active (Daily Intensity)</option>
              </select>
            </div>

          </div>

          <div className="pt-4 border-t border-gray-800 flex items-center justify-between">
            <button
              type="submit"
              className="bg-cyan-500 hover:bg-cyan-600 text-[#121212] font-bold px-6 py-2.5 rounded-lg transition-all duration-150 shadow-md shadow-cyan-500/10"
            >
              Save Configuration
            </button>

            {syncStatus.message && (
              <span className={`text-sm font-medium ${
                syncStatus.type === 'success' ? 'text-emerald-400' : syncStatus.type === 'error' ? 'text-rose-400' : 'text-gray-400'
              }`}>
                {syncStatus.message}
              </span>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
