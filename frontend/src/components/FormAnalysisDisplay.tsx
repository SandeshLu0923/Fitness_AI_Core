import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { AlertTriangle, CheckCircle, Info } from 'lucide-react';

interface FormIssue {
  name: string;
  severity: 'info' | 'warning' | 'critical';
  description: string;
  recommendation: string;
  confidence: number;
}

interface FormAnalysisData {
  exercise: string;
  overall_quality: string;
  form_score: number;
  injury_risk: string;
  issues: FormIssue[];
  strengths: string[];
}

interface ExerciseGuidelines {
  key_points: string[];
  common_mistakes: string[];
  injury_prevention: string[];
}

const FormAnalysisDisplay: React.FC<{
  exerciseType: string;
  landmarks: any;
  isLive: boolean;
}> = ({ exerciseType, landmarks, isLive }) => {
  const [analysis, setAnalysis] = useState<FormAnalysisData | null>(null);
  const [guidelines, setGuidelines] = useState<ExerciseGuidelines | null>(null);
  const [activeTab, setActiveTab] = useState<'analysis' | 'guidelines' | 'prevention'>('analysis');

  useEffect(() => {
    if (isLive && landmarks) {
      analyzeForm();
    }
  }, [landmarks, isLive]);

  useEffect(() => {
    fetchGuidelines();
  }, [exerciseType]);

  const analyzeForm = async () => {
    try {
      const response = await axios.post('/api/form-analysis/analyze', {
        exercise_type: exerciseType,
        landmarks: landmarks,
      });

      if (response.data.success) {
        setAnalysis(response.data);
      }
    } catch (error) {
      console.error('Form analysis failed:', error);
    }
  };

  const fetchGuidelines = async () => {
    try {
      const response = await axios.get(`/api/form-analysis/guidelines/${exerciseType}`);
      if (response.data.success && response.data.guidelines) {
        setGuidelines(response.data.guidelines);
      }
    } catch (error) {
      console.error('Failed to fetch guidelines:', error);
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <AlertTriangle className="w-5 h-5 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case 'info':
        return <Info className="w-5 h-5 text-blue-500" />;
      default:
        return <CheckCircle className="w-5 h-5 text-green-500" />;
    }
  };

  const getQualityColor = (quality: string) => {
    switch (quality) {
      case 'excellent':
        return 'text-green-400 bg-green-900/20';
      case 'good':
        return 'text-cyan-400 bg-cyan-900/20';
      case 'fair':
        return 'text-yellow-400 bg-yellow-900/20';
      case 'poor':
        return 'text-orange-400 bg-orange-900/20';
      case 'risky':
        return 'text-red-400 bg-red-900/20';
      default:
        return 'text-slate-400';
    }
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'low':
        return 'text-green-400';
      case 'medium':
        return 'text-yellow-400';
      case 'high':
        return 'text-red-400';
      default:
        return 'text-slate-400';
    }
  };

  return (
    <div className="bg-slate-900 rounded-lg border border-slate-700 p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-bold text-white flex items-center gap-2">
          🔍 Form Analysis - {exerciseType.toUpperCase()}
        </h3>
        {isLive && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm text-green-400">LIVE</span>
          </div>
        )}
      </div>

      {!isLive && (
        <p className="text-sm text-slate-400">Start training to see live form analysis</p>
      )}

      {isLive && analysis && (
        <>
          {/* Score Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className={`rounded-lg p-4 border border-slate-700 ${getQualityColor(analysis.overall_quality)}`}>
              <p className="text-xs text-slate-400 mb-1">Overall Quality</p>
              <p className="text-2xl font-bold capitalize">{analysis.overall_quality}</p>
              <p className="text-sm mt-1">{analysis.form_score}/100</p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
              <p className="text-xs text-slate-400 mb-1">Injury Risk</p>
              <p className={`text-2xl font-bold capitalize ${getRiskColor(analysis.injury_risk)}`}>
                {analysis.injury_risk}
              </p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
              <p className="text-xs text-slate-400 mb-1">Issues Found</p>
              <p className="text-2xl font-bold text-white">{analysis.issues.length}</p>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex gap-2 border-b border-slate-700">
            <button
              onClick={() => setActiveTab('analysis')}
              className={`pb-2 px-3 text-sm font-semibold transition-colors ${
                activeTab === 'analysis'
                  ? 'text-cyan-400 border-b-2 border-cyan-400'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Issues
            </button>
            <button
              onClick={() => setActiveTab('guidelines')}
              className={`pb-2 px-3 text-sm font-semibold transition-colors ${
                activeTab === 'guidelines'
                  ? 'text-cyan-400 border-b-2 border-cyan-400'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Guidelines
            </button>
            <button
              onClick={() => setActiveTab('prevention')}
              className={`pb-2 px-3 text-sm font-semibold transition-colors ${
                activeTab === 'prevention'
                  ? 'text-cyan-400 border-b-2 border-cyan-400'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Prevention
            </button>
          </div>

          {/* Issues Tab */}
          {activeTab === 'analysis' && (
            <div className="space-y-3">
              {analysis.issues.length > 0 ? (
                <>
                  {analysis.issues.map((issue, idx) => (
                    <div key={idx} className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                      <div className="flex items-start gap-3">
                        <div className="mt-1">{getSeverityIcon(issue.severity)}</div>
                        <div className="flex-1">
                          <p className="font-semibold text-white">{issue.name}</p>
                          <p className="text-sm text-slate-400 mt-1">{issue.description}</p>
                          <p className="text-sm text-cyan-400 mt-2">💡 {issue.recommendation}</p>
                          <p className="text-xs text-slate-500 mt-2">
                            Confidence: {(issue.confidence * 100).toFixed(0)}%
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              ) : (
                <div className="bg-green-900/20 rounded-lg p-4 border border-green-700">
                  <p className="text-green-400 flex items-center gap-2">
                    <CheckCircle className="w-5 h-5" />
                    Perfect form! No issues detected.
                  </p>
                </div>
              )}

              {analysis.strengths.length > 0 && (
                <div className="mt-4 space-y-2">
                  <p className="font-semibold text-white text-sm">✨ Your Strengths</p>
                  {analysis.strengths.map((strength, idx) => (
                    <p key={idx} className="text-sm text-green-400 flex items-center gap-2">
                      <span>•</span>
                      {strength}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Guidelines Tab */}
          {activeTab === 'guidelines' && guidelines && (
            <div className="space-y-4">
              <div>
                <h4 className="font-semibold text-white mb-2">📋 Key Points</h4>
                <ul className="space-y-1">
                  {guidelines.key_points.map((point, idx) => (
                    <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                      <span className="text-cyan-400 mt-1">✓</span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Prevention Tab */}
          {activeTab === 'prevention' && guidelines && (
            <div className="space-y-4">
              <div>
                <h4 className="font-semibold text-white mb-2">🛡️ Injury Prevention</h4>
                <ul className="space-y-1">
                  {guidelines.injury_prevention.map((tip, idx) => (
                    <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                      <span className="text-green-400 mt-1">→</span>
                      <span>{tip}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h4 className="font-semibold text-white mb-2">❌ Common Mistakes</h4>
                <ul className="space-y-1">
                  {guidelines.common_mistakes.map((mistake, idx) => (
                    <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                      <span className="text-red-400 mt-1">✕</span>
                      <span>{mistake}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default FormAnalysisDisplay;
