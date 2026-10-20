import { Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import redteam from "../../results/redteam-llama3.2.json";
import evalOff from "../../results/eval-llama3.2.json";
import evalOn from "../../results/eval-llama3.2-taint.json";

const INK = "#030229";
const SKY = "#5B93FF";
const SUN = "#FFD66B";
const CORAL = "#FF8F6B";
const BRAND = "#605BFF";
const GRID = "#F0F0F5";
const AXIS = { fill: "#9E9DB0", fontSize: 13 };
const TIP = { background: INK, border: "none", borderRadius: 10, color: "#fff", padding: "8px 12px" };

const ICONS = {
  alert: "M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  chat: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  lock: "M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4",
  tag: "M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6a2 2 0 0 1 0 2.8zM7 7h.01",
};

function Kpi({ value, label, sub, color, icon }) {
  return (
    <div className="flex items-center gap-5 rounded-2xl bg-white p-6 shadow-[0_2px_12px_rgba(3,2,41,0.08)]">
      <div className="grid h-14 w-14 shrink-0 place-items-center rounded-full" style={{ background: `${color}1f` }}>
        <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d={ICONS[icon]} />
        </svg>
      </div>
      <div>
        <div className="text-2xl font-extrabold text-ink">{value}</div>
        <div className="text-sm font-semibold text-ink/80">{label}</div>
        <div className="text-xs text-ink/50">{sub}</div>
      </div>
    </div>
  );
}

function Card({ title, note, className = "", children }) {
  return (
    <section className={`rounded-2xl bg-white p-6 shadow-[0_2px_12px_rgba(3,2,41,0.08)] ${className}`}>
      <h2 className="mb-5 text-lg font-bold text-ink">{title}</h2>
      {children}
      {note && <p className="mt-4 text-xs text-ink/50">{note}</p>}
    </section>
  );
}

function Info({ title, color, body }) {
  return (
    <div className="border-b border-ink/5 py-4 first:pt-0 last:border-0 last:pb-0">
      <div className="flex items-center gap-2 text-sm font-bold text-ink">
        <span className="h-3 w-3 rounded" style={{ background: color }} />
        {title}
      </div>
      <p className="mt-2 text-sm leading-relaxed text-ink/70">{body}</p>
    </div>
  );
}

const legend = (v) => <span className="text-sm text-ink">{v}</span>;

export default function App() {
  const s = redteam.summary;
  const total = s["worst/none"].runs;
  const pct = (n, d = total) => Math.round((n / d) * 100);

  const defenseData = ["worst", "realistic"].map((p) => ({
    name: `${p} prompt`,
    none: s[`${p}/none`].read_secret,
    binding: s[`${p}/binding`].read_secret,
  }));
  const bindingReads = defenseData.reduce((n, d) => n + d.binding, 0);

  const labelData = Object.keys(evalOff.per_label).map((label) => ({
    label,
    off: pct(evalOff.per_label[label][0], evalOff.per_label[label][1]),
    on: pct(evalOn.per_label[label][0], evalOn.per_label[label][1]),
  }));

  return (
    <div className="min-h-screen bg-page font-sans text-ink">
      <div className="mx-auto max-w-[1600px] px-4 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-full bg-brand">
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-extrabold">Taintgate</h1>
              <p className="text-sm text-ink/60">Attack success vs triage utility</p>
            </div>
          </div>
          <div className="flex gap-3 text-sm">
            <span className="rounded-xl bg-white px-4 py-2.5 shadow-[0_2px_12px_rgba(3,2,41,0.08)]">{redteam.model}</span>
            <span className="rounded-xl bg-white px-4 py-2.5 shadow-[0_2px_12px_rgba(3,2,41,0.08)]">{evalOff.date}</span>
          </div>
        </header>

        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi value={`${pct(defenseData[0].none)}%`} label="attack success" sub="worst prompt, no defense" color={CORAL} icon="alert" />
          <Kpi value={`${pct(defenseData[1].none)}%`} label="attack success" sub="careful prompt, no defense" color={SUN} icon="chat" />
          <Kpi value={`${pct(bindingReads, total * 2)}%`} label="attack success" sub="repo binding on" color={SKY} icon="lock" />
          <Kpi value={`${pct(evalOff.correct, evalOff.total)}%`} label="triage accuracy" sub="repo binding on" color={BRAND} icon="tag" />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <Card
            className="lg:col-span-2"
            title={`Secret reads by prompt and defense (${redteam.model})`}
            note={`${total} attack variants, ${redteam.runs_per_attack} run each. No secret was posted out in any run. Taint tracking is unit-tested only.`}
          >
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={defenseData} margin={{ top: 20, right: 8, left: -12, bottom: 0 }} barGap={8}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} />
                <YAxis domain={[0, total]} tick={AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip contentStyle={TIP} itemStyle={{ color: "#fff" }} labelStyle={{ color: "#ffffffaa" }} cursor={{ fill: `${BRAND}0d` }} formatter={(v, n) => [`${v} of ${total}`, n]} />
                <Legend iconType="circle" formatter={legend} />
                <Bar dataKey="none" name="no defense" fill={CORAL} radius={[8, 8, 0, 0]} maxBarSize={56}>
                  <LabelList dataKey="none" position="top" fill={INK} fontWeight={700} />
                </Bar>
                <Bar dataKey="binding" name="repo binding" fill={SKY} radius={[8, 8, 0, 0]} maxBarSize={56}>
                  <LabelList dataKey="binding" position="top" fill={INK} fontWeight={700} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card className="lg:row-span-2" title="Summary">
            <Info
              title="What it is"
              color={BRAND}
              body="A GitHub issue-triage bot. Its MCP server enforces security in code, not in the prompt, so the protection holds for any model that runs the agent."
            />
            <Info
              title="What this means"
              color={SKY}
              body={`With no defense, ${defenseData[0].none} of ${total} crafted issues got the agent to read a private secret with a deliberately vulnerable prompt, and ${defenseData[1].none} of ${total} with a careful one. Repo binding dropped both to ${bindingReads}, and the locked agent still labelled ${pct(evalOff.correct, evalOff.total)}% of real issues correctly.`}
            />
            <Info
              title="Why it matters"
              color={CORAL}
              body="Anyone can hide instructions inside a public issue. A prompt rule can be talked around; a check in the server cannot. This is a real, published attack class, measured before and after the fix."
            />
          </Card>

          <Card
            className="lg:col-span-2"
            title={`Triage accuracy by label (${evalOff.model}, lock on)`}
            note={`${evalOff.total} issues from ${evalOff.source}. Taint off ${pct(evalOff.correct, evalOff.total)}%, taint on ${pct(evalOn.correct, evalOn.total)}%, vs 33% for always answering "bug".`}
          >
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={labelData} margin={{ top: 20, right: 8, left: -12, bottom: 0 }} barGap={8}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="label" tick={AXIS} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} unit="%" tick={AXIS} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TIP} itemStyle={{ color: "#fff" }} labelStyle={{ color: "#ffffffaa" }} cursor={{ fill: `${BRAND}0d` }} formatter={(v, n) => [`${v}%`, n]} />
                <Legend iconType="circle" formatter={legend} />
                <Bar dataKey="off" name="taint off" fill={SKY} radius={[8, 8, 0, 0]} maxBarSize={56}>
                  <LabelList dataKey="off" position="top" fill={INK} fontWeight={700} formatter={(v) => `${v}%`} />
                </Bar>
                <Bar dataKey="on" name="taint on" fill={SUN} radius={[8, 8, 0, 0]} maxBarSize={56}>
                  <LabelList dataKey="on" position="top" fill={INK} fontWeight={700} formatter={(v) => `${v}%`} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
      </div>
    </div>
  );
}
