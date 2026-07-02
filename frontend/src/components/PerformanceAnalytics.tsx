import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { TrendingUp, Award, Target, Zap, BarChart3, AlertCircle } from 'lucide-react';

interface PerformanceMetric {
  exercise_type: string;
  performance_score: number;
  accuracy: number;
  date: string;
  reps_completed: number;
}

interface WeeklyReport {
  week_start: string;
  week_end: string;
  total_workouts: number;
  avg_performance_score: number;
  best_exercise: string;
  worst_exercise: string;
  weekly_trend: string;
  recommendations: string[];
  exercises_data: Record<string, any>;
}

interface ExerciseComparison {
  exercise: string;
  avg_score: number;
  total_workouts: number;
  avg_accuracy: number;
}

const PerformanceAnalytics: React.FC<{ userId: string }> = ({ userId }) => {
  const [weeklyReport, setWeeklyReport] = useState<WeeklyReport | null>(null);
  const [history, setHistory] = useState<PerformanceMetric[]>([]);
  const [comparison, setComparison] = useState<ExerciseComparison[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'history' | 'comparison'>('overview');

  useEffect(() => {
    fetchAnalytics();
  }, [userId]);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const [reportRes, historyRes, comparisonRes] = await Promise.all([
        axios.get(`/api/performance/weekly-report/${userId}`),
        axios.get(`/api/performance/history/${userId}`),
        axios.get(`/api/performance/comparison/${userId}`),
      ]);

      if (reportRes.data.success) setWeeklyReport(reportRes.data);
      if (historyRes.data.success) setHistory(historyRes.data.metrics);
      if (comparisonRes.data.success) setComparison(comparisonRes.data.exercises);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400"></div>
      </div>
    );
  }

  const getTrendIcon = (trend: string) => {
    if (trend === 'improving') return <TrendingUp className="w-5 h-5 text-green-400" />;
    if (trend === 'declining') return <TrendingUp className="w-5 h-5 text-red-400 transform rotate-180" />;
    return <Zap className="w-5 h-5 text-yellow-400" />;
  };

  const getScoreColor = (score: number) => {
    if (score >= 85) return 'text-green-400';
    if (score >= 70) return 'text-yellow-400';
    return 'text-red-400';
  };

  return (
    <div className="bg-slate-900 rounded-lg border border-slate-700 p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white mb-2">📊 Performance Analytics</h2>
        <p className="text-slate-400">Track your workout performance and progress</p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-4 mb-6 border-b border-slate-700">
        <button
          onClick={() => setActiveTab('overview')}
          className={`pb-3 px-4 font-semibold transition-colors ${
            activeTab === 'overview'
              ? 'text-cyan-400 border-b-2 border-cyan-400'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          📈 Overview
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`pb-3 px-4 font-semibold transition-colors ${
            activeTab === 'history'
              ? 'text-cyan-400 border-b-2 border-cyan-400'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          📋 History
        </button>
        <button
          onClick={() => setActiveTab('comparison')}
          className={`pb-3 px-4 font-semibold transition-colors ${
            activeTab === 'comparison'
              ? 'text-cyan-400 border-b-2 border-cyan-400'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          🏆 Comparison
        </button>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && weeklyReport && (
        <div className="space-y-6">
          {/* Weekly Summary */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-2">
                <span className="text-slate-400 text-sm">Avg Performance</span>
                <Award className="w-4 h-4 text-cyan-400" />
              </div>
              <div className={`text-3xl font-bold ${getScoreColor(weeklyReport.avg_performance_score)}`}>
                {weeklyReport.avg_performance_score.toFixed(1)}
              </div>
              <p className="text-xs text-slate-500 mt-1">out of 100</p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-2">
                <span className="text-slate-400 text-sm">Workouts</span>
                <BarChart3 className="w-4 h-4 text-purple-400" />
              </div>
              <div className="text-3xl font-bold text-white">{weeklyReport.total_workouts}</div>
              <p className="text-xs text-slate-500 mt-1">this week</p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-2">
                <span className="text-slate-400 text-sm">Best Exercise</span>
                <Target className="w-4 h-4 text-green-400" />
              </div>
              <div className="text-lg font-bold text-green-400 capitalize">
                {weeklyReport.best_exercise || 'N/A'}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {weeklyReport.exercises_data[weeklyReport.best_exercise]?.avg_score?.toFixed(1) || 0}/100
              </p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-2">
                <span className="text-slate-400 text-sm">Weekly Trend</span>
                {getTrendIcon(weeklyReport.weekly_trend)}
              </div>
              <div className="text-lg font-bold text-white capitalize">{weeklyReport.weekly_trend}</div>
              <p className="text-xs text-slate-500 mt-1">compared to previous week</p>
            </div>
          </div>

          {/* Recommendations */}
          <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
            <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-cyan-400" />
              Recommendations
            </h3>
            <ul className="space-y-2">
              {weeklyReport.recommendations.map((rec, idx) => (
                <li key={idx} className="text-slate-300 text-sm flex items-start gap-2">
                  <span className="text-cyan-400 mt-1">•</span>
                  <span>{rec}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Exercises Breakdown */}
          <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
            <h3 className="text-lg font-semibold text-white mb-4">Exercise Breakdown</h3>
            <div className="space-y-3">
              {Object.entries(weeklyReport.exercises_data).map(([exercise, data]: any) => (
                <div key={exercise} className="flex items-center justify-between p-3 bg-slate-700 rounded">
                  <div>
                    <p className="font-semibold text-white capitalize">{exercise}</p>
                    <p className="text-xs text-slate-400">{data.total_reps} reps • {data.count} workouts</p>
                  </div>
                  <div className="text-right">
                    <p className={`text-xl font-bold ${getScoreColor(data.avg_score)}`}>
                      {data.avg_score.toFixed(1)}
                    </p>
                    <p className="text-xs text-slate-400">{data.avg_accuracy.toFixed(0)}% accuracy</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div>
          {history.length > 0 ? (
            <div className="space-y-3">
              {history.map((metric, idx) => (
                <div key={idx} className="bg-slate-800 rounded-lg p-4 border border-slate-700 flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-white capitalize">{metric.exercise_type}</p>
                    <p className="text-xs text-slate-400">
                      {new Date(metric.date).toLocaleDateString()} • {metric.reps_completed} reps
                    </p>
                  </div>
                  <div className="text-right">
                    <p className={`text-lg font-bold ${getScoreColor(metric.performance_score)}`}>
                      {metric.performance_score.toFixed(1)}
                    </p>
                    <p className="text-xs text-slate-400">{metric.accuracy.toFixed(0)}% accuracy</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-400 text-center py-8">No performance data yet. Complete a workout to see your metrics!</p>
          )}
        </div>
      )}

      {/* Comparison Tab */}
      {activeTab === 'comparison' && (
        <div>
          {comparison.length > 0 ? (
            <div className="space-y-4">
              {comparison.map((exercise, idx) => (
                <div key={idx} className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-semibold text-white capitalize">{exercise.exercise}</p>
                    <p className={`text-sm font-bold ${getScoreColor(exercise.avg_score)}`}>
                      {exercise.avg_score.toFixed(1)}/100
                    </p>
                  </div>

                  {/* Score Bar */}
                  <div className="h-2 bg-slate-700 rounded-full overflow-hidden mb-2">
                    <div
                      className={`h-full ${
                        exercise.avg_score >= 85
                          ? 'bg-green-500'
                          : exercise.avg_score >= 70
                          ? 'bg-yellow-500'
                          : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.min(exercise.avg_score, 100)}%` }}
                    />
                  </div>

                  <div className="flex justify-between text-xs text-slate-400">
                    <span>{exercise.total_workouts} workouts</span>
                    <span>{exercise.avg_accuracy.toFixed(0)}% avg accuracy</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-400 text-center py-8">No comparison data yet.</p>
          )}
        </div>
      )}

      {/* Refresh Button */}
      <button
        onClick={fetchAnalytics}
        className="mt-6 w-full bg-slate-700 hover:bg-slate-600 text-white py-2 rounded-lg transition-colors flex items-center justify-center gap-2"
      >
        <span>🔄 Refresh Data</span>
      </button>
    </div>
  );
};

export default PerformanceAnalytics;
