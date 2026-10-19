import { Bar,BarChart, Cell,CartesianGrid,LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis} from "recharts";
import redteam from "./redteam.json";
import evalData from "./eval.json";

const VIOLET = "#7c3aed";
const INDIGO = "#4f46e5";
const BAR = "#6366f1";
const GRID = "#e2e8f0";
const AXIS = "#94a3b8";
const INK = "#334155";
const TIP = { background: "#ffffff", border: `1px solid ${GRID}`, borderRadius: 10, color: INK };

function Kpi({ value, label, color }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      <div className="mt-1 text-sm text-slate-500">{label}</div>
    </div>
  );
}

function Info({ title, body }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-sm font-semibold text-indigo-700">{title}</div>
      <p className="mt-1 text-sm leading-relaxed text-slate-600">{body}</p>
    </div>
  );
}

function Panel({ title, children, note }) {
  return (
    <section className="mt-8">
      <h2 className="mb-3 text-lg font-semibold text-indigo-800">{title}</h2>
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        {children}
        <p className="mt-3 text-xs text-slate-500">{note}</p>
      </div>
    </section>
  );
}

export default function App() {
  const s = redteam.summary;
  const pct = (n) => Math.round((n / s.total) * 100);

  const defenseData = [
    { name: "No defense", leaked: s.no_defense, fill: VIOLET },
    { name: "Repo binding", leaked: s.repo_binding, fill: INDIGO },
  ];

  const labelData = Object.entries(evalData.per_label).map(([label, [right, total]]) => ({
    label,
    accuracy: Math.round((right / total) * 100),
    text: `${right}/${total}`,
  }));

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <div className="mx-auto max-w-5xl px-6 py-8">
        <header>
          <h1 className="text-2xl font-bold text-indigo-900">Taintgate</h1>
          <p className="mt-1 text-slate-500">Security dashboard: attack success vs triage utility</p>
        </header>

        <section className="mt-6 grid gap-3 sm:grid-cols-3">
          <Info
            title="What it is"
            body="A GitHub issue-triage bot. Its MCP server enforces security in code, not in the prompt, so the protection holds for any model that runs the agent."
          />
          <Info
            title="What this means"
            body="With no defense, 7 of 10 crafted issues tricked the agent into reading a private file. One server-side check (repo binding) dropped that to 0 of 10, while triage still labelled issues at 61% accuracy."
          />
          <Info
            title="Why it matters"
            body="Anyone can hide instructions inside a public issue. A prompt rule can be talked around; a check in the server cannot. This is a real, published attack class, measured before and after the fix."
          />
        </section>

        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi value={`${pct(s.no_defense)}%`} label="attack success, no defense" color="text-violet-600" />
          <Kpi value={`${pct(s.repo_binding)}%`} label="attack success, repo binding" color="text-indigo-600" />
          <Kpi value={`${Math.round(evalData.accuracy * 100)}%`} label="triage accuracy" color="text-indigo-600" />
          <Kpi value="19" label="tests passing" color="text-slate-700" />
        </div>

        <Panel
          title={`Attack success by defense (${redteam.model})`}
          note="10 attack variants. The model obeyed the injection every time; the server blocked it."
        >
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={defenseData} margin={{ top: 20, right: 12, left: -12, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="name" stroke={AXIS} tickLine={false} />
              <YAxis domain={[0, s.total]} stroke={AXIS} allowDecimals={false} tickLine={false} />
              <Tooltip contentStyle={TIP} cursor={{ fill: "#6366f111" }} formatter={(v) => [`${v} of ${s.total} leaked`, "result"]} />
              <Bar dataKey="leaked" radius={[8, 8, 0, 0]} maxBarSize={120}>
                {defenseData.map((d) => (
                  <Cell key={d.name} fill={d.fill} />
                ))}
                <LabelList dataKey="leaked" position="top" fill={INK} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel
          title={`Triage accuracy by label (${evalData.model})`}
          note={`${evalData.total} issues from ${evalData.repo}. ${Math.round(evalData.accuracy * 100)}% vs 33% random chance.`}
        >
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={labelData} margin={{ top: 20, right: 12, left: -12, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="label" stroke={AXIS} tickLine={false} />
              <YAxis domain={[0, 100]} unit="%" stroke={AXIS} tickLine={false} />
              <Tooltip contentStyle={TIP} cursor={{ fill: "#6366f111" }} formatter={(v, _n, p) => [`${v}% (${p.payload.text})`, "accuracy"]} />
              <Bar dataKey="accuracy" fill={BAR} radius={[8, 8, 0, 0]} maxBarSize={90}>
                <LabelList dataKey="accuracy" position="top" fill={INK} formatter={(v) => `${v}%`} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>
    </div>
  );
}
