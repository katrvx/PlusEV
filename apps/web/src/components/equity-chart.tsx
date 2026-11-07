"use client";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EquityPoint } from "../../../../packages/contracts/types";

export default function EquityChart({ data, compact = false }: { data: EquityPoint[]; compact?: boolean }) {
  return <div className={`equity-chart ${compact ? "compact" : ""}`} role="img" aria-label="Indexed equity curves comparing the unchanged strategy, a simple rule, the proposed policy, and cash. Exact metrics are available in the comparison table.">
    <ResponsiveContainer width="100%" height="100%" minWidth={0}>
      <LineChart data={data} margin={{ top: 18, right: 8, left: -23, bottom: 0 }}>
        <CartesianGrid stroke="#eceef2" strokeDasharray="3 5" vertical={false} />
        <XAxis dataKey="date" axisLine={false} tickLine={false} minTickGap={48} tick={{ fill: "#8b909c", fontSize: 11 }} tickFormatter={date => new Date(date).toLocaleDateString("en-GB", { month: "short", day: "numeric", timeZone: "UTC" })} dy={9} />
        <YAxis axisLine={false} tickLine={false} tick={{ fill: "#8b909c", fontSize: 11 }} domain={["auto", "auto"]} tickFormatter={value => Number(value).toFixed(0)} />
        <Tooltip contentStyle={{ border: "1px solid #e7e9ef", borderRadius: 9, fontSize: 12, boxShadow: "0 8px 24px #23293810" }} labelFormatter={label => new Date(String(label)).toLocaleDateString("en-GB", { timeZone: "UTC" })} formatter={(value, name) => [Number(value).toFixed(2), name]} />
        <Line type="monotone" dataKey="cash" name="Cash" stroke="#c7cad3" strokeDasharray="3 4" dot={false} strokeWidth={1} isAnimationActive={false} />
        <Line type="monotone" dataKey="base" name="Original strategy" stroke="#929aaa" dot={false} strokeWidth={1.8} isAnimationActive={false} />
        <Line type="monotone" dataKey="rule" name="Simple rule" stroke="#67a6b0" dot={false} strokeWidth={1.7} isAnimationActive={false} />
        <Line type="monotone" dataKey="proposed" name="Suggested rule" stroke="#635bdf" dot={false} strokeWidth={2.8} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  </div>;
}
