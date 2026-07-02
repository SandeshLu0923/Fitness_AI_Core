import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, BarChart3, Clock, Cpu, PieChart, TrendingUp, Users } from 'lucide-react';
import axios from 'axios';

export default function AdminDashboardTab() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchAdminData = async () => {
    setLoading(true);
    try {
      const token = sessionStorage.getItem('auth_token');
      const response = await axios.get('http://localhost:8000/api/admin/overview', {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined
      });
      setData(response.data);
    } catch (error) {
      console.error('Failed to load admin dashboard:', error);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
    const interval = setInterval(fetchAdminData, 30000);
    return () => clearInterval(interval);
  }, []);

  const kpis = data?.kpis || {};
  const charts = data?.charts || {};
  const activeUsers = kpis.active_users || {};

  return (
    <div className="w-full space-y-6 text-zinc-300">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-bold text-zinc-100 uppercase tracking-widest">Admin Analytics</h3>
          <p className="text-xs text-zinc-500 mt-1">Operational KPIs, AI usage, retention, and system health.</p>
        </div>
        <button onClick={fetchAdminData} className="bg-cyan-500 hover:bg-cyan-600 text-zinc-950 text-xs font-black px-4 py-2 rounded-lg uppercase tracking-wider">
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <Kpi icon={Users} label="Active Users" value={`${activeUsers.daily || 0} / ${activeUsers.weekly || 0} / ${activeUsers.monthly || 0}`} note="Unique users active in daily / weekly / monthly windows." />
        <Kpi icon={Activity} label="AI Inference Volume" value={kpis.ai_inference_volume ?? 0} note="AI/chat/diet/trainer/performance model events in the last 7 days." />
        <Kpi icon={BarChart3} label="Model Accuracy Rate" value={`${kpis.model_accuracy_rate ?? 0}%`} note="Correct workout reps over total reps, or successful inference rate if rep data is unavailable." />
        <Kpi icon={Clock} label="System Latency" value={`${kpis.system_latency_ms ?? 0} ms`} note="Average backend API response time over the last 24 hours." />
        <Kpi icon={TrendingUp} label="Retention Rate" value={`${kpis.user_retention_rate ?? 0}%`} note="Previous-week active users who were also active this week." />
        <Kpi icon={Clock} label="Peak Activity Hour" value={kpis.peak_activity_hour || 'N/A'} note="Hour with the highest completed workout log volume." />
        <Kpi icon={AlertTriangle} label="Error Log Rate" value={`${kpis.error_log_rate ?? 0}%`} note="Percentage of API requests returning errors in the last 24 hours." />
        <Kpi icon={Cpu} label="Server Load" value={`${charts.server_load?.[0]?.cpu_percent ?? 0}% CPU`} note={`Current server snapshot. Memory: ${charts.server_load?.[0]?.memory_percent ?? 0}%.`} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <Panel title="User Growth Trend" icon={TrendingUp} description="Daily new registrations from the users collection.">
          <LineTrend rows={charts.user_growth || []} labelKey="date" valueKey="count" />
        </Panel>
        <Panel title="Feature Distribution" icon={PieChart} description="Share of logged AI/model events by feature area.">
          <FeatureDonut rows={charts.feature_distribution || []} />
        </Panel>
        <Panel title="Server Load Tracker" icon={Cpu} description="Current CPU and memory snapshot from the backend host.">
          <ServerLoad rows={charts.server_load || []} />
        </Panel>
        <Panel title="Behavioral Predictions" icon={BarChart3} description="Skip-risk predictions grouped into low, medium, and high buckets.">
          <RiskBuckets rows={charts.behavioral_predictions || []} />
        </Panel>
      </div>

      <Panel title="API Response Times" icon={Clock} description="Recent request latency. Red dots indicate failed responses.">
        <LatencyScatter rows={charts.api_response_times || []} />
      </Panel>
    </div>
  );
}

function Kpi({ icon: Icon, label, value, note }: { icon: any; label: string; value: any; note: string }) {
  return (
    <div className="bg-[#161616] border border-zinc-800 rounded-lg p-4 space-y-3 hover:border-cyan-500/30 transition-colors">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-black uppercase tracking-wider text-zinc-500">{label}</p>
        <Icon size={15} className="text-cyan-400" />
      </div>
      <p className="text-xl font-black text-zinc-100 break-words">{value}</p>
      <p className="text-[11px] text-zinc-500">{note}</p>
    </div>
  );
}

function Panel({ title, icon: Icon, description, children }: { title: string; icon: any; description: string; children: any }) {
  return (
    <div className="bg-[#161616] border border-zinc-800 rounded-lg p-5 space-y-4">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Icon size={15} className="text-cyan-400" />
          <h4 className="text-xs font-black uppercase tracking-widest text-zinc-300">{title}</h4>
        </div>
        <p className="text-[11px] text-zinc-500">{description}</p>
      </div>
      {children}
    </div>
  );
}

function LineTrend({ rows, labelKey, valueKey }: { rows: any[]; labelKey: string; valueKey: string }) {
  const max = useMemo(() => Math.max(...rows.map(row => Number(row[valueKey] || 0)), 1), [rows, valueKey]);
  if (!rows.length) return <EmptyState />;
  const points = rows.map((row, idx) => {
    const x = rows.length === 1 ? 50 : (idx / (rows.length - 1)) * 100;
    const y = 90 - (Number(row[valueKey] || 0) / max) * 75;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="space-y-4">
      <div className="h-56 bg-zinc-950 border border-zinc-800 rounded-lg p-3">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full">
          <defs>
            <linearGradient id="growthFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          <polyline points={`0,95 ${points} 100,95`} fill="url(#growthFill)" stroke="none" />
          <polyline points={points} fill="none" stroke="#06b6d4" strokeWidth="2.2" vectorEffect="non-scaling-stroke" />
          {rows.map((row, idx) => {
            const x = rows.length === 1 ? 50 : (idx / (rows.length - 1)) * 100;
            const y = 90 - (Number(row[valueKey] || 0) / max) * 75;
            return <circle key={idx} cx={x} cy={y} r="1.8" fill="#22d3ee" vectorEffect="non-scaling-stroke" />;
          })}
        </svg>
      </div>
      <div className="grid grid-cols-3 gap-2 text-[10px] text-zinc-500">
        <span>{rows[0]?.[labelKey]}</span>
        <span className="text-center">Peak {max}</span>
        <span className="text-right">{rows[rows.length - 1]?.[labelKey]}</span>
      </div>
    </div>
  );
}

function FeatureDonut({ rows }: { rows: any[] }) {
  if (!rows.length) return <EmptyState />;
  const total = rows.reduce((sum, row) => sum + Number(row.count || 0), 0);
  const colors = ['#06b6d4', '#10b981', '#f59e0b', '#a855f7', '#f43f5e'];
  let offset = 0;
  const gradient = rows.map((row, idx) => {
    const pct = total > 0 ? (Number(row.count || 0) / total) * 100 : 0;
    const segment = `${colors[idx % colors.length]} ${offset}% ${offset + pct}%`;
    offset += pct;
    return segment;
  }).join(', ');

  return (
    <div className="grid grid-cols-1 md:grid-cols-[180px_minmax(0,1fr)] gap-5 items-center">
      <div
        className="h-44 w-44 rounded-full mx-auto border border-zinc-800 relative"
        style={{ background: `conic-gradient(${gradient})` }}
      >
        <div className="absolute inset-8 rounded-full bg-[#161616] border border-zinc-800 flex flex-col items-center justify-center">
          <span className="text-2xl font-black text-zinc-100">{total}</span>
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">events</span>
        </div>
      </div>
      <div className="space-y-2">
        {rows.map((row, idx) => (
          <div key={idx} className="flex items-center justify-between gap-3 bg-zinc-900/50 border border-zinc-800 rounded-lg p-2 text-xs">
            <div className="flex items-center gap-2 min-w-0">
              <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: colors[idx % colors.length] }} />
              <span className="text-zinc-300 truncate">{formatFeatureName(row.feature)}</span>
            </div>
            <span className="font-bold text-zinc-100">{row.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ServerLoad({ rows }: { rows: any[] }) {
  const latest = rows[rows.length - 1] || {};
  return (
    <div className="grid grid-cols-2 gap-4">
      <Gauge label="CPU" value={Number(latest.cpu_percent || 0)} />
      <Gauge label="Memory" value={Number(latest.memory_percent || 0)} />
    </div>
  );
}

function Gauge({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-4 space-y-3">
      <div className="flex justify-between text-xs mb-2">
        <span className="text-zinc-500 uppercase tracking-wider font-bold">{label}</span>
        <span className="font-bold text-cyan-400">{value}%</span>
      </div>
      <div className="h-3 bg-zinc-800 rounded-full overflow-hidden">
        <div className="h-full bg-cyan-500" style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <p className="text-[10px] text-zinc-600">{value < 70 ? 'Normal operating range' : 'High utilization'}</p>
    </div>
  );
}

function RiskBuckets({ rows }: { rows: any[] }) {
  if (!rows.length) return <EmptyState />;
  const max = Math.max(...rows.map(row => Number(row.count || 0)), 1);
  const colorMap: Record<string, string> = {
    Low: 'bg-emerald-500',
    Medium: 'bg-amber-500',
    High: 'bg-rose-500',
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {rows.map((row) => {
        const count = Number(row.count || 0);
        const pct = Math.round((count / max) * 100);
        return (
          <div key={row.bucket} className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-zinc-300">{row.bucket}</span>
              <span className="text-lg font-black text-zinc-100">{count}</span>
            </div>
            <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
              <div className={`h-full ${colorMap[row.bucket] || 'bg-cyan-500'}`} style={{ width: `${count > 0 ? Math.max(pct, 8) : 0}%` }} />
            </div>
            <p className="text-[10px] text-zinc-600">Predicted skip-risk events</p>
          </div>
        );
      })}
    </div>
  );
}

function LatencyScatter({ rows }: { rows: any[] }) {
  if (!rows.length) return <EmptyState />;
  const maxLatency = Math.max(...rows.map(row => Number(row.latency_ms || 0)), 1);
  const latestRows = rows.slice(-6).reverse();
  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_420px] gap-4">
      <div className="h-64 bg-zinc-950 border border-zinc-800 rounded-lg relative overflow-hidden p-3">
        <div className="absolute inset-x-3 top-1/2 border-t border-zinc-800/70" />
        {rows.slice(-120).map((row, idx) => {
          const visible = rows.slice(-120);
          const x = (idx / Math.max(visible.length - 1, 1)) * 94 + 3;
          const y = 90 - (Number(row.latency_ms || 0) / maxLatency) * 78;
          const isError = Number(row.status_code || 200) >= 400;
          return (
            <span
              key={idx}
              title={`${row.method} ${row.endpoint}: ${row.latency_ms}ms`}
              className={`absolute h-2.5 w-2.5 rounded-full border border-zinc-950 ${isError ? 'bg-rose-400' : 'bg-cyan-400'}`}
              style={{ left: `${x}%`, top: `${y}%` }}
            />
          );
        })}
        <div className="absolute bottom-2 left-3 text-[10px] text-zinc-600">Recent requests</div>
        <div className="absolute top-2 right-3 text-[10px] text-zinc-600">Max {Math.round(maxLatency)}ms</div>
      </div>
      <div className="space-y-2">
        <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Latest Requests</p>
        {latestRows.map((row, idx) => (
          <div key={idx} className="grid grid-cols-[minmax(0,1fr)_70px_52px] gap-3 text-xs bg-zinc-900/60 border border-zinc-800 rounded-lg p-2">
            <span className="truncate text-zinc-300">{row.method} {row.endpoint}</span>
            <span className="text-right font-bold text-cyan-400">{Math.round(row.latency_ms)}ms</span>
            <span className={`text-right font-bold ${Number(row.status_code || 200) >= 400 ? 'text-rose-400' : 'text-emerald-400'}`}>{row.status_code}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatFeatureName(value: string) {
  return String(value || 'unknown').replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
}

function EmptyState() {
  return <div className="text-xs text-zinc-500 bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">No data available yet.</div>;
}
